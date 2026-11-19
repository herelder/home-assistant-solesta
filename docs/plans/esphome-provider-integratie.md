# Plan van aanpak — ESPHome-provider in de Solesta-integratie

> Actualisering 13 november 2026: de kandidaat is opgeschoond volgens
> [D-ESP-013](../decisions/0013-production-baseline-compatibility-cleanup.md).
> Het [opschoningsverslag](../results/compatibility-cleanup-2026-11-13.md)
> beschrijft de nieuwe controles en de resterende volledige upgradeproef;
> historisch M7-bewijs geldt voor de toenmalige kandidaat.


Datum: 24 oktober 2026; bijgewerkt op 27 oktober 2026
Status: fase 5 en MQTT-acceptatie afgerond; gezamenlijke releasevoorbereiding
in M7 voor kandidaat 1.0.0, met resterende vrijgavepoorten in het M7-verslag

Dit document legt de leidende fasering vast. Een volgende fase begint alleen na
expliciete opdracht en nadat de stopcriteria van de voorafgaande fase zijn
beoordeeld. De volledige providerwissel hoort uitsluitend bij fase 5.

## Doel en randvoorwaarden

De bestaande Solesta-integratie via de Web API blijft ongewijzigd actief. De
ontwikkeling en acceptatie van de ESPHome-provider gebeurt daarnaast in de
gegenereerde integratie **Solesta Lab** (`solesta_lab`). Solesta Lab bevat
zowel de Web API-provider als de ESPHome Native-provider, zodat beide routes en
een protocolwissel onder hetzelfde entiteitscontract kunnen worden beproefd.

De live Home Assistant-configuratie onder `/Volumes/config` wordt pas gewijzigd
na een afzonderlijke opdracht, een herstelpad en een geslaagde labcontrole.

## Fasen

### Fase 1 — contract en empirische basis — afgerond

- De startbasis, identiteitscontracten en bestaande Web API-route zijn
  vastgelegd.
- De NanoC6-bronvelden en hun gedrag zijn empirisch gecontroleerd.
- Lokale werking zonder internet voor Nano en Solesta is bevestigd.
- Alle door ESPHome ontdekte `object_id`-velden, waaronder `flow_raw` en
  `frame_sequence`, zijn gewone publieke bronvelden voor source-expressies.
- `temperature_4_raw` blijft gekoppeld aan de bestaande gereserveerde T4-
  entiteit.
- Controllerstatus wordt nog niet als Solesta-entiteit gepubliceerd.

### Fase 2 — geïsoleerde labintegratie — afgerond

- Een reproduceerbare generator maakt `solesta_lab` uit de canonieke
  `solesta`-bron.
- Productie- en labdomein, config entries, entiteiten en runtimegegevens zijn
  van elkaar gescheiden.
- Het lab registreert zijn dashboardkaart onder een eigen custom-elementnaam
  en resourcepad; archivering blijft uit om productie-effecten te voorkomen.
- De labbuild krijgt een herleidbare build-ID zonder de publieke versie te
  verhogen.

### Fase 3 — ESPHome Native-provider en directe validatie — afgerond

De eerste verticale implementatie omvat:

- expliciete keuze tussen **Web API** en **ESPHome Native** in de
  configuratiestroom;
- een rechtstreeks versleutelde native-API-verbinding met host, poort en
  Noise-PSK;
- verificatie en opslag van het door de node gemelde MAC-adres;
- één stabiele hoofdbronidentiteit `<mac>`, met `<mac>/<device_id>` voor
  eventueel expliciet gemelde ESPHome-subdevices;
- vertaling van vluchtige native API-keys naar ESPHome-`object_id`;
- een abonnements-cache die door de bestaande Solesta-coordinator wordt
  gelezen;
- standaardmapping voor T1–T4, pomppercentage, geldigheid en laatste
  rapportage;
- de technische basis voor een latere protocolwissel, waarbij hub- en
  systeemidentiteiten en source-expressies behouden moeten blijven en systemen
  eerst worden uitgeschakeld voor handmatige controle;
- herauthenticatie en herconfiguratie per providerprotocol;
- regressietests voor de bestaande Web API-route en contracttests voor de
  nieuwe lokale route.

Op 22 oktober 2026 zijn aanvullend afgerond:

- de in ontwerpbesluit D-ESP-002 vastgelegde mDNS-keuzelijst, met handmatige
  hostinvoer als terugvalroute;
- een verbindingstest tegen de fysieke Nano vanuit Solesta Lab, inclusief een
  tweede verbinding met controle van het eerder vastgestelde MAC-adres.

De fysieke verbindingsproef is vastgelegd in
[`../results/esphome-native-provider-physical-acceptance-2026-10-22.md`](../results/esphome-native-provider-physical-acceptance-2026-10-22.md).

