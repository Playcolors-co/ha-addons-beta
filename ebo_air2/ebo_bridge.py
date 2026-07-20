#!/usr/bin/env python3
"""
ebo_bridge.py — EBO Air 2 ⇆ Home Assistant bridge.

Establishes the robot control session (RTM login + RTC join, like the app), then:
  - publishes telemetry as Home Assistant entities via MQTT Discovery
  - receives commands from HA (speed, laser, movement) and forwards them to the robot
  - keeps a 10 Hz movement loop with a watchdog (dead-man's switch)

Autonomous: with EBO_EMAIL/EBO_PASSWORD it logs into the Enabot cloud, discovers the
robot, gets the Agora tokens and renews them by itself before expiry (~24h). No
emulator, no session.json. See docs/STATO.md.

Config via env:
  EBO_EMAIL, EBO_PASSWORD          the user's Enabot credentials (autonomous)
  EBO_REGION=GB                    account region
  EBO_ROBOT_ID                     optional: if the account has more than one robot
  EBO_MQTT_HOST, EBO_MQTT_PORT=1883, EBO_MQTT_USER, EBO_MQTT_PASS
  (fallback: EBO_SESSION=/app/session.json)
"""
import json
import os
import sys
import threading
import time

import paho.mqtt.client as mqtt

import ebo_cloud

from agora.rtc.agora_service import AgoraService, AgoraServiceConfig
from agora.rtc.agora_base import (
    RTCConnConfig, ClientRoleType, ChannelProfileType, RtcConnectionPublishConfig,
)
from agora.rtc.rtc_connection_observer import IRTCConnectionObserver
from agora.rtm.rtm_client import create_rtm_client
from agora.rtm.rtm_base import (
    RtmConfig, PublishOptions, SubscribeOptions,
    RtmChannelType, RtmMessageType, IRtmEventHandler,
)

# ---- protocol opcodes (see docs/PROTOCOLLO.md) ----
OP_HANDSHAKE = 101003
OP_HEARTBEAT = 101005
OP_GET_SETTINGS = 101027
OP_MOVE = 101007
OP_TELEMETRY = 101026
OP_SETTINGS = 101028
OP_INFO = 101004
OP_SET_SPEED = 103009
OP_LASER = 103051

DISCOVERY_PREFIX = "homeassistant"
NODE = "ebo_air2"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


