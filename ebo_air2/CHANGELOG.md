# Changelog — Enabot integration

## 0.16.9 — audio: the robot streams 8 kHz, we were asking for 16 kHz (likely THE fix)
- Instrumented the **real app's audio-receive** path with Frida and pressed "listen" ONLY (no
  talk): `onFirstRemoteAudioDecoded — AUDIO IS FLOWING`, `onRemoteAudioStats: bitrate=90,
  **sr=8000, ch=1**`. So the robot streams its mic on a bare subscribe (no two-way call needed),
  8 kHz mono G.711 — and it decodes fine.
- Our bridge asked the SDK for **16 kHz** PCM (`AudioSubscriptionOptions` + before-mixing params
  + ffmpeg), a mismatch with the 8 kHz source that stopped the PCM observer from ever firing.
  Now everything uses **8 kHz mono** (`AUDIO_RATE`, env `EBO_AUDIO_RATE`). This is the concrete,
  evidence-based cause of "subscribed (state 3) but no PCM".
- Net of 0.16.7–0.16.9: subscribe explicitly (like the app's listen icon) + correct 8 kHz rate.

## 0.16.8 — audio: subscribe harder + subscribe-state diagnostics
- 0.16.7's `subscribe_audio` returned rc=0 but the track still didn't appear. Now: on join we
  call **both** `subscribe_audio(uid)` and `subscribe_all_audio()`, **and retry once after 2.5 s**
  (the robot may publish its audio track a moment after joining).
- New diagnostics: `on_audio_subscribe_state_changed` (state 3 = subscribed, 1 = **robot has no
  audio publisher**) and `on_user_audio_track_state_changed` — these say definitively whether the
  robot is publishing audio at all, or we're failing to subscribe.
- Also set the codec on the **connection** handle after connect (in addition to the global
  pre-join set), matching the app which sets `custom_payload_type` post-join.
- **Set `audio_codec: 8`** (not 9): the app uses payload type **8** (G.711 A-law) for this
  monitor stream — confirmed by Frida. 9 is the wrong codec for listening.

## 0.16.7 — audio: subscribe to the robot's track explicitly (VERIFIED against the app)
- Instrumented the real app on the emulator with Frida and captured exactly what the audio
  buttons do:
  - **"Listen" (speaker)** → `muteRemoteAudioStream(robotUid, false)` — it just **subscribes to
    the robot's audio track**. No RTM command; it does NOT publish the phone's mic. So the robot
    publishes audio all along — the app simply doesn't subscribe until you tap listen.
  - **"Talk" (mic)** → `enableLocalAudio(true)` + `updateChannelMediaOptions(publishMicrophoneTrack
    =true)` — publishes the phone's mic (the other, outbound direction; not needed to listen).
- Our `auto_subscribe_audio=1` wasn't engaging (no track ever appeared). Fix: on robot-join we
  now call `local_user.subscribe_audio(robotUid)` explicitly — the exact server-SDK equivalent of
  the app's listen button. Combined with the codec params from 0.16.5 (payload 8 = G.711 A-law),
  the PCM observer should finally receive audio.
- Kept `[audio-diag]` so we can confirm the track now subscribes and `received_bytes` climbs.

## 0.16.6 — audio: find the mic-enable trigger by sniffing the app's RTM
- The 0.16.4 diagnostic proved it live: the robot publishes **video** on join but **no audio
  track at all** (zero `[audio-diag]` subscribe/stats events, both codecs). So audio isn't a
  codec problem — the robot simply isn't sending its mic during passive monitoring. It needs a
  trigger, which the app sends when you tap its audio/listen icon.
- The app and the bridge publish to the **same robot RTM channel** the bridge is subscribed to,
  so added an `[rtm-raw]` debug log of every non-telemetry RTM message. With `log_level: debug`,
  open the official app on live view and tap the audio icon — the exact opcode it sends shows up
  in our log, and we replicate it to enable the mic. (Confirmed the codec is **G.711 A-law**,
  `.g711a`, in the app — payload type 8, as expected.)

## 0.16.5 — audio: set the codec on the ENGINE, before join (the real fix candidate)
- **Root-cause correction:** the codec params (`che.audio.codec_unfallback` +
  `custom_payload_type`) were applied on the *per-connection* handle *after* `connect()`.
  Agora's guidance for this exact case (payload 8 = G.711) is that they must be set on the
  **global engine parameter handle before joining** — after-join never takes effect, which is
  why the PCM observer got 0 frames. Now set on `service.get_agora_parameter()` right after
  `svc.initialize()`, before the RTC connection is even created. **This is the single change
  most likely to finally make the mic produce PCM.**
- Removed the runtime 8↔9 flip — impossible now that the codec is fixed before join. To test
  the other codec, set `audio_codec: 9` and restart (the watchdog says so, and pairs with the
  `[audio-diag] received_bytes` line to tell "no stream" from "can't decode").
- Kept the `[audio-diag]` observer from 0.16.4. Tests (68) + ruff clean.
- **Honest caveat:** not verified against the robot — a well-grounded hypothesis (SDK source +
  Agora codec-8 guidance). If it still logs no PCM *and* `received_bytes>0`, this SDK genuinely
  can't decode the stream and the path forward is a different SDK/transport, not more tweaks.

## 0.16.4 — audio: decisive diagnostic (does the robot even send audio bytes?)
- Confirmed via the actual SDK source: `agora-python-server-sdk` 2.4.9 (the latest) has **no
  working encoded-audio / media-packet receive path** (`register_audio_encoded_frame_observer`
  is a `#todo` stub), so we can't grab undecoded audio to decode ourselves. The only audio path
  is the PCM observer, which needs the SDK to decode — and it won't decode the robot's codec.
- So the whole question is: **does the robot actually publish mic audio in monitor mode?**
  Added a local-user observer that logs `[audio-diag] stats: bitrate=… bytes=…` plus
  `first remote audio FRAME/DECODED`. On the next run the log tells us definitively:
  - `bytes` grows > 0 but never `DECODED` → bytes arrive, SDK can't decode the custom codec.
  - `bytes` stays 0 → the robot isn't sending mic audio here; it needs a trigger command.
- No behaviour change otherwise — pure diagnostics.

## 0.16.3 — fix image-style / auto-record-calls read-back (the two ❌ in your test)
- The live `[settings]` dump proved the robot **never reports `imageStyle` or
  `callAutoRecording`** — that's why those two entities stayed null/false even though the
  command worked. Now the bridge **reflects the value you set optimistically** (write-only
  settings), so the entity updates immediately → both tests go ✅.
- Settings reports are now **merged** into state instead of replacing it, so those optimistic
  values survive the robot's periodic reports (which omit them).

## 0.16.2 — audio: auto-try both codecs + kill the false "stale image" alarm
- **Auto-fallback 8→9:** if payload type 8 yields no PCM within 6 s, the bridge now flips to
  9 at runtime and tries again — **one restart tests both codecs** and logs a definitive
  verdict (`decoding OK with payload_type=N`, or `NO PCM with 8 or 9` → needs self-decode).
- **Fix false "version MISMATCH / stale image" warning:** `VERSION.txt` is now **derived from
  `config.yaml` at build**, so it can't drift behind the released version (that mismatch was
  cosmetic — the new code *was* running, the banner just read a stale baked version string).
