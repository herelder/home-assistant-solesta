# D-ESP-006 — Universele lokale afleiding van pomp- en systeemdiagnostiek

Datum: 24 oktober 2026; aangescherpt tot en met 30 oktober 2026

Status: aanvaard en geïmplementeerd; regressieacceptatie voor fase 6

Aanscherping op 27 oktober 2026: [D-ESP-007](0007-provider-independent-expressions-and-optional-evaluation.md)
legt de catalogus als enige bron van fabrieksexpressies vast. De actuele
invoerfunctie is uitgewerkt in [D-ESP-014](0014-null-fields-expression-contract.md).
Geen enkele bestaande expressie wordt nog door een upgrade herschreven,
ook een vroegere fabrieksexpressie niet. Dat vervangt de migratie- en
providerafhankelijke standaardkeuzes hieronder; de oorspronkelijke afleiding
en empirische grenswaarden blijven gelden.

Aanscherping op 29 oktober 2026:
[D-ESP-008](0008-provider-observation-and-timestamps.md) vervangt uitsluitend
de eerdere regel dat een volledige geldige meetset nodig is om `last_report`
te verversen. `last_report()` en `last_update()` worden voortaan voor Web API,
ESPHome Native en MQTT door dezelfde integratie-eigen observatielaag bepaald.
De lokale `report_delay`-, offline- en alertafleiding hieronder blijft gelden.

Aanscherping op 30 oktober 2026: integratie-eigen alertrecords bevatten geen
hardgecodeerde gebruikerszin meer. Zij dragen een stabiele vertaalsleutel en
parameters; de statuskaart gebruikt daarvoor de Home Assistant-vertalingen in
de taal van de actieve gebruiker. Vrije providerteksten blijven ongewijzigd.

## Aanleiding en verhouding tot D-ESP-004

D-ESP-004 legde al vast dat status- en alarmdiagnostiek in de universele
expression-evaluator thuishoort en niet in een provider, entiteitsplatform of
dashboardkaart. De daarin geschetste functie was nog niet geïmplementeerd en
nam `controller_state_code` en `temp_tank_bottom` als invoer aan.

Het empirische rapport *Solesta pompgedrag en lokale alertlogica*, versie 1.0
van 24 oktober 2026, maakt een smaller en beter toetsbaar contract mogelijk.
Het rapport vergelijkt bewaarde Web API-alerts met lokale meetwaarden. De drie
online regels pasten op alle bruikbare meetmomenten; de offlinegrens is minder
exact waargenomen maar reproduceerbaar als vijftien minuten sinds de laatste
geldige complete meetset.

Dit besluit behoudt het architectuurprincipe van D-ESP-004, maar vervangt de
daar voorgestelde functiesignatuur en scherpt de tijd-, alert- en
configuratiecontracten aan. Controllerstatus blijft buiten de publieke
Solesta-entiteiten en is geen invoer voor deze afleiding. Ook
`temp_tank_bottom` is voor de aangetoonde alertregels niet nodig.

## Besluit

De volgende drie bestaande entiteiten worden voor iedere provider uit reeds
genormaliseerde lokale Solesta-entiteiten afgeleid:

1. `state_pump` met een source-expression uit `perc_pump_pwm`;
2. `status_reporting` met een source-expression uit `report_delay`;
3. `alerts_system` uit `status_reporting`, `state_pump`,
   `temp_collector`, `temp_tank_top` en instelbare alarmgrenzen.

Providers leveren alleen ruwe meetwaarden en, indien aanwezig, aanvullende
bronalerts. Zij beslissen niet over de universele pomp-, rapportage- of
alertstatus. Dezelfde functies en grenswaarden worden daarom gebruikt voor de
Web API-, ESPHome Native- en eventuele latere MQTT-provider.

De afleidingsketen is:

```text
providerwaarden
    -> genormaliseerde temperaturen, pomppercentage en last_report
    -> bestaande source-expressions en delay_zone()
    -> state_pump en status_reporting
    -> solar_thermal_alerts()
    -> bestaande Solesta-entiteiten en dashboardkaart
```

## Functiecontracten

De expression-evaluator blijft alleen positionele functieargumenten
ondersteunen. De nieuwe alertfunctie is begrensd en behandelt `None` als
ontbrekende invoer. Andere ongeldige typen en niet-eindige getallen leveren
een geclassificeerde expressiefout op.

### Source-expression voor `state_pump`

```text
perc_pump_pwm > 0
```

