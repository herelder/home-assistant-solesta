# Empirische acceptatie ESPHome M5Stack NanoC6

Datum analyse: 21 oktober 2026
Aanvullende WAN-isolatietest: 22 oktober 2026, ongeveer drie uur
Waargenomen meetvenster: 18 oktober 2026 22:00 tot 21 oktober 2026 23:15,
ongeveer 73 uur en 15 minuten
Resultaat: de seriele brug en parser zijn functioneel geaccepteerd; de
betekenis van `temperature_4_raw` en `flow_raw` blijft bewust onbewezen

## Doel en methode

Dit verslag sluit de open empirische acceptatiepunten uit hoofdstuk 10 van
het ontwerp voor de ESPHome-provider. De opgebouwde ESPHome-entiteiten zijn
in de native Home Assistant-app onderzocht via Geschiedenis en Activiteit.
Waar een bestaande Solesta-Web-API-entiteit beschikbaar was, zijn beide
reeksen in hetzelfde tijdvenster vergeleken.

De geschiedenisselectie in Home Assistant liep technisch door tot 22 oktober
2026 01:00. De analyse werd op 21 oktober omstreeks 23:15 afgesloten; de nog
toekomstige 1 uur en 45 minuten is daarom geen onderdeel van het waargenomen
meetvenster.

De bekende werkzaamheden met een of meer korte stroom- of
verbindingsonderbrekingen zijn niet als spontane firmwarefout aangemerkt.
Wel is afzonderlijk gecontroleerd of een onderbreking de tellers reset of de
seriele datageldigheid aantastte.

## Samenvatting acceptatiepunten

| Punt | Waarneming | Uitkomst |
| --- | --- | --- |
| Minimaal 24 uur zonder onverwachte reboot, framing- of bufferfout | `frame_sequence` en `valid_frame_count` stonden beide op `84631`; `rejected_record_count` bleef `0`; de actuele tellerstand vertegenwoordigt bij circa 3,0 tot 3,1 seconden per frame ruim 70 uur | geslaagd |
| Natuurlijke Z-overgang vult code en tekst | meerdere volledige cycli met synchroon gepubliceerde code en tekst; `controller_state_count=94` | geslaagd |
| Fractionele pompwaarde in de definitieve opstelling | naast `0.000000` en `1.000000` zijn onder meer `0.748993`, `0.746185` en `0.743377` geregistreerd | geslaagd |
| Temperatuurvelden vergelijken met betrouwbare waarneming | `T1`, `T2` en `T3` volgen respectievelijk de bestaande collector-, tank-boven- en tank-onderentiteit; waarden en verloop komen overeen, met de verwachte grovere Web-API-bemonstering | geslaagd voor `T1`-`T3` |
| Betekenis en eenheid `flow_raw` en `temperature_4_raw` | `flow_raw` bleef ook bij pompbedrijf exact `0`; `temperature_4_raw` bleef exact `309`; er is geen bruikbare Web-API-tegenhanger | onderzocht, maar semantiek niet bevestigd; flow buiten Solesta houden en bestaand T4-contract ongewijzigd laten |
| Beschikbaarheid en diagnostiek aan praktijk toetsen | `data_valid` bleef verbonden en `data_age` lag vrijwel steeds tussen 0 en circa 3,1 seconde, met een korte piek onder 4 seconden; de 15-secondenlimiet heeft ruime marge | beschikbaarheidscontract geslaagd; recorderbelasting verdient aanpassing |
| Werking zonder internet | internettoegang van zowel de NanoC6 als de Solesta-installatie was ongeveer drie uur geblokkeerd; de Web API rapporteerde het systeem correct als offline, terwijl de NanoC6 lokaal metingen bleef ontvangen en via ESPHome Native aan Home Assistant bleef leveren | geslaagd; de lokale meetroute is WAN-onafhankelijk |

## Parserstabiliteit en beschikbaarheid

Om 23:15:55 stonden `frame_sequence` en `valid_frame_count` beide op
`84631`. Omdat beide tellers bij iedere boot expliciet op nul worden gezet en
bij elk geldig statusframe samen oplopen, bewijst deze stand een doorlopende
actuele bootperiode van ruim meer dan 24 uur. Er is geen verschil tussen beide
tellers ontstaan. `rejected_record_count` bleef in het gehele onderzochte
venster `0`.

`data_age` vertoonde het verwachte zaagtandpatroon tussen opeenvolgende
statusregels: meestal ongeveer 0 tot 3,1 seconde, incidenteel kort hoger maar
nog onder 4 seconden. De actuele waarde tijdens de controle was 1,6 tot 1,9
seconde. `data_valid` bleef daardoor verbonden en kwam niet in de buurt van de
grens van 15 seconden.

