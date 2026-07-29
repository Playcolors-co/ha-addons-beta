# Analysis — Dock & Routes on the EBO Air 2 (definitive understanding + APK deep-dive plan)

> **Audience:** the implementing agent. This is an **analysis / research brief**, not code.
> Goal: pin down *definitively* what the Air 2 can and cannot do for **docking** and **route
> (teach-and-repeat)**, separate fact from inference, hand over an executable APK deep-dive plan to
> close the remaining gaps, and generalize it to a **per-model capability matrix** — which opcodes /
> functions *each* EBO robot exposes (§8-§9), not just the Air 2.
>
> **Legend of confidence:** ✅ CONFIRMED (empirical or from decompiled app) · 🟡 INFERRED (consistent
> with evidence, not proven) · ❓ UNKNOWN (needs the APK / a live probe to settle).

---

## 1. Executive summary — the current best answers

### Routes (teach-and-repeat)
- ✅ The **protocol exists and is fully mapped** from the app (`Air2LiveModel` + `RouteViewModel`):
  record = `103201` → ack `103202` → progress `103204` → stop `103205` → data `103206` → save
  `104003`; list `104001`→`104002`; delete `104005`; run = patrol `103061`. See `COMMANDS-APK.md`
  and `ebo_bridge.py:88-101`.
