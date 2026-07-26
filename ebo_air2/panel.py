"""
panel.py — the add-on's Ingress web UI (a Zigbee2MQTT-style sidebar panel).

ONE instance for the whole add-on (not per robot). It subscribes to MQTT to aggregate the state
of every robot the bridges publish, serves a small dashboard, forwards safe control + settings
commands over MQTT, and lets you edit add-on options (log level, video quality…) via the
Supervisor. Live preview is an on-demand JPEG grabbed from each robot's RTSP.

No extra dependencies: stdlib http.server + paho-mqtt (already used by the bridge) + ffmpeg.
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
OPTIONS_FILE = "/data/options.json"

# Command suffixes the panel may publish (allow-list). Controls + per-robot settings. Movement is
# deliberately excluded — driving belongs on a dashboard where the user is watching.
ALLOWED_CMDS = {
    "camera/set", "laser/set", "dock", "sleep/set", "connected/set", "patrol/start",
    "say", "talk",
    # per-robot settings:
    "video_quality/set", "image_style/set", "volume/set", "talkback_volume/set",
    "speed/set", "sports_record/set", "call_rec/set", "eyes/set",
}

# Add-on options the panel may edit (others — email/password/region — stay in the add-on config).
EDITABLE_OPTS = {
    "log_level": {"type": "select", "choices": ["debug", "info", "warning"]},
    "video_max_height": {"type": "int"},
    "video_fps": {"type": "int"},
    "video_bitrate": {"type": "int"},
    "video_preset": {"type": "select",
                     "choices": ["ultrafast", "superfast", "veryfast", "faster", "fast"]},
    "audio": {"type": "bool"},
    "talk": {"type": "bool"},
}

_robots = {}                 # node -> {name, sn, mac, model, rtsp, online, state{}, camera, url}
_lock = threading.Lock()
_snap_cache = {}             # node -> (ts, jpeg_bytes)
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


# --------------------------- add-on options via the Supervisor ---------------------------
def _read_options():
    try:
        with open(OPTIONS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _supervisor(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request("http://supervisor" + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + SUPERVISOR_TOKEN)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read() or b"{}")


def _save_options(patch):
    """Merge a patch into the current add-on options and apply via the Supervisor, then restart."""
    opts = _read_options()
    for k, v in patch.items():
        if k in EDITABLE_OPTS:
            opts[k] = v
    _supervisor("POST", "/addons/self/options", {"options": opts})
    threading.Thread(target=lambda: (time.sleep(1), _supervisor("POST", "/addons/self/restart")),
                     daemon=True).start()


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
    internal = "rtsp://127.0.0.1:%s%s" % (p.port or 8554, p.path)   # panel shares the container
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
            opts = _read_options()
            return self._send(200, json.dumps(
                {k: opts.get(k) for k in EDITABLE_OPTS} | {"_schema": EDITABLE_OPTS}))
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
            node = str(body.get("node", ""))
            suffix = str(body.get("suffix", ""))
            payload = str(body.get("payload", ""))
            if not node or suffix not in ALLOWED_CMDS or _client is None:
                return self._send(400, json.dumps({"error": "bad command"}))
            _client.publish("%s/%s" % (node, suffix), payload)
            log("[panel] cmd %s/%s = %s" % (node, suffix, payload))
            return self._send(200, json.dumps({"ok": True}))
        if path.endswith("/api/options"):
            try:
                _save_options(body.get("options", {}))
                return self._send(200, json.dumps({"ok": True, "restarting": True}))
            except Exception as e:
                log("[panel] save options failed:", e)
                return self._send(500, json.dumps({"error": str(e)}))
        return self._send(404, "{}")


PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EBO robots</title><style>
:root{color-scheme:light dark}
body{font-family:system-ui,sans-serif;margin:0;background:#f4f5f7;color:#111}
@media(prefers-color-scheme:dark){body{background:#111417;color:#e9ecef}}
header{padding:14px 18px;font-size:20px;font-weight:600;display:flex;justify-content:space-between;align-items:center}
.btn{border:0;border-radius:9px;padding:8px 12px;font-size:13px;cursor:pointer;background:#e6e8eb;color:inherit}
@media(prefers-color-scheme:dark){.btn{background:#2a3138;color:#e9ecef}}
.btn:hover{filter:brightness(.95)}
.btn.pri{background:#2b6cff;color:#fff}
.wrap{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));padding:0 18px 24px}
.card{background:#fff;border-radius:14px;box-shadow:0 1px 4px rgba(0,0,0,.12);overflow:hidden}
@media(prefers-color-scheme:dark){.card{background:#1c2126}}
.prev{width:100%;aspect-ratio:16/9;object-fit:cover;background:#000;display:block}
.body{padding:12px 14px}
.name{font-weight:600;font-size:17px;display:flex;align-items:center;gap:8px}
.dot{width:9px;height:9px;border-radius:50%;background:#c33}.on{background:#2ea44f}
.meta{color:#7a828a;font-size:13px;margin:4px 0 10px}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:8px}
.set{margin-top:10px;padding-top:10px;border-top:1px solid #0001;display:none}
.set.show{display:block}
label{font-size:12px;color:#8a929a;display:block;margin:8px 0 3px}
select,input[type=number]{width:100%;padding:7px;border-radius:8px;border:1px solid #0002;background:transparent;color:inherit;box-sizing:border-box}
input[type=range]{width:100%}
.url{font-size:11px;color:#8a929a;word-break:break-all;margin-top:8px}
.empty{padding:40px 18px;color:#8a929a}
dialog{border:0;border-radius:14px;padding:0;max-width:420px;width:92%;background:#fff;color:#111}
@media(prefers-color-scheme:dark){dialog{background:#1c2126;color:#e9ecef}}
dialog .body{padding:18px}
h3{margin:0 0 10px}
.note{font-size:12px;color:#8a929a;margin-top:10px}
</style></head><body>
<header><span>🤖 EBO robots</span><button class="btn" onclick="openOpts()">⚙ Add-on settings</button></header>
<div id="wrap" class="wrap"></div>
<div id="empty" class="empty">Waiting for robots… make sure the add-on is running.</div>

<dialog id="opts"><div class="body">
  <h3>Add-on settings</h3>
  <div id="optform"></div>
  <div class="row" style="justify-content:flex-end;margin-top:16px">
    <button class="btn" onclick="document.getElementById('opts').close()">Cancel</button>
    <button class="btn pri" onclick="saveOpts()">Save &amp; restart</button>
  </div>
  <div class="note">Saving restarts the add-on (brief video interruption).</div>
</div></dialog>

<script>
const B = window.location.pathname.replace(/\/$/,'');
const VQ=["Low","Medium","High"], IS=["Standard","Vivid","Soft"], EY=["Dynamic","Clock","Custom"];
async function cmd(node,suffix,payload){
  await fetch(B+'/api/cmd',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({node,suffix,payload})}); setTimeout(load,400);
}
function opt(list,cur){return list.map(v=>`<option ${v==cur?'selected':''}>${v}</option>`).join('')}
function toggleSet(n){document.getElementById('set-'+n).classList.toggle('show')}
function card(r){
  const st=r.state||{}, cam=(r.camera==='on');
  const bat=(st.battery!=null)?st.battery+'%':'—', wifi=(st.wifi!=null?st.wifi:(st.rssi!=null?st.rssi:'—'));
  const n=r.node;
  return `<div class="card">
    <img class="prev" src="${B}/api/snapshot?node=${encodeURIComponent(n)}&t=${Date.now()}" onerror="this.style.opacity=.25">
    <div class="body">
      <div class="name"><span class="dot ${r.online?'on':''}"></span>${r.name||n}</div>
      <div class="meta">${r.model||'EBO'} · SN ${r.sn||'—'} · 🔋 ${bat} · 📶 ${wifi}</div>
      <div class="row">
        <button class="btn ${cam?'pri':''}" onclick="cmd('${n}','camera/set','${cam?'off':'on'}')">${cam?'Camera ON':'Camera OFF'}</button>
        <button class="btn" onclick="cmd('${n}','laser/set','on')">Laser</button>
        <button class="btn" onclick="cmd('${n}','dock','')">Dock</button>
        <button class="btn" onclick="toggleSet('${n}')">⚙ Settings</button>
      </div>
      <div class="set" id="set-${n}">
        <label>Video quality</label>
        <select onchange="cmd('${n}','video_quality/set',this.value)">${opt(VQ, st.video_quality)}</select>
        <label>Image style</label>
        <select onchange="cmd('${n}','image_style/set',this.value)">${opt(IS, st.image_style)}</select>
        <label>Eyes</label>
        <select onchange="cmd('${n}','eyes/set',this.value)">${opt(EY, st.eyes)}</select>
        <label>Volume (${st.volume??st.playback_volume??'—'})</label>
        <input type="range" min="0" max="100" value="${st.volume??st.playback_volume??50}"
          onchange="cmd('${n}','volume/set',this.value)">
        <label>Speed (${st.speed??st.move_speed??'—'})</label>
        <input type="range" min="1" max="100" value="${st.speed??st.move_speed??50}"
          onchange="cmd('${n}','speed/set',this.value)">
        <div class="row">
          <button class="btn" onclick="cmd('${n}','sports_record/set','on')">Motion rec ON</button>
          <button class="btn" onclick="cmd('${n}','sports_record/set','off')">OFF</button>
        </div>
      </div>
      <div class="url">${r.url||''}</div>
    </div></div>`;
}
async function load(){
  try{
    const list = await (await fetch(B+'/api/robots')).json();
    document.getElementById('empty').style.display = list.length?'none':'block';
    // keep open settings drawers open across refreshes
    const open = [...document.querySelectorAll('.set.show')].map(e=>e.id);
    document.getElementById('wrap').innerHTML = list.map(card).join('');
    open.forEach(id=>{const e=document.getElementById(id); if(e)e.classList.add('show')});
  }catch(e){}
}
async function openOpts(){
  const d = await (await fetch(B+'/api/options')).json(); const sc=d._schema;
  let h='';
  for(const k in sc){
    const s=sc[k], v=d[k];
    h+=`<label>${k}</label>`;
    if(s.type==='bool') h+=`<select id="o-${k}"><option ${v?'selected':''}>true</option><option ${!v?'selected':''}>false</option></select>`;
    else if(s.type==='select') h+=`<select id="o-${k}">${s.choices.map(c=>`<option ${c==v?'selected':''}>${c}</option>`).join('')}</select>`;
    else h+=`<input id="o-${k}" type="number" value="${v??''}">`;
  }
  document.getElementById('optform').innerHTML=h;
  document.getElementById('opts').showModal();
}
async function saveOpts(){
  const d = await (await fetch(B+'/api/options')).json(); const sc=d._schema; const out={};
  for(const k in sc){
    const el=document.getElementById('o-'+k); if(!el) continue;
    if(sc[k].type==='bool') out[k]=(el.value==='true');
    else if(sc[k].type==='int') out[k]=parseInt(el.value||'0',10);
    else out[k]=el.value;
  }
  await fetch(B+'/api/options',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({options:out})});
  document.getElementById('opts').close();
  alert('Saved. The add-on is restarting…');
}
load(); setInterval(load, 4000);
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