### Fase 4 — installatie en parallelle acceptatie in Home Assistant — afgerond

- Leg vóór plaatsing het herstelpad, de actuele productiebaseline en het
  expliciete herstartmoment vast.
- Genereer en installeer Solesta Lab naast de bestaande Solesta-integratie.
  De productie-integratie en haar Web API-configuratie blijven daarbij actief
  en ongewijzigd.
- Voeg in het lab één Web API-hub en één ESPHome Native-hub toe.
- Vergelijk waarden, beschikbaarheid en timing gedurende een representatief
  meetvenster.
- Controleer expliciet dat `flow_raw`, `frame_sequence` en controllerstatus
  geen Solesta-entiteiten worden en dat T4 gereserveerd blijft.
- Test Nano lokaal met geblokkeerde internettoegang; internet voor de Nano is
  voor deze dataroute niet vereist.
- Test beide storingsrichtingen afzonderlijk: Web API/internet onbereikbaar
  terwijl ESPHome lokaal doorgaat, en Nano onbereikbaar terwijl de Web API
  doorgaat en ESPHome na terugkeer automatisch herstelt.
- Maak een afzonderlijk Home Assistant-dashboard waarop beide providerkaarten
  naast elkaar worden vergeleken.
- Leg afwijkingen tussen beide providers vast en los blokkerende verschillen
  op voordat een providerwissel wordt getest.

Op 22 en 23 oktober 2026 zijn Solesta Lab, een Web API-labhub en een ESPHome
Native-labhub naast de ongewijzigde productie-integratie geaccepteerd. De
parallelle controle, het herstelpad, de entiteitsgrenzen, het geïsoleerde
vergelijkingsdashboard en beide uitval-/herstelrichtingen zijn vastgelegd in
[`../results/esphome-provider-phase4-parallel-acceptance-2026-10-23.md`](../results/esphome-provider-phase4-parallel-acceptance-2026-10-23.md).

### Fase 5 — providerwissel binnen Solesta Lab — afgerond

Deze fase begint pas nadat beide providers afzonderlijk in fase 4 zijn
geaccepteerd.

- Leg vooraf de config-entry-, hub-, systeem-, apparaat-, entity- en unique-ID-
  identiteit vast, samen met een controleerbare historiebaseline.
- Wissel de Web API-labhub naar ESPHome Native. Controleer dat systemen eerst
  uitgeschakeld zijn en uitsluitend na handmatige controle opnieuw worden
  gekoppeld.
- Controleer dat hub- en systeemidentiteiten, entity unique ID's en bestaande
  historie behouden blijven en dat geen dubbele entiteiten ontstaan.
- Herhaal de wissel terug naar de Web API-provider en voer dezelfde controles
  opnieuw uit.
- Test fout- en herstelroutes, waaronder een onbereikbare provider, een
  onjuiste encryptiesleutel en een afwijkend MAC-adres.
- Documenteer de uitkomst en beslis pas daarna of de wissel geschikt is voor
  een productie-upgrade.

Op 24 oktober 2026 is de bestaande Web API-labhub heen en terug gewisseld naar
ESPHome Native. Config entry, hub, permanente systeem-UID, apparaat,
entiteitsidentiteiten en historie bleven behouden; de systemen werden na beide
providerwissels zoals ontworpen eerst uitgeschakeld en pas na handmatige
broncontrole opnieuw geactiveerd. Een onbereikbare host en een onjuiste
encryptiesleutel zijn live geweigerd. De afwijkende-MAC-route is wegens het
ontbreken van een tweede geschikte fysieke node via de gerichte contracttests
gevalideerd. De volledige acceptatie, versies en productiebeoordeling staan in
[`../results/esphome-provider-phase5-switch-acceptance-2026-10-24.md`](../results/esphome-provider-phase5-switch-acceptance-2026-10-24.md).

### Voorwaarde voor fase 6 — universele lokale afleiding — geïmplementeerd

Voor de productievoorbereiding worden pompstatus, rapportagestatus en
systeemalerts eerst provider-onafhankelijk uit de genormaliseerde lokale
entiteiten afgeleid. De empirische Web API-regels, exacte grenssemantiek,
instelbare waarden, bronalert-samenvoeging, timeoutbeschikbaarheid en minimale
acceptatietests zijn vastgelegd in
[`../decisions/0006-universal-local-derived-diagnostics.md`](../decisions/0006-universal-local-derived-diagnostics.md).

