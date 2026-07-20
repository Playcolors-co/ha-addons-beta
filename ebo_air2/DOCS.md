# EBO Air 2 — documentazione

## Configurazione

| opzione | descrizione |
|---------|-------------|
| `email` | email del tuo account Enabot |
| `password` | password Enabot (memorizzata solo qui, in HA) |
| `region` | regione dell'account (es. `GB`, `US`, `EU`) |
| `host` | endpoint cloud regionale. Default EU; US ≈ `ebox-us.enabotserverintl.com` |
| `robot_id` | `0` = scoperta automatica. Imposta un id solo con più robot |

Le credenziali restano nella configurazione dell'add-on (in HA) e vengono inviate solo ai
server Enabot, esattamente come fa l'app ufficiale.

## MQTT

L'add-on richiede il servizio `mqtt` del Supervisor: prende in automatico host, porta e
credenziali del broker di Home Assistant. Assicurati di avere l'add-on *Mosquitto broker*
e l'integrazione MQTT attivi.

## Movimento da automazioni / AI

Oltre ai pulsanti, puoi pubblicare un vettore analogico:

```yaml
service: mqtt.publish
data:
  topic: ebo_air2/move/vector
  payload: '{"ly":-50,"rx":20,"hold":1.5}'
```

- `ly` < 0 = avanti, > 0 = indietro
- `rx` = rotazione (< 0 sinistra, > 0 destra)
- `hold` = secondi di durata; scaduto il tempo il robot si ferma (watchdog)

Scala dei valori ~±100. Il vettore va "tenuto": l'add-on lo ritrasmette a 10 Hz finché non
scade `hold` o arriva un nuovo comando.

## Limiti noti

- **Solo amd64** (SDK Agora x86_64).
- **Video non incluso** (solo controllo + telemetria).
- Un solo client di controllo alla volta: mentre l'add-on è attivo, l'app EBO HOME sullo
  stesso account potrebbe venire disconnessa dal controllo.
- Dipende dalle API cloud di Enabot: un loro cambiamento può richiedere un aggiornamento.

## Risoluzione problemi

- **"login fallito"**: verifica email/password e la `region`/`host` corretti.
- **Nessuna entità in HA**: controlla che MQTT (Mosquitto + integrazione) sia attivo.
- **Il robot non risponde ai comandi**: assicurati che nessun'altra sessione (app) stia
  controllando il robot nello stesso momento.
