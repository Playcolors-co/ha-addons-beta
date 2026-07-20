# Home Assistant add-on — Enabot EBO Air 2

Control your **Enabot EBO Air 2** from Home Assistant: battery, wifi, laser, speed,
movement (forward/back/left/right) and a "vector" channel meant for driving it from an
automation or an AI agent.

It works with **your own Enabot credentials** (the same as the EBO HOME app): the add-on
signs into the Enabot cloud, discovers your robot, and keeps the session alive by itself.
No phone, no emulator.

> ⚠️ **Independent, unofficial project.** Not affiliated with Enabot or ThroughTek/Agora.
> It interoperates with the Enabot cloud through reverse engineering, using your own
> credentials and device. Use at your own risk; it may break if Enabot changes their API.

## Requirements

- Home Assistant **OS** or **Supervised** (add-ons require the Supervisor)
- **amd64** architecture (the Agora SDK is x86_64 only — e.g. HAOS as a VM on Proxmox/NUC ✓)
- An **MQTT** broker in HA (the *Mosquitto broker* add-on) and the **MQTT** integration enabled

## Installation

1. **Settings → Add-ons → Add-on Store → ⋮ (top right) → Repositories**
2. Paste this repository URL:
   ```
   https://github.com/Playcolors-co/ha-ebo-air2
   ```
3. Find **EBO Air 2** in the store and install it.
4. In the add-on's **Configuration** tab set:
   - `email` / `password` — your Enabot credentials
   - `region` — your account region (e.g. `GB`, `US`, `EU`)
   - `host` — keep the default if you are in Europe; US/other regions may need to change it
     (e.g. `ebox-us.enabotserverintl.com`)
   - `robot_id` — leave `0`: it is discovered automatically (set a value only if you have
     more than one robot on the account)
5. **Start** the add-on. The entities appear in Home Assistant via MQTT Discovery, under the
   **EBO Air 2** device.

## Entities

| entity | type |
|--------|------|
| battery, wifi, SD space | sensor |
| charging, recording | binary_sensor |
| laser | switch |
| speed (1–100) | number |
| forward / back / left / right / stop | button |

Plus the MQTT topic `ebo_air2/move/vector` which accepts `{"ly":-50,"rx":0,"hold":1.0}`
for continuous analog control (useful for automations or AI).

## How it works / technical notes

The robot talks to the cloud over **Agora RTM** (commands/telemetry, JSON) + **RTC**
(presence). The add-on replicates the app flow: encrypted login → Agora session → control.
Movement is retransmitted at 10 Hz with a **watchdog** (if the add-on stops, the robot
stops). Details in [DOCS.md](ebo_air2/DOCS.md).

## License

Original code under **MIT** (see [LICENSE](LICENSE)). No proprietary Enabot/ThroughTek
component is included or redistributed.
