# NanoC6 — herstel na de fysieke uitvalproef

Datum: 17 november 2026, Europe/Amsterdam (CET).

Status: geslaagd. De gebruiker heeft de Solesta weer ingeschakeld; de Nano
bleef aan. Uitval en herstel zijn nu via Native en MQTT/Mosquitto bevestigd.

## Apparaatrapportage hervat

Dezelfde alleen-lezen, versleutelde Native-observer volgde firmware 0.1.2.
Deze client levert geen tijd en stuurt geen opdrachten.

| Waarneming | Geldige frames | Apparaatrapporttijd | Ouderdom |
| --- | ---: | --- | ---: |
| 23:39:55 | 297 | 22:47:15 | 3160,2 s |
| 23:40:25 | 306 | 23:40:24 | 1,2 s |
| 23:40:55 | 315 | 23:40:52 | 3,2 s |

`data_valid` veranderde van false naar true. De frameteller liep verder vanaf
297; het eerder bevroren tijdstip werd door nieuwe apparaatrapporten vervangen
en bleef vervolgens oplopen. De Nano hoefde niet opnieuw gestart of geflasht
te worden.

## Werkelijke Home Assistant-entiteiten en kaarten

De Mosquitto-apparaatpagina registreert om **23:40:03 CET**:

- **Reporting status: Verbonden**;
- **Report delay: `[0,150]`**;
- de offline-melding is verdwenen;
- pompstatus **Niet actief**, pomppercentage **0%**;
- actuele temperaturen: collector 9 °C, vat boven 15 °C, vat onder 14 °C,
  gemiddelde 14,5 °C;
- vatenergie **0,291 kWh**.

Om **23:42:07 CET** toonden de drie vergelijkingskaarten — Web API, ESPHome
Native en Synology EMQX — alle **Online**, actuele meetwaarden en
**Alles werkt normaal**. Web API en Native waren tijdens de uitval offline
geworden en zijn hersteld. EMQX bleef tijdens de uitval online met de
ongewijzigde transportmapping; na inschakelen toont zij weer actuele waarden.
De afzonderlijke Mosquitto-route is rechtstreeks via haar entiteiten getoetst.

Er was geen HA-herstart, providerherconfiguratie of nieuwe code nodig voor
het herstel. Vergelijking met de eerdere snapshots bevestigt dat alle
opgeslagen configuraties gelijk zijn gebleven sinds de expliciete
Mosquitto-mappingwijziging.

## Afgeronde acceptatie en resterende grens

Samen met de [uitvalproef](nanoc6-uart-outage-2026-11-17.md) en de
[Mosquitto-mappingcontrole](mosquitto-device-last-report-2026-11-17.md) zijn
het bevriezen van de apparaatrapporttijd, offline worden en automatisch
herstellen bij nieuwe geldige frames live aangetoond voor Native en MQTT.

De afzonderlijke MQTT-only-duurproef zonder Native-clients maakte geen deel
uit van deze UART-proef en is daarna
[op 18 november geslaagd](nanoc6-mqtt-only-s100-01-acceptance-2026-11-18.md).
De eerder onderzochte EMQX-herconfiguratiebeperking is niet gewijzigd.
De EMQX-expressie blijft `last_report()`; Native gebruikt
`last_report` en Mosquitto `state__last_report__sensor`.

Private bewijsbestanden staan in `work/uart-outage-20261117/` als
`power-on-recovery-observations.json` en `power-on-recovery-verification.json`.
Er is niets rechtstreeks in `.storage` geschreven en de actieve
Recorderdatabase is niet benaderd. De Mac bleef wakker.
