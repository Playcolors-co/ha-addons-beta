#!/usr/bin/env bash
# Add-on entrypoint: reads user config from /data/options.json and the MQTT broker
# credentials from the Supervisor (mqtt:need service), then starts the bridge.
set -e

OPTS=/data/options.json

export EBO_EMAIL="$(jq -r '.email // empty' "$OPTS")"
export EBO_PASSWORD="$(jq -r '.password // empty' "$OPTS")"
export EBO_REGION="$(jq -r '.region // "GB"' "$OPTS")"
export EBO_HOST="$(jq -r '.host // "ebox-eu.enabotserverintl.com"' "$OPTS")"
export EBO_VIDEO="$(jq -r 'if .video==false then "0" else "1" end' "$OPTS")"
# experimental encoded-video path (may crash the SDK) — off unless explicitly enabled
export EBO_VIDEO_ENCODED="$(jq -r 'if .video_encoded==true then "1" else "0" end' "$OPTS")"
export EBO_AUDIO="$(jq -r 'if .audio==true then "1" else "0" end' "$OPTS")"
# robot mic codec payload type: 8 (monitor, default) or 9 (two-way call). Flip if silent.
export EBO_AUDIO_PT="$(jq -r '.audio_codec // 8' "$OPTS")"
export EBO_LOG_LEVEL="$(jq -r '.log_level // "info"' "$OPTS")"
# video re-encode tuning: max height (0 = native) + libx264 preset
export EBO_VIDEO_MAX_HEIGHT="$(jq -r '.video_max_height // 720' "$OPTS")"
export EBO_VIDEO_PRESET="$(jq -r '.video_preset // "ultrafast"' "$OPTS")"
ROBOT_ID="$(jq -r '.robot_id // 0' "$OPTS")"
[ "$ROBOT_ID" != "0" ] && export EBO_ROBOT_ID="$ROBOT_ID"

if [ -z "$EBO_EMAIL" ] || [ -z "$EBO_PASSWORD" ]; then
  echo "[add-on] ERROR: set email and password in the add-on configuration."
  exit 1
fi

# --- MQTT from the Supervisor ---
if [ -n "$SUPERVISOR_TOKEN" ]; then
  MQTT_JSON="$(curl -sf -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" http://supervisor/services/mqtt || true)"
  if [ -n "$MQTT_JSON" ]; then
    export EBO_MQTT_HOST="$(echo "$MQTT_JSON" | jq -r '.data.host')"
    export EBO_MQTT_PORT="$(echo "$MQTT_JSON" | jq -r '.data.port')"
    export EBO_MQTT_USER="$(echo "$MQTT_JSON" | jq -r '.data.username // empty')"
    export EBO_MQTT_PASS="$(echo "$MQTT_JSON" | jq -r '.data.password // empty')"
    echo "[add-on] MQTT from Supervisor: ${EBO_MQTT_HOST}:${EBO_MQTT_PORT}"
  fi
fi
: "${EBO_MQTT_HOST:=core-mosquitto}"
: "${EBO_MQTT_PORT:=1883}"
export EBO_MQTT_HOST EBO_MQTT_PORT

# Home Assistant host IP for the RTSP camera URL: use the manual option if set, else ask
# the Supervisor for the primary interface address.
EBO_HOST_IP="$(jq -r '.host_ip // empty' "$OPTS")"
if [ -z "$EBO_HOST_IP" ] && [ -n "$SUPERVISOR_TOKEN" ]; then
  NET_JSON="$(curl -sf -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" http://supervisor/network/info 2>/dev/null || true)"
  EBO_HOST_IP="$(echo "$NET_JSON" | jq -r 'first((.data.interfaces[]? | select(.primary==true) | .ipv4.address[0]) // empty) // (.data.interfaces[]? | select(.enabled==true) | .ipv4.address[0])' 2>/dev/null | sed 's#/.*##' | head -1)"
fi
export EBO_HOST_IP
if [ -n "$EBO_HOST_IP" ]; then
  echo "[add-on] host IP for camera URL: ${EBO_HOST_IP}"
else
  echo "[add-on] could not detect host IP — set 'host_ip' in the add-on config for the camera URL"
