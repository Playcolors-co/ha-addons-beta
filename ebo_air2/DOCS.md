# Enabot integration — documentation

> ℹ️ **Tested devices.** So far this add-on has been tested **only on the Enabot EBO Air 2**.
> It may work with other EBO models that talk to the same Enabot cloud (EBO SE 2, Max, EBO X…),
> but that is **unverified** — if you try it on another model, feedback and issues are very
> welcome.
>
> ⚠️ **Independent, unofficial project.** Not affiliated with Enabot or ThroughTek/Agora. It
> interoperates with the Enabot cloud through reverse engineering, using **your own**
> credentials and device. Use at your own risk; it may break if Enabot changes their API.

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

## More entities (v0.4)

Besides battery/wifi/charging/recording/laser/speed and the move buttons, the add-on now
exposes: **sleep** (switch), **say** (text — the robot speaks what you type), **volume**
(number), and **return to base** (button — starts driving to the dock; only works when the
robot is *not* already charging).

### Patrol

- **patrol route** (select) — lists the patrol routes saved in the EBO HOME app, plus
  `auto (no route)`. The list is fetched from the robot at start-up.
- **start patrol** (button) — starts patrolling: with `auto (no route)` the robot does a
  free patrol (no route needed); with a named route it follows that saved route.

There is **no dedicated "stop patrol"** command in the robot's protocol — to interrupt a
patrol, just send any movement (e.g. the *stop* button). Routes are **created in the EBO
HOME app** (the add-on can only list and start them).

> **AI tracking** stays raw-only: it is interactive (you pick the subject, `{mode,
> trackTarget}`). Trigger it via the raw command channel below — see [COMANDI.md](COMANDI.md).

## Full command catalog + raw channel (AI)

The robot understands many more commands than there are entities. The topic **`ebo_air2/cmd`**
accepts a raw command for an automation or an AI agent:

```yaml
service: mqtt.publish
data:
  topic: ebo_air2/cmd
  payload: '{"id": 103501, "data": {"userId": "<yourUserId>", "text": "hello"}}'
```

The complete opcode catalog (movement, motion presets, voice, TTS, camera, eyes emoji,
scheduling, system…) is in [COMANDI.md](COMANDI.md). Commands marked *(moves)* drive the
robot — use them only when you can see it.

## Video (camera) — still limited

> **Status (v0.5.3):** the missing **port 8554** bind is fixed, so the RTSP URL is now
> reachable. However, the attempt to force *encoded-only* reception (`auto_subscribe_video=0`)
> **crashed the native Agora SDK** (segfault, taking the whole bridge down), so it was
> reverted to the stable config. The robot streams **H.265** and this Python server SDK has
> no H.265 decoder, so frames are typically not delivered — the log will show `⚠ still 0
> frames after 20s`. Control and telemetry are unaffected. A working camera needs a different
> decode path; video stays **off by default** (`video: false`).

With `video: true` the add-on subscribes to the robot's Agora video stream and republishes
it as **RTSP** on port **8554**. To see it in Home Assistant:

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
- **Video** requires the robot to publish its stream; if the log shows 0 frames, the
  robot may only stream on demand (open an issue).
- One control client at a time: while the add-on is active, the EBO HOME app on the same
  account may be disconnected from control.
- Depends on Enabot's cloud API: a change on their side may require an update.

## Troubleshooting

- **"login failed"**: check email/password and the correct `region`/`host`.
- **No entities in HA**: make sure MQTT (Mosquitto + integration) is running.
- **Robot does not respond to commands**: make sure no other session (the app) is
  controlling the robot at the same time.

## Support

This is a free, independent project. If it's useful to you, you can support the work:

[![Buy me a coffee](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=%E2%98%95&slug=scattolacom&button_colour=FFDD00&font_colour=000000&font_family=Lato&outline_colour=000000&coffee_colour=ffffff)](https://www.buymeacoffee.com/scattolacom)

☕ **[buymeacoffee.com/scattolacom](https://www.buymeacoffee.com/scattolacom)**
