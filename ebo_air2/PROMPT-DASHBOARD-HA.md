# Prompt da dare al Claude che configura Home Assistant

Copia tutto ciò che segue e incollalo al Claude che gestisce la tua Home Assistant.

---

Sei l'assistente che configura la mia Home Assistant. Ho un robot **Enabot EBO Air 2**
(camera su ruote) integrato tramite un add-on custom che fa da ponte cloud→MQTT. L'add-on
espone il robot come **entità MQTT Discovery** sotto un unico device chiamato **"EBO Air 2"**
(tutte le entità hanno il nome che inizia con `EBO …`). Il prefisso MQTT è `ebo_air2`.

Ho **due compiti** per te:
1. **Genera/aggiorna una dashboard Lovelace** completa per il robot.
2. **Testa che ogni controllo funzioni davvero**, usando il servizio `mqtt.publish` per
   inviare i comandi e osservando le entità di stato / il comportamento del robot.

## Come funziona
- Le entità appaiono da sole via MQTT Discovery: aprile da **Impostazioni → Dispositivi →
  "EBO Air 2"**. Non devi crearle a mano.
- Ogni **controllo** ha un *command topic* MQTT: puoi azionarlo dall'entità **oppure**
  pubblicando sul topic con il servizio `mqtt.publish` (utile per i test automatici).
- Lo **stato reale** del robot arriva sul topic ritenuto `ebo_air2/state` (un JSON) ed è già
  mappato nelle entità sensore. Molti controlli “con stato” (qualità video, volumi, velocità…)
  si aggiornano quando il robot conferma → è così che verifichi che il comando ha avuto effetto.