class Bridge:
    def __init__(self, session, mqtt_conf, provider=None, robot_id=None):
        self.provider = provider        # callable -> fresh session dict (login/refresh)
        self.robot_id = robot_id
        self.s = session
        self.account = self.s["rtm_user"].rsplit("_", 1)[-1]
        self.sid = self.s.get("sid")
        self.telemetry = {}
        self.settings = {}
        self.info = {}
        self.rtc_state = None

        # current movement vector + watchdog
        self.vec = {"lx": 0, "ly": 0, "rx": 0, "ry": 0, "buttons": 0}
        self.vec_deadline = 0.0
        self.lock = threading.Lock()
        self.stop = threading.Event()

        self.rtm = None
        self.rtc = None
        self.mqtt = None
        self.mqtt_conf = mqtt_conf

    # ---------------- Agora ----------------

    def connect_agora(self):
        s = self.s

        class RtcObs(IRTCConnectionObserver):
            def on_connected(o, conn, info, reason):
                self.rtc_state = "connected"
                log("[RTC] connected")

            def on_disconnected(o, conn, info, reason):
                self.rtc_state = "disconnected"
                log("[RTC] disconnected")

            def on_connection_failure(o, conn, info, reason):
                self.rtc_state = "failed"
                log("[RTC] connection failed:", reason)

            def on_user_joined(o, conn, uid):
                log("[RTC] robot present:", uid)

        bridge = self

        class RtmH(IRtmEventHandler):
            def on_message_event(o, event):
                bridge._on_rtm(event)

            def on_login_result(o, req, err):
                log("[RTM] login result:", err)

        self.rtm = create_rtm_client(RtmConfig(
            app_id=s["app_id"], user_id=s["rtm_user"], use_string_user_id=1,
            presence_timeout=300, heartbeat_interval=5, event_handler=RtmH(),
        ))
        r, _ = self.rtm.login(s["rtm_token"])
        if r != 0:
            raise RuntimeError("RTM login failed: %s" % self.rtm.get_error_reason(r))
        self.rtm.subscribe(s["robot_rtm"],
                           SubscribeOptions(with_message=True, with_presence=True))
        log("[RTM] login and subscribe ok")

        svc = AgoraService()
        scfg = AgoraServiceConfig()
        scfg.appid = s["app_id"]
        svc.initialize(scfg)
        ccfg = RTCConnConfig(
            auto_subscribe_audio=0, auto_subscribe_video=0,
            client_role_type=ClientRoleType.CLIENT_ROLE_BROADCASTER,
            channel_profile=ChannelProfileType.CHANNEL_PROFILE_LIVE_BROADCASTING,
        )
        pcfg = RtcConnectionPublishConfig(is_publish_audio=False, is_publish_video=False)
        self.rtc = svc.create_rtc_connection(ccfg, pcfg)
        self.rtc.register_observer(RtcObs())
        self.rtc.connect(s["rtc_token"], s["rtc_channel"], s["rtc_uid"])
        for _ in range(20):
            if self.rtc_state:
                break
            time.sleep(0.5)
        log("[RTC] state:", self.rtc_state)

    def _opts(self):
        return PublishOptions(
            channel_type=RtmChannelType.RTM_CHANNEL_TYPE_USER,
            message_type=RtmMessageType.RTM_MESSAGE_TYPE_BINARY,
        )

    def send(self, mid, data=None):
        msg = {"id": mid, "type": 0, "timestamp": time.time() * 1000}
        if self.sid:
            msg["sid"] = self.sid
        if data is not None:
            msg["data"] = data
        payload = json.dumps(msg, separators=(",", ":")).encode()
        r, _ = self.rtm.publish(self.s["robot_rtm"], payload, self._opts())
        if r != 0:
            log("[!] publish %s failed: %s" % (mid, self.rtm.get_error_reason(r)))

    def _on_rtm(self, event):
        try:
            raw = event.message
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", "replace")
            obj = json.loads(raw)
        except Exception:
            return
        mid = obj.get("id")
        data = obj.get("data", {})
        if obj.get("rsid"):
            self.sid = obj["rsid"]
        if mid == OP_TELEMETRY:
            self.telemetry = data
            self._publish_telemetry()
        elif mid == OP_SETTINGS:
            self.settings = data
            self._publish_settings()
        elif mid == OP_INFO:
            self.info = data

    # ---------------- control loop ----------------

    def control_loop(self):
        """Heartbeat every 2 s + movement at 10 Hz with watchdog."""
        last_beat = 0.0
        while not self.stop.is_set():
            now = time.time()
            if now - last_beat >= 2:
                self.send(OP_HEARTBEAT, {"state": 0})
                last_beat = now
            with self.lock:
                v = dict(self.vec)
                # watchdog: if the command expired, zero it (dead-man's switch)
                if self.vec_deadline and now > self.vec_deadline:
                    self.vec = {"lx": 0, "ly": 0, "rx": 0, "ry": 0, "buttons": 0}
                    self.vec_deadline = 0.0
                    v = dict(self.vec)
                moving = any(v[k] for k in ("lx", "ly", "rx", "ry"))
            if moving or (self.vec_deadline == 0 and now - last_beat < 0.15):
                self.send(OP_MOVE, v)
            time.sleep(0.1)

    def set_move(self, lx=0, ly=0, rx=0, ry=0, hold=0.6):
        with self.lock:
            self.vec = {"lx": lx, "ly": ly, "rx": rx, "ry": ry, "buttons": 0}
            self.vec_deadline = time.time() + hold if any((lx, ly, rx, ry)) else 0

    # ---------------- MQTT / Home Assistant ----------------

    def connect_mqtt(self):
        # paho-mqtt 2.x requires the callback API version; fall back for 1.x
        try:
            c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="ebo_air2_bridge")
        except (AttributeError, TypeError):
            c = mqtt.Client(client_id="ebo_air2_bridge")
        if self.mqtt_conf.get("user"):
            c.username_pw_set(self.mqtt_conf["user"], self.mqtt_conf["pass"])
        c.on_connect = self._on_mqtt_connect
        c.on_message = self._on_mqtt_message
        c.will_set("%s/status" % NODE, "offline", retain=True)
        c.connect(self.mqtt_conf["host"], self.mqtt_conf["port"], 60)
        c.loop_start()
        self.mqtt = c

    def _dev(self):
        return {
            "identifiers": [NODE],
            "name": "EBO Air 2",
            "manufacturer": "Enabot",
            "model": self.info.get("model", "EBO Air 2"),
            "sw_version": self.info.get("masterMcuVersion", ""),
        }

    def _disc(self, comp, oid, cfg):
        cfg["device"] = self._dev()
        cfg["unique_id"] = "%s_%s" % (NODE, oid)
        cfg["availability_topic"] = "%s/status" % NODE
        topic = "%s/%s/%s/%s/config" % (DISCOVERY_PREFIX, comp, NODE, oid)
        self.mqtt.publish(topic, json.dumps(cfg), retain=True)

    def _on_mqtt_connect(self, c, u, flags, rc):
        log("[MQTT] connected rc=%s" % rc)
        c.publish("%s/status" % NODE, "online", retain=True)
        st = "%s/state" % NODE

        self._disc("sensor", "battery", {
            "name": "EBO battery", "state_topic": st,
            "value_template": "{{ value_json.battery }}",
            "unit_of_measurement": "%", "device_class": "battery"})
        self._disc("sensor", "wifi", {
            "name": "EBO wifi", "state_topic": st,
            "value_template": "{{ value_json.wifi }}",
            "unit_of_measurement": "dBm", "device_class": "signal_strength",
            "entity_category": "diagnostic"})
        self._disc("binary_sensor", "charging", {
            "name": "EBO charging", "state_topic": st,
            "value_template": "{{ value_json.charging }}",
            "payload_on": "true", "payload_off": "false", "device_class": "battery_charging"})
        self._disc("binary_sensor", "recording", {
            "name": "EBO recording", "state_topic": st,
            "value_template": "{{ value_json.recording }}",
            "payload_on": "true", "payload_off": "false"})

        self._disc("switch", "laser", {
            "name": "EBO laser", "state_topic": st,
            "value_template": "{{ value_json.laser }}",
            "command_topic": "%s/laser/set" % NODE,
            "payload_on": "on", "payload_off": "off",
            "state_on": "true", "state_off": "false"})
        self._disc("number", "speed", {
            "name": "EBO speed", "state_topic": st,
            "value_template": "{{ value_json.speed }}",
            "command_topic": "%s/speed/set" % NODE,
            "min": 1, "max": 100, "step": 1})

        # movement: 4 buttons (also handy for an AI agent via MQTT)
        for direction, label in [("forward", "forward"), ("back", "back"),
                                 ("left", "left"), ("right", "right"),
                                 ("stop", "stop")]:
            self._disc("button", "move_%s" % direction, {
                "name": "EBO %s" % label,
                "command_topic": "%s/move/%s" % (NODE, direction)})

        c.subscribe("%s/laser/set" % NODE)
        c.subscribe("%s/speed/set" % NODE)
        c.subscribe("%s/move/+" % NODE)
        # canale generico per un agente: JSON {"ly":-50,"rx":0,"hold":1.0}
        c.subscribe("%s/move/vector" % NODE)

    def _on_mqtt_message(self, c, u, msg):
        topic = msg.topic
        payload = msg.payload.decode("utf-8", "replace").strip()
        try:
            if topic.endswith("/laser/set"):
                self.send(OP_LASER, {"laser": payload.lower() in ("on", "true", "1")})
            elif topic.endswith("/speed/set"):
                self.send(OP_SET_SPEED, {"moveSpeed": int(float(payload))})
            elif topic.endswith("/move/vector"):
                v = json.loads(payload)
                self.set_move(v.get("lx", 0), v.get("ly", 0), v.get("rx", 0),
                              v.get("ry", 0), v.get("hold", 0.6))
            elif "/move/" in topic:
                d = topic.rsplit("/", 1)[-1]
                mag = 60
                mapping = {
                    "forward": (0, -mag, 0), "back": (0, mag, 0),
                    "left": (0, 0, -mag), "right": (0, 0, mag), "stop": (0, 0, 0),
                }
                if d in mapping:
                    lx, ly, rx = mapping[d]
                    self.set_move(lx, ly, rx, hold=0.8)
        except Exception as e:
            log("[MQTT] command error %s: %s" % (topic, e))

    def _publish_telemetry(self):
        t = self.telemetry
        b = t.get("battery", {})
        stt = t.get("status", {})
        payload = {
            "battery": b.get("percentage"),
            "charging": "true" if b.get("chargeStatus") else "false",
            "wifi": t.get("wifiStrength"),
            "recording": "true" if stt.get("isVideoRecording") else "false",
            "laser": "true" if stt.get("laserStatus") else "false",
            "speed": self.settings.get("moveSpeed"),
        }
        self.mqtt.publish("%s/state" % NODE, json.dumps(payload), retain=True)

    def _publish_settings(self):
        # unisce moveSpeed nello stato
        self._publish_telemetry()

    # ---------------- avvio ----------------

    def _token_age_ok(self):
        # RTC expires ~24h: renew with margin (every 20h)
        return (time.time() - self.s.get("captured_at", 0)) < 20 * 3600

    def refresh_session(self):
        if not self.provider:
            return
        try:
            fresh = self.provider()
            if fresh:
                self.s = fresh
                log("[*] Agora session renewed (auto)")
        except Exception as e:
            log("[!] session refresh failed:", e)

    def run(self):
        self.connect_agora()
        self.connect_mqtt()
        threading.Thread(target=self.control_loop, daemon=True).start()
        self.send(OP_HANDSHAKE, {"userId": self.account})
        time.sleep(1)
        self.send(OP_GET_SETTINGS)
        log("[*] bridge attivo")
        try:
            while not self.stop.is_set():
                time.sleep(30)
                if self.provider and not self._token_age_ok():
                    self.refresh_session()
                    # reconnect Agora with the new tokens
                    try:
                        self.rtc.disconnect()
                    except Exception:
                        pass
                    self.connect_agora()
                    self.send(OP_HANDSHAKE, {"userId": self.account})
        except KeyboardInterrupt:
            pass
        finally:
            if self.mqtt:
                self.mqtt.publish("%s/status" % NODE, "offline", retain=True)
            self.stop.set()


