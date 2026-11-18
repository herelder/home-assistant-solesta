# Volledige projectreview — Solesta 1.0.0

Datum: **16 november 2026**, Europe/Amsterdam.

Oordeel: **nog niet vrijgeven**. Deze onafhankelijke review vindt negen
reproduceerbare P2-problemen en drie kleinere P3-afwijkingen in de volledige
kandidaat. Daarnaast ontbreken enkele al bekende acceptatieresultaten. Er is
geen P0- of P1-defect aangetoond. De geslaagde bestaande controles nemen de
hieronder bewezen fouten niet weg.

Dit is uitsluitend een review. Productcode, firmware, werkboeken, tests,
bestaande documenten en de kennisbasis zijn niet aangepast. Er is niets
geïnstalleerd, geflasht, herstart, gecommit, getagd, gepusht of gepubliceerd.
Productie en Lab zijn niet benaderd of gewijzigd. Alleen dit rapport en lokale
tijdelijke onderzoeksbestanden zijn geschreven.

## 1. Exacte reviewbasis

| Onderdeel | Vastgestelde basis |
| --- | --- |
| Gedeelde ontwikkelcheckout | Branch `codex/esphome-provider`, commit `a4214fd871675b5f176db542d8946eed56935e42` |
| Commitonderwerp | `Add public NanoC6 firmware kit for Solesta 1.0.0` |
| Voorgaande ontwikkelcommit | `ef7d9ae` — expressiecontracten, productiecompatibiliteit en documentatie |
| Afzonderlijke releasecheckout | `work/solesta-1.0.0-clean-release-20261116`, branch `release/1.0.0-nanoc6` |
| Releasecommit | `487b6f6ea7df44380bfdaf6c1397bd4e35a1174b` |
| Git-boom van **beide** commits | `5f7d24d1b848c216da58e758e6bb7041ae184a5f` |
| Beoordeelde publicatie-inhoud | Dezelfde 166 bijgehouden bestanden, inclusief inhoud, paden en Git-bestandsmodi |
| Ondersteunde productiebasis | `0.2.3`, commit `bccaee942ec20fe906f7ea3dd4a9978f1abba0b6` |
| Integratie / kaart / resourcecache | `1.0.0` |
| Publiek ESPHome-project | `herelder.solesta-nanoc6`, firmwareversie `0.1.0` |
| Config-entry / expressieschema / catalogus | `1.9` / `11` / revisie `16`, 21 entiteitsdefinities |

Beide checkouts waren bij aanvang schoon. Gelijkheid is vastgesteld met hun
volledige Git-tree-ID, niet afgeleid uit versienummers of commitonderwerpen.
Alle bevindingen over de broninhoud gelden daardoor ook voor de genoemde
releasecommit. Dit nieuwe rapport behoort nog niet tot die beoordeelde boom.
De gedeelde checkout is niet van branch gewisseld.

De releasebranch heeft lokaal precies vijf bereikbare commits: de nieuwe
releasecommit en `bccaee942ec20fe906f7ea3dd4a9978f1abba0b6`,
`1fbdca2387a5486f3136c07740bac519ad1ba38a`,
`2c0f9d3dfa8a0f84b35910d380c6786dd74501ca` en
`5dd3fc651644a21d9e05a89d2c129f0631bf5756`. De privéontwikkelgeschiedenis
zit daar niet tussen. Dit is een lokale geschiedeniscontrole; de actuele
GitHub-`main` en repositoryinstellingen zijn in deze review niet opnieuw
opgevraagd. Controleer die vóór een eventuele publicatie opnieuw volgens
[maintainer-security.md](../maintainer-security.md).

Productie `0.2.3` en Lab `0.2.8` zijn context uit de overdracht en het
installatieverslag, geen nieuw vastgestelde live toestand.

## 2. Methode, dekking en grenzen

De review is opnieuw vanuit de volledige kandidaat uitgevoerd, met drie
parallelle deelreviews voor integratie/configuratie, dashboard en firmware.
De hoofdreview omvatte daarnaast compiler/evaluator, bronbinding, archivering,
back-up, documentatie, publicatieboom en verificatie. De concrete bevindingen
zijn aan de bron getoetst; de hoofdreviewer heeft de integratie-, kaart-,
expressie-, meetactualiteits- en C++-parserproeven zelfstandig herhaald.

Gelezen zijn `AGENTS.md`, de vijf verplichte kennisbasisdocumenten, de eerdere
review en het herstelverslag van 26/27 oktober, besluiten 0013–0015, de
compatibiliteits- en nullverslagen, het Lab-installatieverslag van 15 november,
het M7-verslag en de NanoC6-releasevoorbereiding. Relevante oudere besluiten
en de huidige gebruikersdocumentatie zijn meegelezen. Historische
acceptatiebewijzen zijn als context behandeld. Zij vervangen geen acceptatie
van deze gewijzigde kandidaat.

