# D-ESP-016 — NanoC6-meetactualiteit en zelfstandig MQTT-gebruik

Datum: 17 november 2026.

Status: uitgevoerd in de lokale kandidaat; fysieke acceptatie volgt bij een
afzonderlijk opgedragen installatie.

Aanvulling 18 november 2026: **S100-01 is fysiek geaccepteerd** met firmware
0.1.2: 31 minuten zonder de bekende Native-/logclients, frametellers
671 → 1271 zonder reset, doorlopende MQTT-data en gecontroleerd herstel van
beide gestopte HA-clients. Zie de
[MQTT-only-duurproef](../results/nanoc6-mqtt-only-s100-01-acceptance-2026-11-18.md).

Aanvulling 17 november 2026: de S100-02-validiteitsmapping hieronder is
vervangen door het expliciete gebruikersbesluit
[D-ESP-020](0020-firmware-device-last-report.md). De S100-01-correctie van de
API-herstarttimer blijft gelden. De oorspronkelijke onderbouwing staat hier
als besluitgeschiedenis.

## Ontwerp en risicoanalyse

De reviewbevindingen S100-01 en S100-02 betreffen de publieke NanoC6-kit.
Een standaard API-reboottimer herstart ook een gezond MQTT-apparaat zonder
Native-client. Daarnaast blijft transportactiviteit bestaan wanneer de UART
stilstaat, doordat de firmware data age blijft publiceren. Zonder expliciete
bronvaliditeitsmapping kan de systeemstatus oude meetwaarden actueel noemen.

De correctie blijft bij de firmwareconfiguratie en de concrete kitmapping.
Er komt geen ESPHome-specifieke interpretatie in providers, entiteiten,
evaluator, kaart of archivering. Bestaande bronexpressies worden niet
gemigreerd of overschreven. Ruwe waarden blijven behouden voor diagnose.

## Besluit

- Zet `api.reboot_timeout` expliciet op `0s`, naast de bestaande MQTT-timer
  op nul. Native- en OTA-encryptie blijven geconfigureerd. Wi-Fi-herstel en
  overige ESPHome-componentinstellingen veranderen niet.
- Publiceer complete mappings voor Native en de echte MQTT-topics van de kit.
  `status_reporting` vereist zowel UART-`data_valid` als de bestaande
  rapportageleeftijd. Native levert een boolean; MQTT levert tekst `ON`/`OFF`.
- `data_valid` blijft gebaseerd op een compleet geldig statusframe binnen
  15 seconden. Geen nieuwe temperatuurfilters, wijziging van de parser of
  veronderstelde betekenis voor T4/flow/controller state.
- `last_report()` en Report delay blijven transportobservaties. De kituitleg
  maakt duidelijk waarom data age de transporttijd kan verversen terwijl de
  meetbron stilgevallen is. Retained replay bewijst geen nieuw fysiek frame.
- De generieke coordinator behandelt `status_reporting=False` al door actuele
  meetwaarden onbekend te maken. De lokale alertfunctie geeft de offlinealert.
  Herstel gebruikt dezelfde bestaande entiteitsidentiteit.
- Verhoog uitsluitend de firmwareprojectversie naar `0.1.1`. Integratie,
  kaart en resource blijven kandidaat `1.0.0`. Een bestaande installatie
  vereist zowel firmware-installatie als bewuste opslag van de kitmappings.

## Verificatiegrens

Toets de gedocumenteerde expressies met de volledige catalogus op verse data,
UART-stilte met doorgaande transportevents, transportstilte en herstel, voor
beide providers. Valideer beide ESPHome-profielen en de opgeloste API-timer.
De regressies bewijzen geen fysieke looptijd: meer dan 30 minuten zonder
Native/logclient en een veilige fysieke UART-uitval/herstelproef blijven
acceptatiepunten voor een afzonderlijk opgedragen plaatsing.

Primaire bronnen:
[ESPHome API](https://esphome.io/components/api/),
[ESPHome MQTT](https://esphome.io/components/mqtt/).
