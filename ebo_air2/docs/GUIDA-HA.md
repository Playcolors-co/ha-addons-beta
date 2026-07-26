# Guida pratica HA — video fluido, audio, controlli come l'app

Risponde alle domande concrete: come si attivano invio/ricezione audio, come rendere il video
più fluido, e come avere un'interfaccia con la telecamera + i pad di controllo come nell'app.

---

## 1. Cosa attivare (toggle dell'add-on)

Non sono pulsanti a runtime: sono **opzioni** dell'add-on. Impostazioni → EBO Air 2 →
Configurazione. Dopo averle cambiate, **riavvia l'add-on**.

| Opzione | Cosa fa | Stato |
|---|---|---|
| `video: true` | Pubblica lo stream RTSP → telecamera in HA | ✅ funziona |
| `audio: true` | **Ricezione**: senti il microfono del robot nella telecamera | ⚠️ best-effort (vedi sotto) |
| `talk: true` | **Invio**: mandi TU audio all'altoparlante del robot | ✅ funziona (canale a parte) |
| `audio_codec: 8` | Codec del microfono (lascia 8) | — |

### Verità sull'audio in ricezione (`audio: true`)
La decodifica funziona, ma **il robot tiene il microfono spento** e lo apre **da solo, in modo
imprevedibile** (a volte dopo qualche minuto, a volte per niente). Nell'app è immediato perché
manda un comando interno (RTM) che **non ho ancora catturato**. Finché non lo isolo, in HA
l'audio si sentirà **solo quando il robot decide di aprire il mic**. Nel log vedrai onestamente:
- `[audio] robot mic is OPEN — audio flowing` → in quel momento si sente;
- `[audio] subscribed OK, but the robot's mic is still MUTED …` → non ancora.

(La v0.17.1 provava a forzarlo con una traccia silenziosa: **non funzionava** e dichiarava il
falso "audio works". Rimosso in 0.17.2.)

### Parlare al robot (`talk: true`)
Mandi un audio all'altoparlante pubblicando un **URL o percorso** (qualsiasi cosa legga ffmpeg)
sul topic MQTT `ebo_air2/talk`. Esempio automazione: TTS di HA → URL media → `mqtt.publish`.
```yaml
# Esempio: fai "parlare" il robot con la voce TTS di HA
service: tts.speak
data:
  cache: true
  media_player_entity_id: media_player.un_qualsiasi   # richiesto dal servizio, non usato dal robot
  message: "Ciao, sono a casa!"
target:
  entity_id: tts.google_translate_it   # o il tuo motore TTS
# …poi in un secondo step pubblichi l'URL generato su ebo_air2/talk.
```
Modo più semplice per provare subito: pubblica un URL di un mp3 pubblico su `ebo_air2/talk` da
Strumenti per sviluppatori → MQTT.

> **Nota:** questo fa **emettere suono** al robot. È una tua azione, ma tienilo a mente: è un
> dispositivo in casa tua.

---

## 2. Video più fluido (la parte che si nota di più)

L'add-on già trasmette con impostazioni a bassa latenza. Il ritardo/scatti residui vengono
**dalla card di HA**: la telecamera standard usa **HLS**, che bufferizza 1-3 secondi. La
soluzione è far riprodurre il video in **WebRTC** (sotto il secondo). Due strade:

### A) Card HACS "WebRTC Camera" (consigliata, più semplice)
1. HACS → Frontend → installa **WebRTC Camera** (`AlexxIT/WebRTC`).
2. Aggiungi una card manuale:
```yaml
type: custom:webrtc-camera
url: rtsp://IP-DEL-TUO-HA:8554/ebo   # l'URL che l'add-on mostra in "EBO camera URL"
mode: webrtc                          # webrtc = bassa latenza; mse come fallback
```
Questa card apre lo stream in WebRTC direttamente → niente buffer HLS.

### B) go2rtc integrato in HA (senza HACS)
HA include go2rtc. In `configuration.yaml` (o nel file go2rtc), aggiungi la sorgente:
```yaml
go2rtc:
  streams:
    ebo:
      - rtsp://IP-DEL-TUO-HA:8554/ebo
```
Poi usa una telecamera `generic` che punta a quello stream: la card mostrerà WebRTC quando
possibile.

> Se resti sulla telecamera "Generic Camera" standard, il video funziona ma con il ritardo HLS.
> Il salto di fluidità reale lo dà WebRTC (A o B).

---

## 3. Interfaccia "come l'app" (telecamera + pad di controllo)

Domanda: meglio farla su HACS? **Non serve un componente HACS su misura** (è un progetto a sé).
La cosa pratica è comporre card **esistenti**. Due livelli:

### Livello 1 — massima fluidità, controlli sotto (consigliato per pilotare davvero)
Video WebRTC pieno + una riga di controlli sotto. Reattivo e semplice:
```yaml
type: vertical-stack
cards:
  - type: custom:webrtc-camera
    url: rtsp://IP-DEL-TUO-HA:8554/ebo
    mode: webrtc
  - type: horizontal-stack
    cards:
      - type: button
        entity: button.ebo_forward
        name: ▲
      - type: button
        entity: button.ebo_stop
        name: STOP
  - type: horizontal-stack
    cards:
      - type: button
        entity: button.ebo_left
        name: ◄
      - type: button
        entity: button.ebo_back
        name: ▼
      - type: button
        entity: button.ebo_right
        name: ►
  - type: entities
    entities:
      - switch.ebo_camera
      - switch.ebo_laser
      - number.ebo_speed
      - button.ebo_return_to_base
```

### Livello 2 — pad IN OVERLAY sul video (estetica "app a tutto schermo")
Usa `picture-elements` con i pulsanti sopra il video. Nota: in `picture-elements` il video usa
il path camera standard (un filo più di latenza dell'opzione WebRTC pura). YAML pronto in
[`DASHBOARD-CONTROL-OVERLAY.md`](DASHBOARD-CONTROL-OVERLAY.md), che pubblica il **vettore di
movimento** su `ebo_air2/move/vector` (`{"lx":..,"ly":..,"hold":0.6}`) per un controllo continuo
tipo joystick, non a scatti.

> Consiglio: **Livello 1** per guidare (reattività), **Livello 2** se vuoi l'effetto estetico.
> Si può anche tenere la card WebRTC per guardare e una tab separata con l'overlay.

---

## Riassunto onesto

- **Video, movimento, sensori, snapshot, patrol, occhi, TTS**: funzionano.
- **Video fluido**: si ottiene lato-HA con WebRTC (sezione 2). L'add-on è già a bassa latenza.
- **Parlare al robot** (`talk`): funziona, via `ebo_air2/talk`.
- **Sentire il robot** (`audio`): best-effort finché non catturo il comando RTM del microfono.
  È l'unico pezzo non affidabile, e ora il log te lo dice in chiaro senza falsi "funziona".
