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

echo "[add-on] starting EBO Air 2 bridge (region ${EBO_REGION})"
# retry: login/cloud can fail transiently; don't let the add-on die
while true; do
  python /app/ebo_bridge.py || echo "[add-on] bridge exited (rc=$?), restarting in 30s…"
  sleep 30
done
