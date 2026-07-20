# Home Assistant add-on — Enabot EBO Air 2

Controlla il tuo **Enabot EBO Air 2** da Home Assistant: batteria, wifi, laser, velocità,
movimento (avanti/indietro/sinistra/destra) e un canale "vettore" pensato per farlo
guidare da un'automazione o da un agente AI.

Funziona con le **tue credenziali Enabot** (le stesse dell'app EBO HOME): l'add-on accede
al cloud Enabot, scopre il tuo robot, e mantiene la sessione da solo. Nessun telefono,
nessun emulatore.

> ⚠️ **Progetto indipendente, non ufficiale.** Non affiliato a Enabot né a
> ThroughTek/Agora. Interopera col cloud Enabot tramite reverse engineering, usando le
> tue credenziali e il tuo dispositivo. Usalo a tuo rischio; potrebbe smettere di
> funzionare se Enabot cambia le API.

## Requisiti

- Home Assistant **OS** o **Supervised** (gli add-on richiedono il Supervisor)
- Architettura **amd64** (l'SDK Agora è solo x86_64 — es. HAOS come VM su Proxmox/NUC ✓)
- Un broker **MQTT** in HA (add-on *Mosquitto broker*) e l'integrazione **MQTT** attiva

## Installazione

1. **Impostazioni → Add-on → Store → ⋮ (in alto a destra) → Repository**
2. Incolla l'URL di questo repo:
   ```
   https://github.com/Playcolors-co/ha-ebo-air2
   ```
3. Trova **EBO Air 2** nello store e installa.
4. Nella scheda **Configurazione** dell'add-on inserisci:
   - `email` / `password` — le tue credenziali Enabot
   - `region` — la regione del tuo account (es. `GB`, `US`, `EU`)
   - `host` — lascia il default se sei in Europa; utenti US/altre regioni potrebbero
     doverlo cambiare (es. `ebox-us.enabotserverintl.com`)
   - `robot_id` — lascia `0`: viene scoperto in automatico (imposta un valore solo se hai
     più robot sull'account)
5. **Avvia** l'add-on. Le entità compaiono in Home Assistant via MQTT Discovery, sotto il
   dispositivo **EBO Air 2**.

## Entità

| entità | tipo |
|--------|------|
| batteria, wifi, spazio SD | sensor |
| in carica, registrazione | binary_sensor |
| laser | switch |
| velocità (1–100) | number |
| avanti / indietro / sinistra / destra / stop | button |

Più il topic MQTT `ebo_air2/move/vector` che accetta `{"ly":-50,"rx":0,"hold":1.0}` per
un controllo analogico continuo (utile per automazioni o AI).

## Come funziona / dettagli tecnici

Il robot parla col cloud via **Agora RTM** (comandi/telemetria, JSON) + **RTC** (presenza).
L'add-on replica il flusso dell'app: login cifrato → sessione Agora → controllo. Il
movimento è ritrasmesso a 10 Hz con un **watchdog** (se l'add-on si ferma, il robot si
ferma). Dettagli in [DOCS.md](ebo_air2/DOCS.md).

## Licenza

Codice originale sotto **MIT** (vedi [LICENSE](LICENSE)). Nessun componente proprietario
Enabot/ThroughTek è incluso o ridistribuito.