| Gebied | Uitgevoerde inhoudelijke beoordeling |
| --- | --- |
| Configuratie en identiteit | Aanmaken/activeren, herconfiguratie, reauthenticatie, claims na asynchrone validatie, revisieconflicten, zes providerwisselrichtingen, duplicaten en isolatie |
| Upgrade en expressies | Werkelijke 0.2.3-fabrieksexpressies, letterlijk behoud, metadatawrites, huidige/afgewezen schema's, bronpaden, korte/absolute namen, eigenvelden, nullable afhankelijkheden, typen, foutlocaties en onafhankelijke alerts |
| Providers en systeemlaag | Web API-verzoekgrenzen en authenticatie, Native MAC/encryptie en states, MQTT-roots/TLS/subscriptie/discovery, reconnect/cache, timestamps, coordinator en entiteitsidentiteit |
| Dashboard | Entiteitsresolutie, dynamische en expliciete namen, unknown/offline, alertrecords/Unicode/escaping/severity, historieverdichting, gemiddelden, HA-tijdzone, daggrenzen, retries en resourcecache |
| Bouwpakket | De drie publieke bestanden; GPIO/UART, werkelijke C++-parser, corrupte/deelrecords, buffering/resynchronisatie, waarden/eenheden, stale data, boot, Native/MQTT/OTA, secrets en importmetadata |
| Archief en back-up | Permanente systeemidentiteit, registerhistorie en eigendom van Recorderrijen, week-/tijdzonegrenzen, voortgang, atomaire publicatie, validatie, providerwissel en back-upvergrendeling |
| Release en uitleg | Route van firmware tot HA, mappings, defaults, behoud/herstel, versies, privacy, manifest/HACS/workflows en de schone publicatieroute |

De netwerkloze integratieproeven gebruiken echte HA 2026.10.4-klassen en
provider-/compiler-/evaluatorcode met gesimuleerde verbindingen en opslag.
De kaartproeven voeren de werkelijke JavaScript-methoden uit met minimale
DOM-doubles. De firmwareproef gebruikt de ongewijzigd uit de publieke YAML
gehaalde C++-parserlambda met nagebootste UART/sensors en geheugencontroles.
Deze methoden bewijzen de beschreven codepaden; zij bewijzen geen fysieke
netwerktiming, ESP32-drivergedrag of browserlayout.

Er is geen live HA-actie uitgevoerd, geen actieve Recorderdatabase geopend,
geen `.storage` gelezen of geschreven en geen apparaatverbinding gemaakt.
Daarom was een live infrastructuurpreflight niet aan de orde. De gemelde
fysieke flash en HA-rediscovery uit de overdracht blijven gebruikersbewijs,
geen tijdens deze review herhaalde acceptatie.

## 3. Bevindingen op ernst

P2 betekent hier een concreet functioneel probleem in een ondersteunde route
dat vóór vrijgave moet worden afgehandeld. P3 betreft een kleinere maar
aantoonbare presentatie- of documentatieafwijking. Ook voor een P3-afwijking
moet het releasebesluit vastleggen of zij wordt hersteld of bewust aanvaard.

| ID | Ernst | Bevinding |
| --- | --- | --- |
| S100-01 | P2 | MQTT zonder Native-client leidt door de API-timeout tot herhaalde NanoC6-herstarts |
| S100-02 | P2 | De concrete kitmapping houdt stilgevallen UART-metingen ten onrechte actueel |
| S100-03 | P2 | Kopieën valideren met een andere bronbinding dan hun runtime gebruikt |
| S100-04 | P2 | Een bronveld met de eigen entiteitsnaam omzeilt pad- en ambiguïteitscontrole |
| S100-05 | P2 | MQTT-validatie verklaart een onvolledige veldtabel na 100 ms definitief |
| S100-06 | P2 | Geldige exacte MQTT-roots worden voor kopieën gestript of verworpen |
| S100-07 | P2 | MQTT-authenticatie kan via herconfiguratie niet naar anoniem worden gewijzigd |
| S100-08 | P2 | Historieverdichting vervalst de tijdgewogen daggemiddelden |
| S100-09 | P2 | Een zomertijdovergang op middernacht kan de volledige kaartweergave breken |
| S100-10 | P3 | Een ontbrekende collectormeting krijgt toch de groene totaalstatus |
| S100-11 | P3 | De entiteitentabel belooft niet-bestaande automatische alertmerging |
| S100-12 | P3 | Gebruikersdocumentatie beschrijft de bewust interne functie `drop()` |

### S100-01 — API-timeout herstart een uitsluitend via MQTT gebruikt apparaat

**Locatie:** [publieke YAML](../../esphome/public/solesta-nanoc6.yaml),
regels **49–51**; MQTT-instelling op regel **30**.
[Kit-README](../../esphome/public/README.md), regels **53–58 en 74–80**.

**Trigger/reproductie:** schakel MQTT in, verbind de Solesta MQTT-provider en
laat geen Native API-client of ESPHome-logviewer verbonden. Deze route is
toegestaan: de officiële HA ESPHome-integratie is optioneel en de kit kan de
MQTT-provider voeden.