fi

# Log the version actually running (baked into the image) vs what the Supervisor thinks is
# installed. If they differ, the image wasn't rebuilt on update (stale) — that's the real bug.
CODE_VER="$(cat /app/VERSION.txt 2>/dev/null || echo '?')"
INST_VER="?"
if [ -n "$SUPERVISOR_TOKEN" ]; then
  INST_VER="$(curl -sf -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" http://supervisor/addons/self/info 2>/dev/null | jq -r '.data.version // "?"')"
fi
if [ "$CODE_VER" = "$INST_VER" ]; then
  echo "[add-on] version ${CODE_VER} (running code matches installed)"
else
  echo "[add-on] ⚠ version MISMATCH: running code=${CODE_VER}, Supervisor installed=${INST_VER} — the image was NOT rebuilt (stale). Try: uninstall + reinstall the add-on."
fi

echo "[add-on] starting Enabot integration bridge (region ${EBO_REGION})"

# --- which robot(s) to run: a specific robot_id, or discover every robot on the account ---
RIDS=(); RNAMES=()
if [ -n "$EBO_ROBOT_ID" ]; then
  RIDS=("$EBO_ROBOT_ID"); RNAMES=("EBO Air 2")
else
  DISC="$(EBO_DISCOVER=1 python /app/ebo_bridge.py 2>/dev/null)"
  while IFS=$'\t' read -r tag id name; do
    [ "$tag" = "ROBOT" ] && [ -n "$id" ] && { RIDS+=("$id"); RNAMES+=("$name"); }
  done <<< "$DISC"
fi
NR=${#RIDS[@]}
if [ "$NR" -eq 0 ]; then
  # discovery failed (network/creds): fall back to a single default bridge (picks 1st robot)
  RIDS=(""); RNAMES=("EBO Air 2"); NR=1
fi
[ "$NR" -gt 1 ] && echo "[add-on] ${NR} robots on the account — running one bridge each"

stopping=0
term() {
  stopping=1
  echo "[add-on] stopping…"
  pkill -TERM -f '/app/ebo_bridge.py' 2>/dev/null || true
  for _ in $(seq 1 16); do
    pgrep -f '/app/ebo_bridge.py' >/dev/null 2>&1 || break
    sleep 0.5
  done
  exit 0
}
trap term SIGTERM SIGINT

# Supervise ONE robot: restart on exit; after repeated quick crashes with A/V on, fall back
# to control-only for that robot (control and video share one Agora connection).
run_robot() {
  local id="$1" idx="$2" name="$3" crashes=0 v="$EBO_VIDEO" a="$EBO_AUDIO"
  while [ "$stopping" -eq 0 ]; do
    local start; start=$(date +%s)
    (
      export EBO_VIDEO="$v" EBO_AUDIO="$a"
      [ -n "$id" ] && export EBO_ROBOT_ID="$id"
      if [ "$NR" -gt 1 ]; then          # per-robot identity only when there's more than one
        export EBO_NODE="ebo_air2_${id}" EBO_RTSP_PATH="ebo_${id}" \
               EBO_RTSP_PORT="$((8554 + idx))" EBO_DEVICE_NAME="$name"
      fi
      exec python /app/ebo_bridge.py
    ) &
    wait $!; local rc=$?
    [ "$stopping" -eq 1 ] && break
    local ran=$(( $(date +%s) - start ))
    if [ "$ran" -lt 60 ] && { [ "$rc" -ge 128 ] || [ "$rc" -ne 0 ]; }; then
      crashes=$(( crashes + 1 ))
    else
      crashes=0
    fi
    if [ "$crashes" -ge 2 ] && { [ "$v" != "0" ] || [ "$a" = "1" ]; }; then
      echo "[add-on] robot ${id:-single} crashed ${crashes}× with A/V — control only."
      v=0; a=0; crashes=0
    fi
    echo "[add-on] bridge (${id:-single}) exited (rc=${rc}), restarting in 15s…"
    sleep 15 & wait $!
  done
}

for i in "${!RIDS[@]}"; do
  run_robot "${RIDS[$i]}" "$i" "${RNAMES[$i]}" &
done
wait
