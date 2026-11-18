# Review — Solesta-releasekandidaat voor HACS

Datum: 26 oktober 2026

Beoordeelde commit: `e023ba1dc36f94473f1fea777c9b5c9ea0df356d`

Branch: `codex/esphome-provider`

Vergelijkingsbasis: release `0.2.3`, commit
`bccaee942ec20fe906f7ea3dd4a9978f1abba0b6`

Review: GPT-6.1 Sol, met drie parallelle deelreviews en verificatie van de
bevindingen door de hoofdreviewer

Oordeel: **nog niet vrijgeven voor HACS**

Opvolging op 27 oktober 2026: de gebruiker heeft herstel van R01–R07 en R10
opgedragen; R08/R09 blijven publicatiewerk in fase 6. De aangescherpte
besluiten, waaronder het verbod op iedere bestaande expressieherschrijving,
staan in [D-ESP-007](../decisions/0007-provider-independent-expressions-and-optional-evaluation.md).
Het [herstelverslag](solesta-review-fixes-2026-10-27.md) beschrijft de nieuwe
kandidaat. De reviewtekst hieronder blijft het oorspronkelijke oordeel over
de hierboven genoemde commit.

## 1. Releaseoordeel

De architectuur en de eerdere praktijkacceptatie vormen een goede basis, maar
de huidige kandidaat voldoet nog niet aan het eigen migratie-, validiteits- en
alertcontract. De review heeft zes reproduceerbare runtime-/configuratiefouten
gevonden, één concrete Hassfest-blokkade, twee publicatieproblemen en één
kleiner probleem met alertrecords. Twee van de configuratiefouten bestonden
ook in de 0.2.3-basis; zij worden hieronder expliciet als zodanig gemarkeerd.

De bestaande 244 Python-tests, 30 kaarttests, generatorchecks en Ruff-controle
slagen. Dat is geen tegenbewijs voor de bevindingen: gerichte extra proeven
reproduceren situaties die de bestaande suite niet afdekt. De officiële
Hassfest-validator van Home Assistant 2026.10.4 meldt bovendien precies één
fout: de exacte pin van een bibliotheek die Home Assistant zelf ook gebruikt.

De definitieve releasenummering is overeenkomstig de opdracht buiten het
reviewoordeel gehouden. Alleen een ander versienummer geven is echter
onvoldoende voor vrijgave; de onderstaande P2-punten moeten eerst worden
afgehandeld. P2 betekent hier een aantoonbaar functioneel of publicatieprobleem
dat vóór deze release moet worden opgelost. P3 is een kleinere
robuustheidsverbetering. Er zijn geen P0- of P1-bevindingen vastgesteld.

| ID | Prioriteit | Bevinding | Herkomst |
| --- | --- | --- | --- |
| R01 | P2 | Ontbrekende/NaN ESPHome-waarden kunnen een geldige, verse meetset suggereren | Nieuwe provider |
| R02 | P2 | Een ongeldige pomp- of temperatuurwaarde kan onafhankelijke danger- en offlinealerts onderdrukken | Nieuwe alertketen |
| R03 | P2 | Protocolwissel met een duplicaatsysteem kan de hele hub onstartbaar maken | Nieuwe wisselroute |
| R04 | P2 | Schema-upgrade kan een aangepaste Web API-alertexpressie overschrijven | Nieuwe migratie |
| R05 | P2 | Herconfiguratie herstelt een verborgen `drop()` ongevraagd naar de fabrieksexpressie | Reeds aanwezig in 0.2.3 |
| R06 | P2 | Gelijktijdige configuratiestromen kunnen dezelfde provider-ID opslaan | Bestaand patroon; ook nieuwe ESPHome-route |
| R07 | P2 | Vaste `aioesphomeapi`-pin wordt door Hassfest geweigerd | Nieuwe afhankelijkheid |
| R08 | P2 | Installatie- en privacydocumentatie beschrijven uitsluitend de Web API | Publicatieachterstand |
| R09 | P2 | Te publiceren acceptatierapporten bevatten echte installatie-identificatoren | Publicatie/privacy |
| R10 | P3 | Eén lang JSON-alertrecord kan door Unicode-regelscheiding beschadigen | Nieuwe recordafhandeling |

## 2. Scope en werkwijze