**Bewijs:** de exacte publieke YAML valideert, maar de uitgewerkte
ESPHome 2026.9.1-configuratie bevat `api.reboot_timeout: 15min`. Alleen de
MQTT-timeout is expliciet op nul gezet. Volgens de actuele primaire
[API-documentatie](https://esphome.io/components/api/) en de expliciete
[MQTT-waarschuwing](https://esphome.io/components/mqtt/) herstart een apparaat
met deze API-instelling na vijftien minuten zonder API-client, ook als MQTT
gewoon werkt. Een open logviewer kan dit in een korte proef maskeren.

**Gevolg:** periodieke herstarts, onderbrekingen van UART/MQTT en opnieuw
beginnende parserdiagnostiek. Dit is een bewezen configuratieprobleem met een
gedocumenteerd runtimegevolg; de herstarts zijn in deze review niet op de
fysieke Nano geobserveerd.

**Herstel-/acceptatiecriterium:** beheer de API-reboottimer expliciet voor de
ondersteunde MQTT-route. Bewijs daarna meer dan dertig minuten MQTT-gebruik
zonder Native-client/logviewer, met doorlopende data en niet-geresette
opstart-/frametellers. Behoud Native- en OTA-authenticatie.

### S100-02 — Kitroute biedt geen volledige mapping voor meetactualiteit

**Locatie:** [kit-README](../../esphome/public/README.md), regels **74–80**;
[worked mappings](../source-expressions.md), regels **97–108**.
Onderliggende firmware: [YAML](../../esphome/public/solesta-nanoc6.yaml),
regels **166–191 en 323–337**; fabrieksrapportage in
[thetruth.py](../../custom_components/solesta/thetruth.py), regels **186 en 312**.

**Trigger/reproductie:** volg de concrete Native-mappings voor temperaturen,
pomp en `last_report()`, laat de overige fabrieksexpressies staan en stop na
een geldige meetset uitsluitend de Solesta-UART. Wi-Fi en transport blijven
werken. MQTT heeft hetzelfde probleem met de overeenkomstige topicmapping.

**Bewijs:** de firmware bewaart de laatste ruwe meetwaarden en zet na vijftien
seconden `data_valid` op onwaar. `Data age` blijft iedere vijf seconden een
callback/PUBLISH opleveren. Dat ververst volgens het bewuste generieke
providercontract `last_report()`. Een proef met de echte observationcache,
volledige catalogus en evaluator geeft na één uur zonder UART:

```text
data_valid = False
last_report() = nu
report_delay = "[0,150]"
status_reporting = True
temp_collector / temp_tank_top / temp_tank_bottom = 31 / 52 / 40 °C
alerts_system = ""
evaluatiefouten = geen
```

De algemene waarschuwing over fysieke meetactualiteit op regels 243–247 van
de expressiehandleiding is correct. De concrete kitroute levert echter geen
Native- en MQTT-recept dat het aanwezige `data_valid` aan de systeemstatus
bindt. Een gebruiker kan de uitgewerkte route correct uitvoeren en toch
onbeperkt oude waarden als actuele metingen tonen.

**Gevolg:** uitval van de eigenlijke meetbron blijft verborgen terwijl de
kaart rapportage en metingen als actueel presenteert.

**Herstel-/acceptatiecriterium:** geef voor deze kit volledige expliciete
validiteitsmappings: Native met het booleanveld, MQTT met het werkelijk
gepubliceerde ON/OFF-veld, beide gecombineerd met transportactualiteit.
Controleer stoppen en hervatten van UART tot en met entiteiten en kaart.
Het generieke provider-/timestampcontract hoeft hiervoor niet te veranderen;
voeg geen firmwarekennis toe aan de entiteits- of kaartlaag.

### S100-03 — Kopieën verliezen de bronveldtabel bij runtimecompilatie

**Locatie:** [configuration.py](../../custom_components/solesta/configuration.py),
regels **334–338**; [mqtt.py](../../custom_components/solesta/mqtt.py),
regels **189–191**; [esphome_native.py](../../custom_components/solesta/esphome_native.py),
regels **157–160**. De live validatie gebruikt het communicatiedoel in
[config_flow.py](../../custom_components/solesta/config_flow.py),
regels **2562–2568**.

**Trigger/reproductie:** maak een MQTT-kopie met alias `copy`, communicatieroot
`root` en de gedocumenteerde verkorte expressies zoals
`to_number(state__collector)` voor `root/sensor/collector/state`. Activeer na
geslaagde live validatie. Hetzelfde type fout is gereproduceerd met een
Native-kopie en de geldige absolute vorm
`to_number(_0R__temperature_1_raw)`.

**Bewijs:** validatie bindt tegen de veldtabel van het communicatiedoel en
slaagt. `build_system_runtimes()` vraagt vervolgens de veldtabel op onder de
lokale alias. Beide providers vinden daar geen tabel. MQTT compileert daardoor
`state__collector` letterlijk, terwijl de snapshot
`state__collector__sensor` bevat. De runtime eindigt met
`ProviderSystemError: MQTT source values did not arrive in time`.
Bij Native blijft zonder tabel de `_0R__`-prefix onopgelost en volgt
`ESPHome source keys are unavailable`. In beide proeven gaf de voorafgaande
live validatie `valid=True`.

Voor de eerste gerichte MQTT-proef is alleen de runtime-wachttijd tijdelijk
in het onderzoeksproces verkort van twintig seconden tot 0,01 seconde; de
verkeerde sleutelverzamelingen zijn rechtstreeks vastgesteld. Er is geen
bronbestand gewijzigd.

**Gevolg:** een als geldig geactiveerde kopie komt niet beschikbaar. Gewone
Native-veldnamen zonder absolute prefix kunnen dit probleem verbergen.

**Herstel-/acceptatiecriterium:** gebruik bij validatie én runtime dezelfde
bronveldtabel van de effectieve communicatiebron. Test kort, volledig en
absoluut gekwalificeerde namen bij MQTT/Native-kopieën, inclusief reload en
herkoppeling, zonder providerlogica naar entiteiten te verplaatsen.

### S100-04 — Eigenveldreferentie omzeilt de gewone bronresolver

**Locatie:** [compile.py](../../custom_components/solesta/compile.py),
regels **224–227**, tegenover de resolver op **242–251**.
Contract: [source-expressions.md](../source-expressions.md),
regels **29–34 en 70–78**.

**Trigger/reproductie:** configureer voor entiteit `temp_collector` de
expressie `to_number(temp_collector)` terwijl de bron het unieke veld
`temp_collector__metrics` aanbiedt. De eigen naam behoort volgens de
handleiding naar de bron te verwijzen.

**Bewijs:** de compiler registreert letterlijk `temp_collector`, zonder de
beschikbare veldtabel te raadplegen. De evaluator geeft `missing_source`.
Dezelfde expressie met expliciete apostrof,
`to_number(temp_collector')`, bindt wel naar `temp_collector__metrics` en
levert `42.0`.

Ook de ambiguïteitsgrens wordt gepasseerd: bij aangeboden velden
`temp_collector` én `temp_collector__metrics` accepteert
`null(temp_collector)` het eerste veld en leest `10.0`. De expliciete
bronvorm `null(temp_collector')` wijst dezelfde dubbelzinnigheid correct af.

**Gevolg:** twee gedocumenteerde manieren om een bron te lezen hebben
verschillende binding. Een geldige unieke mapping faalt, of een ambigue
mapping kiest toch stilzwijgend een bron.

**Herstel-/acceptatiecriterium:** laat ook de eigenveldroute dezelfde
canonieke resolver gebruiken. Test unieke geneste velden, ambigue korte namen,
nullable/vereiste invoer en de gewone velden `None`/`none`. Behoud bestaande
expressieteksten en het onderscheid tussen eigenbron en andere entiteiten.

### S100-05 — MQTT-discovery sluit te vroeg af bij gespreide publicaties

**Locatie:** [mqtt.py](../../custom_components/solesta/mqtt.py),
regels **337–356**; [config_flow.py](../../custom_components/solesta/config_flow.py),
regels **1059–1071**.

**Trigger/reproductie:** een geldige niet-retained uitgever publiceert onder
één root collector, vat boven, vat onder en pomp met 300 ms tussenruimte.
Gebruik de gedocumenteerde korte MQTT-mappings. Alle waarden arriveren ruim
binnen de interne twintigseconden-wachttijd voor bronwaarden.

**Bewijs:** zodra één topic bekend is, beëindigt discovery na 100 ms stilte
de veldinventarisatie. Live validatie behandelt die gedeeltelijke tabel als
volledig en keert na circa **0,12 seconde** terug met drie fouten
`source_value_missing_source`. Na **1,22 seconde** zijn alle vier velden
bekend. De normale status-wachttijd wordt door de eerdere compilefout niet
bereikt. Discoverytiming en validatie zijn in deze proef ongewijzigd; alleen
de verbinding is gesimuleerd en tijdelijke afsluiting uitgesteld om de
later arriverende velden zichtbaar te maken.

**Gevolg:** een werkende uitgever met gespreide updates kan niet betrouwbaar
worden geactiveerd. De ondersteunde MQTT-route vereist nergens dat alle
topics in een burst van minder dan 100 ms of retained worden aangeboden.

**Herstel-/acceptatiecriterium:** onderscheid een onvolledige inventarisatie
van werkelijk ontbrekende velden en geef de gevraagde bindingen gelegenheid
binnen een begrensde validatietermijn te verschijnen. Test gespreide
niet-retained waarden, een echt ontbrekend veld en pas later zichtbare
ambiguïteit; bindings mogen niet tijdens een configuratierevisie verschuiven.

Dit is **geen vastgestelde verklaring** voor het tijdelijke EMQX-incident in
Lab. Daarvoor ontbreekt een tijdgecorreleerde bron-/transportregistratie.

### S100-06 — Kopieën behandelen een MQTT-root als een lokale alias

**Locatie:** [config_flow.py](../../custom_components/solesta/config_flow.py),
regels **2720–2725 en 2419–2420**;
[configuration.py](../../custom_components/solesta/configuration.py),
regels **258–260**.

**Trigger/reproductie:** gebruik een geldige reguliere MQTT-root ` root ` met
betekenisvolle randspaties en selecteer precies die aangeboden root als
communicatiedoel van een kopie. Een root van 257 tekens toont de tweede
beperking.

**Bewijs:** `canonicalize_mqtt_root()` accepteert deze exacte MQTT-roots.
De kopieflow stript het geselecteerde communicatiedoel en geeft voor ` root `
`invalid_source_system`. Daarnaast eist `duplicate_systems_from_entry()`
voor zowel lokale alias als extern doel een getrimde string van maximaal
256 tekens; beide geldige targets leveren daar een lege aliasmapping op.
Ook herconfiguratie stript het communicatiedoel.

**Gevolg:** een reguliere ondersteunde bron kan niet op dezelfde manier als
kopie worden gekoppeld of wordt bij runtimeopbouw verworpen. Dit raakt de
exacte bronidentiteit, niet alleen een zichtbare naam.

**Herstel-/acceptatiecriterium:** onderscheid validatie van de lokale alias
van het providergebonden externe doel. Bewaar MQTT-roots letterlijk en test
randspaties, lange geldige roots, create/reconfigure/reload en providerwissel.
Blijf echte ongeldige MQTT-roots weigeren.

### S100-07 — Lege MQTT-credentials verwijderen de oude authenticatie niet

**Locatie:** [config_flow.py](../../custom_components/solesta/config_flow.py),
regels **1751–1753** en validatie op **865–866**.
Belofte: [installation.md](../installation.md), regels **99–104 en 177–179**.

**Trigger/reproductie:** herconfigureer een bestaande MQTT-hub met opgeslagen
gebruikersnaam en wachtwoord naar een brokerprofiel dat anonieme toegang
toestaat. Maak beide velden leeg.

**Bewijs:** de echte handler vervangt het lege wachtwoord altijd door het oude
wachtwoord, ook als de gebruikersnaam is verwijderd of gewijzigd. Lege
gebruikersnaam plus dat oude wachtwoord wordt daarna afgekeurd met
`invalid_provider_config`. Een rechtstreeks opgebouwde kandidaat met beide
waarden werkelijk leeg is geldig. De documentatie belooft wachtwoordbehoud
alleen bij een ongewijzigde gebruikersnaam; de code maakt dat onderscheid niet.

**Gevolg:** de ondersteunde overgang naar anonieme verbinding is via dit
formulier niet uitvoerbaar. Bij een gewijzigde gebruikersnaam wordt bovendien
onbedoeld het vorige wachtwoord in de kandidaat meegenomen. Er is in de proef
geen wachtwoord naar een echte broker gestuurd.

**Herstel-/acceptatiecriterium:** maak behouden, vervangen en verwijderen van
de credentialset ondubbelzinnig. Test anoniem → authenticatie,
authenticatie → anoniem, gebruikersnaamwissel en leeg wachtwoord bij dezelfde
gebruikersnaam. Behoud de bestaande atomaire validatie/publicatie van
verbinding en systeemstempels.

### S100-08 — Reductie tot 720 historiepunten vervalst gemiddelden

**Locatie:** [solesta-status-card.js](../../custom_components/solesta/frontend/solesta-status-card.js),
regels **1864–1897**; tijdweging op **1373–1394**, gebruikt op **1639**.

**Trigger/reproductie:** bied meer dan 720 geldige Recorderveranderingen aan.
De concrete proef gebruikt 7.141 minuutpunten: per uur `20, 80, 20`, daarna
afwisselend `50/50.1 °C`, over 119 uur.

**Bewijs:** de kaart bewaart 359 punten, vooral begin/einde en extrema per
tijdvak, en berekent vervolgens de gemiddelden uit die gereduceerde reeks.
Een kort bewaard maximum geldt zo tot het volgende bewaarde punt, hoewel
andere metingen binnen dat interval bekend waren.

| Berekening | Volledige meetreeks | Huidige kaartreeks |
| --- | ---: | ---: |
| Tijdgewogen gemiddelde over 119 uur | 49,548333 °C | 77,547871 °C |
| Eerste 24 uur | 49,548333 °C | 76,126667 °C |

Dit is uitgevoerd met de werkelijke `_temperatureHistory()` en
`_timeWeightedAverage()`-methoden. De fout is geen afrondingsverschil.

**Gevolg:** misleidende daggemiddelden en duurweergave van historische
temperaturen. Het contract dat de kaart geen metingen verzint wordt hiermee
inhoudelijk geschonden.

**Herstel-/acceptatiecriterium:** bereken statistieken en ontbrekende
intervallen uit de volledige reeks, of gebruik reductie die hun duur en
integralen aantoonbaar bewaart. Beperk alleen de tekengeometrie. Test grote
reeksen met korte extrema, meerdere hiaten en daggrenzen.

### S100-09 — Niet-bestaande lokale middernacht veroorzaakt een renderfout

**Locatie:** [solesta-status-card.js](../../custom_components/solesta/frontend/solesta-status-card.js),
regels **739–754 en 1633–1635**.

**Trigger/reproductie:** kies de geldige HA-tijdzone `America/Santiago`,
bevries de klok op `2026-09-07T12:00:00Z` en open de zeven dagenweergave.

**Bewijs:** op 6 september 2026 slaat deze tijdzone lokale middernacht over.
`_addCalendarDays(new Date('2026-09-05T04:00:00Z'), 1)` geeft `null`, doordat
de helper een exacte lokale 00:00 eist. `_historyMarkup()` roept vervolgens
ongecontroleerd `next.getTime()` aan en gooit:

```text
TypeError: Cannot read properties of null (reading 'getTime')
```

De fout ontstaat tijdens de kaart-render en wordt daar niet afgevangen. Ook
de vandaagweergave vóór zo'n overgang kan bij de volgende daggrens dit pad
bereiken. De bestaande Amsterdamse zomertijdtests dekken dit niet.

**Gevolg:** in een ondersteunde HA-tijdzone kan de hele kaartweergave falen
gedurende een relevant historievenster.

**Herstel-/acceptatiecriterium:** bepaal de eerste geldige tijd van een lokale
kalenderdag en maak daggrenzen robuust voor overgeslagen middernachten.
Een onberekenbare grafiekgrens mag hoogstens de grafiek treffen. Test naast
Amsterdam ten minste deze overgang in Santiago.

### S100-10 — Ontbrekende collector blijft als volledig normaal gepresenteerd

**Locatie:** [solesta-status-card.js](../../custom_components/solesta/frontend/solesta-status-card.js),
regels **1132–1137**, in samenhang met **982–1021**.

**Trigger/reproductie:** rapportage `on`, lege alertlijst, geldige
vattemperaturen/koudwater/pomp/energie, maar collector `unavailable`.

**Bewijs:** de werkelijke `_render()` toont tegelijk `—°` voor de collector
en de groene klasse `solesta-health normal` met de tekst
`Everything is working normally`. `coreKnown` controleert alleen gemiddelde
vattemperatuur, koud water en pomp. De collector ontbreekt daarin. De nullable
alertketen mag bij die ontbrekende invoer terecht leeg blijven; dat bewijst
geen volledige meetgezondheid.

**Gevolg:** de totaalstatus zegt dat alles normaal werkt terwijl een
kernmeting ontbreekt.

**Herstel-/acceptatiecriterium:** laat ontbrekende benodigde metingen tot de
incompletestatus leiden, met behoud van prioriteit voor onafhankelijke
danger- en offlinealerts. Test expliciet een ontbrekende collector naast
gezonde andere entiteiten.

### S100-11 — Entiteitentabel belooft automatische alertmerging

**Locatie:** [entities.md](../entities.md), regel **33**; actuele uitleg op
**109–112** en [source-expressions.md](../source-expressions.md),
regels **282–287**.

**Trigger:** een gebruiker configureert de huidige fabrieksalert en verwacht
op basis van de entiteitentabel daarnaast de bronalerts terug te zien.

**Bewijs:** de tabel beschrijft universele lokale alerts als samengevoegd met
extra provideralerts. De actuele helper verwerkt uitsluitend vier lokale
invoerwaarden en vier thresholds; de volledige-catalogustest bevestigt dat
een niet-gerefereerd bronalertveld wordt genegeerd. Verderop in dezelfde
handleiding staat wel correct dat bronalerttekst een eigen expressie vereist.

**Gevolg:** tegenstrijdige uitleg van welke waarschuwingen zichtbaar zijn,
relevant bij upgrade en vergelijking met de Solesta-webdienst.

**Herstel-/acceptatiecriterium:** beschrijf in de tabel de daadwerkelijke
lokale fabriek en het behoud van bestaande bronalertrecepten afzonderlijk.
Behoud de bestaande ondersteuning voor bronalerttekst; voeg geen verborgen
automatische merging of expressiemigratie toe.

### S100-12 — Interne functie staat alsnog in de gebruikershandleidingen

**Locatie:** [entities.md](../entities.md), regels **114–116**;
[troubleshooting.md](../troubleshooting.md), regel **96**.

**Trigger/bewijs:** de gebruikersroute noemt `drop()` expliciet en beschrijft
zijn interne betekenis. De actuele opdracht legt juist vast dat gebruikers
deze functie niet mogen configureren en dat de gebruikershandleiding haar
bewust niet noemt. De formulierafwijzing zelf werkt en is geen defect.

**Gevolg:** de publicatie-inhoud voldoet niet aan de afgesproken scheiding
tussen gebruikersuitleg en interne catalogushulpen.

**Herstel-/acceptatiecriterium:** verwijder deze interne uitleg uit de
gebruikersdocumentatie. Historische resultaten, ontwerpbesluiten en interne
tests mogen hun relevante context behouden. Verander het bestaande interne
`drop()`-contract niet.

## 4. Werkelijk uitgevoerde verificatie

Er is een schone `git archive`-kopie van de 166 kandidaatbestanden gebruikt in
`/private/tmp/solesta-review-20261116`, zonder `work/`, lokale omgevingen of
kennisbasis. Uitvoerbestanden staan buiten die bronkopie.

| Controle | Nieuwe uitkomst en begrenzing |
| --- | --- |
| Git-basis en inhoud | Beide schone checkouts bevestigd; volledige tree-ID identiek |
| `tools/build.py --check` | Geslaagd: beide gegenereerde runtimecatalogi reproduceerbaar |
| `tools/build_lab.py --check` | Geslaagd: deterministische Lab-build `7405793f3a14` |
| Ruff 0.16.7 | `All checks passed!` op de schone kandidaat |
| Python `unittest discover` | **304 tests geslaagd**, inclusief archief-, back-up-, provider-, generator- en hygiënetests |
| HA 2026.9.0-contracten | **30 tests geslaagd**, zelfstandige Python 3.14.10 met de opgegeven minimumomgeving |
| HA 2026.10.4-contracten | **30 tests geslaagd**, dezelfde zelfstandige Python met de opgegeven tweede omgeving |
| Bestaande kaarttests | **33 callbacks met hun oorspronkelijke assertions geslaagd** via reproduceerbare Node REPL-harness; geen geslaagde native `node --test`-run |
| Echte 0.2.3-fixture | Alle **21** fixture-expressies exact gelijk aan de defaults in `thetruth.py` van commit `bccaee…`; niet uitsluitend tegen een intern verwachte fixture getest |
| Markdown-bestandslinks | Alle **65** Markdownbestanden in de kandidaat recursief nagegaan; geen ontbrekend lokaal bestandsdoel. Headingankers/externe URLs niet als volledige linkchecker gevalideerd |
| ESPHome-profiel MQTT uit | Exacte publieke YAML valideert met ESPHome **2026.9.1**, dummysecrets en lege broker |
| ESPHome-profiel MQTT aan | Dezelfde YAML valideert met dummybroker en MQTT ingeschakeld |
| Werkelijke C++-parserlambda | Hostcompilatie en uitvoering met Clang AddressSanitizer/UndefinedBehaviorSanitizer geslaagd |
| Gerichte codeproeven | Bronbinding/kopieën, exacte roots, credentials, gespreide MQTT-publicaties, kitactualiteit, geschiedenis, Santiago en ontbrekende collector reproduceerbaar |
| Lokale officiële Hassfest | **Niet voltooid**: HA Core `2026.10.4` (`357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b`) vereist voor zijn formatter Ruff `>=0.16.9`; de aanwezige project-Ruff is `0.16.7` |
| Volledige ESP32-firmwarebuild | **Niet voltooid**: pakketresolutie van `noise-c` blokkeerde op DNS voor `api.registry.platformio.org` en mirror |

Bij de eerste Python-run waren per abuis de eigen `.log`-bestanden binnen de
testkopie geplaatst. De hygiënetest wees precies die bestanden af. Na
verplaatsing buiten de schone bronkopie slaagden alle 304 tests. Dat was een
fout in de reviewopstelling, geen productbevinding.

De native Node-testrunner bleef in de beschikbare REPL hangen en eindigde
met een kernel-timeout. De alternatieve harness hergebruikt alle 33 bestaande
testcallbacks/assertions en vervangt de runner met minimale Event/DOM-doubles.
Dat is bruikbaar gedragstestbewijs, maar geen bewijs voor de exacte
GitHub-Node-22-uitvoeringsomgeving. Er is geen nieuwe afhankelijkheid
geïnstalleerd om deze beperkingen te omzeilen.

De C++-proef dekt geldige records en pompfracties, ongewijzigd doorlaten van
de ruwe waarde 309, atomaire afwijzing van NaN/floatoverflow, deelrecords en
CR/LF, overmatige regellengte, niet-ASCII-resynchronisatie, controllercodes,
onverwante logregels en behoud van ruwe waarden bij stale data. Zij bewijst
geen ESP32 UART-driveroverflow of timing tijdens Wi-Fi-/brokerproblemen.

Lokale tijdelijke bewijsbestanden, geen publicatie-inhoud:

- `work/full-review-20261116/integration_probes.py` en
  `mqtt_discovery_probe.py`, met bijbehorende uitvoer;
- `work/full-review-20261116-dashboard/probe.mjs` en
  `run-card-assertions.mjs`;
- `/private/tmp/solesta-review-evidence-20261116/`, met suite-uitvoer,
  `expression_probe.py` en `kit_freshness_probe.py`;
- `/private/tmp/solesta-fw-review-20261116/`, met uitgewerkte dummyconfiguraties,
  buildbeperking en `parser-harness.cpp`.

## 5. Contracten die standhouden en bewuste keuzes

De volledige codebeoordeling en tests leveren ook positief bewijs, binnen de
hierboven genoemde grenzen:

- De productie-upgrade is beperkt tot de benodigde 0.2.3-opslagmetadata en
  het huidige formaat. Alle bestaande expressieteksten blijven letterlijk
  behouden, inclusief bronveld `last_update`, aangepaste spaties en bestaande
  alerttekst. Er is geen nieuwe impliciete providerafhankelijke mapping.
- Permanente entiteitsidentiteit volgt `system_uid` plus entiteitssleutel;
  credentials, hosts en zichtbare namen zijn geen vervanging daarvan.
  Providerwissels behouden identiteit, schakelen systemen uit en vereisen
  validatie voor heractivering. De reguliere zes wisselrichtingen zijn in de
  HA-contractsuite afgedekt; S100-03/S100-06 begrenzen de kopieroute.
- Het huidige `null()`-contract, lijstbehoud, veldvrije rekenfouten,
  hoofdlettergevoelige velden `None`/`none`, cyclusdetectie en gerichte
  expressiefouten zijn getest. De standaardalertketen blijft bij een defecte
  pomp/temperatuur onafhankelijke collector- en offlinealerts evalueren.
  S100-04 is een aparte bindingsuitzondering, geen heropening van de
  vervallen algemene foutbeschermer.
- Nieuwe reguliere systemen en kopieën kunnen uitgeschakeld vóór geslaagde
  live bronmapping worden opgeslagen; syntax en interne afhankelijkheden
  blijven gecontroleerd. Activering blijft aan live validatie gebonden.
- De generieke observationcache onderscheidt rapporttijd en wijzigingstijd.
  Identieke/ongebruikte callbacks en retained berichten tellen als report;
  cachelezing en reconnectpoging verzetten de tijd niet. Dit is een bewuste
  transportsemantiek. S100-02 betreft de ontbrekende concrete kitmapping.
- Web API blijft op het gegenereerde HTTPS-contract, met redirect-, omvang-
  en nestinggrenzen. Native controleert de bevestigde MAC en encryptie;
  MQTT TLS gebruikt normale certificaat-/hostcontrole. Diagnostiek bevat
  foutcategorieën/bronveldnamen en tijden, geen credentials of ruwe waarden.
- Archiefmappen, voortgang en status blijven aan permanente systeem-UIDs
  gekoppeld. Provideridentiteit is geen archiefsleutel. Bronhistorie,
  registereigendom, tijdzoneweekgrenzen, validatie vóór atomaire publicatie
  en back-upbarrières zijn beoordeeld en vallen onder de geslaagde suites.
  Er is geen nieuw archief- of back-updefect aangetoond.
- De kit is receive-only op GPIO1, gebruikt USB Serial/JTAG voor logging,
  secretverwijzingen en geen MQTT Discovery. Alle elf secretverwijzingen
  sluiten aan op het voorbeeldbestand; er zit geen echte `secrets.yaml` in
  de kandidaat. De README beschrijft losgekoppelde eerste flash, spanningsloos
  aansluiten, weerstand en gescheiden voedings-/programmeerhandelingen.
- Het kale OTA-`encryption:`-blok is volgens de actuele primaire
  [ESPHome OTA-documentatie](https://esphome.io/components/ota/esphome/)
  juist geldig en gebruikt de API-key. Het ontbreken van een apart
  OTA-wachtwoord is daarom geen bevinding. De bestaande firmwareversie bij
  een OTA-overgang blijft relevant; USB-herstel is gedocumenteerd.
- Integratie, kaart en canonieke resource gebruiken `1.0.0`; firmware
  `0.1.0` is bewust een andere versiecyclus. De twee gegenereerde Pythonmodules
  volgen hun canonieke werkboeken en zijn niet handmatig gewijzigd.

Bewust **geen** bevinding zijn: het niet ondersteunen van tijdelijke
Labschema's/oude resourcepaden/oude alertargumentvormen; de handmatige
providerexpressiemapping; het bestaande kaartrecept voor voorverwarmd water;
de verwijderde dashboardmigratiesectie; het ontbreken van Solesta-entiteiten
voor `flow_raw`, `frame_sequence` en controller state; de instelbare
collector-dangergrens van 200 °C; en het niet invoeren van een filter op de
onverklaarde ruwe waarde 309. De vergelijking met Solesta's eigen
energieformules is behouden.

Same-provider-herconfiguratie die alle gekoppelde systemen valideert is
expliciet beschreven in de duplicatenhandleiding. Dat beleid is niet als een
nieuwe fout aangemerkt. De gezonde runtime blijft apart beoordeeld op
isolatie van ongeldige of uitgeschakelde kopieën.

## 6. Nog ontbrekend acceptatiebewijs

Deze punten zijn geen extra bewezen productdefecten en tellen niet mee in de
twaalf bevindingen:

1. **Publieke eindref:** HACS, Hassfest, Python/JavaScript en CodeQL moeten
   slagen op precies de uiteindelijke publieke branch/PR/ref na eventuele
   reparaties. Lokale controles en eerdere resultaten vervangen dat niet.
   De [HACS Action](https://hacs.xyz/docs/publish/action/) valideert de
   betreffende GitHub-branch/ref; dat is hier niet uitgevoerd.
2. **Volledige 1.0.0-upgrade op een HA-doelomgeving:** een consistente
   0.2.3-herstelkopie moet met de uiteindelijke code worden gecontroleerd op
   letterlijke expressies, registers/apparaten, historie, bestaande kaart en
   herstel. Het M7-bewijs van 5 november had nog een inmiddels verwijderde
   `last_update`-herschrijving. De Lab-0.2.8-controle bewijst evenmin deze
   volledige productie-upgrade. De 30+30 HA-contracttests starten geen
   volledige HA-server.
3. **Firmware-eindbuild en fysiek gedrag:** voltooi de build van beide
   profielen in een werkende omgeving en controleer de herstelde MQTT-route,
   UART-uitval/herstel, boot en reconnect. De gemelde eerdere flash is nuttig
   bewijs, maar vervangt geen proef voor S100-01/S100-02 na herstel. De
   UART-driver/buffer onder transportbelasting is niet fysiek beproefd.
4. **Werkelijke Device Builder Dashboard import:** nadat de YAML werkelijk
   op de genoemde publieke `main` staat: ontdek/adopteer, haal de volledige
   YAML op, vul de private secrets aan en bouw het resultaat. De primaire
   [ESPHome-publicatiehandleiding](https://esphome.io/guides/creators/)
   koppelt import aan de openbare configuratielocatie en importmodus.
   mDNS-/HA-rediscovery bewijst deze download-/adoptieroute niet.
5. **Tijdelijke EMQX-afwijzing:** oorzaak blijft onbewezen. S100-05 is een
   reproduceerbare kandidaatcodefout, maar zonder bijpassende incidentdata
   mag geen causale koppeling worden geclaimd.
6. **Publicatieprivacy en repositoryinstellingen:** de lokale schone branch
   sluit de privéontwikkelgeschiedenis uit en de hygiënechecks slagen.
   Een nieuwe integrale vergelijking met alle oorspronkelijke private waarden,
   de actuele publieke geschiedenis, branchbescherming, private meldingen en
   GitHub-workflowstatus is niet uitgevoerd. Houd de beschreven schone
   publicatieroute aan en inspecteer de uiteindelijke payload/geschiedenis
   opnieuw. Een geslaagde patronen-/hygiënetest garandeert geen afwezigheid
   van ieder mogelijk persoonsgegeven.

De primaire ESPHome-documentatie is tijdens de review opnieuw geraadpleegd
en presenteerde versie 2026.10.2. De lokaal uitvoerbare configuratiechecks
gebruikten 2026.9.1. Dat verschil is expliciet; er wordt geen geslaagde build
met de nieuwste versie geclaimd. Voor OpenAI-productgedrag was geen externe
claim nodig.

## 7. Gemotiveerd releaseadvies

De kandidaat heeft een samenhangende provideronafhankelijke basis, sterke
regressiechecks en een correcte scheiding tussen ontwikkel- en
publicatiegeschiedenis. De oorspronkelijke Web API-upgrade is in code en
contracttests behouden. Dat is voldoende om gericht te repareren en daarna
opnieuw te accepteren.

Voor vrijgave ontbreken nu echter zowel concrete correcties als eindbewijs.
Vooral de herstart bij MQTT zonder Native-client, onzichtbare uitval van de
kitmeetbron, verschil tussen validatie en runtimebinding, voortijdige
MQTT-veldvalidatie en onjuiste historiepresentatie raken beloofde
gebruikersroutes. De eindrefchecks, Device Builder-import en volledige
doelomgevingscontrole blijven daarnaast zelfstandige vrijgavevoorwaarden.

**Advies: geef deze exacte kandidaat nog niet vrij en upgrade productie er
nog niet mee.** Handel S100-01 tot en met S100-09 af, besluit expliciet over
S100-10 tot en met S100-12, voer gerichte regressiechecks op de gewijzigde
inhoud uit en voltooi de open acceptatiepunten. Reparaties en live/publicatie-
acties volgen uitsluitend na een nieuwe opdracht.