Dit is het volledige empirische contract: `0` betekent uit en iedere waarde
groter dan `0` betekent actief. Als `perc_pump_pwm` ontbreekt, kan de
vergelijking niet worden uitgevoerd; de bestaande geclassificeerde
evaluatiefoutafhandeling publiceert voor `state_pump` dan `None`. Een aparte
functie of instelbare pompgrens voegt daarom geen betekenis toe.

### Source-expression voor `status_reporting`

Een afzonderlijke evaluatorfunctie voor rapportagestatus is niet nodig.
`report_delay` heeft de klok- en timestampnormalisatie al uitgevoerd. De
standaardexpressie daarvan blijft ongewijzigd:

```text
delay_zone(last_report, 2*60+30, 10*60)
```

Zolang de vertraging binnen een geconfigureerde zone valt, bevat
`report_delay` een zonestring. Buiten de laatste zone bevat de entiteit de
genormaliseerde timestamp van de laatste geldige rapportage. De generieke
hulpfunctie `is_timestamp()` herkent alle timestampvormen die `delay_zone()`
ondersteunt. De `status_reporting`-expressie hoeft daardoor geen zonenamen of
zonegrenzen te kennen:

```text
report_delay and not is_timestamp(report_delay)
```

Bij ontbrekende `last_report` is ook `report_delay` `None` en blijft de
binary-sensor onbekend. Bij iedere andere niet-lege waarde is hij waar; zodra
`report_delay` een timestamp bevat, is hij onwaar. De omslag blijft volledig
bepaald door de laatste inclusieve zonegrens van `delay_zone()`. Daardoor blijft
de afleiding universeel als een provider of installatie andere zonegrenzen
gebruikt.

Alleen een volledige, geldige meetset mag `last_report` verversen. Een
gedeeltelijk, ongeldig of uitsluitend technisch transportbericht doet dat
niet. Providerteksten zoals `status == "online"` en ESPHome-`data_valid`
worden niet als vervanging voor het lokale tijdscriterium gebruikt.

### `solar_thermal_alerts()`

```text
solar_thermal_alerts(
    optional_values,
    collector_hot_threshold,
    collector_danger_threshold,
    pump_idle_delta,
    pump_active_delta,
)
```

De hierboven getoonde vijfdelige labvorm is vervallen. De actuele functie
krijgt de vier lokale velden via `null(...)`, zonder bronalertargument; zie
[D-ESP-014](0014-null-fields-expression-contract.md). De onderstaande
historische uitwerking van het recordformaat blijft de onderbouwing.
De functie produceert een begrensde reeks compacte JSON-objecten met `type`,
`severity` en óf een externe `message` óf een integratie-eigen
`translation_key` met optionele `translation_placeholders`. Records worden
gescheiden met ASCII Record Separator (`U+001E`), niet met een newline. Dit
controleteken kan in geldige JSON-tekstvelden alleen escaped voorkomen, zodat
een newline in een externe `message` geen extra alertrecord kan vormen. Een
lege string betekent dat geen actuele alert bekend is. De kaart blijft voor
bestaande opgeslagen waarden ook de oude newline-scheiding lezen.

`solar_thermal_alerts()` maakt zelf geen gebruikerszin en bevat dus geen
hardgecodeerde taal. Voor lokale alerts produceert de functie uitsluitend een
stabiele vertaalsleutel en taalneutrale parameters. De kaart resolveert die via
`component.solesta.common.*` met het Home Assistant-vertaalmechanisme in de
taal van de actieve gebruiker. Alleen vrije meldingstekst die daadwerkelijk
door een provider is geleverd blijft als `message` behouden.

## Exacte alertregels

De vergelijkingen zijn bewust strikt. Gelijkheid activeert de betreffende
strengere regel niet; een lagere severity kan dan nog wel van toepassing zijn.

| Type | Voorwaarde | Severity | Vertaalsleutel |
| --- | --- | --- | --- |
| `offline` | `status_reporting is False` | `danger` | `alert_offline` |
| `collector_hot` | `temp_collector > collector_danger_threshold` | `danger` | `alert_collector_danger`, parameter `temperature` |
| `collector_hot` | anders: `temp_collector > collector_hot_threshold` | `warning` | `alert_collector_hot`, parameter `temperature` |
| `pump_idle` | `state_pump is False` en `temp_collector > temp_tank_top + pump_idle_delta` | `warning` | `alert_pump_idle` |
| `pump_active` | `state_pump is True` en `temp_collector < temp_tank_top - pump_active_delta` | `warning` | `alert_pump_active_cold` |
| `pump_active` | anders: `state_pump is True` en `temp_collector < temp_tank_top` | `info` | `alert_pump_active_cool` |