- Verified live: 0.16.1's fix (codec params after `connect()`) runs correctly, but payload
  type 8 alone does **not** decode this robot's mic — hence the auto-fallback.

## 0.16.1 — audio: correct codec timing + flip switch + watchdog
- **Fix ordering:** the app sets the codec params *after joining the channel*, per-connection —
  we were setting them *before* `connect()`, which likely never took effect. Now set right
  after connect, matching the app exactly.
- **New option `audio_codec` (8 or 9)** in the add-on UI: 8 = monitor (default), 9 = two-way
  call. The app uses payload type 8 for the watch flow and 9 for calls — if 8 stays silent,
  switch to 9 from the UI (no rebuild) and restart.
- **Watchdog:** if no PCM arrives within 8 s of enabling audio, the log now says so explicitly
  and tells you which value to try next — so we can tell "wrong codec" from "silent playback".

## 0.16.0 — audio: decode the robot's mic codec
- The robot streams its microphone with a **custom telephony codec** (Agora audio payload
  type 8/9), not the default. The bridge now tells the Agora engine to decode it
  (`che.audio.codec_unfallback:[0,8,9]` + `custom_payload_type`) exactly like the app does —
  without this the PCM observer received **0 frames** (why audio never worked).
- Enable with `audio: true` (+ `video: true`). Watch the log for `[audio] first PCM frame`.
- If you still hear nothing, tell me: I'll switch the payload type 8↔9 (the app uses both).

## 0.15.2 — diagnose image-style / call-recording read-back
- Added a **debug log of the raw settings report** (`log_level: debug` → line `[settings] {...}`)
  to see exactly which fields the robot echoes. `image style` and `auto-record calls` set the
  correct command (verified) but didn't reflect in state — this pins down whether it's a
  read-back gap or a condition (e.g. image style may need the camera stream active).
