# EBO Air 2 — Catalogo completo comandi (dall'APK)

**Trasporto:** Agora RTM `publish`. **Messaggio:** `{"id":<opcode>,"sid":"<sessione>","data":{...},"type":0,"timestamp":<ms>}`.
**Heartbeat:** `101005 {state:0}` ogni ~2s (obbligatorio per tenere viva la sessione).
**Joystick (101007):** `{lx,ly,rx,ry,buttons}`, valori ~ -100..100. `ly<0`=avanti, `ly>0`=indietro, `rx<0`=gira sx, `rx>0`=gira dx, `buttons:1`=attivo. Coppia (valore, poi 0=stop).

**Totale: 112 comandi. Gia nell'add-on: 20. Da aggiungere: 92.**

| Opcode | Categoria | Nome (inferito) | Parametri | Nell'add-on |
|---|---|---|---|---|
| 101003 | Sistema/Sessione |  | userId | ✅ |
| 101005 | Sistema/Sessione | heartbeat (stato, ogni 2s) | state | ✅ |
| 101007 | Sistema/Sessione | JOYSTICK analogico (movimento) | lx, ly, rx, ry, buttons | ✅ |
| 101009 | Sistema/Sessione | set per tipo | type | ⬜ |
| 101013 | Sistema/Sessione | sync orario (timestamp) | — | ⬜ |
| 101017 | Sistema/Sessione | set regione | region | ⬜ |
| 101021 | Sistema/Sessione |  | — | ⬜ |
| 101023 | Sistema/Sessione |  | — | ⬜ |
| 101025 | Sistema/Sessione |  | — | ⬜ |
| 101027 | Sistema/Sessione |  | — | ✅ |
| 101029 | Sistema/Sessione |  | — | ⬜ |
| 101033 | Sistema/Sessione | upload log al cloud | userId, robotId, uploadLogToken, desc, contact | ⬜ |
| 101039 | Sistema/Sessione | set per tipo | type | ⬜ |
| 101041 | Sistema/Sessione |  | — | ⬜ |
| 101047 | Sistema/Sessione | sleep / wake | isSleeping | ✅ |
| 101049 | Sistema/Sessione | registrazione "sports" | sportsRecord | ✅ |
| 101059 | Sistema/Sessione | azione | — | ⬜ |
| 101061 | Sistema/Sessione | roaming auto (on, sensibilita) | isRoamOn, sensitivity | ⬜ |
| 101063 | Sistema/Sessione | azione | — | ⬜ |
| 101065 | Sistema/Sessione | auto-switch (sensibilita) | autoSwitch, sensitivity | ⬜ |
| 101067 | Sistema/Sessione | azione | — | ⬜ |
| 101081 | Sistema/Sessione | azione | — | ⬜ |
| 101901 | Sistema/Sessione |  | — | ⬜ |
| 101903 | Sistema/Sessione |  | — | ⬜ |
| 101905 | Sistema/Sessione |  | — | ⬜ |
| 101907 | Sistema/Sessione |  | — | ⬜ |
| 102001 | Audio/Camera | set audio/media tipo | type | ⬜ |
| 102003 | Audio/Camera | set tipo | type | ⬜ |
| 102005 | Audio/Camera | set tipo | type | ⬜ |
| 102007 | Audio/Camera | set tipo | type | ⬜ |
| 102011 | Audio/Camera |  | — | ⬜ |
| 102013 | Audio/Camera |  | — | ⬜ |
| 102015 | Audio/Camera |  | — | ⬜ |
| 102017 | Audio/Camera |  | — | ⬜ |
| 102023 | Audio/Camera | volume playback (+mute) | playbackVolume, isPlaybackMuted | ✅ |
| 102031 | Audio/Camera | volume talkback (mic) | talkbackVolume | ✅ |
| 102035 | Audio/Camera | shootMode (foto/video) | shootMode | ✅ |
| 102037 | Audio/Camera |  | — | ⬜ |
| 102039 | Audio/Camera |  | — | ⬜ |
| 102055 | Audio/Camera | QUALITA video | videoQuality | ⬜ |
| 102057 | Audio/Camera | stile immagine (filtro) | imageStyle | ⬜ |
| 102101 | Audio/Camera |  | — | ⬜ |
| 103001 | Movimento/AI/Skill | ROTAZIONE ad angolo | angle | ⬜ |
| 103003 | Movimento/AI/Skill | crea routine (moves+voci+emoji) | cycleMode, moveIds, voiceIds, emojiIds | ⬜ |
| 103005 | Movimento/AI/Skill | esegui move | cycleMode, moveId | ✅ |
| 103007 | Movimento/AI/Skill | esegui voce | cycleMode, voiceId | ✅ |
| 103009 | Movimento/AI/Skill | VELOCITA movimento | moveSpeed | ✅ |
| 103011 | Movimento/AI/Skill | modalita movimento | moveMode | ✅ |
| 103013 | Movimento/AI/Skill |  | — | ⬜ |
| 103015 | Movimento/AI/Skill |  | — | ⬜ |
| 103017 | Movimento/AI/Skill |  | — | ⬜ |
| 103019 | Movimento/AI/Skill | auto-recharge setting | — | ⬜ |
| 103021 | Movimento/AI/Skill |  | — | ⬜ |
| 103023 | Movimento/AI/Skill |  | — | ⬜ |
| 103025 | Movimento/AI/Skill |  | — | ⬜ |
| 103027 | Movimento/AI/Skill |  | — | ⬜ |
| 103029 | Movimento/AI/Skill |  | sn | ⬜ |
| 103039 | Movimento/AI/Skill |  | — | ⬜ |
| 103041 | Movimento/AI/Skill |  | — | ⬜ |
| 103043 | Movimento/AI/Skill | RITORNO alla base (dock) | startUp | ✅ |
| 103047 | Movimento/AI/Skill | safe mode | safeMode | ⬜ |
| 103049 | Movimento/AI/Skill | start AI-track | — | ✅ |
| 103055 | Movimento/AI/Skill |  | — | ⬜ |
| 103061 | Movimento/AI/Skill | start patrol | — | ✅ |
| 103063 | Movimento/AI/Skill |  | — | ⬜ |
| 103071 | Movimento/AI/Skill | auto-rec in chiamata | callAutoRecording | ✅ |
| 103081 | Movimento/AI/Skill | azione | — | ⬜ |
| 103083 | Movimento/AI/Skill |  | — | ⬜ |
| 103091 | Movimento/AI/Skill |  | — | ⬜ |
| 103093 | Movimento/AI/Skill |  | — | ⬜ |
| 103095 | Movimento/AI/Skill |  | — | ⬜ |
| 103101 | Movimento/AI/Skill |  | — | ⬜ |
| 103103 | Movimento/AI/Skill |  | — | ⬜ |
| 103201 | Movimento/AI/Skill |  | — | ⬜ |
| 103301 | Movimento/AI/Skill | AI conversation (chiedi) | modelType, session, question, userId | ⬜ |
| 103305 | Movimento/AI/Skill | AI conversation (sessione) | session, questionId, userId | ⬜ |
| 103307 | Movimento/AI/Skill |  | — | ⬜ |
| 103309 | Movimento/AI/Skill |  | — | ⬜ |
| 103341 | Movimento/AI/Skill |  | — | ⬜ |
| 103343 | Movimento/AI/Skill |  | — | ⬜ |
| 103345 | Movimento/AI/Skill |  | — | ⬜ |
| 103401 | Movimento/AI/Skill | AI object-track (on, objectId) | enable, objectId | ⬜ |
| 103501 | Movimento/AI/Skill | TTS - dì testo | userId, text | ✅ |
| 104001 | File/Registrazioni/Occhi |  | — | ✅ |
| 104003 | File/Registrazioni/Occhi |  | — | ⬜ |
| 104005 | File/Registrazioni/Occhi | elimina file (ids) | ids | ⬜ |
| 104011 | File/Registrazioni/Occhi |  | — | ⬜ |
| 104013 | File/Registrazioni/Occhi | snapshot | — | ⬜ |
| 104015 | File/Registrazioni/Occhi |  | — | ⬜ |
| 104017 | File/Registrazioni/Occhi |  | — | ⬜ |
| 104019 | File/Registrazioni/Occhi | elimina (ids) | ids | ⬜ |
| 104021 | File/Registrazioni/Occhi |  | — | ⬜ |
| 104023 | File/Registrazioni/Occhi | registrazione programmata | — | ⬜ |
| 104025 | File/Registrazioni/Occhi |  | — | ⬜ |
| 104027 | File/Registrazioni/Occhi |  | — | ⬜ |
| 104029 | File/Registrazioni/Occhi | elimina (ids) | ids | ⬜ |
| 104031 | File/Registrazioni/Occhi |  | — | ⬜ |
| 104033 | File/Registrazioni/Occhi |  | — | ⬜ |
| 104035 | File/Registrazioni/Occhi |  | — | ⬜ |
| 104037 | File/Registrazioni/Occhi |  | — | ⬜ |
| 104039 | File/Registrazioni/Occhi |  | — | ⬜ |
| 104055 | File/Registrazioni/Occhi |  | — | ⬜ |
| 104057 | File/Registrazioni/Occhi | occhi/emoji mode | — | ⬜ |
| 104061 | File/Registrazioni/Occhi |  | — | ⬜ |
| 104093 | File/Registrazioni/Occhi | cifratura video (secretKey) | deviceEncryption, secretKey | ⬜ |
| 104095 | File/Registrazioni/Occhi | set secretKey | secretKey | ⬜ |
| 104097 | File/Registrazioni/Occhi |  | — | ⬜ |
| 104099 | File/Registrazioni/Occhi | upload video al cloud | videoUploadCloud | ✅ |
| 104401 | File/Registrazioni/Occhi |  | — | ⬜ |
| 106003 | Misc |  | — | ⬜ |
| 106005 | Misc |  | — | ⬜ |
| 198001 | Meta | comando generico (commandId) | commandId | ⬜ |