De twee regels met hetzelfde type leveren nooit twee meldingen op. De strengste
ware voorwaarde bepaalt de severity. De deltavoorwaarde van `pump_active` wordt
dus eerst getoetst; alleen binnen de ingestelde delta kan de `info`-variant
worden gekozen. Bij een delta van nul is die informatieruimte leeg en krijgt
iedere strikte onderschrijding de severity `warning`.

De offlinealert is exclusief: als `status_reporting` onwaar is, retourneert de
functie uitsluitend `offline`. Zo kunnen oude temperaturen en pompwaarden
geen aanvullende meldingen veroorzaken. Als `status_reporting` onbekend is,
worden evenmin meetwaarde-afhankelijke alerts gemaakt; de bestaande
rapportagestatus laat het dashboard dan de toestand *onbekend* tonen.

Bij actuele rapportage worden de drie overige alerttypes onafhankelijk
geëvalueerd. `collector_hot` en `pump_idle` kunnen dus tegelijk voorkomen. Een
ontbrekende invoer slaat alleen de daarvan afhankelijke regel over:

- `collector_hot` heeft alleen een geldige collectortemperatuur nodig;
- beide pomptypes vereisen daarnaast een geldige boventemperatuur en bekende
  pompstatus.

Er wordt geen hysterese of tijdvertraging aan deze drie regels toegevoegd. Het
rapport toont daarvoor geen bewijs; een nieuwe geldige meetset wist een alert
zodra de strikte voorwaarde niet meer waar is.

## Samenvoegen met bronalerts

De lokale evaluator is gezaghebbend voor de vier bekende types `offline`,
`collector_hot`, `pump_idle` en `pump_active`. Eventuele bronregels met zo'n
type worden vervangen door de lokaal berekende uitkomst. Daarmee kan een
vluchtige providerstatus geen lokale versheidscontrole overrulen.

De oude bronnaam `pump_wrong` wordt uitsluitend als compatibiliteitsalias bij
het inlezen herkend en samen met andere lokaal beheerde types onderdrukt. De
evaluator publiceert die naam nooit; de universele uitvoernaam is
`pump_active`.

Andere bronalerts blijven behouden, omdat het rapport onvoldoende basis geeft
om bijvoorbeeld `over_temp`, `freeze_risk`, `needs_refill` of `sensor_fault`
lokaal te reconstrueren. Zij worden genormaliseerd, begrensd en
gededupliceerd. Een kale niet-lege tekstregel blijft als `warning` leesbaar.

De uitvoervolgorde is stabiel: eerst de lokaal afgeleide types in de volgorde
uit de regeltabel, daarna onbekende bronalerts gesorteerd op genormaliseerd
type, severity en bericht. Duplicaten worden op type en inhoud verwijderd.
`type` en `severity` vormen het machinecontract. De dashboardkaart mag bekende
types voor presentatie vertalen; `message` blijft de terugvaltekst voor
onbekende types en oudere kaarten.

De genormaliseerde severitywoorden zijn `info`, `warning`, `error`, `danger`
en `critical`. `danger` blijft behouden voor compatibiliteit met de empirisch
waargenomen offlinepayload; het wordt voor sortering en presentatie als een
foutniveau behandeld. Een onbekende severity blijft als broninformatie
leesbaar, maar krijgt geen hogere betekenis dan `warning`.

## Alertconstanten in de source-expression

De vier alertinstellingen zijn geen Home Assistant-entiteiten. De canonieke
`alerts_system`-expressie bevat achtereenvolgens de constante waarden 90 °C,
200 °C, 10 K en 10 K. Een gebruiker kan ze alleen wijzigen door de
`alerts_system`-source-expression tijdens systeemconfiguratie of
herconfiguratie te bewerken.

De basisvoorwaarden voor de waarschuwing en pomplogica reproduceren de in het
rapport vastgestelde Web API-logica. Voor `pump_active` wordt die bestaande
voorwaarde nu als `info` geclassificeerd. De standaarddelta van 10 K maakt de
nieuwe `warning`-escalatie betekenisvol; een gebruiker kan haar vanwege andere
sensorplaatsing of meetruis in de source-expression aanpassen. Een expliciete
nul laat beide voorwaarden samenvallen en classificeert iedere strikte
onderschrijding als `warning`.

