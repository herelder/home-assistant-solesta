# NanoC6 — fysieke uitvalproef met blijvend ingeschakelde Nano

Datum: 17 november 2026. Alle lokale tijden zijn CET, Europe/Amsterdam.

Status: uitval via Web API en Native bevestigd. Daarna is op gebruikersopdracht
ook de Mosquitto-route naar apparaatrapporttijd omgezet en offline bevestigd.
Ook het [herstel na inschakelen](nanoc6-uart-recovery-2026-11-17.md) is bevestigd.
De eerder gevraagde EMQX-wijziging is niet opgeslagen.

## Opstelling en waarnemingen

De gebruiker heeft de Solesta-controller uitgezet en de Nano laten aanstaan.
De Nano draait firmware 0.1.2; de drie vergelijkingskaarten draaien Solesta
Lab 0.2.9. Native gebruikt bronveld `last_report`. EMQX gebruikt bij aanvang
nog de functie `last_report()`. De Web API-mapping gebruikt `last_update`.

Een versleutelde, alleen-lezen Native-subscriptie volgde de apparaatvelden.
Deze client leverde geen tijd en stuurde geen opdrachten. Het laatste
apparaatrapport bleef `2026-11-17T21:47:15Z`, lokaal **22:47:15**. Frame sequence
en valid frame count bleven beide **297**. `data_valid` was false; `data_age`
liep door. Om 22:58:20 was de rapporttijd 665 seconden oud en nog ongewijzigd.
Een tweede observatie liep tot 23:01:06, eveneens zonder nieuwe frames.

| Route | Waargenomen reactie |
| --- | --- |
| Web API | Kaart meldde **Systeem offline**, statuswijziging **22:57:14** |
| ESPHome Native | Kaart meldde **Systeem offline**, statuswijziging **22:57:23**; 608 seconden na de apparaatrapporttijd |
| EMQX met oorspronkelijke mapping | Bleef **Online / Alles werkt normaal** terwijl diagnostisch MQTT-verkeer doorging |

Om 22:56:47 toonden de drie kaarten nog normale status. Om 22:57:26 waren
Web API en Native offline; hun actuele temperatuur en energie werden als
streepjes weergegeven en de offline-melding was zichtbaar. EMQX hield de
laatste meetwaarden en bleef online. De Native-overgang valt binnen de
bestaande grens van 600 seconden plus de eerstvolgende systeemupdate.

Dit bevestigt dat de Native-rapportage nu de ouderdom van geldige
apparaatframes volgt, onafhankelijk van doorlopende Nano-diagnostiek.
Het is geen MQTT-only-duurproef: de Native-integratie en een observatieclient
waren verbonden.

## Aanvullende EMQX-opdracht en huidige beperking

De gebruiker vroeg vervolgens de Solesta uit te laten en eerst ook EMQX aan
de apparaatrapporttijd te koppelen. Vooraf zijn een credentialvrije snapshot
van de systeemconfiguratie en hashes van de volledige bestaande entries
vastgelegd. Herstelpad is de normale configuratieflow: uitsluitend de
rapportage-expressie terugzetten naar `last_report()`.

Het juiste MQTT-bronpad is `sensor/last_report/state`, met canonieke
expressienaam **`state__last_report__sensor`**. Om 23:06:00 leverde de direct
door de Nano gebruikte broker dit veld retained met waarde
`2026-11-17T21:47:15Z`, samen met retained temperatuur- en pompvelden.
Een nieuwe EMQX-subscriptie onder de bestaande systeemroot ontving tijdens
de uitval alleen `sensor/data_age/state`, zonder retained replay van deze
meetvelden. Er is niets naar een broker gepubliceerd of aan een broker
gewijzigd. De oorzaak in de brokerroute is niet nader vastgesteld.

In de normale HA-flow is uitsluitend de rapportage-expressie ingevoerd.
De opslagpoging werd door live validatie afgewezen met **Een vereiste
bronwaarde van de provider ontbreekt**. Een read-only vergelijking bevestigt
dat alle opgeslagen Solesta- en Solesta Lab-entries nog bytegelijk zijn aan
de nulmeting van deze wijzigingspoging. Er is geen gewijzigde mapping opgeslagen.

De gebruiker heeft vervolgens gevraagd de Solesta uit te laten en eerst deze
beperking te onderzoeken. De onopgeslagen formulierpoging is gesloten.
De oorzaak en het benodigde herstel van het configuratiepad staan in het
[aanvullende onderzoek](mqtt-reconfiguration-during-source-silence-2026-11-17.md).
EMQX offline na de nieuwe mapping is geen bewezen resultaat. Op de
daaropvolgende gebruikersopdracht is de
[Mosquitto-mapping wel gewijzigd en offline bevestigd](mosquitto-device-last-report-2026-11-17.md),
terwijl de Solesta uit bleef. Daarmee is de bedoelde uitvalwerking ook via MQTT
in de werkelijke HA-entiteiten aangetoond.

Na weer inschakelen van de Solesta is ook het
[automatische herstel](nanoc6-uart-recovery-2026-11-17.md) bevestigd.

Private observatiebestanden staan in de genegeerde werkmap
`work/uart-outage-20261117/`. De actieve Recorderdatabase is niet benaderd;
`.storage` is uitsluitend gelezen. De Mac bleef tijdens de proef wakker.
