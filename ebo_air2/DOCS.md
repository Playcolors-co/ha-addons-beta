# EBO Air 2 — documentation

## Configuration

| option | description |
|--------|-------------|
| `email` | your Enabot account email |
| `password` | Enabot password (stored only here, in HA) |
| `region` | account region (e.g. `GB`, `US`, `EU`) |
| `host` | regional cloud endpoint. Default is EU; US ≈ `ebox-us.enabotserverintl.com` |
| `robot_id` | `0` = auto-discovery. Set an id only if you have more than one robot |
| `video` | `true` = expose the camera over RTSP (default). `false` to disable |

Your credentials stay in the add-on configuration (in HA) and are sent only to Enabot's
servers, exactly like the official app does.

## MQTT

The add-on requests the Supervisor `mqtt` service: it automatically picks up host, port and
credentials of the Home Assistant broker. Make sure the *Mosquitto broker* add-on and the
MQTT integration are enabled.

## Driving from automations / AI

Besides the buttons, you can publish an analog vector:

```yaml
service: mqtt.publish
data:
  topic: ebo_air2/move/vector
  payload: '{"ly":-50,"rx":20,"hold":1.5}'
```

- `ly` < 0 = forward, > 0 = back
- `rx` = rotation (< 0 left, > 0 right)
- `hold` = duration in seconds; when it expires the robot stops (watchdog)

Value scale is ~±100. The vector must be "held": the add-on retransmits it at 10 Hz until
`hold` expires or a new command arrives.

## Video (camera)

With `video: true` (default) the add-on subscribes to the robot's Agora video stream and
republishes it as **RTSP** on port **8554**. To see it in Home Assistant:

1. **Settings → Devices & Services → + Add Integration → Generic Camera**
2. Stream URL:
   ```
   rtsp://<HOME_ASSISTANT_IP>:8554/ebo
   ```
   (use the IP of the machine running HA; the add-on exposes port 8554 on the host)
3. Leave the rest at defaults → Submit.

The stream is passed through without transcoding (`-c copy`), so CPU usage is low. Check the
add-on log for `[video] N frames received` to confirm the robot is publishing video.

## Known limitations

- **amd64 only** (Agora SDK is x86_64).
- **Video not included** (control + telemetry only).
- One control client at a time: while the add-on is active, the EBO HOME app on the same
  account may be disconnected from control.
- Depends on Enabot's cloud API: a change on their side may require an update.

## Troubleshooting

- **"login failed"**: check email/password and the correct `region`/`host`.
- **No entities in HA**: make sure MQTT (Mosquitto + integration) is running.
- **Robot does not respond to commands**: make sure no other session (the app) is
  controlling the robot at the same time.