De review omvat de volledige huidige integratie, met extra aandacht voor de
wijzigingen sinds 0.2.3: providerprotocol, versleutelde native API, mDNS,
configuratie- en expressiemigratie, providerwissel, entiteitsidentiteit,
beschikbaarheid, lokale alerts, instelbare grenzen, frontend en
releasevalidatie. De ongewijzigde Web API-, archief- en back-upcontracten zijn
meegenomen via broninspectie en regressietests.

De verplichte kennisbasis, actuele ontwerpbesluiten D-ESP-001 tot en met
D-ESP-006, het leidende faseplan en de eerdere acceptatieresultaten zijn als
context gebruikt. De expliciete gebruikersregel is leidend: een
providerwissel verandert geen source-expressies; uitsluitend
`source_system_id` mag automatisch worden ingevuld. Een schemamigratie mag
herkenbare historische fabrieksexpressies bijwerken, maar moet bewuste
gebruikersaanpassingen behouden.

Er is gewerkt op de bovengenoemde schone commit en in een afzonderlijke
`git archive`-kopie. Voor gerichte integratieproeven zijn de reeds aanwezige
Home Assistant 2026.10.4-installatie, echte entiteitencatalogus en echte
`aioesphomeapi==46.6.0`-statemodellen gebruikt. Netwerkgedrag is in die nieuwe
proeven gesimuleerd. De fysieke Nano, productieconfiguratie, live Recorder en
live `.storage` zijn niet aangeraakt. Er zijn geen runtimefixes aangebracht.

## 3. Functionele bevindingen

### R01 — ESPHome verwerkt onbekende states als echte waarden

**P2.** Locatie:
[`esphome_native.py:301–339`](../../custom_components/solesta/esphome_native.py),
vooral de verwerking van data-age rond regels 320–329 en meetgolven rond
regels 336–339.

De native modellen hebben naast `state` een vlag `missing_state`. De callback
leest alleen `state`. Daardoor is een onbekende numerieke state met de
standaardwaarde `0.0` niet te onderscheiden van een echte nulmeting. Ook
niet-eindige meetwaarden tellen mee bij het compleet verklaren van een
meetgolf.

Drie proeven met echte native statemodellen reproduceren dit:

1. Vijf meet-only-states met `missing_state=True` worden vijf nulmetingen,
   `data_valid=True` en een verse `last_update`.
2. Na een bestaande meetset met `data_valid=False` en een age van 600 seconden
   verplaatst een onbekende age-state (`state=0.0, missing_state=True`) de
   `last_update` ongeveer 600 seconden vooruit. `data_valid` blijft onwaar,
   maar de universele rapportagestatus volgt uitsluitend de timestamp en kan
   de oude meetset dus weer actueel noemen.
3. Vijf `NaN`-metingen leveren eveneens `data_valid=True` en een verse
   timestamp op. De evaluator kan daarna wel waarden afkeuren, maar de
   rapportagetijd is dan al onterecht vernieuwd.

**Gevolg:** onbekende of ongeldige metingen kunnen geldige nulwaarden en/of
actuele rapportage suggereren. Dat schendt de voorwaarde dat alleen een
complete, geldige meetset de rapportagetijd vernieuwt.

**Herstelcriterium:** verwerk `missing_state` expliciet, valideer de voor
compleetheid benodigde meetwaarden en voorkom freshnessvernieuwing door zulke
states. Test ook de overgang van een eerder geldige waarde naar onbekend;
alleen de callback overslaan mag geen oude geldige waarde blijven suggereren.
Gebruik hiervoor echte native statemodellen in de regressietests.

### R02 — Foutpropagatie schakelt onafhankelijke alertregels uit

**P2.** Locatie:
[`evaluator.py:205–229`](../../custom_components/solesta/evaluator.py),
in combinatie met de nieuwe `alerts_system`-expressie in de gegenereerde
catalogus.

`solar_thermal_alerts()` accepteert bewust ontbrekende pomp- en meetwaarden.
De evaluator roept deze functie echter helemaal niet aan zodra een
afhankelijkheid een fout heeft. De standaardexpressie `perc_pump_pwm > 0`
faalt bij een ontbrekende pompwaarde. Dat maakt `state_pump` ongeldig, waarna
`alerts_system` met `dependency_failed` wordt overgeslagen.

Met de echte volledige catalogus en evaluator zijn onder meer deze uitkomsten
vastgesteld:

