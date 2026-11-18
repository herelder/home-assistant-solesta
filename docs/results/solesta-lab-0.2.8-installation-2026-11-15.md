# Solesta Lab 0.2.8 — installatie en herconfiguratie

Datum: 15 november 2026, Europe/Amsterdam (CET)

Status: geïnstalleerd en gecontroleerd. Alle vier labsystemen zijn bewust
geherconfigureerd en na live validatie weer geactiveerd. HA en Companion zijn
in de opgedragen volgorde herstart. Er is niet gecommit.

## Pakket en voorcontrole

| Onderdeel | Waarde |
| --- | --- |
| Home Assistant | 2026.11.1 |
| Productie-Solesta | 0.2.3, programmabestanden en configuratie ongewijzigd |
| Oude labversie | 0.2.7, build `58f5834a4ca6` |
| Nieuwe labintegratie en kaart | 0.2.8 |
| Nieuwe labbuild | `c17cd0b42797` |
| Installatiedoel | `/config/custom_components/solesta_lab` |
| Plaatsing voltooid | 10:25:42 CET |
| Alle labsystemen uitgeschakeld | 10:28:40 CET |
| Companion volledig afgesloten en opnieuw geopend | bevestigd om 10:31:06 CET |

De afzonderlijke labbronkopie gebruikt versie 0.2.8; de canonieke
releasekandidaat blijft 1.0.0. Het pakket bevat het nieuwe `null()`-contract,
de mogelijkheid een MQTT-systeem of kopie uitgeschakeld zonder geslaagde live
bronvalidatie op te slaan, en foutmeldingen bij de betrokken expressievelden.
De uitleg van een spatie tegenover een leeg expressieveld is bijgewerkt.
Er is geen automatische migratie van bronexpressies en geen `optional()`-alias.

De voorbereidende controles slaagden: 303 Python-tests, 33 kaarttests,
30 HA-contracttests op zowel HA 2026.9.0 als 2026.10.4, generatorcontrole,
Ruff en whitespacecontrole. Daarnaast slaagden 104 modeltests op het
daadwerkelijke 0.2.8-labpakket. De acht geplande expressiewijzigingen zijn
vooraf gecompileerd tegen de opgeslagen gevalideerde bronvelden van de vier
systemen.

## Herstelpad

Vooraf is via de native HA-app een automatische back-up gemaakt. De interface
bevestigde **Back-up gemaakt** en een geslaagde back-up op één opslaglocatie.
Het aantal automatische back-ups nam toe van twee naar drie.

De oude 51 programmabestanden zijn bytegelijk buiten de live share bewaard in
`work/deployment-20261115-null-validation/solesta_lab-0.2.7-before`.
Daarnaast staat de vervangen oude labmap onder
`/config/.solesta_lab-previous-20261115-58f5834a4ca6`. Alle 51 nieuwe
programmabestanden zijn na de directorywissel bytegelijk gecontroleerd.
De nulmeting, hashes en installatiegegevens staan in dezelfde lokale werkmap
in `deployment.json`; `systems-before.json` bewaart de oude systeemexpressies
zonder providercredentials. Na herconfiguratie vergt teruggaan naar 0.2.7 ook
herstel van die expressies via de configuratieflow, omdat 0.2.7 het nieuwe
`null(veld)`-contract niet ondersteunt. De HA-back-up biedt een volledig
herstelpad; alleen oude programmabestanden terugplaatsen is dan onvoldoende.

## Volgorde van uitvoering

Na de plaatsing zijn alle vier systemen via hun configuratieformulier
uitgeschakeld: ESPHome Native, MQTT via Mosquitto, MQTT via EMQX en Web API.
Een read-only controle bevestigde dat alle vier uitgeschakeld waren en dat
hun expressies en permanente systeemidentiteiten nog exact gelijk waren aan
de nulmeting. Pas daarna is HA via de native app herstart.

Zodra **Je hebt geen verbinding meer** verscheen, is Companion via **Stop
Home Assistant** volledig afgesloten. De appinventaris bevestigde dat de app
niet meer draaide. Daarna is Companion opnieuw geopend. De integratiepagina
toonde na de herstart **Versie 0.2.8**, vier apparaten en 84 entiteiten.

De Mac-bediening liep vervolgens langdurig vast bij een poging de app via
Dock te activeren. Na herstel was HA bereikbaar en stonden de systemen nog
uit. Tekstinvoer koos daarna niet betrouwbaar het bedoelde formulieronderdeel.
De onopgeslagen pogingen zijn geannuleerd; een veiligheidscontrole heeft
verdere onbetrouwbare invoer geblokkeerd. De gebruiker is gevraagd de twee
expressies per systeem handmatig op te slaan, met de systemen nog uit.

