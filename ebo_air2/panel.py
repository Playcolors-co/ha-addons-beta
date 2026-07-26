"""
panel.py — the add-on's Ingress web UI (a Zigbee2MQTT-style sidebar panel).

ONE instance for the whole add-on (not per robot). It subscribes to MQTT to aggregate the state
of every robot the bridges publish, serves a small dashboard, and forwards a few safe control
commands back over MQTT. Live preview is an on-demand JPEG grabbed from each robot's RTSP.

No extra dependencies: stdlib http.server + paho-mqtt (already used by the bridge) + ffmpeg.
"""
import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import paho.mqtt.client as mqtt

from ebo_log import log

PORT = int(os.environ.get("EBO_PANEL_PORT", "8099"))
MQTT_HOST = os.environ.get("EBO_MQTT_HOST", "core-mosquitto")
MQTT_PORT = int(os.environ.get("EBO_MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("EBO_MQTT_USER", "") or None
MQTT_PASS = os.environ.get("EBO_MQTT_PASS", "") or None

# Only these command suffixes may be published from the panel (safety allow-list). Movement is
# deliberately excluded — driving belongs on a dashboard where the user is watching.
ALLOWED_CMDS = {
    "camera/set", "laser/set", "dock", "speed/set", "sleep/set", "connected/set",
    "patrol/start", "say", "talk",
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
    client.subscribe("ebo_air2/discovery/#")
    client.subscribe("+/status")
    client.subscribe("+/state")
    client.subscribe("+/camera/state")
    client.subscribe("+/camera/url")


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


# --------------------------- live preview: one JPEG from RTSP ---------------------------
def _snapshot(node):
    with _lock:
        r = _robots.get(node)
        url = r and r.get("rtsp")
    if not url:
        return None
    now = time.time()
    ts, cached = _snap_cache.get(node, (0, None))
    if cached and now - ts < 2.0:            # throttle: at most one grab / 2 s per robot
        return cached
    # the panel shares the container with mediamtx → grab from the internal RTSP (localhost)
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
                snapshot = json.dumps(list(_robots.values()))
            return self._send(200, snapshot)
        if path.endswith("/api/snapshot"):
            q = parse_qs(urlparse(self.path).query)
            node = (q.get("node") or [""])[0]
            jpg = _snapshot(node)
            if jpg:
                return self._send(200, jpg, "image/jpeg")
            return self._send(404, b"", "image/jpeg")
        return self._send(200, PAGE, "text/html; charset=utf-8")

    def do_POST(self):
        if not urlparse(self.path).path.rstrip("/").endswith("/api/cmd"):
            return self._send(404, "{}")
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            node = str(body.get("node", ""))
            suffix = str(body.get("suffix", ""))
            payload = str(body.get("payload", ""))
            if not node or suffix not in ALLOWED_CMDS or _client is None:
                return self._send(400, json.dumps({"error": "bad command"}))
            _client.publish("%s/%s" % (node, suffix), payload)
            log("[panel] cmd %s/%s = %s" % (node, suffix, payload))
            return self._send(200, json.dumps({"ok": True}))
        except Exception as e:
            return self._send(500, json.dumps({"error": str(e)}))


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EBO robots</title><style>
:root{color-scheme:light dark}
body{font-family:system-ui,sans-serif;margin:0;background:#f4f5f7;color:#111}
@media(prefers-color-scheme:dark){body{background:#111417;color:#e9ecef}}
header{padding:14px 18px;font-size:20px;font-weight:600}
.wrap{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));padding:0 18px 24px}
.card{background:#fff;border-radius:14px;box-shadow:0 1px 4px rgba(0,0,0,.12);overflow:hidden}
@media(prefers-color-scheme:dark){.card{background:#1c2126}}
.prev{width:100%;aspect-ratio:16/9;object-fit:cover;background:#000;display:block}
.body{padding:12px 14px}
.name{font-weight:600;font-size:17px;display:flex;align-items:center;gap:8px}
.dot{width:9px;height:9px;border-radius:50%;background:#c33}
.on{background:#2ea44f}
.meta{color:#7a828a;font-size:13px;margin:4px 0 10px}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
button{border:0;border-radius:9px;padding:8px 12px;font-size:13px;cursor:pointer;background:#e6e8eb;color:inherit}
button:hover{filter:brightness(.95)}
button.pri{background:#2b6cff;color:#fff}
.url{font-size:11px;color:#8a929a;word-break:break-all;margin-top:8px}
.empty{padding:40px 18px;color:#8a929a}
</style></head><body>
<header>🤖 EBO robots</header>
<div id="wrap" class="wrap"></div>
<div id="empty" class="empty">Waiting for robots… make sure the add-on is running.</div>
<script>
const B = (window.location.pathname.replace(/\\/$/,''));
async function cmd(node,suffix,payload){
  await fetch(B+'/api/cmd',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({node,suffix,payload})});
  setTimeout(load,400);
}
function card(r){
  const st=r.state||{}, cam=(r.camera==='on');
  const bat=(st.battery!=null)?st.battery+'%':'—';
  const wifi=(st.wifi!=null)?st.wifi:(st.rssi!=null?st.rssi:'—');
  return `<div class="card">
    <img class="prev" src="${B}/api/snapshot?node=${encodeURIComponent(r.node)}&t=${Date.now()}"
         onerror="this.style.opacity=.25">
    <div class="body">
      <div class="name"><span class="dot ${r.online?'on':''}"></span>${r.name||r.node}</div>
      <div class="meta">${r.model||'EBO'} · SN ${r.sn||'—'} · 🔋 ${bat} · 📶 ${wifi}</div>
      <div class="row">
        <button class="${cam?'pri':''}" onclick="cmd('${r.node}','camera/set','${cam?'off':'on'}')">
          ${cam?'Camera ON':'Camera OFF'}</button>
        <button onclick="cmd('${r.node}','laser/set','on')">Laser</button>
        <button onclick="cmd('${r.node}','dock','')">Dock</button>
      </div>
      <div class="url">${r.url||''}</div>
    </div></div>`;
}
async function load(){
  try{
    const r = await fetch(B+'/api/robots'); const list = await r.json();
    document.getElementById('empty').style.display = list.length?'none':'block';
    document.getElementById('wrap').innerHTML = list.map(card).join('');
  }catch(e){}
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