- ✅ The **EBO Air 2 firmware does NOT implement it.** Empirically confirmed (changelog 0.26.57): the
  Air 2 **never answers** the route query `104001`, never acks a record start, never returns a
  recorded path. The official app also **hides patrol** for the Air 2. The add-on now runtime-probes
  with `104001` and hides the Routes UI when there's no reply within 15 s (`ebo_bridge.py:184-188,
  1683-1686, 1814-1816`).
- **Net:** on the Air 2 there is **no native path recording**. Any "routes" feature for the Air 2
  must be built **add-on-side** (open-loop replay of drive vectors — see §4). Other models (e.g. SE)
  may support the native path; keep the capability probe.

### Dock
- ✅ `103043 {startUp:true}` triggers the robot's **own return-to-base**; it is a **firmware-internal
  closed-loop homing**, handled entirely on the robot. We only *fire* it (`ebo_bridge.py:1524-1526`).
- ✅ There is an **auto-recharge setting** opcode `103019` (battery-triggered auto-dock) — ⬜ not yet
  implemented. Its existence proves the robot self-returns to the dock autonomously, not only on
  manual command.
- 🟡 The homing is almost certainly **local, reactive homing to a single beacon** (IR on the dock,
  possibly camera-assisted): "sense the dock direction → steer toward it → align → mate contacts." It
  is **not** global localization/mapping — the robot knows how to reach *that one target*, not where
  it is in the room.
- ✅ The only feedback we get is a **binary completion signal**: `docked` is inferred from
  `adapterStatus != -1` (charger connected), plus `charging` (`ebo_bridge.py:1707-1708`, telemetry
  `101026`). **No trajectory, direction, distance, or heading is ever reported.**

### One-line conclusion
The robot **can self-home to the dock** (one target, firmware-internal, no exposed telemetry) but has
**no general localization**, and the Air 2 **lacks native route recording**. So a "dock" leg can be
delegated to the robot reliably; an "outbound path" cannot — it can only be dead-reckoned by the
add-on.

---

## 2. Why the firmware binary is *not* the primary lever

The robot exposes **two firmwares** (`ebo_bridge.py:1712-1713`):
- `ipcVersion` — the **camera SoC** (embedded Linux): Agora cloud, video, the opcode protocol.
- `masterMcuVersion` — the **MCU**: motors, self-balancing, and the **dock IR/sensing** live here.

Docking behavior is MCU-level. **But our control surface is fixed = the cloud opcodes.** Even with
both firmware images in hand we could not add MCU behaviors or bypass the protocol — the firmware
would give *understanding*, not a new API. Therefore:

> The highest-value, lowest-effort lever is the **APK / cloud protocol**, not a firmware dump. The
> APK already yielded 112 opcodes (20 used, 92 unmapped). Several unmapped ones are directly on-topic
> (§5). Get the firmware **only** if the APK + live probing leave a specific gap (§6).

---

## 3. Evidence ledger (dock & route)

| # | Claim | Confidence | Source |
|---|---|---|---|
| 1 | Route protocol opcodes & flow are known | ✅ | decompiled `Air2LiveModel`/`RouteViewModel`; `ebo_bridge.py:88-101` |
| 2 | Air 2 ignores route/patrol (no `104002`, no `103202/103206`) | ✅ | live probe, changelog 0.26.57 |
| 3 | Official app hides patrol on Air 2 | ✅ | app behavior |
| 4 | `103043 {startUp:true}` = return-to-base, robot-internal | ✅ | `COMMANDS-APK.md`; `ebo_bridge.py:88,1524-1526` |
| 5 | `docked` derived from `adapterStatus`; `charging` reported | ✅ | telemetry `101026`; `ebo_bridge.py:1707-1708` |
| 6 | Auto-recharge setting exists (`103019`) | ✅ (opcode) / ❓ (payload) | `COMMANDS-APK.md:62` |
| 7 | Autonomous roaming exists (`101061 isRoamOn, sensitivity`) | ✅ (opcode) / ❓ (behavior) | `COMMANDS-APK.md:28`; `ebo_bridge.py:108` |
| 8 | Dock homing = local IR/vision beacon, not mapping | 🟡 | inference from behavior + no positional telemetry |
| 9 | No position/heading/odometry telemetry of any kind | ✅ | full telemetry field audit (`ebo_bridge.py:1223-1429, 1700-1713`) |
| 10 | `103201` (route record start) payload | ❓ | unmapped |

---

## 4. If routes are done add-on-side (Air 2): the design constraint

Because the Air 2 gives **zero positional feedback**, an add-on "route" is **open-loop dead
reckoning**: record the timed sequence of `move/vector` commands (the bridge already sees them all,
`ebo_bridge.py:897-900, 1475-1477`) and replay them with the same cadence. Known limits: drift
accumulates (surface, battery level, wheel slip), turns amplify it, collision-avoidance can deviate,
and replay only makes sense from a **fixed start pose**.

**Key architectural insight (from the dock analysis):** don't replay a round trip. Record only the
**outbound** leg; for the **return**, issue the native `103043` dock command and let the robot's own
homing bring it back — with a **real completion signal** (`docked`/`charging`). This removes drift
from half the problem. Pattern: **start at dock → drive-recorded outbound → `dock` home.**

---

## 5. Unmapped opcodes worth resolving (directly on-topic)

From `COMMANDS-APK.md`, the ⬜ entries most relevant to dock/route/autonomy:

- `101061` **auto roaming** (`isRoamOn`, `sensitivity`) — a built-in autonomous wander; may partly
  substitute for "routes" without any replay engine. **Probe first.**
- `103019` **auto-recharge setting** — battery-triggered auto-dock; confirms/needs payload.
- `103003` **create routine** (`cycleMode, moveIds, voiceIds, emojiIds`) + `103005` **run move** — a
  native "routine" system of *canned* moves (not free paths, but scriptable behavior).
- `103201` — route-record start; unknown payload (the Air 2 ignores it anyway).
- `103047` **safe mode**, `103061`/`103063` patrol start/stop — patrol context.
- Unnamed neighbors likely in the movement/dock cluster: `103013/103015/103017/103021/103023/103025/
  103027/103055/103101/103103`.

---

## 6. APK deep-dive playbook (executable hand-off)

`COMMANDS-APK.md` was already produced from a decompile, so these **class names are known and
searchable**: `Air2LiveModel`, `RouteViewModel`, `RouteReportInfo`, `RouteDataInfo`,
`StartAiTrackData`, `EyesEmojiModeData`, `MotionSettings`. Tooling: **jadx** (Java decompile),
**apktool** (resources/strings), **mitmproxy** (cloud/OTA capture on your own phone). This is
interoperability RE of your own device.

**A. Settle the route-capability question definitively.**
- These apps typically fetch a **device capability list** per `productId`/model that enables/hides
  features. Find it — it is the *authoritative* yes/no for Air 2 routes. Search strings:
  `capability`, `ability`/`abilities`, `support`, `productConfig`, `feature`, `productId`. Grep the
  decompiled sources and the `assets/`/`res/raw/` JSON.
- In `RouteViewModel`/`Air2LiveModel`, find the exact guard that hides patrol for the Air 2 (model
  string, `productId`, or a `supportRoute`/`supportPatrol` boolean).
- Extract the exact payloads for `103201`/`103205`/`103206`/`104003` and the **`routeFile` format**
  (so a future SE implementation is turnkey).

**B. Nail down docking.**
- Find the `103043` builder and any **dock/charge/IR** strings and UI states. Look for failure
  strings ("cannot find base", "docking failed", "return failed") → tells us **how/if failure is
  reported** (today we only see `adapterStatus`).
- Extract `103019` (auto-recharge) payload and whether the app **polls a dock/charge status**.
- Determine sensing modality (IR vs vision) from any dock-detection strings/resources.

**C. Firmware / OTA (only if A+B leave a gap).**
- Find the **version-check opcode** and **OTA URL**: grep for `upgrade`, `update`, `ota`, `firmware`,
  `.bin`, `version`. Or MITM the app's "check for updates" to capture the image URL, then download
  the two images (IPC + MCU) directly. Purpose: understand dock homing / confirm route absence at the
  source.

**D. Resolve the on-topic unmapped opcodes** in §5 from the command builder (payload shapes), then
live-probe on the real robot (send + watch telemetry `101026` and physical behavior).

---

## 7. Recommendation to the implementing agent

1. **Do not** speculatively build a dead-reckoning replay engine yet.
2. First, **live-probe `101061` (roaming)** and **`103019` (auto-recharge)** on the real robot — 30
   minutes may reveal the robot already does most of what we want autonomously.
3. In parallel, run **playbook §6A** to get the *definitive* answer on Air 2 route support (capability
   list) — so we stop inferring from silence.
4. If route is confirmed dead on Air 2 **and** roaming is useful → expose **roaming + the
   "outbound-record → native dock" pattern** (§4) instead of a symmetric teach-and-repeat.
5. Keep the native route path (already coded) gated behind the capability probe for models that do
   support it.
6. **Build the per-model capability matrix (§8-§9).** Determining which opcodes/functions each robot
   exposes is a prerequisite for correct multi-model support — start from the app's `productId →
   capability` map (§8.2), fall back to safe runtime probing (§8.3), and land it as a data-driven
   table in the add-on (§8.5).

---

## 8. Per-model capability matrix — which opcodes/functions each robot exposes

The dock/route findings above are **Air 2-specific**. The same opcode can be implemented on one model
and ignored on another (route is dead on the Air 2 but may be alive on the EBO X). So the analysis
must generalize to: **for each model, which of the 112 opcodes / features does the firmware actually
expose?** This section is the method to build that matrix definitively.

### 8.1 How a robot identifies itself (the matrix key)
- `101004` (`OP_INFO`) returns the device record: **`model`**, `sn`, `mac`, `ipcVersion`,
  `masterMcuVersion`, `ip`, `wifiSsid` (`ebo_bridge.py:71,987-988,1712-1715`). `model` is the
  human key we have today (defaulted to "EBO Air 2").
- The **cloud robot list** `GET /api/v1/ebox/robots/robot` returns per-robot metadata incl.
  `agora_info` and almost certainly a **`productId`/product-type** field (`ebo_cloud.py:9,113-114`).
  ❓ Confirm the exact field name and values — **`productId` is the real key the app gates on**, more
  reliable than the display `model` string.
- **Action:** capture the raw robot-list JSON (one call, any account) and the `101004` payload for
  each model you can access; record the `productId` ↔ `model` mapping.

### 8.2 Authoritative source: the app's per-model capability map
Apps like EBO HOME almost never probe each unit — they ship or fetch a **feature/capability map keyed
by `productId`** that decides which UI (and thus which opcodes) each model gets. That map is the
**definitive answer** to "which functions each robot exposes," without touching hardware.
- Find it via the APK: search the decompiled sources **and** `assets/` / `res/raw/` for
  `capability`, `abilities`, `support`, `productConfig`, `productId`, `feature`, `deviceConfig`,
  `funcList`. It may be a static JSON asset or a response cached at login.
- Also check the **cloud login / robot-list response** for an embedded capabilities/feature block
  (MITM the app once, or inspect `ebo_cloud.py` login response fields).
- Output: a table `productId → {featureFlags}` (e.g. `supportRoute`, `supportPatrol`,
  `supportAutoRecharge`, `supportRoam`, `supportAiTrack`, `supportEyes`, …). This directly yields the
  opcode-per-model matrix, because each feature flag maps to a known opcode group.

### 8.3 Runtime-probe fallback (when the map is unavailable for a model)
Generalize the existing route probe (`104001`→`104002` within 15 s; `ebo_bridge.py:184-188,999-1006,
1683-1686`) into a **capability-discovery pass**. **Critical safety rule:**
- **Safe to probe** = read-only *query* opcodes that ack with a reply and don't move the robot:
  get-info `101004`, get-settings `101027`, get-routes `104001`, get-motion `101021`, list/query
  ops. A reply → feature present; silence past a timeout → absent/unsupported.
- **NOT safe to blind-probe** = *action* opcodes (any tagged "MOVES", dock `103043`, patrol `103061`,
  roam `101061`, rotate `103001`): they physically move the robot or change state. Never enumerate
  these automatically — gate them on 8.2 flags, or trigger only on explicit user action and observe
  the result.

### 8.4 Model differences to expect (hypotheses to verify)
- **EBO Air 2** ✅ verified baseline: move, dock, telemetry, sleep, eyes, settings; **route/patrol
  absent**.
- **Air 2 Plus / Air 2S / Mini** 🟡 same cloud + opcode base as Air 2; core features work, some
  model-specific commands differ (`DOCS.md`). Likely also no route.
- **EBO X / EBO Max** ❓ premium models with more autonomy — **route/patrol and richer navigation may
  actually be present here.** Highest-value models to get a capability map / live probe for.
- **EBO SE** ⛔ out of scope for this matrix: it uses **LAN TUTK/Kalay**, *not* the Agora opcode
  protocol at all (`DOCS.md`), so none of these opcodes apply. Track it separately.

### 8.5 Deliverable: a data-driven capability table in the add-on
Once 8.2 is known, the add-on should carry a **`productId → capabilities` table** and gate the whole
UI generically off it (today only routes are gated, and only by a runtime probe). This replaces
per-feature ad-hoc probing with one source of truth, and makes multi-model support declarative.

---

## 9. Capability matrix — template to fill in

Rows = opcode/function; columns = model. Cells: ✅ present · ❌ absent · ❓ unknown · — N/A.
Seed values are what we know today; the rest is the deep-dive's job (§8.2 first, §8.3 fallback).

| Opcode | Function | Air 2 | Air2 Plus/2S/Mini | EBO X | EBO Max | SE (TUTK) |
|---|---|---|---|---|---|---|
| 101007 | move (joystick) | ✅ | 🟡 | ❓ | ❓ | — |
| 101047 | sleep/wake | ✅ | 🟡 | ❓ | ❓ | — |
| 101061 | auto roaming | ❓ | ❓ | ❓ | ❓ | — |
| 103001 | rotate by angle | ❓ | ❓ | ❓ | ❓ | — |
| 103003/103005 | routine / run move | ✅(run) | ❓ | ❓ | ❓ | — |
| 103019 | auto-recharge setting | ❓ | ❓ | ❓ | ❓ | — |
| 103043 | return to dock | ✅ | 🟡 | ❓ | ❓ | — |
| 103049 | AI track | ✅ | ❓ | ❓ | ❓ | — |
| 103061/103063 | patrol start/stop | ❌ | ❓ | ❓ | ❓ | — |
| 103201/103205/103206 | route record | ❌ | ❓ | ❓ | ❓ | — |
| 104001/104002 | list routes | ❌ | ❓ | ❓ | ❓ | — |
| 104057 | eyes/emoji | ✅ | ❓ | ❓ | ❓ | — |
| 102035 | day/night (shootMode) | ✅ | ❓ | ❓ | ❓ | — |

> The full 112-row version should be generated by joining `COMMANDS-APK.md` with the `productId →
> featureFlags` map from §8.2. That join **is** the definitive "which functions each robot exposes."