De gebruiker heeft vervolgens uitsluitend ESPHome zelf aangepast en de
Companion-app op de linkerhelft van het scherm gezet. Op diens verzoek zijn
de overige drie opnieuw via de app bediend. Met een zichtbare veldfocus,
gerichte tekstselectie en controle van de complete formulierinvoer vóór
opslaan lukte dat. ESPHome, Mosquitto en Web API zijn na controle en live
validatie ingeschakeld; EMQX volgde na de hieronder beschreven hercontrole.

## Expliciete herconfiguratie

Per systeem zijn uitsluitend de volgende twee expressies gewijzigd:

| Entiteit | Oude expressie | Nieuwe expressie |
| --- | --- | --- |
| `state_pump` | `optional(perc_pump_pwm > 0)` | `null(perc_pump_pwm) > 0` |
| `alerts_system` | `solar_thermal_alerts(optional(status_reporting, state_pump, temp_collector, temp_tank_top), 90, 200, 10, 10)` | `solar_thermal_alerts(null(status_reporting, state_pump, temp_collector, temp_tank_top), 90, 200, 10, 10)` |

`null(perc_pump_pwm > 0)` is geen geldige vervanging: een argument van
`null()` moet één veld zijn of een expressie zonder velden. Daarom blijft de
vergelijking buiten de functie. Alle overige expressies blijven letterlijk
behouden, inclusief het Web API-bronveld `last_update`.

Een read-only vergelijking met de nulmeting bevestigt voor alle vier systemen:

- ingeschakeld en gevalideerd tegen de huidige hub en providerrevisie;
- exact de twee bovenstaande expressiewijzigingen, geen overige wijzigingen
  aan expressieteksten en nergens een resterende vervallen functieaanroep;
- behoud van hub-UID, systeem-UID, systeem-ID en bron-systeem-ID.

## EMQX-validatie

De eerste twee opslagpogingen in het uitgeschakelde EMQX-systeem werden door
live validatie afgewezen. De meldingen **Een vereiste bronwaarde van de
provider ontbreekt** stonden bij de drie temperatuurvelden en het
pomppercentage; er is toen niets opgeslagen of geactiveerd.

Een tijdelijke alleen-lezen MQTT-subscriptie met een eigen client-ID bevestigde
vervolgens dat beide brokers de verwachte Nano-topics leverden, waaronder
`sensor/temperature_1_raw/state` tot en met temperatuur 4 en
`sensor/pump_raw/state`. De eerste verbinding vanaf de Mac mislukte voor beide
brokers; de tweede slaagde. Er is niets gepubliceerd of aan de brokers gewijzigd.

Daarna is de systeemvalidatie ook rechtstreeks met het voorbereide,
bytegelijk geïnstalleerde labpakket uitgevoerd. EMQX leverde alle vier vereiste
canonieke bronvelden; geen vereist veld ontbrak en de evaluator gaf geen
fout. De gemeten waarden waren op dat moment 37, 15 en 15 °C en 0% pomp.
Dezelfde twee expressies zijn opnieuw in het HA-formulier ingevoerd. Nu
slaagden zowel het opslaan als de afzonderlijke activering. De oorzaak van de
eerdere tijdelijke validatiefout is hiermee niet vastgesteld; er is geen
code- of configuratiewijziging gedaan om deze te omzeilen.

## Eindcontrole

- Alle vier opgeslagen systemen zijn ingeschakeld en hebben actuele
  validatiestempels. De drie vergelijkingskaarten tonen **v0.2.8**, **Online**,
  actuele meetwaarden en **Alles werkt normaal**. Ook de lokale alert
  **Collector warm maar pomp uit** wordt weergegeven; een normale
  rapportagestatus betekent niet dat de alertlijst leeg is.
- Het Mosquitto-apparaat is afzonderlijk bekeken: collectortemperatuur 36 °C,
  vat boven en onder 15 °C, gemiddelde vattemperatuur 15,0 °C, pomppercentage
  0%, rapportagevertraging `[0,150]` en rapportagestatus **Verbonden**.
- Productie-Solesta toont **v0.2.3**, **Online** en actuele metingen.
  De programmabestanden en de complete opgeslagen productie-config-entry
  komen overeen met hun SHA-256-nulmeting.
- Het vernieuwde Core-log bevat geen Solesta- of Solesta Lab-fout. Er staat
  wel een HA-frontendmelding over `_showVoiceCommandDialog` en
  `this.hass.config.components`: twee gebeurtenissen om 11:50:14, tijdens
  de eerdere problematische appbediening. Deze melding is niet gewist.
- Het labdashboard is circa 12:11 CET geopend achtergelaten in Companion.

Dit is een installatie-, herconfiguratie- en statuscontrole, geen volledige
herhaling van de productie-upgrade-, providerwissel- of historieacceptatie.
Er is niet gecommit. `.storage` is uitsluitend read-only gecontroleerd; de
actieve Recorderdatabase is niet geopend of gekopieerd.
