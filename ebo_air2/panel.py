"""
panel.py — the add-on's Ingress web UI (a Zigbee2MQTT-style sidebar panel, "Enabot").

ONE instance for the whole add-on. It subscribes to MQTT to aggregate every robot's state, shows a
LIST of robots (click one → its detail page with preview + controls + settings), forwards safe
control/settings commands over MQTT, and edits operational add-on settings stored in
/data/panel.json (read by run.sh at boot). Live preview = on-demand JPEG from each robot's RTSP.

No extra dependencies: stdlib http.server + paho-mqtt + ffmpeg.
"""
import json
import os
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import paho.mqtt.client as mqtt

from ebo_log import log

PORT = int(os.environ.get("EBO_PANEL_PORT", "8099"))
MQTT_HOST = os.environ.get("EBO_MQTT_HOST", "core-mosquitto")
MQTT_PORT = int(os.environ.get("EBO_MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("EBO_MQTT_USER", "") or None
MQTT_PASS = os.environ.get("EBO_MQTT_PASS", "") or None
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
PANEL_CFG = "/data/panel.json"

# Command suffixes the panel may publish (allow-list). Movement is excluded on purpose.
ALLOWED_CMDS = {
    "camera/set", "laser/set", "dock", "sleep/set", "connected/set", "patrol/start", "say", "talk",
    "video_quality/set", "image_style/set", "volume/set", "talkback_volume/set",
    "speed/set", "sports_record/set", "call_rec/set", "eyes/set",
}

# Add-on settings the panel manages (stored in /data/panel.json, read by run.sh). Everything
# except the account login (email/password) lives here now, not in the Configuration tab.
EDITABLE_OPTS = {
    "region": {"type": "text", "default": "GB"},
    "host": {"type": "text", "default": "ebox-eu.enabotserverintl.com"},
    "robot_id": {"type": "int", "default": 0},
    "video": {"type": "bool", "default": True},
    "audio": {"type": "bool", "default": True},
    "talk": {"type": "bool", "default": False},
    "audio_codec": {"type": "select", "choices": [8, 9], "default": 8},
    "log_level": {"type": "select", "choices": ["debug", "info", "warning"], "default": "info"},
    "video_max_height": {"type": "int", "default": 720},
    "video_fps": {"type": "int", "default": 20},
    "video_bitrate": {"type": "int", "default": 2500},
    "video_preset": {"type": "select",
                     "choices": ["ultrafast", "superfast", "veryfast", "faster", "fast"],
                     "default": "ultrafast"},
}

_robots = {}
_lock = threading.Lock()
_snap_cache = {}
_client = None


# --------------------------- MQTT: aggregate every robot's state ---------------------------
def _robot(node):
    return _robots.setdefault(node, {"node": node, "online": False, "state": {}})


def _on_connect(client, userdata, flags, rc, properties=None):
    log("[panel] MQTT connected rc=%s" % rc)
    for t in ("ebo_air2/discovery/#", "+/status", "+/state", "+/camera/state", "+/camera/url"):
        client.subscribe(t)


def _on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode("utf-8", "replace")
        if topic.startswith("ebo_air2/discovery/"):
            data = json.loads(payload) if payload else {}
            node = data.get("node") or topic.rsplit("/", 1)[-1]
            with _lock:
                _robot(node).update({k: data.get(k) for k in
                                     ("name", "sn", "mac", "model", "rtsp")})
            return
        node = topic.split("/", 1)[0]
        leaf = topic[len(node) + 1:]
        with _lock:
            r = _robot(node)
            if leaf == "status":
                r["online"] = (payload == "online")
            elif leaf == "state":
                try:
                    r["state"] = json.loads(payload)
                except ValueError:
                    pass
            elif leaf == "camera/state":
                r["camera"] = payload
            elif leaf == "camera/url":
                r["url"] = payload
    except Exception as e:
        log("[panel] message error:", e)


def _start_mqtt():
    global _client
    c = mqtt.Client(client_id="ebo_panel")
    if MQTT_USER:
        c.username_pw_set(MQTT_USER, MQTT_PASS)
    c.on_connect = _on_connect
    c.on_message = _on_message
    c.connect(MQTT_HOST, MQTT_PORT, 30)
    c.loop_start()
    _client = c


# --------------------------- operational settings (/data/panel.json) ---------------------------
def _read_cfg():
    try:
        with open(PANEL_CFG) as f:
            cur = json.load(f)
    except Exception:
        cur = {}
    return {k: cur.get(k, s["default"]) for k, s in EDITABLE_OPTS.items()}


def _coerce(k, v):
    t = EDITABLE_OPTS[k]["type"]
    if t == "bool":
        return v is True or str(v).lower() == "true"
    if t == "int":
        try:
            return int(v)
        except (TypeError, ValueError):
            return EDITABLE_OPTS[k]["default"]
    if t == "select" and all(isinstance(c, int) for c in EDITABLE_OPTS[k]["choices"]):
        try:
            return int(v)
        except (TypeError, ValueError):
            return EDITABLE_OPTS[k]["default"]
    return v


def _save_cfg(patch):
    cur = _read_cfg()
    for k, v in patch.items():
        if k in EDITABLE_OPTS:
            cur[k] = _coerce(k, v)
    with open(PANEL_CFG, "w") as f:
        json.dump(cur, f)
    log("[panel] saved /data/panel.json — restarting add-on to apply")
    threading.Thread(target=_restart_self, daemon=True).start()


def _restart_self():
    time.sleep(1)
    try:
        req = urllib.request.Request("http://supervisor/addons/self/restart",
                                     data=b"", method="POST")
        req.add_header("Authorization", "Bearer " + SUPERVISOR_TOKEN)
        urllib.request.urlopen(req, timeout=30).read()
    except Exception as e:
        log("[panel] self-restart failed:", e)


# --------------------------- live preview: one JPEG from RTSP ---------------------------
def _snapshot(node):
    with _lock:
        r = _robots.get(node)
        url = r and r.get("rtsp")
    if not url:
        return None
    now = time.time()
    ts, cached = _snap_cache.get(node, (0, None))
    if cached and now - ts < 2.0:
        return cached
    p = urlparse(url)
    internal = "rtsp://127.0.0.1:%s%s" % (p.port or 8554, p.path)
    try:
        out = subprocess.run(
            ["ffmpeg", "-nostdin", "-rtsp_transport", "tcp", "-i", internal,
             "-frames:v", "1", "-q:v", "6", "-f", "mjpeg", "pipe:1"],
            capture_output=True, timeout=8).stdout
        if out:
            _snap_cache[node] = (now, out)
            return out
    except Exception:
        pass
    return cached


# --------------------------- HTTP: dashboard + tiny API ---------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/")
        if path.endswith("/api/robots"):
            with _lock:
                return self._send(200, json.dumps(list(_robots.values())))
        if path.endswith("/api/options"):
            return self._send(200, json.dumps({"values": _read_cfg(), "schema": EDITABLE_OPTS}))
        if path.endswith("/api/snapshot"):
            q = parse_qs(urlparse(self.path).query)
            jpg = _snapshot((q.get("node") or [""])[0])
            return self._send(200 if jpg else 404, jpg or b"", "image/jpeg")
        return self._send(200, PAGE, "text/html; charset=utf-8")

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(400, json.dumps({"error": "bad body"}))
        if path.endswith("/api/cmd"):
            node, suffix = str(body.get("node", "")), str(body.get("suffix", ""))
            if not node or suffix not in ALLOWED_CMDS or _client is None:
                return self._send(400, json.dumps({"error": "bad command"}))
            _client.publish("%s/%s" % (node, suffix), str(body.get("payload", "")))
            log("[panel] cmd %s/%s = %s" % (node, suffix, body.get("payload", "")))
            return self._send(200, json.dumps({"ok": True}))
        if path.endswith("/api/options"):
            try:
                _save_cfg(body.get("options", {}))
                return self._send(200, json.dumps({"ok": True, "restarting": True}))
            except Exception as e:
                log("[panel] save options failed:", e)
                return self._send(500, json.dumps({"error": str(e)}))
        return self._send(404, "{}")


PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Enabot</title><style>
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{font-family:system-ui,sans-serif;margin:0;background:#f4f5f7;color:#111}
@media(prefers-color-scheme:dark){body{background:#111417;color:#e9ecef}}
header{padding:14px 18px;font-size:20px;font-weight:600;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;background:inherit;border-bottom:1px solid #0001}
.btn{border:0;border-radius:9px;padding:8px 12px;font-size:13px;cursor:pointer;background:#e6e8eb;color:inherit}
@media(prefers-color-scheme:dark){.btn{background:#2a3138;color:#e9ecef}}
.btn:hover{filter:brightness(.95)}.btn.pri{background:#2b6cff;color:#fff}
.list{padding:10px 14px 24px;max-width:760px;margin:0 auto}
.rowitem{display:flex;gap:12px;align-items:center;background:#fff;border-radius:12px;padding:10px;margin-bottom:10px;cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,.1)}
@media(prefers-color-scheme:dark){.rowitem{background:#1c2126}}
.rowitem:hover{filter:brightness(.98)}
.thumb{width:104px;height:60px;border-radius:8px;object-fit:cover;background:#000;flex:none}
.ri-name{font-weight:600;font-size:16px;display:flex;align-items:center;gap:8px}
.dot{width:9px;height:9px;border-radius:50%;background:#c33;flex:none}.on{background:#2ea44f}
.ri-meta{color:#7a828a;font-size:13px;margin-top:3px}
.chev{margin-left:auto;color:#9aa2aa;font-size:22px;padding-right:6px}
.empty{padding:40px 18px;color:#8a929a;text-align:center}
/* detail */
.detail{max-width:760px;margin:0 auto;padding:0 14px 30px}
.big{width:100%;aspect-ratio:16/9;object-fit:cover;background:#000;border-radius:12px;display:block;margin-top:12px}
.dname{font-size:22px;font-weight:700;margin:14px 0 2px;display:flex;align-items:center;gap:9px}
.dmeta{color:#7a828a;font-size:14px;margin-bottom:8px}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0}
.sec{background:#fff;border-radius:12px;padding:14px;margin-top:12px}
@media(prefers-color-scheme:dark){.sec{background:#1c2126}}
.sec h4{margin:0 0 8px;font-size:14px;color:#8a929a;font-weight:600;text-transform:uppercase;letter-spacing:.4px}
label{font-size:12px;color:#8a929a;display:block;margin:10px 0 3px}
select,input[type=number]{width:100%;padding:8px;border-radius:8px;border:1px solid #0002;background:transparent;color:inherit}
input[type=range]{width:100%}
.url{font-size:11px;color:#8a929a;word-break:break-all;margin-top:10px}
dialog{border:0;border-radius:14px;padding:0;max-width:440px;width:92%;background:#fff;color:#111}
@media(prefers-color-scheme:dark){dialog{background:#1c2126;color:#e9ecef}}
dialog .in{padding:18px}h3{margin:0 0 10px}.note{font-size:12px;color:#8a929a;margin-top:10px}
</style></head><body>
<header>
  <span id="title" onclick="goBack()" style="cursor:pointer">🤖 Enabot</span>
  <span><button class="btn" id="addbtn" onclick="alert('Coming soon: pair a new robot')">+ Add robot</button>
        <button class="btn" onclick="openOpts()">⚙ Settings</button></span>
</header>
<div id="view"></div>

<dialog id="opts"><div class="in">
  <h3>Add-on settings</h3><div id="optform"></div>
  <div class="row" style="justify-content:flex-end;margin-top:16px">
    <button class="btn" onclick="document.getElementById('opts').close()">Cancel</button>
    <button class="btn pri" onclick="saveOpts()">Save &amp; restart</button></div>
  <div class="note">Saving restarts the add-on (brief interruption).</div>
</div></dialog>

<script>
const B = window.location.pathname.replace(/\/$/,'');
const VQ=["Low","Medium","High"], IS=["Standard","Vivid","Soft"], EY=["Dynamic","Clock","Custom"];
let ROBOTS=[], SEL=null;
async function cmd(node,suffix,payload){
  await fetch(B+'/api/cmd',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({node,suffix,payload})}); setTimeout(refresh,400);
}
function esc(s){return (s==null?'':(''+s))}
function opt(list,cur){return list.map(v=>`<option ${v==cur?'selected':''}>${v}</option>`).join('')}
function meta(r){const st=r.state||{};
  const bat=(st.battery!=null)?st.battery+'%':'—', wifi=(st.wifi!=null?st.wifi:(st.rssi!=null?st.rssi:'—'));
  return `${r.model||'EBO'} · 🔋 ${bat} · 📶 ${wifi}`;}
function thumb(n){return `${B}/api/snapshot?node=${encodeURIComponent(n)}&t=${Math.floor(Date.now()/4000)}`}
function openRobot(n){SEL=n; render()}
function goBack(){SEL=null; render()}

function listView(){
  if(!ROBOTS.length) return `<div class="empty">Waiting for robots… make sure the add-on is running.</div>`;
  return `<div class="list">`+ROBOTS.map(r=>`
    <div class="rowitem" onclick="openRobot('${r.node}')">
      <img class="thumb" src="${thumb(r.node)}" onerror="this.style.opacity=.25">
      <div>
        <div class="ri-name"><span class="dot ${r.online?'on':''}"></span>${esc(r.name||r.node)}</div>
        <div class="ri-meta">${meta(r)}</div>
      </div><div class="chev">›</div>
    </div>`).join('')+`</div>`;
}
function detailView(r){
  const st=r.state||{}, cam=(r.camera==='on');
  return `<div class="detail">
    <img class="big" src="${thumb(r.node)}" onerror="this.style.opacity=.25">
    <div class="dname"><span class="dot ${r.online?'on':''}"></span>${esc(r.name||r.node)}</div>
    <div class="dmeta">${r.model||'EBO'} · SN ${esc(r.sn)||'—'} · 🔋 ${st.battery??'—'}% · 📶 ${st.wifi??'—'}</div>
    <div class="row">
      <button class="btn ${cam?'pri':''}" onclick="cmd('${r.node}','camera/set','${cam?'off':'on'}')">${cam?'Camera ON':'Camera OFF'}</button>
      <button class="btn" onclick="cmd('${r.node}','laser/set','on')">Laser</button>
      <button class="btn" onclick="cmd('${r.node}','dock','')">Dock</button>
    </div>
    <div class="sec"><h4>Robot settings</h4>
      <label>Video quality</label><select onchange="cmd('${r.node}','video_quality/set',this.value)">${opt(VQ,st.video_quality)}</select>
      <label>Image style</label><select onchange="cmd('${r.node}','image_style/set',this.value)">${opt(IS,st.image_style)}</select>
      <label>Eyes</label><select onchange="cmd('${r.node}','eyes/set',this.value)">${opt(EY,st.eyes)}</select>
      <label>Volume (${st.volume??st.playback_volume??'—'})</label>
      <input type="range" min="0" max="100" value="${st.volume??st.playback_volume??50}" onchange="cmd('${r.node}','volume/set',this.value)">
      <label>Speed (${st.speed??'—'})</label>
      <input type="range" min="1" max="100" value="${st.speed??50}" onchange="cmd('${r.node}','speed/set',this.value)">
      <div class="row">
        <button class="btn" onclick="cmd('${r.node}','sports_record/set','on')">Motion rec ON</button>
        <button class="btn" onclick="cmd('${r.node}','sports_record/set','off')">OFF</button>
      </div>
    </div>
    <div class="url">${esc(r.url)}</div>
  </div>`;
}
function render(){
  document.getElementById('addbtn').style.display = SEL?'none':'';
  document.getElementById('title').innerHTML = SEL? '‹ Enabot' : '🤖 Enabot';
  const r = SEL && ROBOTS.find(x=>x.node===SEL);
  document.getElementById('view').innerHTML = r? detailView(r) : listView();
}
async function refresh(){
  try{ ROBOTS = await (await fetch(B+'/api/robots')).json(); render(); }catch(e){}
}
async function openOpts(){
  const d = await (await fetch(B+'/api/options')).json(); const sc=d.schema, v=d.values;
  let h='';
  for(const k in sc){const s=sc[k];
    h+=`<label>${k}</label>`;
    if(s.type==='bool') h+=`<select id="o-${k}"><option ${v[k]?'selected':''}>true</option><option ${!v[k]?'selected':''}>false</option></select>`;
    else if(s.type==='select') h+=`<select id="o-${k}">${s.choices.map(c=>`<option ${c==v[k]?'selected':''}>${c}</option>`).join('')}</select>`;
    else if(s.type==='text') h+=`<input id="o-${k}" type="text" value="${v[k]??''}">`;
    else h+=`<input id="o-${k}" type="number" value="${v[k]??''}">`;
  }
  document.getElementById('optform').innerHTML=h;
  document.getElementById('opts').showModal();
}
async function saveOpts(){
  const d = await (await fetch(B+'/api/options')).json(); const sc=d.schema; const out={};
  for(const k in sc){const el=document.getElementById('o-'+k); if(!el)continue;
    out[k] = sc[k].type==='bool' ? (el.value==='true') : el.value;}
  await fetch(B+'/api/options',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({options:out})});
  document.getElementById('opts').close(); alert('Saved. The add-on is restarting…');
}
refresh(); setInterval(refresh, 4000);
</script></body></html>"""


def main():
    try:
        _start_mqtt()
    except Exception as e:
        log("[panel] MQTT connect failed:", e)
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log("[panel] Ingress UI on :%d" % PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
