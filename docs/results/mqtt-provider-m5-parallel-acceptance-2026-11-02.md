# MQTT-provider M5 — parallelle acceptatie in Solesta Lab

> Publicatiekopie: installatie-, apparaat- en netwerkidentificatoren zijn
> consequent gepseudonimiseerd. Meetwaarden, tijden en uitkomsten zijn behouden.

Datum: 2 november 2026

Meetvenster: 09:51–10:00 CET

## Uitkomst

De normale parallelle route is functioneel aanvaard. Web API, ESPHome Native
en MQTT keken naar dezelfde fysieke zonneboiler en leverden gedurende het
meetvenster dezelfde genormaliseerde systeemuitkomst. Native en MQTT kwamen
op het laatste meetpunt ook exact overeen in relevante wijzigingstijd en
gewijzigde entiteiten. Verschillen in transportcadans bleven zichtbaar in de
Recorderhistorie en zijn conform het contract.

M5 heeft geen providerwissel, broker-/publisheruitval of reconnectproef
uitgevoerd. Die handelingen blijven M6 en vereisen opnieuw expliciete
toestemming.

## Omgeving en identiteit

| Onderdeel | Waarde |
| --- | --- |
| Home Assistant | 2026.10.4 |
| Solesta Lab | 0.2.6, build `51e7fce38228` |
| Broncommit | `cfd275d9fa7b77c4db2b33ccd961d72394b726b9` |
| Productie-integratie | ongewijzigd op 0.2.3 |

De integratiepagina bevestigde drie afzonderlijke hubs en apparaten:

| Provider/hub | Bronsysteem | Entiteiten |
| --- | --- | ---: |
| Web API — `lab-web-api` | `sol_0217181ef299` | 21 |
| ESPHome Native — `lab-esphome-native` | `02_b6_a2_14_14_16_uart1` | 21 |
| MQTT — `lab-mqtt` | `nanoc6_01` | 21 |

Home Assistant rapporteerde 3 apparaten en 63 entiteiten totaal. De drie
systemen bleven dus identiteits- en entiteitsmatig gescheiden. De bestaande
handmatig geconfigureerde MQTT-bron leverde na de herstart direct geldige
states voor alle verplichte fabrieksexpressies; er is tijdens M5 geen
configuratieformulier opnieuw opgeslagen.

## Genormaliseerde waarden

Op het laatste volledige vergelijkingspunt toonden alle drie apparaten:

| Entiteit | Web API | Native | MQTT |
| --- | ---: | ---: | ---: |
| Collectortemperatuur | 14 °C | 14 °C | 14 °C |
| Temperatuur boven in vat | 16 °C | 16 °C | 16 °C |
| Temperatuur onder in vat | 16 °C | 16 °C | 16 °C |
| Watertemperatuur vat | 16,0 °C | 16,0 °C | 16,0 °C |
| Pomp-PWM | 0% | 0% | 0% |
| Vatenergie | 0,465 kWh | 0,465 kWh | 0,465 kWh |
| Vatenergie | 1,6744 MJ | 1,6744 MJ | 1,6744 MJ |
| Vatenergie in douches | 0,38 | 0,38 | 0,38 |

Alle kaarten toonden `Online`, `Stand-by`, `LIVE`, nul volledige standaard-
douchebeurten en afgerond 0,47 kWh / 1,67 MJ. Tijdens het navigeren liep de
collector van 13 naar 14 °C. Incidenteel liep één provider één meetstap voor;
de volgende reportcyclus trok dit gelijk zonder afwijkende afleiding.

## Reports en updates

Aan het einde van het venster toonden alle drie kaarten hetzelfde zichtbare
reportvenster: 09:58:03–10:00:33. De reports bleven dus op alle routes
doorlopen.

Native en MQTT toonden op hetzelfde moment exact:

- laatste relevante wijziging 09:57:56;
- gewijzigde velden: watertemperatuur vat, temperatuur onder in vat,
  vatenergie in kWh, vatenergie in MJ en vatenergie in douches.

Web API toonde 09:58:25 met collectortemperatuur. Dat verschil past bij de
pollcadans en bij de bewust ingestelde Web API-source-expression die het ruwe
bronveld `last_update` gebruikt. Het is geen afwijkende Native/MQTT-
observatieregel.

## Historie en kaartgedrag

De daggrafieken eindigden alle op 16,0 °C en bewogen in dezelfde temperatuur-
band. De eventdichtheid verschilde zoals verwacht:

- Web API vormde pollstappen;
- Native vormde losse state-events;
- MQTT liet de hogere dichtheid van afzonderlijke topicberichten zien.