Er bestaat geen natuurkundig of normatief absoluut maximum dat voor ieder type
zonnecollector geldig is. ISO 9806:2025 omvat uiteenlopende vloeistof-, lucht-
en concentrerende collectoren en schrijft testmethoden voor, maar bewust geen
algemene productgrens. Niet-concentrerende collectoren kunnen bij stagnatie
rond 250 °C bereiken; concentrerende technieken kunnen bedrijfstemperaturen
rond 400 °C bereiken. Daarom is de dangergrens wel universeel in de betekenis
*provider-onafhankelijk*, maar niet bedoeld alsof één temperatuur voor ieder
product een absolute natuurkundige limiet is. De fabrieksconstante is 200 °C:
hoog genoeg om normale stilstand- en drainbacktemperaturen niet als
gevaar te classificeren, maar met marge onder de door Solesta voor de
Silverline-vacuümcollector gepubliceerde stagnatietemperatuur van 221 °C. De
standaard is daarmee een vroegtijdige dangergrens voor de beoogde
huishoudelijke zonneboilerklasse, geen universeel kookpunt of productmaximum.
Zie de scope en productbenadering van
[ISO 9806:2025](https://www.iso.org/standard/78801.html), de door Solar Heat
Europe beschreven bereiken voor
[niet-concentrerende collectoren](https://solarheateurope.eu/wp-content/uploads/2017/07/Solar_thermal_SRP.pdf)
en [concentrerende technieken](https://solarheateurope.eu/market/our-technologies/concentrated-technologies/),
en de [Solesta-installatiehandleiding](https://www.solesta.nl/wp-content/uploads/2015/08/10_Installatiehandleiding.pdf).

De source-expressioncompiler vereist vier eindige numerieke constante
expressies. Hij valideert tijdens (her)configuratie dat de dangergrens groter
is dan de waarschuwingsgrens en dat beide pompdelta's niet negatief zijn. De
runtimefunctie en de generieke Number-entiteit bevatten hiervoor geen
entity-keyspecifieke controles.

De offlinegrens wordt geen Number-entiteit. Zij volgt rechtstreeks uit de
bestaande laatste zone van `report_delay`. Daarmee kan geen tegenstrijdigheid
ontstaan tussen de weergegeven vertraging en `status_reporting`. De in het
rapport geschatte grens rond vijftien minuten wordt dus niet als afzonderlijke
instelling of verborgen tweede tijdscriterium overgenomen.

Niet instelbaar worden:

- de rond 60 °C waargenomen pompstart en de pompcyclusduur; dit zijn
  regelaarwaarnemingen, geen bewezen alertvoorwaarden;
- alertprioriteit, exclusiviteit, type en severity; die horen bij het stabiele
  contract;
- berichten of vertalingen; die horen bij presentatie;
- controllerstatus, T4, tank-onder of koudwatertemperatuur; zij zijn voor deze
  vier regels niet nodig;
- grenzen voor `over_temp`, `freeze_risk`, `needs_refill` en `sensor_fault`;
  daarvoor zijn geen betrouwbare lokale criteria vastgesteld.

## Providerbedrading

Na invoering verschillen de standaardexpressies alleen nog waar de fysieke
bron verschilt:

```text
# Beide providers
report_delay = delay_zone(last_report, 2*60+30, 10*60)
state_pump = perc_pump_pwm > 0
status_reporting = report_delay and not is_timestamp(report_delay)

# Alle providers
alerts_system = solar_thermal_alerts(
    null(status_reporting, state_pump, temp_collector, temp_tank_top),
    90, 200, 10, 10
)
```

De beslislogica en fabrieksexpressie zijn identiek. Bij migratie worden waarden
uit de vier vervallen drempelentiteiten in resterende source-expressies
ingevoegd en verdwijnen de vier entiteitssleutels. De evaluator blijft de
eerdere negenargumentenvorm accepteren voor expliciet opgeslagen
compatibiliteitsexpressies.

## Tijdsevaluatie en beschikbaarheid

Omdat `report_delay` via `delay_zone()` van de klok afhangt, moet de coordinator
ook na een mislukte providerpoll op zijn normale interval blijven evalueren.
Hij bewaart de laatst geaccepteerde complete meetset en ververst het
bijbehorende `last_report` niet. Daardoor wordt de overgang bij de vaste grens
ook zonder nieuw providerbericht zichtbaar.

Tot de timeout mag de laatste complete meetset als actueel binnen het gekozen
versheidscontract gelden. Vanaf de timeout:

- zijn gewone meet- en pompwaarden niet beschikbaar;
- blijven lokale configuratie-entiteiten, `last_report`, `report_delay`,
  `status_reporting` en `alerts_system` beschikbaar voor diagnose;
- bevat `alerts_system` uitsluitend de offlinealert.

Een providerfout blijft daarnaast als geredigeerde technische foutklasse in de
integratiediagnostiek zichtbaar; hij wordt niet verstopt door de lokale
evaluatie en wordt na een geslaagde providerpoll weer gewist.

## Versie- en migratiegevolgen

De aanvankelijk toegevoegde vier Number-entiteiten zijn weer uit de catalogus
verwijderd. De bestaande unique ID's van `state_pump`, `status_reporting` en
`alerts_system` veranderen niet. Hun opgeslagen drempelwaarden worden bij de
schema-10-migratie in resterende source-expressies ingevoegd. De migratie
verwijdert ook eventueel nog geregistreerde Home Assistant-entiteiten voor de
vier vervallen Number-sleutels.

Implementatie wijzigt de canonieke bron `EntityDescriptions.xlsx`; het
gegenereerde `thetruth.py` wordt niet handmatig aangepast. De eerste
implementatie verhoogde het expressieschema van 4 naar 5 en het
config-entryschema van 1.1 naar 1.2. De universele correctie van
`status_reporting` verhoogt die versies naar respectievelijk 6 en 1.3. De
migratie vervangt alleen herkenbare oude fabrieksexpressies; aangepaste
gebruikersexpressies blijven staan.

Manifest-, integratie- en kaartversie zijn voor deze correctie gezamenlijk
verhoogd naar `0.2.4`. Iedere volgende labwijziging krijgt eveneens een nieuw
`0.2.x`-nummer. De uiteindelijke productie-uitgave krijgt een nieuwe major
release; het definitieve nummer wordt bij release vastgesteld.

## Minimale acceptatie

De functietests nemen de empirische grensgevallen en het aangescherpte
severitycontract over, waaronder:

- precies 90 °C activeert `collector_hot` niet;
- precies 200 °C activeert de `warning`-variant van `collector_hot`, maar niet
  de `danger`-variant; een waarde boven 200 °C activeert alleen de
  `danger`-variant;
- precies 10 K verschil activeert `pump_idle` niet;
- gelijke collector- en vattemperatuur activeert `pump_active` niet;
- een draaiende pomp met een collector net onder de vattemperatuur levert
  `pump_active` met severity `info`; een onderschrijding groter dan de vierde
  alertconstante levert hetzelfde type met severity `warning`;
- bij een onderschrijding die exact gelijk is aan die constante blijft de
  severity door de strikte vergelijking `info`;
- precies 600 seconden oud valt nog in de actuele laatste vertragingszone en
  een rapport ouder dan 600 seconden levert uitsluitend `offline` op;
- pomppercentage `0` geeft `state_pump=False`, een positieve waarde geeft
  `True` en een ontbrekende waarde geeft `None`;
- 90 °C collector, 40 °C vat en pomp uit levert alleen `pump_idle` op;
- 95 °C collector, 50 °C vat en pomp uit levert zowel `collector_hot` als
  `pump_idle` op;
- een ontbrekende vattemperatuur onderdrukt alleen de pompregel en niet
  `collector_hot`;
- Web API- en ESPHome-bedrading leveren bij dezelfde genormaliseerde invoer
  byte-identieke lokaal afgeleide recordreeksen met `U+001E` als scheiding;
- de dashboardkaart presenteert `collector_hot` met severity `danger` als
  foutniveau en toont voor `pump_active` steeds de door de evaluator gekozen
  severity;
- de timeoutovergang vindt ook plaats tijdens aanhoudende provideruitval;
- terugkeer met een geldige complete meetset wist niet langer geldige alerts.

Daarnaast blijven generatorcheck, Python-regressietests, kaarttests en de
bestaande providerswitchtests verplicht voordat fase 6 mag beginnen.

De uitvoering en geautomatiseerde regressiecontrole zijn vastgelegd in
[`../results/universal-local-diagnostics-implementation-2026-10-25.md`](../results/universal-local-diagnostics-implementation-2026-10-25.md).