| Invoer | Werkelijke uitkomst | Contractuele uitkomst |
| --- | --- | --- |
| Actueel rapport, collector 250 °C, pomp `None` | `alerts_system=None` | `collector_hot`, severity `danger` |
| Rapport 601 seconden oud, pomp `None` | `alerts_system=None` | uitsluitend `offline`, severity `danger` |
| Offline rapport, ongeldig collectorveld | `alerts_system=None` | uitsluitend `offline`, severity `danger` |

Een directe aanroep van `solar_thermal_alerts(True, None, 250, 40, 90, 200,
10, 10, None)` geeft wel de juiste dangeralert. De fout zit dus in de keten,
niet in die losse alertregel.

Ook een ontbrekende Web API-bronsleutel `alerts` blokkeert in een directe
evaluatorproef de lokale alerts via `missing_source`; expliciet `alerts=None`
werkt wel. Die proef betreft de evaluatorketen, niet een nieuwe fysieke
Web API-uitvaltest.

**Gevolg:** één ontbrekende invoer onderdrukt ook meldingen die daar volgens
D-ESP-006 onafhankelijk van moeten zijn. De offlinealert hoort bijvoorbeeld
geen geldige collector- of pompwaarde nodig te hebben.

**Herstelcriterium:** maak de nullable invoer van de universele alertfunctie
ook in de echte afhankelijkheidsketen bereikbaar, met behoud van gerichte
foutdiagnostiek voor de overige entiteiten. Voeg tests toe met de volledige
catalogus, inclusief offline plus kapotte meting en danger plus onbekende
pomp. Alleen de losse helper testen is onvoldoende.

### R03 — Een gedeactiveerd duplicaat blokkeert een protocolwissel

**P2.** Locaties:
[`config_flow.py:827–842`](../../custom_components/solesta/config_flow.py),
[`__init__.py:399–419`](../../custom_components/solesta/__init__.py) en
[`provider.py:250–254`](../../custom_components/solesta/provider.py).

Een protocolwissel deactiveert de systeemsubentries, maar bewaart bij een
`duplicate_system` het oude `communication_source_system_id`. De nieuwe
provider krijgt ook de gedeactiveerde duplicaataliases mee. Zijn initialisatie
vereist dat ieder communicatiedoel in de nieuwe discovery voorkomt.

Reproductie: een hub heeft een duplicaatalias `second_view` die naar
`old_webapi_system` verwijst. Na een protocolwissel biedt de nieuwe provider
uitsluitend een nieuwe lokale bron aan. Het duplicaat is correct
gedeactiveerd, maar de hele hub faalt op:

```text
ProviderResponseError:
communication source-system ID is absent from provider discovery
```

Ook de gewone systemen onder die hub komen daardoor niet op. De
herconfiguratie biedt voor een duplicaat alleen zijn bestaande alias als
bronkeuze aan (`config_flow.py:1903–1905`) en geen nieuw communicatiedoel.
Terugwisselen naar de oorspronkelijke provider kan de toestand herstellen,
maar de bedoelde handmatige herkoppeling ontbreekt.

**Herstelcriterium:** een bewust gedeactiveerde, nog niet herkoppelde
duplicaatverbinding mag niet de hele nieuwe hub blokkeren. Bied expliciete
handmatige herkoppeling met behoud van systeem-UID en source-expressies. Test
beide wisselrichtingen met een gewoon systeem én een duplicaatsysteem.

### R04 — Migratie herkent fabrieksexpressies te ruim

**P2.** Locatie:
[`configuration.py:306–317`](../../custom_components/solesta/configuration.py).

Bij de schema-4-migratie worden historische fabrieksexpressies uit beide
protocollen in één verzameling herkend. `alerts_system = '""'` was de
ESPHome-fabriekswaarde, maar is bij een bestaande Web API-configuratie een
geldige bewuste aanpassing om alerts te onderdrukken. De Web API-migratie
vervangt die waarde toch door `solar_thermal_alerts(..., alerts)`.

De directe migratieproef bevestigt dat de aangepaste expressie verandert.
Daarmee is de belofte dat gebruikersaanpassingen behouden blijven niet voor
alle geldige configuraties waar. Vergelijkbare protocolvreemde herkenning
bestaat bij `status_reporting`.

**Herstelcriterium:** begrens de herkenning tot aantoonbare fabrieksexpressies
van het betreffende historische protocol en schema. Leg vast hoe een
eventuele eerdere protocolwissel wordt behandeld als de herkomst niet meer
ondubbelzinnig is. Behoud bij twijfel de opgeslagen expressie. Test zowel de
normale fabriekspaden als bewust aangepaste kruisprotocolwaarden.