De zevendaagse weergave werkte voor alle drie apparaten. Web API en Native
hadden al een volledige week Recorderhistorie; MQTT bevatte alleen de dagen
sinds de latere ingebruikname. Er werd geen historie van een ander apparaat
geleend. De kaart bleef bij alle drie systemen groen en toonde de correcte
hub-/systeemidentiteit.

## M5-hercontrole na correctie van de MQTT-import

Het HA-log bevatte bij de oorspronkelijke M5-herstart geen Solesta Lab-fout,
maar wel een groep van drie eenmalige blocking-I/O-waarschuwingen om 09:34:43.
De traceback wijst naar `custom_components/solesta_lab/mqtt.py:210`:

```text
from aiomqtt import Client, ProtocolVersion
```

Deze lazy import wordt vanuit `MqttProvider._run()` binnen de eventloop
uitgevoerd. `importlib.metadata` deed daarbij onder meer `listdir` en
`read_text` op de Python-packagegegevens. De waarschuwing is na de eerste
clientaanmaak niet herhaald en de MQTT-provider bleef normaal werken.

Daarnaast meldde Home Assistant om 09:35:10 een algemene waarschuwing dat
meerdere integraties hun setup na een minuut nog niet hadden voltooid; daarin
stonden ook de drie Solesta Lab-config entries. Alle drie zijn daarna geladen
en bleven gedurende M5 online.

De functionele M5-acceptatie bleef geldig. Na M5 is de broncode gecorrigeerd:
`aiomqtt` wordt nu geladen wanneer de MQTT-module wordt geïmporteerd, en zowel
de integratie-initialisatie als de configuratieflow laden de MQTT-provider op
moduleniveau. `MqttProvider._new_client()` gebruikt uitsluitend de vooraf
geladen client en protocolversie. Een regressietest maakt de client aan in een
actieve eventloop en controleert dat daarbij geen nieuwe `aiomqtt`-import
plaatsvindt. De HA-contracttests voor 2026.9.0 en 2026.10.4 slagen.

De live hercontrole is op 2 november 2026 om 12:44–12:48 CET uitgevoerd:

| Onderdeel | Waarde |
| --- | --- |
| Nieuwe Solesta Lab-build | `c67c6ed260e1` |
| SHA-256 canonieke componentboom | `c67c6ed260e1c326c6948675181052e66f47895936ce2e4edfd77ca53b643c4c` |
| Codeplaatsing voltooid | 12:44:55 CET |
| HA-herstart | rond 12:45 CET via de native Companion-app |
| Companion-herstart | app volledig gestopt, `isRunning: false` bevestigd, daarna opnieuw gestart |

Na de herverbinding toonden Web API, ESPHome Native en MQTT alle drie
`Alles werkt normaal`, de juiste hub-/systeemidentiteit en een actuele
rapporttijd. De drie routes stonden eerst gelijk op 12:46:11 en liepen daarna
gezamenlijk door tot 12:48:20. Daarmee waren ook de MQTT-verbinding en de drie
parallelle provider-routes na de HA-procesherstart actief.

Het HA-log bewaart de oorspronkelijke blocking-I/O-groep als historische
melding. De details tonen na de nieuwe herstart nog steeds exact drie
gebeurtenissen, met zowel `Eerst voorgekomen` als `Laatst gelogd` op 09:34:43.
Er is dus rond 12:45 geen vierde gebeurtenis en geen nieuw laatste tijdstip
ontstaan. Ook de algemene setupwaarschuwing bleef op 09:35:10 staan. Daarmee
is live bevestigd dat de MQTT-import niet meer vanuit de actieve eventloop
plaatsvindt.

De enige andere zichtbare loggroep was een productie-Web-API-fout van
`custom_components.solesta.coordinator`, voor het laatst gelogd om 12:40:30,
dus vóór deze herstart. Er was geen nieuwe Solesta Lab-fout of -waarschuwing.

## Mutatiegrens

Tijdens M5 en de hercontrole zijn geen hubs, systemen, source-expressions,
entiteiten of dashboardconfiguraties gewijzigd. `.storage` en de
Recorderdatabase zijn niet rechtstreeks geopend of aangepast. Alleen de
componentboom `custom_components/solesta_lab` is vervangen. De 51
bronbestanden zijn bytegelijk aan build `c67c6ed260e1`; de productiecomponent
bleef bytegelijk aan de nulmeting. De vorige labbuild `51e7fce38228` blijft
volledig herstelbaar in
`work/deployment-20261102-m5-import-fix/solesta_lab-51e7fce38228-before`.