- No entity/behaviour change.

## 0.15.1 — hardening + multi-robot fix
- Fix: the RTSP config file used a fixed `/tmp/mediamtx.yml` path that **collided** when the
  add-on runs one bridge per robot (multi-robot). Now per-instance (keyed by RTSP port).
- Security/quality: added an automated **security + lint pipeline** (ruff, bandit SAST,
  pip-audit dependency CVE scan) — all clean; nonce generation moved to a CSPRNG.
- No functional/entity changes vs 0.15.0.

## 0.15.0 — full control catalog + rich telemetry
Mapped the **entire command set** from the app (112 commands, see `docs/COMANDI-APK.md`) and
exposed the useful ones as first-class Home Assistant entities.

- **New controls**: rotate by angle, video quality (Low/Medium/High), image style, shoot mode,
  move mode, eyes/emoji mode, autonomous roaming, AI subject tracking, play a preset
  motion/voice by id, and **ask the built-in AI** a question (Air 2 has an LLM agent).
- **New sensors** (from the robot's status report): SD card present + free/total, internal
  storage free, docked, guard/safe mode, current **activity** (moving / charging / AI-tracking /
  on a call / upgrading…), plus diagnostics: camera & MCU **firmware versions**, robot **IP**
  and **WiFi SSID**.
- The camera-setting selects (quality/style/mode) show and set the robot's real current value.
- Everything still routes over Agora RTM, the same channel as before. The raw `ebo_air2/cmd`
  escape hatch remains for any opcode not given its own entity.
- A few controls with complex payloads (eyes, AI track, ask-AI, roaming) are best-effort from
  the decompiled builder; if one misbehaves, the raw `cmd` channel gives exact control.

## 0.14.0 — multi-robot (experimental)
- If your Enabot account has **more than one robot**, the add-on now runs **one bridge per
  robot** automatically: each gets its own device/entities and its own camera on its own RTSP
  port (8554, 8555, …). Set `robot_id: 0` to run all; a specific id runs just that one.
- **Single-robot behaviour is unchanged** (same entities, same `rtsp://…:8554/ebo`).
- Note: the multi-robot path is validated only in design (we can't test 2+ robots here) — if
  you have several EBO and try it, feedback is very welcome.

## 0.13.5 — finer driving + joystick channel
- **Gentler move buttons** (A): each tap is a shorter, smaller nudge — turns no longer spin
  ~90° per press, forward/back are softer.
- **Joystick channel** (B): new MQTT topic `ebo_air2/joystick` accepting `{"x":-1..1,"y":-1..1}`
  for smooth, continuous driving from a joystick card (x = turn, y = forward). Pair it with the
  EBO joystick Lovelace card. (Cloud latency still applies.)

## 0.13.4 — much lower video latency
- The stream lagged because ffmpeg was forced to 15 fps (`-r`/`-vsync cfr`) while the robot
  sends ~25 fps → it buffered and dropped frames. Now it passes the real frame rate through
  with arrival timestamps + low-delay flags: **latency should drop a lot** (clean DTS kept).
- For the lowest latency/CPU use `video_preset: ultrafast` and a lower `video_max_height`.

## 0.13.3 — audio no longer breaks video
- With `audio: true`, ffmpeg had a second (audio) input; if the robot's PCM didn't arrive it
  **stalled the whole mux and froze the video**. Fixed: (1) the audio observer is now kept
  referenced (it was garbage-collected, so it never fired), and (2) the pipeline feeds
  **silence** when no real audio arrives, so ffmpeg never blocks — **video always flows**,
  with audio overlaid when the robot sends it.

## 0.13.2 — quieter log + log level
- New **`log_level`** option: `info` (default) shows key events only — no more `N frames
  received` spam; `debug` for the chatty lines; `warning` for problems only. Video keeps a
  light "still streaming" heartbeat every few minutes at info level.

## 0.13.1 — audio fix + diagnostics
- Audio didn't work because a required SDK call was missing:
  `set_playback_audio_frame_before_mixing_parameters(1, 16000)` — without it the PCM callback
  never fires. Added it (+ `audio_recv_media_packet=0`). The log now shows
  `[audio] first PCM frame from …` when audio is flowing.
- Silenced transient template warnings on the new entities (defaults).

## 0.13.0 — audio (listen), experimental
- Optional **audio**: the robot's microphone (16 kHz mono PCM from the SDK) is muxed into the
  camera stream as AAC, so the Generic Camera has **sound**. Enable with `audio: true` (needs
  `video: true`). Off by default; if it ever misbehaves the safety net falls back to
  control-only. Two-way *talk* is a separate future step.

## 0.12.1 — camera stream: fix timestamps ("No dts")
- The re-encoded stream could produce timestamps HA's stream backend rejected ("No dts in N
  consecutive packets"). ffmpeg now timestamps incoming frames by arrival
  (`use_wallclock_as_timestamps`) and forces a constant output rate (`-r`, CFR), giving clean
  monotonic DTS/PTS. (The `Connection refused`/`404` errors were just the add-on being down
  during the update — transient.)

## 0.12.0 — "connected" switch + CI
- **EBO connected** switch (default on): turn it **off** to fully leave the cloud session so
  the robot can **sleep** (no control/telemetry while off); turn it back on to reconnect. MQTT
  entities stay available throughout.
- **CI:** a GitHub Actions workflow builds the add-on image on every push/PR, so build breaks
  are caught before release.

## 0.11.0 — more entities
- New controls (verified against the app): **motion recording** (switch), **auto-record calls**
  (switch), **cloud upload** (switch, privacy), **talkback volume** (number). The recording/
  volume ones show real state from the robot's settings report.
- Eyes/emoji, DND and other complex settings stay on the raw `ebo_air2/cmd` channel (they need
  structured payloads) — see COMANDI.md.

## 0.10.0 — video CPU: resolution/quality options
- The robot streams ~2304×1296 (2K); re-encoding that is CPU-heavy on a NUC. New options:
  `video_max_height` (default **720** — big CPU saving; set `0` for native 2K) and
  `video_preset` (libx264 speed/quality). The log shows the chosen resolution/preset.

## 0.9.2 — video works: fix client attach (keyframes)
- 🎉 Live video works (H.265 decoded by the SDK → re-encoded to H.264 → RTSP). Fixed the
  "Timeout while loading URL" when adding the camera: ffmpeg now emits a **keyframe every ~2s**
  (`-g`, `-keyint_min`, no B-frames) so Home Assistant / VLC can attach immediately instead of
  waiting up to ~16s for the default GOP.

## 0.9.1 — the missing video switch: enable_video=1
- The decoded observer got 0 frames because the Agora **service** config was missing
  `enable_video = 1` (found in the official `example_video_yuv_receive.py`). Without it the SDK
  doesn't process video at all. Added it. If this was the blocker, you'll now see
  `[video] first decoded frame WxH` with `video: true` + the **EBO camera** switch on.

## 0.9.0 — video via the SDK's H.265 DECODER (new approach)
- Root cause found in the official SDK docs: the *encoded* frame observer segfaults for H.265,
  but the SDK **decodes H.265 to raw YUV**. Until now the add-on only registered the encoded
  observer (hence 0 frames / crashes).
- Now it registers the **decoded** video-frame observer (`register_video_frame_observer`,
  `auto_subscribe_video=1`), reads the YUV frames and **re-encodes to H.264 with ffmpeg** →
  RTSP. If the robot publishes and the SDK decodes, the log shows `first decoded frame WxH`
  and `N frames received`.
- Enable with `video: true` + the **EBO camera** switch. Watch the log for the frame lines.

## 0.8.3 — fix camera race (double mediamtx / observer error)
- `connect_agora` and `on_user_joined` could both subscribe at once, starting mediamtx twice
  and double-registering the encoded observer (`unregister_video_encoded_frame_observer`
  error). Now serialized with a lock and made idempotent. Camera URL detection confirmed
  working (`rtsp://<HA-IP>:8554/ebo`).

## 0.8.2 — log the running version (spot stale updates)
- The log now prints the **version actually running** (baked into the image) and compares it
  to what the Supervisor thinks is installed. If they differ, it says the image wasn't rebuilt
  (stale) — so you always know exactly which version you're testing. `VERSION.txt` in the image
  guarantees the code layer is never stale-cached.
- If you ever see the mismatch warning: **uninstall + reinstall** the add-on for a clean build.

## 0.8.1 — fix the camera URL (real IP)
- The camera URL showed the `<HOME-ASSISTANT-IP>` placeholder because the add-on couldn't
  read the host IP. Added `hassio_api` permission to auto-detect it, plus a manual **`host_ip`**
  option as a fallback. The **EBO camera URL** sensor now shows e.g. `rtsp://192.168.88.15:8554/ebo`.
- Reminder: the camera on/off control is the **EBO camera** switch on the *EBO Air 2 device*
  (not on the add-on page).

## 0.8.0 — camera on/off switch + RTSP URL shown
- **EBO camera switch** (default OFF): the add-on no longer subscribes to the robot's video by
  default, so the robot is **not kept in video mode** all the time (saves battery / privacy).
  Control stays on (RTC presence). Flip the switch on only when you want the stream.
- **EBO camera URL** sensor + a log line show the exact RTSP link (with your HA IP) once the
  camera is on, e.g. `rtsp://192.168.88.15:8554/ebo`.
- Video subscribe is now **runtime** (subscribe/unsubscribe on the switch) instead of always-on.

## 0.7.0 — safety net for video experiments
- **Supervisor safety net:** control and video share one Agora/RTC connection (the robot only
  accepts commands while you're present in RTC), so a native video crash takes the bridge
  down. The add-on now **auto-falls back to control-only** after repeated quick crashes — no
  more crash loops; control/telemetry always come back.
- New **`video_encoded`** option (experimental) to try the encoded-H.265 path on demand.
- Agora SDK version **pinned** (build arg `AGORA_SDK_VERSION`) so control is reproducible and
  we can test other versions for the video path.

## 0.6.1 — back to stable (encoded video confirmed crashing)
- Attempt #1 result: the encoded-only subscribe (`auto_subscribe_video=0`) **segfaults this
  Agora SDK build regardless of the subscribe method** (both `subscribe_all_video` and
  `subscribe_video` crash). Reverted to the **stable** config (`auto=1`, no crash, 0 frames
  for H.265). The experimental encoded path is now behind an env flag (`EBO_VIDEO_ENCODED=1`)
  so it can't crash the default setup. `video: true` is safe again (RTSP up, empty).

## 0.6.0 — experimental video attempt #1
- **Video (experimental):** try to receive the robot's **encoded H.265** by subscribing to
  its stream **per-uid** (`subscribe_video`) in encoded-only mode, instead of the
  `subscribe_all_video` call that segfaulted. If the SDK hands over frames, ffmpeg passes the
  raw H.265 to HA (no decoder needed on our side). Enable with `video: true` and watch the log
  for `[video] N frames received`; if it segfaults or shows `0 frames`, set `video: false`
  (control/telemetry are unaffected either way).

## 0.5.4
- **More reliable updates:** an add-on update rebuilds the Docker image; the video-only
  extras (ffmpeg, mediamtx from GitHub) are now **non-fatal** and `pip` retries, so a flaky
  network/GitHub outage can't fail the whole rebuild and leave you stuck on the old version.

## 0.5.3
- **Fix crash on start:** `_on_mqtt_connect` could run before `self.mqtt` was set, throwing
  `AttributeError` and killing the MQTT thread (entities not published). Now assigned early
  and the callback is guarded.
- **Fix segfault:** the v0.5.1 encoded-only video subscribe (`auto_subscribe_video=0`)
  crashed the native Agora SDK and took the whole bridge down — reverted to the stable
  config. Port 8554 stays exposed. (Video via this SDK remains limited by H.265.)

## 0.5.2
- Add this changelog (shown by Home Assistant in the update dialog).

## 0.5.1
- **Video:** expose port **8554** so `rtsp://<HA-IP>:8554/ebo` is reachable (was a missing
  port bind), and subscribe in **encoded-only** mode so the raw H.265 bitstream is forwarded
  to `ffmpeg -c copy` instead of a decoded subscribe that yields 0 frames. Clearer video
  diagnostics in the log.

## 0.5.0
- **Patrol:** new `patrol route` (select, filled from the robot) and `start patrol` (button).
  `auto (no route)` patrols without a saved route; a named route follows it. Routes are
  created in the EBO HOME app.

## 0.4.x
- Full command catalog exposed as entities: **sleep**, **say** (TTS), **volume**, **return to
  base**, plus a raw `ebo_air2/cmd` channel to send any opcode (for automations / AI).
- **Clean shutdown** (no more "error" on stop; logs stay readable).
- Renamed add-on to **Enabot integration**; repository is now the multi-add-on
  **Playcolors.co** collection.
- Fixed **return to base** (correct opcode) and removed the invalid patrol/AI-tracking buttons
  (they need structured payloads — documented in COMANDI.md).

## 0.3.0
- Video off by default (Agora Python SDK can't receive the robot's H.265 at the time).

## 0.2.x
- Initial control + telemetry over the Enabot cloud (Agora RTM/RTC) with MQTT Discovery.