def _make_provider():
    """If EBO_EMAIL/EBO_PASSWORD are set, the provider logs in and discovers the robot,
    renewing the session on each call. Returns (provider, robot_id, first_session)."""
    email = os.environ.get("EBO_EMAIL")
    password = os.environ.get("EBO_PASSWORD")
    if not (email and password):
        return None, None, None
    region = os.environ.get("EBO_REGION", "GB")
    host = os.environ.get("EBO_HOST", "ebox-eu.enabotserverintl.com")
    app_id = os.environ.get("EBO_APP_ID", "941ef1b4f14743fc8fdcf96b9331ca01")
    want_robot = os.environ.get("EBO_ROBOT_ID")

    def provider():
        c = ebo_cloud.EboCloud(host=host)
        r = c.login(email, password, region=region)
        if r.get("code") != 200:
            raise RuntimeError("login failed: %s" % r.get("msg"))
        robots = c.robots().get("data", {}).get("list", [])
        if not robots:
            raise RuntimeError("no robot on the account")
        rid = int(want_robot) if want_robot else robots[0]["robot_info"]["robot_id"]
        return ebo_cloud.build_bridge_session_from(c, rid, app_id)

    first = provider()
    rid = int(want_robot) if want_robot else None
    return provider, rid, first


def main():
    provider, robot_id, session = _make_provider()
    if session is None:
        sess_path = os.environ.get("EBO_SESSION", os.path.join(
            os.path.dirname(__file__), "session.json"))
        with open(sess_path) as f:
            session = json.load(f)
    mqtt_conf = {
        "host": os.environ.get("EBO_MQTT_HOST", "127.0.0.1"),
        "port": int(os.environ.get("EBO_MQTT_PORT", "1883")),
        "user": os.environ.get("EBO_MQTT_USER", ""),
        "pass": os.environ.get("EBO_MQTT_PASS", ""),
    }
    Bridge(session, mqtt_conf, provider=provider, robot_id=robot_id).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
