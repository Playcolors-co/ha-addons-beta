# EBO — vista "come l'app": video con controlli in overlay

Riproduce la schermata a tutto schermo dell'app: lo **stream della camera** con sopra un
**D-pad** per muovere il robot, più laser, ritorno alla base, "parla", velocità e stato.

## Prerequisiti (lato Home Assistant)
1. **Add-on avviato** con `video: true` (e, se vuoi audio, `audio: true` / `talk: true`).
2. **Un'entità camera** che punta allo stream RTSP dell'add-on. Il modo migliore è **go2rtc**
   (incluso in HA OS) così hai anche l'**audio** e bassa latenza:
   - In `configuration.yaml` (o nella config di go2rtc) aggiungi lo stream:
     ```yaml
     go2rtc:
       streams:
         ebo: rtsp://<IP-ADD-ON>:8554/ebo
     ```
     e crea la camera generica che lo usa, **oppure** usa la card WebRTC (`custom:webrtc-camera`)
     con `url: ebo`.
   - In alternativa rapida (solo video, niente audio): **Impostazioni → Dispositivi → Aggiungi
     integrazione → Generic Camera**, Stream URL = `rtsp://<IP-ADD-ON>:8554/ebo`.
   Chiama l'entità risultante, ad es., `camera.ebo`. **Sostituisci `camera.ebo`** sotto con la tua.
3. Accendi lo switch **EBO camera** (o `mqtt.publish` su `ebo_air2/camera/set` = `on`): solo così
   il bridge si iscrive al video del robot.

## Card A — `picture-elements` (nativa, nessun componente extra)
Incolla come nuova card (modalità YAML). Le frecce muovono il robot con un "passo" morbido che si
ferma da solo (`hold`), come un tap ripetibile. **Sostituisci `camera.ebo`** e gli `entity` di stato
con gli ID reali (li trovi in Impostazioni → Dispositivi → "EBO Air 2").

```yaml
type: picture-elements
camera_image: camera.ebo
camera_view: live
elements:
  # ---------- MOVIMENTO (D-pad in basso a sinistra) ----------
  - type: icon
    icon: mdi:chevron-up
    title: Avanti
    style: {left: 15%, top: 62%, color: white, "--mdc-icon-size": 44px}
    tap_action:
      action: call-service
      service: mqtt.publish
      data: {topic: ebo_air2/move/vector, payload: '{"lx":0,"ly":-55,"rx":0,"ry":0,"hold":0.8}'}
  - type: icon
    icon: mdi:chevron-down
    title: Indietro
    style: {left: 15%, top: 90%, color: white, "--mdc-icon-size": 44px}
    tap_action:
      action: call-service
      service: mqtt.publish
      data: {topic: ebo_air2/move/vector, payload: '{"lx":0,"ly":55,"rx":0,"ry":0,"hold":0.8}'}
  - type: icon
    icon: mdi:chevron-left
    title: Gira sinistra
    style: {left: 5%, top: 76%, color: white, "--mdc-icon-size": 44px}
    tap_action:
      action: call-service
      service: mqtt.publish
      data: {topic: ebo_air2/move/vector, payload: '{"lx":0,"ly":0,"rx":-65,"ry":0,"hold":0.6}'}
  - type: icon
    icon: mdi:chevron-right
    title: Gira destra
    style: {left: 25%, top: 76%, color: white, "--mdc-icon-size": 44px}
    tap_action:
      action: call-service
      service: mqtt.publish
      data: {topic: ebo_air2/move/vector, payload: '{"lx":0,"ly":0,"rx":65,"ry":0,"hold":0.6}'}
  - type: icon
    icon: mdi:stop-circle-outline
    title: Stop
    style: {left: 15%, top: 76%, color: "#ff5252", "--mdc-icon-size": 40px}
    tap_action:
      action: call-service
      service: mqtt.publish
      data: {topic: ebo_air2/move/stop, payload: ""}

  # ---------- AZIONI (colonna a destra) ----------
  - type: icon
    icon: mdi:laser-pointer
    title: Laser
    style: {right: 4%, top: 60%, color: white, "--mdc-icon-size": 34px}
    tap_action:
      action: call-service
      service: mqtt.publish
      data: {topic: ebo_air2/laser/set, payload: "on"}
    hold_action:
      action: call-service
      service: mqtt.publish
      data: {topic: ebo_air2/laser/set, payload: "off"}
  - type: icon
    icon: mdi:home-import-outline
    title: Torna alla base
    style: {right: 4%, top: 72%, color: white, "--mdc-icon-size": 34px}
    tap_action:
      action: call-service
      service: mqtt.publish
      data: {topic: ebo_air2/dock, payload: ""}
  - type: icon
    icon: mdi:camera-iris
    title: Snapshot
    style: {right: 4%, top: 84%, color: white, "--mdc-icon-size": 34px}
    tap_action:
      action: call-service
      service: mqtt.publish
      data: {topic: ebo_air2/cmd, payload: '{"id":102101,"data":{}}'}   # opzionale/best-effort

  # ---------- VELOCITÀ (in alto a destra) ----------
  - type: icon
    icon: mdi:speedometer-slow
    title: Più lento
    style: {right: 16%, top: 8%, color: white, "--mdc-icon-size": 28px}
    tap_action:
      action: call-service
      service: mqtt.publish
      data: {topic: ebo_air2/speed/set, payload: "40"}
  - type: icon
    icon: mdi:speedometer
    title: Più veloce
    style: {right: 4%, top: 8%, color: white, "--mdc-icon-size": 28px}
    tap_action:
      action: call-service
      service: mqtt.publish
      data: {topic: ebo_air2/speed/set, payload: "95"}

  # ---------- STATO (in alto a sinistra) — sostituisci con i tuoi entity id ----------
  - type: state-label
    entity: sensor.ebo_battery
    prefix: "🔋 "
    style: {left: 3%, top: 6%, color: white, font-weight: bold}
  - type: state-label
    entity: sensor.ebo_activity
    style: {left: 3%, top: 12%, color: white}
```

### Note
- Il D-pad usa `ebo_air2/move/vector` con `hold`: ogni tocco muove un po' e **si ferma da solo**.
  Vuoi passi più lunghi/corti? cambia `hold` (secondi) o i valori `ly`/`rx` (−100..100).
- **Sicurezza:** questi comandi *muovono* il robot. Usali solo con il robot in area sicura e
  sotto la tua supervisione (mai da remoto se non sai cosa c'è intorno).
- Vuoi anche **parlare** dal video? aggiungi un'icona `mdi:microphone` che apre un `input_text`
  con l'URL audio e pubblica su `ebo_air2/talk` (serve `talk: true`).

## Card B — joystick analogico (fedele all'app, trascinamento)
Richiede una card custom. Se la vuoi te la scrivo: un file JS (risorsa Lovelace) che disegna un
**joystick trascinabile** sopra il video e pubblica in continuo su `ebo_air2/move/vector`
(rilascio → stop), esattamente come il pad analogico dell'app. Dimmi "fai la card B".