### R05 — Verborgen `drop()` verdwijnt bij systeemherconfiguratie

**P2; reeds aanwezig in de 0.2.3-basis.** Locaties:
[`config_flow.py:356–370`](../../custom_components/solesta/config_flow.py) en
de formulieropbouw rond regels 426–430.

Het formulier verbergt opgeslagen `drop()`-expressies. Bij verwerken van het
formulier gebruikt `_source_expressions()` voor ieder ontbrekend veld juist
de fabrieksexpressie. Daardoor wordt het verborgen veld ongevraagd hersteld.

Dit is ook met een volledig geldige configuratie en de echte
`SystemSubentryFlowHandler.async_step_reconfigure` gereproduceerd:

```text
temp_reserved vooraf: drop()
veld zichtbaar in formulier: False
livevalidatie: geslaagd
opslag door herconfiguratiehandler: uitgevoerd
temp_reserved achteraf: to_number(temp4)
```

De proef gebruikt de echte catalogus, compiler en evaluator, met een
netwerkloze provider. Een andere instelling wijzigen of het systeem
activeren kan dus een bewust onderdrukte entiteit opnieuw aan brondata binden.

**Herstelcriterium:** behoud opgeslagen expressies voor verborgen velden.
Onderscheid een ontbrekend veld van een zichtbaar veld dat de gebruiker
bewust leeg heeft gemaakt. Voeg een volledige formulier-roundtrip toe aan de
regressietests.

### R06 — Provider-ID-claim staat te laat bij gelijktijdige flows

**P2; het Web API-patroon bestaat al in 0.2.3.** Locaties:
[`config_flow.py:1109–1122`](../../custom_components/solesta/config_flow.py)
en de overeenkomstige ESPHome-route rond regels 1175–1188.

Beide configuratiestromen controleren de beschikbaarheid van `provider_id`
vóór de asynchrone verbindingsvalidatie. Pas daarna wordt de claim gezet,
zonder een nieuwe controle. Twee gelijktijdige flows kunnen zo beide dezelfde
vrije ID zien en vervolgens twee hubs met die ID opslaan.

De echte `async_step_web_api` is met een gesynchroniseerde validatiebarrière
uitgevoerd. Resultaat: twee aangemaakte hubs met allebei `same_provider`.
Hun willekeurige hub-UID's lossen de botsing op de lokale provider-ID niet op.
De setup weigert zulke dubbele provider-ID's vervolgens
(`__init__.py:183–189`), uiterlijk bij een herstart.

**Herstelcriterium:** reserveer de ID vóór netwerk-I/O met correcte vrijgave
bij mislukken/annuleren, of controleer en claim hem atomisch na validatie en
vóór opslaan. Test twee overlappende flows, ook tussen verschillende
protocollen.

## 4. HACS, compatibiliteit en publicatie

### R07 — Hassfest weigert de exacte ESPHome-bibliotheekpin

**P2.** Locatie:
[`manifest.json:19–20`](../../custom_components/solesta/manifest.json).

De officiële Hassfest-validator uit de Home Assistant 2026.10.4-bron is lokaal
tegen de ongewijzigde kandidaat uitgevoerd. Alle integratiecontroles zijn
doorlopen. De enige gemelde fout is:

```text
Requirement aioesphomeapi==46.6.0 pins a package Home Assistant depends on
(aioesphomeapi==46.6.0). Use a minimum version ("aioesphomeapi>=46.6.0")
instead, so it can follow along when Home Assistant updates it.
```

Dit is een validatoruitkomst, niet alleen een theoretisch versiebezwaar. De
gedeelde Python-omgeving maakt een exacte pin bovendien kwetsbaar bij een
latere Home Assistant-upgrade. De kandidaat declareert nog minimum
Home Assistant 2026.9.0, waarvan de ingebouwde ESPHome-integratie
`aioesphomeapi==46.2.0` gebruikt; 2026.10.4 gebruikt `46.6.0`.

De eerdere fase-4-acceptatie beschrijft al een daadwerkelijke
versieconflictuitval die lokaal door afstemming op de toenmalige Core-versie
is opgelost. Die lokale oplossing is geen duurzaam compatibiliteitsbeleid
voor een publieke release.