Het besluit is op 25 oktober 2026 geïmplementeerd in de universele evaluator,
de gegenereerde entiteitencatalogus, het migratiepad 1.1/1.2 → 1.3,
coordinator en dashboardkaart. De regressiecontrole omvat beide providerbedradingen,
grensgevallen, bronalert-samenvoeging en de offline-/herstelovergang op basis
van een bewaarde complete meetset. Controllerstatus blijft buiten de publieke
Solesta-entiteiten; de waargenomen pompstart rond 60 °C en pompcyclustijden
zijn niet als alertlogica ingevoerd.

Het implementatie- en regressieresultaat staat in
[`../results/universal-local-diagnostics-implementation-2026-10-25.md`](../results/universal-local-diagnostics-implementation-2026-10-25.md).

### Fase 6 — productievoorbereiding en migratiebesluit — gestart

Op 5 november 2026 heeft de gebruiker verduidelijkt dat de resterende
productievoorbereiding gezamenlijk wordt uitgevoerd voor **Web API, ESPHome
Native en MQTT**. M7 van het
[MQTT-plan](mqtt-provider-integratie.md#m7--gezamenlijke-productievoorbereiding-voor-alle-providers)
werkt die gezamenlijke scope uit. De configuratieflow krijgt concrete
GUI-instructies voor alle drie providers, met een afzonderlijke uitgebreide
gebruikershandleiding voor source-expressions. De bestaande
[uitleg over de energieformules en verschillen met Solesta](../energy-calculations.md)
blijft behouden en wordt vanuit de configuratie- en expressie-uitleg gelinkt.
M7 is op opdracht gestart; de gebruiker koos **1.0.0** als gezamenlijke
releasekandidaat. Het [M7-resultaat](../results/solesta-m7-release-preparation-2026-11-05.md)
legt de gebruikersdocumentatie, actuele herstelkopieproef, lokale controles en
resterende publicatiepoorten vast. Live productieplaatsing en publicatie
blijven afzonderlijke besluiten.

- Automatisering bij een providerwissel mag uitsluitend de nieuwe
  `source_system_id` invullen. Bronvelden en hun onderlinge betekenis zijn niet
  generiek of ondubbelzinnig herkenbaar; bestaande source-expressies worden
  daarom nooit automatisch afgeleid, vervangen of aangepast. Het systeem
  blijft uitgeschakeld totdat de gebruiker de ongewijzigde expressies heeft
  beoordeeld, waar nodig handmatig heeft aangepast en live heeft gevalideerd.
- Test een echte `solesta`-upgrade op een herstelkopie, niet in Solesta Lab.
- Werk gebruikersdocumentatie, changelog en release notes bij.
- Verhoog en synchroniseer pas bij release de integratie-, manifest- en
  kaartversie.
- Publiceer pas na generatorcheck, Python-tests, kaarttests, HACS-validatie en
  Hassfest.

Op 26 oktober 2026 is het upgradepunt uitgevoerd met een door Home Assistant
gemaakte herstelback-up van de echte productie-integratie `solesta` `0.2.3`.
Kandidaat `0.2.4` migreerde de config entry van 1.1 naar 1.3 en het
expressieschema van 4 naar 6. De 21 bestaande entiteiten, hun unique ID's,
apparaat, dashboardbinding en 119.436 historieregels bleven behouden; de vier
nieuwe drempelentiteiten zijn eenmaal toegevoegd. Een tweede start was
idempotent en de terugrolkopie startte opnieuw correct met 0.2.3. Productie is
niet gewijzigd. Het volledige resultaat staat in
[`../results/solesta-production-upgrade-recovery-acceptance-2026-10-26.md`](../results/solesta-production-upgrade-recovery-acceptance-2026-10-26.md).

De resterende fase-6-punten — gebruikersdocumentatie, changelog,
releaseversie, publicatiecontrole en uiteindelijke releasevalidatie — worden
gezamenlijk in M7 afgehandeld. Het herstelkopiebewijs van 0.2.4 hierboven is
historisch; voor de actuele 1.0.0-kandidaat geldt het M7-verslag.

De review van 26 oktober en het aansluitende herstel wijzigen het
expressiecontract: upgrades behouden nu iedere bestaande expressie, ook oude
fabrieksteksten. Providerafhankelijke standaardexpressies zijn verwijderd;
de catalogus is de enige fabriek. De actuele `null(...)`-invoer voor
onafhankelijke alertregels staat in
[D-ESP-014](../decisions/0014-null-fields-expression-contract.md). Het eerdere
herstel staat in
[D-ESP-007](../decisions/0007-provider-independent-expressions-and-optional-evaluation.md).
Het [herstelverslag van 27 oktober](../results/solesta-review-fixes-2026-10-27.md)
beschrijft de broncode- en bibliotheektests. Op afzonderlijke opdracht is
kandidaat 0.2.5 daarna in Solesta Lab geplaatst en is Home Assistant herstart.
Beide labproviders en het productiedashboard functioneren; zie het
[installatieverslag](../results/solesta-lab-0.2.5-installation-2026-10-27.md).
Deze opstartcontrole vervangt geen volledige acceptatie van de gewijzigde
kandidaat. De herstelkopieacceptatie van 0.2.4 hierboven blijft versiegebonden.

## Bronmapping in fase 3

| Solesta-doel | ESPHome-bron | Behandeling |
| --- | --- | --- |
| collectortemperatuur | `temperature_1_raw` | rechtstreeks als °C |
| boilertemperatuur boven | `temperature_2_raw` | rechtstreeks als °C |
| boilertemperatuur onder | `temperature_3_raw` | rechtstreeks als °C |
| gereserveerde T4 | `temperature_4_raw` | bestaande verborgen/gereserveerde entiteit behouden |
| pomppercentage | `pump_raw` | fractie maal 100 |
| rapportage geldig | — | universeel afgeleid uit `last_report` via `report_delay`; `data_valid` is niet bepalend |
| laatste rapportage | — | universeel via de lokaal bijgehouden functie `last_report()` |
| flow | `flow_raw` | gewoon bronveld; betekenis uitsluitend in een source-expressie |
| controllerstatus | `controller_state_*` | voorlopig geen Solesta-entiteit; later alleen na apart ontwerpbesluit |

Diagnostische ESPHome-velden mogen in de interne broncache aanwezig zijn voor
validatie en foutonderzoek. Ze worden niet automatisch Solesta-entiteiten.
`frame_sequence`, data-agevelden en `data_valid` zijn gewone bronvelden en
krijgen in de provider geen bijzondere betekenis. Zij verschijnen alleen als
Solesta-state wanneer een source-expressie ze daarvoor gebruikt.

## Versienummering

| Component | Tijdens labontwikkeling | Bij publieke release |
| --- | --- | --- |
| Solesta-integratie en manifest | productie blijft `0.2.3`; labkandidaat `0.2.5` is geplaatst | nieuwe major release; definitief nummer bij release vaststellen |
| Dashboardkaart/resource-URL | gelijk aan de labmanifestversie; `LAB_BUILD_ID` blijft extra cachekenmerk | tegelijk met manifest naar de nieuwe major release |
| Solesta Lab | `0.2.5`, build `ddcbfd4ceef5`, opstartcontrole geslaagd | geen zelfstandige releaseversie |
| Config-entryschema | `1.4`; schema-upgrade behoudt alle bestaande expressies | nieuwe kandidaat afzonderlijk accepteren vóór release |
| Expressieschema/catalogus | versie `7` / revisie `10` | bij release meenemen |
| Web API-preset | bestaande gegenereerde revisie blijft leidend | generatorbron eerst aanpassen als het contract verandert |
| ESPHome-clientbibliotheek | `aioesphomeapi>=46.2.0`; contracttests met HA 2026.9.0/46.2.0 en HA 2026.10.4/46.6.0 | Home Assistant kiest de compatibele versie |
| NanoC6-firmware | huidige gevalideerde configuratie en rapporten zijn leidend | apart firmware-/projectversienummer vastleggen vóór distributie |

Een labbuild-ID maakt twee builds met dezelfde `0.2.x`-manifestversie
onderscheidbaar. Dat nummer is geen SemVer en vervangt de verplichte
versieverhoging bij een volgende labwijziging niet.

## Acceptatiecriteria fase 3

- Een onjuiste encryptiesleutel of ander MAC-adres wordt geweigerd zonder het
  secret te loggen.
- De Web API-provider en bestaande config entries blijven werken.
- De ESPHome-provider levert de goedgekeurde bronvelden via hetzelfde
  providercontract.
- `flow_raw` en `frame_sequence` zijn niet beschikbaar voor source-expressies;
  controllerstatus heeft geen standaardmapping naar een Solesta-entiteit.
- Generatorcheck, Python-tests en kaarttests zijn groen.

## Volgorde- en stopcriteria voor de resterende fasen

- Fase 4 vereist een afzonderlijke opdracht voor plaatsing van Solesta Lab in
  Home Assistant en een vooraf vastgelegd herstelpad.
- Fase 5 mag pas starten nadat de parallelle Web API- en ESPHome-metingen uit
  fase 4 inhoudelijk zijn geaccepteerd.
- Een protocolwissel mag geen permanente hub-, systeem- of entity-identiteit
  veranderen en mag geen onbevestigde mapping activeren.
- Fase 6 mag pas starten na een geslaagde heen-en-terugwissel in Solesta Lab,
  implementatie en regressieacceptatie van D-ESP-006 en een expliciet
  migratiebesluit.