Home Assistant registreerde op enkele momenten wel kort `Niet beschikbaar`
voor de ESPHome-entiteiten. Een deel daarvan viel samen met de bekende
onderbrekingen. Daarnaast was er vanaf 20 oktober 20:44 een opvallend patroon
met korte terugkeer rond intervallen van zes uur. Dit zijn geen aangetoonde
NanoC6-reboots: de tellerwaarden werden niet op nul gezet, de geldige
frameteller bleef doorlopen en de seriele `data_valid`-reeks bleef geldig. Het
verschijnsel hoort daarom voorlopig bij de native-API-/Home-Assistantlaag en
niet bij parserframing of UART-ontvangst. Het verdient observatie, maar
blokkeert de providerimplementatie niet.

## WAN-onafhankelijkheid

Op 22 oktober 2026 is de internettoegang van zowel de NanoC6 als de
Solesta-installatie gedurende ongeveer drie uur geblokkeerd. De lokale
netwerkverbinding tussen NanoC6 en Home Assistant bleef beschikbaar.

De bestaande Web API-integratie rapporteerde het Solesta-systeem in deze
periode zoals verwacht als offline. Tegelijk bleef de NanoC6 zonder
onderbreking seriele metingen ontvangen en deze via de lokale ESPHome Native
API aan Home Assistant leveren.

Daarmee is bewezen dat de meetketen Solesta-controller naar NanoC6 naar lokaal
Home Assistant geen internetverbinding nodig heeft. De proef omvat geen
uitval van lokaal wifi, LAN of Home Assistant zelf. In de provider moeten de
beschikbaarheid van Web API en ESPHome Native daarom volledig gescheiden
blijven: een cloudstoring mag een lokaal geldige ESPHome-bron niet offline
maken.

## Controllerstatus

Code en tekst werden vanuit natuurlijke Z-regels consequent als paar
gepubliceerd. De waargenomen mapping is:

| Code | Tekst |
| ---: | --- |
| `0` | `Initial State SOLESTA` |
| `1` | `Ready State SOLESTA` |
| `2` | `Startup State` |
| `3` | `Run State` |
| `4` | `Pause State` |

Een representatieve cyclus op 20 oktober was:

| Tijd | Code | Tekst |
| --- | ---: | --- |
| 14:11:30 | 1 | `Ready State SOLESTA` |
| 14:11:41 | 2 | `Startup State` |
| 14:12:42 | 3 | `Run State` |
| 14:12:52 | 4 | `Pause State` |
| 14:17:52 | 1 | `Ready State SOLESTA` |

Een tweede volledige cyclus volgde direct daarna. De teller bereikte `94`.
Hiermee zijn zowel het Z-recordcontract als de twee zichtbare Home
Assistant-entiteiten bewezen. De bestaande Solesta-integratie heeft in release
0.2.3 geen rechtstreekse tegenhangers voor controllercode of -tekst.

Dit bewijst de ESPHome-brondata, maar leidt in de eerste provider niet tot
nieuwe Solesta-entiteiten. Controllercode en -tekst blijven voorlopig buiten
de Solesta-entiteitscatalogus. Later wordt beoordeeld of hun betekenis in een
reeds bestaande Solesta-entiteit kan worden verwerkt.

## Pompvergelijking

De permanente opstelling registreerde op 20 oktober meerdere pompruns. In een
representatieve afloop verschenen achtereenvolgens:

```text
1.000000 -> 0.748993 -> 0.746185 -> 0.743377 -> 0.000000
```

De bestaande `Pump PWM percentage`-entiteit uit de Web API toont in hetzelfde
tijdsvenster pompbedrijf en bereikt `100%`. De ESPHome-reeks registreert
daarnaast de korte fractionele afloop, die door de grovere Web-API-bemonstering
niet steeds zichtbaar is. De providerconversie is daarom:

```text
perc_pump_pwm = pump_raw * 100
```

De firmware moet de bronfractie ongewijzigd blijven publiceren.

## Temperatuurvergelijking

De drie bruikbare temperatuurreeksen zijn over hetzelfde meerdaagse venster
naast de bestaande Solesta-entiteiten gelegd.

| ESPHome-bron | Bestaande Solesta-entiteit | Bevinding |
| --- | --- | --- |
| `temperature_1_raw` | `Collector temperature` (`temp1`) | zelfde waarden en dagprofiel; snelle stijging bij zon en sterke nachtelijke daling; Web API volgt met pollingvertraging |
| `temperature_2_raw` | `Tank top temperature` (`temp2`) | zelfde waarden en langzame tankrespons |
| `temperature_3_raw` | `Tank bottom temperature` (`temp3`) | zelfde waarden en langzame tankrespons |
| `temperature_4_raw` | `Unused temperature` (`temp4`, standaard uitgeschakeld en verborgen) | geen bruikbare vergelijking; ESPHome bleef exact `309`, terwijl de Web API het gereserveerde veld niet vult |