**Herstelcriterium:** kies een afhankelijkheidscontract dat de gedeelde
HA-bibliotheek kan volgen en onderbouw de ondersteunde minimumversie.
De validator noemt een minimumrange als oplossing; controleer vóór die
wijziging welke API-versie de provider werkelijk nodig heeft. Test de
minimaal geclaimde HA-versie en de actuele versie, telkens met en zonder een
actieve officiële ESPHome-integratie. Laat daarna Hassfest opnieuw slagen.

Bronnen:
[Hassfest requirementscontrole 2026.10.4](https://github.com/home-assistant/core/blob/2026.10.4/script/hassfest/requirements.py),
[ESPHome-manifest HA 2026.9.0](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/esphome/manifest.json),
[ESPHome-manifest HA 2026.10.4](https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/components/esphome/manifest.json).

### R08 — Publieke uitleg dekt de nieuwe provider en upgrade niet

**P2.** Locaties: [`README.md:36–51`](../../README.md),
[`installation.md:5–45`](../installation.md),
[`privacy-and-security.md:10–34`](../privacy-and-security.md) en
[`CHANGELOG.md`](../../CHANGELOG.md).

De hoofdinstallatiehandleiding vereist nog een Solesta-account en internet,
beschrijft uitsluitend gebruikersnaam/wachtwoord en noemt de hub altijd
`Web API`. De privacyuitleg schrijft de beschikbaarheid geheel aan de
internetverbinding toe en beschrijft geen lokaal opgeslagen Noise-PSK,
MAC-controle of mDNS. Het changelog stopt bij 0.2.3. De nieuwe
entiteitsdocumentatie is deels wel bijgewerkt, waardoor de documenten niet
meer hetzelfde product beschrijven.

**Herstelcriterium:** werk de publieke route uit voor beide protocollen,
inclusief encryptiesleutel, lokale werking zonder Nano-internet,
mDNS/handmatige host, bronexpressies, handmatige herkoppeling na een switch,
uitgeschakelde systemen en herstel. Beschrijf de universele alerts en
configureerbare grenzen, de schemamigratie en het verschil tussen
back-upherstel en alleen oude componentbestanden terugplaatsen. Dat is
inhoudelijk releaseterminologie en gedrag; het staat los van het nog te
kiezen releasenummer.

### R09 — Acceptatieverslagen zijn niet geschikt voor ongewijzigde publicatie

**P2; publicatie/privacy.** Locaties onder meer:
[`upgradeverslag:40–51 en 132–138`](solesta-production-upgrade-recovery-acceptance-2026-10-26.md),
[`fase-4-verslag:95–98`](esphome-provider-phase4-parallel-acceptance-2026-10-23.md)
en het fase-5-verslag.

De Git-tree bevat echte permanente configuratie-, systeem-, apparaat- en
resource-identificatoren en het MAC-adres van de gebruikte woninginstallatie.
De verplichte privacybasis sluit permanente woning-/systeemidentificatoren
expliciet uit van openbaar materiaal. De identifiers zijn geen wachtwoorden,
maar horen daarom evenmin ongewijzigd in de openbare release-repository.

**Herstelcriterium:** maak een publiceerbare, consistent gepseudonimiseerde
versie van de verslagen en bewaar de identificerende bewijsstukken privé.
Controleer ook de te publiceren Git-geschiedenis en overige acceptatieverslagen;
alleen de bovenste bestandsversie schonen garandeert niet dat eerder
gecommitteerde gegevens niet mee openbaar worden. Deze review heeft geen
Git-geschiedenis herschreven en stelt niet vast of deze branch al openbaar is.
De werkelijke identifiers worden in dit reviewrapport niet herhaald.

### R10 — Unicode kan één overflowrecord in fragmenten veranderen

**P3.** Locatie:
[`sensor.py:88–94`](../../custom_components/solesta/sensor.py).

Bij lange tekst gebruikt de sensor de Record Separator als die aanwezig is,
anders `splitlines()`. Eén nieuw JSON-record bevat geen separator. De
serializer gebruikt `ensure_ascii=False`; geldige Unicode-tekens zoals
U+2028 kunnen daardoor letterlijk in een bericht staan en worden door
Python `splitlines()` als scheiding behandeld.

Reproductie met de echte alertfunctie en sensor: één geldig
`sensor_fault/error`-record van 310 tekens met een lange berichttekst en
U+2028 levert twee ongeldige JSON-fragmenten in `attributes.lines` op.
De kaart interpreteert die vervolgens als kale warningteksten en verliest het
oorspronkelijke type en foutniveau.

**Herstelcriterium:** herken een nieuw JSON-record eerst als geheel, of beperk
het legacy-splitsen tot de feitelijk gebruikte CR/LF-scheiding. Test één lang
record met U+2028/U+2029 naast meerdere RS-records en oude newlinewaarden.
Gewone JSON-newlines, die escaped worden, werken in de huidige tests wel.

## 5. Wat de review positief bevestigt

- De ESPHome-provider gebruikt hetzelfde providercontract en dezelfde
  systeemlaag; de entiteitsplatformen hoeven de provider niet te kennen.
- De native API gebruikt encryptie, valideert de PSK-vorm en controleert het
  verwachte MAC-adres. De gebruikte clientargumenten sluiten aan op de echte
  geïnstalleerde bibliotheek.
- De mDNS-selectie is een verbindingshulp en vervangt de geverifieerde
  apparaatidentiteit niet. Handmatige hostinvoer is beschikbaar.
- Eerste gedeeltelijke meetgolven maken geen fallbacktimestamp; bij volgende
  gedeeltelijke golven blijft de vorige timestamp staan. Complete golven en
  framebarrières werken voor geldige meetwaarden. Disconnect wist alle
  relevante caches.
- De directe protocolwissel bewaart source-expressies en permanente
  identiteiten en deactiveert systemen voordat ze opnieuw gevalideerd worden.
- De schemamigratie bereidt subentries vóór publicatie voor en is bij een
  afgeronde 1.3-migratie idempotent. R04 begrenst de positieve conclusie over
  het herkennen van aangepaste expressies.
- De alertfunctie zelf gebruikt de overeengekomen strikte grenzen,
  standaard-dangergrens van 200 °C, offline-exclusiviteit, prioritering en
  deterministische bronalert-samenvoeging. R02 betreft de aanroepketen.
- De kaart presenteert `danger` als foutniveau, haalt provider/systeem-ID uit
  actuele metadata en ontsnapt variabele namen en berichten. Er is geen
  concrete XSS gevonden in de beoordeelde paden.
- Productie- en labkaart registreren verschillende custom elements en
  resources. De runtimecatalogi zijn reproduceerbaar vanuit de canonieke
  werkboeken; de labbuild is deterministisch.
- Archief- en back-upcode zijn niet providerafhankelijk gemaakt. De bestaande
  archiefregressies slagen. Broninspectie van de archiefconfiguratiesnapshot
  toont geen toevoeging van wachtwoord, PSK of ruwe verbindingsconfiguratie.
- De eerdere herstelkopieproef bevestigt behoud van de 21 bestaande
  entiteitsidentiteiten, historie en dashboardbinding voor de daadwerkelijk
  geteste productieconfiguratie; vier nieuwe Number-entiteiten worden eenmaal
  toegevoegd en herstart is idempotent.

## 6. Uitgevoerde verificatie en grenzen van het bewijs

| Controle | Uitkomst | Reikwijdte |
| --- | --- | --- |
| Canonieke generatorcheck | Geslaagd | `thetruth.py` en `provider_defaults.py` |
| Solesta Lab-buildcheck | Geslaagd | build-ID `30b6fffb240a` |
| Python-regressiesuite | 244 tests geslaagd | Schone kopie van de beoordeelde commit |
| Dashboardkaarttests | 30 tests geslaagd | Gebundelde Node-runtime |
| Ruff 0.16.7 | Geslaagd | Integratie, tools en tests volgens repositoryconfiguratie |
| Officiële Hassfest 2026.10.4 | Afgekeurd, 1 fout | Exacte `aioesphomeapi`-pin; overige 22 integratievalidatiestappen zonder gemelde fout |
| Gerichte native-stateproeven | R01 gereproduceerd | Echte native modellen, netwerkloze client |
| Gerichte evaluatorproeven | R02 en R10 gereproduceerd | Echte HA, volledige catalogus, compiler/evaluator en sensor |
| Migratie-/wissel-/parallelle-flowproeven | R03, R04 en R06 gereproduceerd | Werkelijke helpers/flowmethoden, gesimuleerde discovery en opslag |
| Volledige herconfiguratie-roundtrip | R05 gereproduceerd | Echte handler, compiler/evaluator en livevalidatieroute met netwerkloze provider |
| HACS-repositorystructuur/metadata | Statisch beoordeeld | Eén integratiedomein, benodigde manifestvelden en eigen runtimebestanden aanwezig |
| HACS GitHub Action en CodeQL op deze commit | Niet opnieuw uitgevoerd | Geen push, PR of externe workflow gestart |
| Minimum Home Assistant 2026.9.0 | Niet als runtime beproefd | Versiecontractprobleem opgenomen bij R07 |

De officiële validator is uit een afzonderlijke bronkopie uitgevoerd met zijn
benodigde hulpmiddelen. Hiervoor zijn geen Mac-instellingen gewijzigd en is
geen Home Assistant-server gestart. Aanvankelijk ontbrekende
validatorhulpmiddelen zijn in een tijdelijke map aangevuld; de tabel vermeldt
de uiteindelijke volledige validatoruitkomst.

De nieuwe reproduceerproeven staan lokaal onder de genegeerde map
`work/review-20261026/`:

- `provider_probe.py` voor R01 en positieve meetgolf-/disconnectcontroles;
- `evaluator_probe.py` voor R02 en R10;
- `migration_probe.py` voor R03, R04, R06 en de eerste R05-proef;
- `drop_real_flow_probe.py` voor de volledige R05-formulier-/opslagroute.

De native/evaluator/volledige-flowproeven zijn uitgevoerd met de lokale
HA-testomgeving `work/phase6-upgrade-20261026/.venv/bin/python`; de losse
migratieproef met de bestaande `test-venv`. De proefbestanden zijn geen
onderdeel van de publieke testsuite en moeten bij herstel worden vertaald
naar blijvende regressietests.

Een belangrijk dekkingsgat zit in de bestaande evaluatortests: delen daarvan
gebruiken een beperkte catalogusstub. Losse functietests en ketentests met
uitsluitend geldige waarden bewijzen niet dat nullable alertinvoer door de
echte catalogus heen komt. Andere flowtests controleren op sommige plaatsen
alleen AST-/broncodestructuur. De gelijktijdige configuratiestroom en de
formulier-roundtrip moeten op gedrag worden getest.

De eerdere fysieke en herstelkopieacceptaties zijn niet volledig herhaald.
De herstelkopieproef betrof één gewoon Web API-systeem met fabrieksexpressies;
dat is geen dekking voor duplicaten, afwijkende expressies of overlappende
flows. Het historieoordeel is gebaseerd op dezelfde bewaarde ID's en
Recorderrijen uit die proef; deze review voegt geen nieuwe langdurige
Recorder- of archiefpraktijkproef toe. Terugrol betekent herstel van de
passende back-up, niet dat alleen oude componentbestanden over schema 1.3
heen kunnen worden geplaatst.

## 7. Voorwaarden voor vrijgave

1. Herstel R01–R06 en leg de bewezen scenario's vast in blijvende
   regressietests, met de volledige catalogus en echte native statemodellen
   waar dat het gevonden dekkingsgat oplost.
2. Los R07 op, beslis de ondersteunde HA-minimumversie en valideer de
   bibliotheekco-existentie met de officiële ESPHome-integratie.
3. Werk de publieke installatie-, privacy-, migratie- en releaseuitleg bij
   volgens R08. Maak de te publiceren bewijsdocumenten en Git-geschiedenis
   privacygeschikt volgens R09.
4. Neem R10 mee als kleine correctie of leg een expliciet geaccepteerde
   restbeperking vast.
5. Voer generatorchecks, Python-tests, kaarttests, Ruff, Hassfest en de
   HACS-/CodeQL-controles uit op de uiteindelijke releasecommit. Controleer
   daarna uitsluitend de door de fixes geraakte acceptatiepaden opnieuw,
   waaronder de duplicaatwissel en het behoud van custom expressies.
6. Synchroniseer de definitieve integratie-, kaart- en resourceversie en maak
   pas daarna het releasebesluit.

De structuur van een HACS-integratierepository en de manifestvereisten zijn
getoetst aan de officiële
[HACS-integratievereisten](https://hacs.dev/docs/publish/integration/) en
[Home Assistant-manifestdocumentatie](https://contributors.home-assistant.io/core/integrations/manifest/).
Een opname in de standaard HACS-catalogus en de daarvoor geldende
brands-/indieningsprocedure zijn een afzonderlijke stap; de huidige
gebruikersroute is installatie als custom repository.

Deze review levert een afgebakende herstelagenda op. Zij is geen wijziging van
het faseplan, geen installatieopdracht voor productie en geen releasevrijgave.