- Il **video live** è un RTSP: c'è un sensore `EBO camera URL` con l'URL
  (`rtsp://<IP-HA>:8554/ebo`). Prima accendi lo switch **EBO camera**, poi usa una card
  *Generic Camera*/*WebRTC* con quell'URL.

## CONTROLLI (command topic → payload)
Per testare via servizio, esempio:
`service: mqtt.publish` con `topic: ebo_air2/laser/set`, `payload: "on"`.

### Movimento (ATTENZIONE: muovono il robot — supervisiona, tienilo lontano da scale/bordi)
| Entità | Topic | Payload | Note |
|---|---|---|---|
| Buttons **EBO forward/back/left/right/stop** | `ebo_air2/move/<forward\|back\|left\|right\|stop>` | qualsiasi | passo dolce |
| (avanzato) vettore continuo | `ebo_air2/move/vector` | `{"lx":0,"ly":-50,"rx":0,"ry":0,"hold":0.6}` | ly<0 avanti, rx gira; si ferma da solo dopo `hold`s |
| (avanzato) joystick | `ebo_air2/joystick` | `{"x":0.5,"y":1.0}` | x=sterzo (dx+), y=avanti(+), range −1..1 |
| Number **EBO rotate** | `ebo_air2/rotate/set` | `-180`…`180` | ruota di N gradi |
| Number **EBO speed** | `ebo_air2/speed/set` | `1`…`100` | velocità movimento (ha stato) |
| Select **EBO move mode** | `ebo_air2/move_mode/set` | `Mode 1\|Mode 2\|Mode 3` | modalità guida (ha stato) |
| Button **EBO return to base** | `ebo_air2/dock` | qualsiasi | torna in carica (no-op se già in dock) |
| Button **EBO start patrol** | `ebo_air2/patrol/start` | qualsiasi | avvia pattuglia sulla rotta scelta |
| Select **EBO patrol route** | `ebo_air2/patrol/route/set` | un nome dalla lista | “auto (no route)” = senza rotta |

### Camera / media (sicuri, nessun movimento)
| Entità | Topic | Payload |
|---|---|---|
| Switch **EBO camera** | `ebo_air2/camera/set` | `on`/`off` (accende lo stream RTSP) |
| Select **EBO video quality** | `ebo_air2/video_quality/set` | `Low\|Medium\|High` (ha stato) |
| Select **EBO image style** | `ebo_air2/image_style/set` | `Standard\|Vivid\|Soft` (ha stato) |
| Select **EBO shoot mode** | `ebo_air2/shoot_mode/set` | `Normal\|Wide\|Follow` (ha stato) |
| Switch **EBO laser** | `ebo_air2/laser/set` | `on`/`off` (puntatore laser) |
| Number **EBO volume** | `ebo_air2/volume/set` | `0`…`100` (volume altoparlante) |
| Number **EBO talkback volume** | `ebo_air2/talkback_volume/set` | `0`…`100` (ha stato) |
| Text **EBO say** | `ebo_air2/say` | testo → il robot lo pronuncia (TTS) |
| Text **EBO ask AI** | `ebo_air2/ai_ask` | domanda → l'AI di bordo risponde |
| Switch **EBO cloud upload** | `ebo_air2/upload_cloud/set` | `on`/`off` |
| Switch **EBO motion recording** | `ebo_air2/sports_record/set` | `on`/`off` (ha stato) |
| Switch **EBO auto-record calls** | `ebo_air2/call_rec/set` | `on`/`off` (ha stato) |

### Espressioni / autonomia / AI (best-effort — verifica con cura)
| Entità | Topic | Payload | Effetto |
|---|---|---|---|
| Select **EBO eyes** | `ebo_air2/eyes/set` | `Dynamic\|Clock\|Custom` | display occhi |
| Switch **EBO roaming** | `ebo_air2/roaming/set` | `on`/`off` | pattuglia autonoma |
| Button **EBO AI track** | `ebo_air2/ai_track` | qualsiasi | insegue un soggetto |
| Number **EBO play motion** | `ebo_air2/motion/set` | id `0`…`30` | esegue una coreografia preset |
| Number **EBO play voice** | `ebo_air2/voice/set` | id `0`…`30` | riproduce una voce preset |
| Switch **EBO sleep** | `ebo_air2/sleep/set` | `on`/`off` | dormi/sveglia |

### Sistema
| Entità | Topic | Payload |
|---|---|---|
| Switch **EBO connected** | `ebo_air2/connected/set` | `on`/`off` — OFF stacca dal cloud (il robot può dormire) |

### Canale RAW (qualsiasi comando del catalogo completo)
Topic `ebo_air2/cmd`, payload `{"id":<opcode>,"data":{...}}`. Il catalogo dei 112 opcode è in
`docs/COMANDI-APK.md` dell'add-on. Esempio TTS: `{"id":103501,"data":{"userId":"<id>","text":"ciao"}}`.

## SENSORI (solo lettura — mettili in gauge/badge/entità)
`EBO battery` (%), `EBO charging`, `EBO docked`, `EBO wifi` (dBm), `EBO WiFi SSID`, `EBO IP`,
`EBO SD card` (presente), `EBO SD free`/`EBO SD total` (GB), `EBO storage free` (GB),
`EBO recording`, `EBO guard mode`, `EBO activity` (in movimento/carica/AI-track/chiamata/upgrade),
`EBO firmware (camera)`, `EBO firmware (MCU)`, `EBO camera URL`.

## DASHBOARD — cosa voglio
Una vista con, dall'alto in basso:
1. **Card video** (Generic/WebRTC camera) con l'URL RTSP; sopra o accanto lo switch **EBO camera**.
2. **D-pad / joystick** per il movimento (usa i button move, o una card joystick che pubblica su
   `ebo_air2/move/vector`), con lo slider **EBO speed** e il number **EBO rotate**.
3. **Pannello camera**: select qualità/stile/shoot, switch laser, slider volumi, text “say”/“ask AI”.
4. **Pannello espressioni/AI**: eyes, roaming, AI track, play motion/voce.
5. **Stato**: gauge batteria + badge carica/docked/wifi, SD/storage, attività corrente, versioni firmware.
Raggruppa in modo pulito (sezioni/`vertical-stack`), icone sensate, e nascondi le entità
diagnostiche in una sezione a parte.

## TEST — procedura per ognuno
Per **ogni controllo** esegui e annota PASS/FAIL:
- **Controlli “con stato”** (velocità, qualità/stile/shoot/move mode, volumi, sports/call rec):
  invia un valore via `mqtt.publish`, aspetta 2–3 s, **verifica che l'entità corrispondente rifletta
  il nuovo valore** (il robot lo conferma sul topic di stato). Se torna al valore, il robot ha
  accettato → PASS.
- **Azioni/movimento** (buttons, rotate, dock, patrol, ai_track, play motion): eseguile con il
  robot **in un'area sicura e sotto supervisione**; verifica l'effetto fisico (si muove/gira/parla)
  o il cambio del sensore **EBO activity**. Metti sempre `stop` dopo un movimento.
- **Sicuri sempre**: laser, say, volumi, eyes, video quality — testabili senza rischi.
- **Best-effort** (eyes, roaming, ai_track, ai_ask, play motion/voce): se un comando **non produce
  effetto**, segnalamelo con: nome controllo + payload inviato + cosa è (non) successo. Servirà a
  correggere il payload nell'add-on (i loro formati sono stati ricostruiti dal reverse-engineering).

Alla fine dammi una **tabella PASS/FAIL** di tutti i controlli, e la dashboard aggiornata.
Non inviare comandi di **movimento** se il robot non è in un posto sicuro: chiedimelo prima.

---