Voor de ESPHome-provider mogen `T1`, `T2` en `T3` dus rechtstreeks als graden
Celsius naar de bestaande drie temperatuurvelden worden gemapt. Een extra
schaalfactor is niet nodig. `T4=309` mag nadrukkelijk niet als `30,9 °C` worden
geinterpreteerd. De bestaande, standaard uitgeschakelde en verborgen
Solesta-entiteit voor `temp4` blijft ongewijzigd bestaan; deze meting geeft
geen aanleiding voor een nieuwe naam, schaal of betekenis.

## Flow en vierde temperatuurveld

`flow_raw` bleef gedurende het hele venster exact `0.0`, ook tijdens bewezen
pompbedrijf en de bijbehorende controllerovergangen. Daarmee is niet bewezen
dat dit veld een volumestroom voorstelt; het kan in deze installatie ongebruikt
of niet aangesloten zijn. De bestaande Solesta-integratie heeft geen
vergelijkbare zichtbare flow-entiteit.

`temperature_4_raw` bleef gedurende het hele venster exact `309`. Omdat de
Web API-tegenhanger gereserveerd, uitgeschakeld en ongevuld is, kan geen
betekenis, schaal of eenheid worden toegekend. Het bestaande Solesta-contract
voor `temp4` blijft desondanks ongewijzigd behouden.

`flow_raw` blijft uitsluitend een ruwe ESPHome-onderzoekswaarde en wordt niet
opgenomen in het bronmodel of de entiteitscatalogus van Solesta. Er komt dus
geen Solesta-flow-entiteit en ook geen semantische standaardmapping.

## Gevolgen voor firmware en provider

Er is geen functionele parsercorrectie of nieuwe flash nodig. Het bestaande
recordcontract, de grens van 15 seconden en de afzonderlijke code- en
tekstentiteit kunnen behouden blijven.

Voor de providerimplementatie is de empirisch bevestigde mapping:

| Providerdoel | ESPHome-bron | Verwerking |
| --- | --- | --- |
| collectortemperatuur | `temperature_1_raw` | rechtstreeks als °C |
| tanktemperatuur boven | `temperature_2_raw` | rechtstreeks als °C |
| tanktemperatuur onder | `temperature_3_raw` | rechtstreeks als °C |
| gereserveerd vierde temperatuurveld | `temperature_4_raw` | bestaand `temp4`-contract en bestaande zichtbaarheid ongewijzigd behouden; geen nieuwe schaal of betekenis afleiden |
| pomppercentage | `pump_raw` | maal 100 |
| rapportagebeschikbaarheid | `data_valid` plus native-API-beschikbaarheid | beide moeten geldig zijn |

`controller_state_code` en `controller_state_text` worden in de eerste
provider niet naar Solesta-entiteiten gemapt. `flow_raw` wordt evenmin in
Solesta opgenomen. `frame_sequence` blijft buiten het Solesta-bronmodel en de
entiteitscatalogus; als de ESPHome-koppeling het signaal technisch nodig heeft
voor complete-frameverwerking, mag het uitsluitend als private
transportsynchronisatie worden gebruikt en nooit als Solesta-state worden
gepubliceerd.

De praktijkmeting laat wel een recorder- en logboekrisico zien. Bij ongeveer
een statusframe per drie seconden veroorzaken `frame_sequence` en
`valid_frame_count` samen circa 57.600 statewijzigingen per etmaal.
`data_age` voegt bij een interval van vijf seconden nog circa 17.280 updates
toe. `valid_frame_count` bleek bovendien steeds identiek aan
`frame_sequence`.

Aanbevolen voor de productieroute:

- maak van `frame_sequence` geen Solesta-entiteit of Recorder-state;
- neem ook `valid_frame_count`, `data_age` en `last_valid_status_line` niet op
  als reguliere Solesta-entiteiten; houd noodzakelijke technische informatie
  intern of maak haar standaard uitgeschakelde diagnostiek;
- behoud `data_valid` en `rejected_record_count` als laagvolume
  storingsdiagnostiek;
- houd `controller_state_count`, code en tekst buiten de eerste
  Solesta-entiteitsset totdat vaststaat of controllerstatus in een bestaande
  Solesta-entiteit thuishoort.

Dit is een opslag- en presentatieregel, geen reden om de nu stabiele parser of
de live firmware vóór de providerimplementatie te vervangen.

## Eindbesluit

De M5Stack NanoC6-opstelling is empirisch geschikt als bron voor de nieuwe
ESPHome-provider. Alle functionele acceptatiepunten zijn uitgevoerd. De
betekenisproef voor `T4` en `F` leverde bewust geen semantische mapping op;
dat is een begrensde uitkomst en geen parserfout. De eerste
providerimplementatie normaliseert `T1`, `T2`, `T3` en pomp, behoudt het
bestaande gereserveerde T4-contract, houdt flow buiten Solesta en maakt nog
geen Solesta-entiteiten voor controllerstatus. `frame_sequence` wordt evenmin
een Solesta-state. De ESPHome-route blijft bij wegvallend internet lokaal
beschikbaar en wordt niet afhankelijk gemaakt van de status van de Web API.
