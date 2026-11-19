# Plan van aanpak — MQTT-provider in de Solesta-integratie

> Actualisering 13 november 2026: de kandidaat is opgeschoond volgens
> [D-ESP-013](../decisions/0013-production-baseline-compatibility-cleanup.md).
> Het [opschoningsverslag](../results/compatibility-cleanup-2026-11-13.md)
> beschrijft de nieuwe controles en de resterende volledige upgradeproef;
> historisch M7-bewijs geldt voor de toenmalige kandidaat.


> Publicatiekopie: installatie-, apparaat- en netwerkidentificatoren zijn
> consequent gepseudonimiseerd. Meetwaarden, tijden en uitkomsten zijn behouden.

Datum: 27 oktober 2026; bijgewerkt op 5 november 2026

Status: M1 tot en met M6 en aanvullende brokeracceptaties afgerond;
gezamenlijke M7-releasevoorbereiding voor kandidaat 1.0.0 in uitvoering

Positie: begrensde uitbreiding van fase 6 uit het ESPHome-providerplan

## 1. Doel en afbakening

Voeg `mqtt` toe als derde providerprotocol naast `web_api` en
`esphome_native`. De provider maakt zelf een standaard MQTT-verbinding met de
door de gebruiker gekozen broker en biedt een gevalideerde statussnapshot aan
via het bestaande `Provider`-contract. De broker mag binnen of buiten Home
Assistant en binnen het lokale netwerk of op internet draaien. De bestaande
systeemlaag, coordinator, expressie-evaluator, entiteitsplatformen,
dashboardkaart, Recorderhistorie en archiefcode blijven provider-onafhankelijk.

De uitbreiding blijft bewust klein:

- geen aparte broker, vertaaldienst of tweede integratie;
- geen afhankelijkheid van Mosquitto, Home Assistant OS of de Home
  Assistant-MQTT-integratie;
- geen teruglezen van door MQTT Discovery gemaakte Home Assistant-entiteiten;
- geen MQTT-specifieke branches in entiteiten, kaart of archiefcode;
- geen automatische bronmapping of aanpassing van bestaande
  source-expressies;
- geen eisen aan of wijzigingen van firmware of MQTT-publicaties van externe
  aanbieders; de provider voegt zich naar het geconfigureerde broncontract;
- geen productiewijziging totdat de provider in `solesta_lab` afzonderlijk is
  geaccepteerd.

Dit plan autoriseert geen providerimplementatie, wijziging van een externe
publisher, installatie, providerwissel, brokeruitvalproef of Home
Assistant-herstart. De eerder uitgevoerde installatie van Solesta Lab 0.2.5
geeft daarvoor geen doorlopende toestemming.

## 2. Vastgestelde uitgangssituatie

De volgende feiten zijn uit de actuele projectbron, de ontwerpbesluiten, de
resultaatverslagen en het MQTT-infrastructuurverslag vastgesteld:

- de werkbasis is branch `codex/esphome-provider`, commit `8de1c0d`; de
  werkmap was bij aanvang van dit plan schoon;
- productie gebruikt `solesta` 0.2.3 en blijft ongewijzigd functioneren;
- `solesta_lab` 0.2.5, build `ddcbfd4ceef5`, bevat een werkende Web API- en
  ESPHome Native-provider; labarchivering is uitgeschakeld;
- het huidige contract gebruikt permanente `hub_uid`- en `system_uid`-
  identiteiten en een veranderlijke `source_system_id`-koppeling;
- een providerwissel deactiveert systemen en bewaart identiteiten en alle
  bestaande source-expressies; alleen `source_system_id` mag eventueel
  automatisch worden ingevuld;
- de coordinator leest periodiek één providerstatus en evalueert die via de
  bestaande universele keten; de native provider laat zien dat een pushcache
  achter dit pullcontract kan worden geplaatst;
- Mosquitto en de Home Assistant-MQTT-integratie zijn operationeel en vormen
  de snel gerealiseerde eerste testomgeving; de NanoC6 publiceert rechtstreeks
  naar deze broker terwijl de native API blijft werken;
- de uiteindelijke provider moet broker-onafhankelijk zijn: de huidige
  Home Assistant-broker is een testdoel en geen runtime-afhankelijkheid;
- MQTT Discovery staat uit en hoort voor deze provider uit te blijven;
- de huidige testpublisher biedt meerdere losse MQTT-state-topics en
  aanvullende technische metadata; die concrete combinatie is testinput en
  geen eis aan andere ESPHome- of fabrikantimplementaties;
- transportmetadata wordt niet automatisch een publieke Solesta-entiteit; T4
  blijft de bestaande gereserveerde entiteit en controllerstatus blijft buiten
  de publieke Solesta-entiteiten;
- de intern genoemde topic-prefix en het raw-statustopic zijn voorstellen,
  geen geverifieerde interface.

## 3. Wat vóór implementatie wordt geverifieerd

M1 is geen inhoudelijke inventarisatie per topic. De provider behandelt
topicstates als basale, ondoorzichtige bronwaarden; eenheid, betekenis,
geldigheidsgrenzen en omzetting horen uitsluitend in de source-expressies van
het systeem.

De read-only proef stelt alleen het technische transportcontract vast:

1. brokerhost, poort, MQTT-versie, authenticatie en eventueel TLS;
2. de door de gebruiker gekozen root-topic en ontvangst via `<root>/#`;
3. de feitelijk aangeboden relatieve topicnamen en ruwe states, uitsluitend om
   de cache- en configuratieflow te kunnen beproeven;
4. QoS en retain zoals zij werkelijk worden ontvangen;
5. brokerrechten voor verbinden en abonneren onder de gekozen root;
6. het normale opzetten en weer sluiten van verbinding en abonnement.

Actieve reconnect-, herstart- en uitvalproeven vallen niet onder M1. Die
worden pas in M6 uitgevoerd nadat ontwerp, implementatie en lokale
regressietests zijn afgerond.

Er wordt geen topicmatrix met eenheden, cadans, domeinbetekenis of gewenste
waarden gemaakt. Ook availability, LWT, tellers, timestamps of samengestelde
payloads zijn gewone aangeboden topics; zij krijgen geen bijzondere betekenis
in de provider tenzij een source-expression ze gebruikt.

M2 legt daarnaast het broker-neutrale standaardprofiel vast: ondersteunde
MQTT-protocolversie, TCP en TLS met de normale systeemvertrouwensketen,
servercertificaatcontrole, anonieme of gebruikersnaam-/
wachtwoordauthenticatie, keepalive en client-ID. Private CA's,
clientcertificaten, WebSockets en broker- of leveranciersspecifieke
uitbreidingen vallen buiten deze release. De basis mag geen Mosquitto- of Home
Assistant-specifiek gedrag vereisen.

De proef gebruikt een begrensd read-only abonnement op de bestaande broker.
Geheimen, volledige brokerconfiguratie en niet-relevante topics komen niet in
broncode, fixtures of verslagen.

## 4. Hoofdkeuzes

### 4.1 Broker-onafhankelijke MQTT-client per Solesta-hub

De MQTT-provider beheert een eigen asynchrone clientverbinding naar de broker
die in de Solesta-hub is geconfigureerd. Hij gebruikt de Home
Assistant-MQTT-integratie niet als transport en leest geen MQTT-entiteitsstates
uit Home Assistant terug. De bestaande Mosquitto-installatie is daardoor één
geschikt testdoel, maar geen productarchitectuur.

De verbindingsconfiguratie omvat minimaal:

- brokerhost of IP-adres en poort;
- TLS aan/uit, met correcte servercertificaat- en hostnaamvalidatie;
- optionele gebruikersnaam en wachtwoord, of expliciet anonieme toegang;
- een stabiele maar niet-identiteitsbepalende MQTT-client-ID per hub;
- keepalive en een begrensd reconnectbeleid;
- de gevalideerde topicconfiguratie en gewenste QoS.

Voor een internetbroker is versleutelde TLS met certificaatcontrole de
standaard; een onversleutelde internetverbinding wordt niet stilzwijgend
geaccepteerd. Credentials worden als secrets behandeld, niet gelogd, niet in
diagnostiek of archieven opgenomen en nooit gebruikt als hub- of
systeemidentiteit. Een authenticatiefout kan daarom een protocolspecifieke
reauth-route vereisen. Brokerhost, poort en topics zijn herconfigureerbare
verbindingseigenschappen.

Iedere hub bezit zijn eigen client, abonnementen, reconnecttaak en cache.
`async_disconnect()` en `async_close()` stoppen uitsluitend die client en
laten andere Solesta-hubs, de Home Assistant-MQTT-integratie en overige
brokerclients ongemoeid. Een eerste versie voegt geen connection-pooling toe;
dat houdt uitval, herconfiguratie en opruimen per hub controleerbaar.

M2 kiest de stabiele `aiomqtt==2.5.1`-reeks met MQTT 3.1.1. De requirementpin
wordt in M3 opnieuw tegen de ondersteunde Home Assistant-/Python-combinaties
en Hassfest gecontroleerd. De implementatie gebruikt geen intern of instabiel
API-contract van de Home Assistant-MQTT-integratie.

### 4.2 Eén gedeelde observatie- en pushcachetechniek

Alle drie providers krijgen één waarde-agnostische observatielaag voor ruwe
statevergelijking en timestamps. `esphome_native` en `mqtt` zijn daarnaast
beide push-providers en gebruiken dezelfde eventgedreven statecache. De Web
API voert complete snapshots door de snapshotoperatie van dezelfde
observatielaag.

De gedeelde laag beheert:

- de laatst ontvangen basale state per technische bronkey;
- de lokale ontvangst- en wijzigingstijden;
- een wachtmechanisme voor de eerste benodigde states;
- defensieve statussnapshots voor `get_system_status()`;
- de toestand rond connect, disconnect, reconnect en sluiten.

De transportadapter doet uitsluitend transportwerk. ESPHome Native vertaalt
een native statecallback naar een technisch bronpad en state. MQTT abonneert
zich per geconfigureerd systeem op `<root-topic>/#` en gebruikt de exacte
relatieve topiclevels als bronpad. JSON-objectkeys en MQTT-levels volgen
dezelfde omgekeerde kwalificatie: `aaaa/bbbb/cccc` wordt canoniek
`cccc__bbbb__aaaa`, waarna de kortste unieke segmentprefix in expressies mag
worden gebruikt. Web API levert de gevalideerde mapping van iedere succesvolle
statuspoll als complete snapshot. Daarna voeren alle adapters dezelfde
vergelijking uit.

De cache behandelt states als ondoorzichtige waarden. Zij kent geen
temperatuur, pomp, eenheid, grens, JSON-betekenis of Solesta-record. Zij
vergelijkt alleen de aangeleverde state met de vorige state en bewaart de
laatste waarde. Alle inhoudelijke interpretatie en omzetting gebeurt in de
source-expressies van het systeem. De provider voegt geen fabrieksexpressies,
automatische semantische veldmapping of entiteitsbetekenis toe.

### 4.3 Integratie-eigen `last_report()` en `last_update()`

De timestamps worden uit geen van de drie externe transports afgeleid en zijn
geen aangeboden source-topics. De integratie stelt twee contextfuncties
beschikbaar aan iedere source-expression:

- `last_report()` geeft de lokale timestamp van de laatste succesvol
  gevalideerde Web API-statuspoll, Native-statecallback of MQTT-PUBLISH onder
  de gekoppelde root.
- `last_update()` geeft de lokale timestamp waarop voor het laatst de ruwe
  state veranderde van een technische bronkey die daadwerkelijk ergens in de
  source-expressies van dit systeem wordt gebruikt.

Daaruit volgen deze vaste regels:

1. iedere succesvolle Web API-statuspoll ververst `last_report()`, ook als de
   complete snapshot gelijk is aan de vorige;
2. iedere Native-statecallback en ieder MQTT-bericht onder de root ververst
   `last_report()`, ook als de waarde gelijk blijft of de key niet in een
   source-expression voorkomt;
3. alleen een type-/waardeverschil van een in source-expressies gebruikte key
   ververst `last_update()`;
4. een identiek report ververst dus wel `last_report()`, maar niet
   `last_update()`;
5. een wijziging op een niet-gebruikte key ververst alleen `last_report()`;
6. de eerste waargenomen state van een gebruikte key vestigt de cachewaarde en
   telt als update;
7. een Web API-key die uit een complete volgende snapshot verdwijnt, geldt
   als gewijzigde state wanneer die key wordt gebruikt;
8. een retained replay volgt precies dezelfde regels: ontvangst ververst
   `last_report()` en alleen een verschil met de reeds bekende cachewaarde
   ververst `last_update()`;
9. na een nieuwe providerlifecycle is er geen eerdere cachewaarde; de eerste
   waargenomen states vormen daarom de nieuwe lokale basis;
10. een mislukte poll, disconnect, reconnectpoging of herevaluatie van oude
   cachedata ververst geen van beide timestamps.

De compiler levert naast verplichte keys ook de volledige verzameling in
source-expressies gerefereerde bronkeys, inclusief uitsluitend optioneel
gebruikte keys. Daardoor kan de cache `last_update()` bepalen zonder een
inhoudelijke waarde te begrijpen. De evaluator geeft de twee functies via de
evaluatiecontext door; zij worden niet als vervalste providerstates in de
cache geplaatst.

Bestaande source-expressies worden bij deze uitbreiding niet automatisch
gewijzigd. De nieuwe fabrieksexpressie voor de entiteit `last_report` wordt
`last_report()` en komt uitsluitend uit `EntityDescriptions.xlsx`. Een
bestaande bronkey `last_update` zonder haakjes blijft een gewone providerstate
en wordt niet herschreven. Dit volgt het catalogus- en migratiecontract van
D-ESP-007.

### 4.4 Gedeelde reconnect- en lifecycle-semantiek

De concrete verbinding verschilt, maar het zichtbare cache-, fout- en
herstelcontract van alle drie providers wordt zoveel mogelijk gelijk. Native
en MQTT delen bovendien dezelfde pushlifecycle:

1. verbinden en het state-abonnement activeren;
2. pushed states via dezelfde cache publiceren;
3. bij verbindingsverlies de foutklasse vastleggen en timestamps niet meer
   laten voortlopen;
4. de laatst geaccepteerde cache beschikbaar houden voor de bestaande
   coordinator- en time-outevaluatie;
5. met begrensde backoff opnieuw verbinden en opnieuw abonneren;
6. na nieuwe states dezelfde cache- en timestampregels hervatten;
7. bij unload alle provider-eigen taken, callbacks en verbindingen
   idempotent beëindigen.

Transportbibliotheken mogen intern anders reconnecten. Bij Web API is de
volgende coordinatorpoll de hersteltrigger; Native en MQTT gebruiken een
begrensde achtergrondreconnect. Het zichtbare providergedrag, cachebehoud,
foutpad, cancellationgedrag en herstelcontract worden met dezelfde
contracttests afgedekt. Een MQTT-hub raakt daarbij geen andere Solesta-hub, de
Home Assistant-MQTT-integratie of een Native-verbinding.

### 4.5 Handmatig toegevoegde MQTT-systemen; geen discovery

`hub_uid`, `provider_id` en `system_uid` blijven lokale permanente
identiteiten. Brokeradres, account en zichtbare namen zijn veranderlijke
configuratie. De root-topic is rechtstreeks de door MQTT aangeboden
`source_system_id`, maar geen vervanging voor de permanente `system_uid`.

In de eerste MQTT-versie worden geen source-systems ontdekt. De gebruiker:

1. configureert de brokerhub;
2. voegt een systeem handmatig toe;
3. geeft de root-topic en source-expressies op;
4. laat de configuration flow tijdelijk op `<root-topic>/#` abonneren;
5. slaat het systeem pas op nadat de ontvangen cache en expressies live zijn
   gevalideerd.

Ieder handmatig toegevoegd MQTT-bronsysteem gebruikt de exacte root-topic als
`source_system_id`. De provider retourneert zijn geconfigureerde bronnen; hij
scant de broker niet naar andere root-topics en bouwt geen discoverykeuzelijst.
Reconfiguratie blijft eveneens handmatig.

Runtimeabonnementen bestaan uitsluitend voor de roots van actieve,
geconfigureerde systemen. Duplicaten kunnen een bestaande geconfigureerde
MQTT-communicatiebron kiezen met behoud van hun lokale alias, `system_uid`,
entiteiten, historie en source-expressies.

### 4.6 Configuratie, herladen, duplicaten en providerwissel

De hubflow krijgt `mqtt` als expliciete, gevalideerde protocolkeuze. De
protocolspecifieke configuratie bevat het broker- en TLS-profiel en eventuele
credentials. De systeemsubentries bevatten de handmatige MQTT-roots direct als
`source_system_id`; er is geen afzonderlijk rootveld.

- een mislukte kandidaatvalidatie verandert de actieve hub niet;
- herconfiguratie binnen MQTT bouwt eerst een kandidaatverbinding en
  kandidaatprovider en publiceert de wijziging daarna via het bestaande
  alles-of-nietscontract;
- herladen schrijft abonnementen opnieuw in via de nieuwe providercyclus en
  ruimt oude abonnementen op;
- providerwissels tussen Web API, Native en MQTT volgen D-ESP-003 en
  D-ESP-007: alle systemen worden na opslaan uitgeschakeld, lokale identiteiten
  en expressies blijven byte voor byte behouden en alleen een ondubbelzinnige
  `source_system_id` mag worden ingevuld;
- een systeem wordt pas weer actief na live bron- en expressievalidatie;
- MQTT-reconfiguratie toont geen ontdekte bronlijst, maar laat de bestaande of
  nieuwe root-topic handmatig invoeren en opnieuw live valideren;
- onjuiste, uitgeschakelde of verouderde duplicaten blokkeren gezonde actieve
  systemen niet;
- een duplicaat kan een andere actuele MQTT-communicatiebron kiezen met behoud
  van alias, `system_uid`, entiteiten, historie en expressies.

## 5. Gefaseerde uitvoering

### M0 — overall plan — deze stap

**Resultaat:** dit plan, gebaseerd op de actuele bron en bestaande besluiten.

**Acceptatie:** geen code, externe publisher of live omgeving gewijzigd.

### M1 — read-only transport- en cachereferentie

**Status:** afgerond op 29 oktober 2026; zie
[`../results/mqtt-provider-m1-transport-cache-reference-2026-10-29.md`](../results/mqtt-provider-m1-transport-cache-reference-2026-10-29.md).

**Werk:** controleer de brokerverbinding en luister begrensd onder de door de
gebruiker opgegeven testroot. Leg alleen topic, ruwe ontvangen state, QoS,
retain en ontvangstvolgorde vast die nodig zijn voor cachefixtures; onderzoek
geen eenheid, betekenis, cadans of domeinregels per topic.

**Resultaat:** een klein geredigeerd transport-/cacheverslag en representatieve
pushfixtures zonder geheimen of woningidentificatoren.

**Acceptatie:** brokerroute, root-abonnement, topic-sleutelcontract en
testfixtures zijn voldoende om de gedeelde pushcache te ontwerpen.

**Stop:** geen broker-, publisher- of HA-uitvalproef en geen wijziging van de
publisher.

### M2 — duurzame ontwerpbesluiten en testcontract

**Status:** afgerond op 29 oktober 2026:

- [D-ESP-008 — provider-onafhankelijke observatie en timestamps](../decisions/0008-provider-observation-and-timestamps.md);
- [D-ESP-009 — standaard MQTT-provider en handmatige bronnen](../decisions/0009-standard-mqtt-provider-and-manual-sources.md);
- [D-ESP-010 — testcontract voor observatie en MQTT-provider](../decisions/0010-three-provider-observation-test-contract.md);
- [M2-resultaat en verificatie](../results/mqtt-provider-m2-design-contract-2026-10-29.md).

**Werk:** leg minimaal de gedeelde drie-providerobservatie en
Native/MQTT-pushcache,
`last_report()`/`last_update()`, handmatige MQTT-bronnen, reconnectsemantiek,
het broker-onafhankelijke client- en beveiligingscontract, bronidentiteit en
providerwisselgevolgen vast in nieuwe documenten onder `docs/decisions/`.

**Resultaat:** implementeerbaar contract en risicoanalyse.

**Acceptatie:** Web API vergelijkt opeenvolgende complete snapshots, de cache
is waarde-agnostisch, beide push-providers volgen dezelfde zichtbare lifecycle
en MQTT vereist geen discovery of aanvullende publisherfunctie.

### M3 — minimale providerimplementatie in de canonieke bron

**Status:** afgerond op 29 oktober 2026; zie
[`../results/mqtt-provider-m3-implementation-2026-10-29.md`](../results/mqtt-provider-m3-implementation-2026-10-29.md).

**Werk:** bouw de gedeelde observatielaag, push-statecache en
evaluatiecontextfuncties, laat ook Web API opeenvolgende snapshots daarin
vergelijken, implementeer de gekwalificeerde-bronpadtabel en kortste-unieke
compile-time binding, refactor ESPHome Native daarop, voeg `MqttProvider` en de
handmatige MQTT-systeemflow toe en implementeer brokerlifecycle,
TLS/authenticatie, diagnostics-redactie, vertalingen en gerichte tests. De
cache interpreteert geen bronwaarden.

**Resultaat:** derde provider in de bron en reproduceerbare Solesta Lab-build.

**Acceptatie:** alle drie providers gebruiken aantoonbaar dezelfde observatie-
en timestamptechniek en beide pushproviders dezelfde eventcache; geen
MQTT-branches buiten configuratie/providerbedrading; bestaande expressies
blijven byte voor byte behouden; alle lokale controles zijn groen.

**Stop:** nog geen installatie of herstart.

### M4 — lokale regressie- en contractacceptatie

**Status:** afgerond op 2 november 2026; zie
[`../results/mqtt-provider-m4-local-acceptance-2026-11-02.md`](../results/mqtt-provider-m4-local-acceptance-2026-11-02.md).

De brokeracceptatie is conform de opdracht uitgevoerd tegen de bestaande Home
Assistant Mosquitto-opstelling. Een tweede of externe broker viel buiten deze
fase. TLS is met een tijdelijk gegenereerde private test-CA, brokerketen en
hostnaam-/IP-SAN gevalideerd.

Na M4 is het brokercontract aanvullend live geaccepteerd tegen EMQX op de
Synology; zie
[`../results/mqtt-provider-emqx-acceptance-2026-11-05.md`](../results/mqtt-provider-emqx-acceptance-2026-11-05.md).

Test minimaal:

- Web API, Native en MQTT voeren equivalente reports door dezelfde
  observatiecontracttests;
- Native en MQTT voeren dezelfde losse pushreeks door dezelfde
  eventcachecontracttests;
- basale states blijven inhoudelijk ongewijzigd tot de evaluator;
- iedere succesvolle Web API-statuspoll en ieder ontvangen pushbericht
  ververst `last_report()`, ook bij identieke states of ongebruikte keys;
- alleen een gewijzigde, in een source-expression gerefereerde key ververst
  `last_update()`;
- eerste state, identieke herpublicatie, ongebruikte key, optionele key,
  Web API-keyverwijdering, retained replay en proces-/sessieherstart;
- handmatig systeem toevoegen en herconfigureren via root-topic, inclusief
  live expressionvalidatie en zonder discovery;
- disconnect, cachebehoud, begrensde reconnect, opnieuw abonneren, herstel en
  idempotent unload voor beide push-providers;
- het verwijderen van één MQTT-hub zonder andere Solesta-hubs, de HA
  MQTT-integratie of andere brokerclients te stoppen;
- hostname/IP, alternatieve poort, lokale TCP-broker en correct gevalideerde
  TLS-broker zonder Home Assistant-MQTT-integratie;
- anonieme en gebruikersnaam-/wachtwoordauthenticatie, geweigerde
  authenticatie en reauth indien die in M2 is vastgesteld;
- certificaat-, hostnaam- en verbindingsfouten zonder secrets in logs of
  diagnostiek;
- Web API en Native ongewijzigd, inclusief beide HA/aioesphomeapi-combinaties;
- alle zes protocolwisselrichtingen, met gewone systemen en duplicaten;
- bytegelijk behoud van bestaande source-expressies en behoud van hub-,
  systeem-, device- en entity-identiteiten;
- universele afleiding, timeout, historie- en archiefcontracten zonder
  providerafhankelijke zijpaden.

Verplichte controles zijn minimaal:

```text
python3 tools/build.py --check
python3 tools/build_lab.py --check
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_card.mjs
Ruff
relevante Home Assistant-contracttests
Hassfest
```

De snelle volledige suite draait volgens de bestaande werkwijze in een schone
bronkopie; genegeerde ontwikkel- en herstelbestanden blijven intact.

### M5 — Solesta Lab-installatie en parallelle acceptatie

**Status:** volledig aanvaard op 2 november 2026; zie
[`../results/mqtt-provider-m5-parallel-acceptance-2026-11-02.md`](../results/mqtt-provider-m5-parallel-acceptance-2026-11-02.md).

De normale parallelle route voldoet aan het acceptatiecriterium. De technische
M5-bevinding over de eerste `aiomqtt`-import is in de bron gecorrigeerd en met
een regressietest plus de HA-contractmatrix afgedekt: runtime-clientaanmaak
importeert niet meer vanuit de actieve eventloop. Build `c67c6ed260e1` is in
Solesta Lab geïnstalleerd. Na een HA-herstart ontstond geen nieuwe
blocking-I/O-gebeurtenis; alle drie provider-routes kwamen opnieuw online.

De live hercontrole is onder expliciete opdracht, met actuele preflight en
herstelpad uitgevoerd. Uitval-, reconnect- en providerwisselproeven blijven
afzonderlijk M6-werk.

**Werk:** installeer de nieuwe versie uitsluitend in `solesta_lab`; voeg een
MQTT-labhub toe die rechtstreeks met de bestaande HA OS-Mosquitto-testbroker
verbindt, naast Web API en Native; vergelijk voor dezelfde bron genormaliseerde
waarden en de regels voor `last_report()`/`last_update()`; controleer
handmatige systeemvalidatie, identiteit, historie, entiteitsgrenzen en
kaartgedrag.

**Acceptatie:** MQTT en Native leveren over een representatief meetvenster
inhoudelijk dezelfde genormaliseerde Solesta-uitkomst, zonder te eisen dat
beide transports dezelfde framing of publicatiecadans hebben; productie 0.2.3
blijft ongewijzigd.

**Stop:** geen providerwissel of uitvalproef voordat de normale parallelle
route is geaccepteerd.

### M6 — storings-, herstel- en switchacceptatie in het lab

**Status:** afgerond op 3 november 2026 binnen de beschikbare Home
Assistant/Mosquitto-opstelling. Het definitieve live bewijs staat in
[`../results/mqtt-provider-m6-failure-recovery-switch-acceptance-2026-11-02.md`](../results/mqtt-provider-m6-failure-recovery-switch-acceptance-2026-11-02.md).

Broker-, Native API-, publisher- en HA-uitval, retained replay, beide
providerwisselrondes, handmatige bronvalidatie, een tijdelijk duplicaat en
identiteits-/historiebehoud zijn live geslaagd. Een afzonderlijke externe
broker en een internet-TLS-endpoint waren tijdens M6 nog niet beschikbaar;
lokale TLS tegen de Home Assistant Mosquitto-opstelling is in M4 bewezen. De
later beschikbaar gekomen routes zijn op 4 en 5 november aanvullend
geaccepteerd tegen respectievelijk `mqtt.example.com:8883` met TLS en een
afzonderlijke EMQX-broker op de Synology. Zie
[`../results/public-mqtt-elderson-com-acceptance-2026-11-04.md`](../results/public-mqtt-elderson-com-acceptance-2026-11-04.md)
en
[`../results/mqtt-provider-emqx-acceptance-2026-11-05.md`](../results/mqtt-provider-emqx-acceptance-2026-11-05.md).

Deze fase vereist opnieuw expliciete toestemming, omdat broker-/publisheruitval
en providerwissels actieve labdiensten beïnvloeden.

Test afzonderlijk:

1. broker onbereikbaar terwijl Native doorloopt;
2. native API onbereikbaar terwijl MQTT doorloopt;
3. de huidige testpublisher onbereikbaar voor beide lokale routes;
4. broker-, HA- en publisherherstart en automatisch herstel;
5. retained replay, sessiewissel en herstel naar een complete geldige
   statecache;
6. Web API ↔ MQTT en Native ↔ MQTT, heen en terug;
7. duplicaten, handmatige broncontrole, identiteit en historie;
8. dezelfde provider tegen een afzonderlijke broker buiten Home Assistant;
9. waar een geschikt testendpoint beschikbaar is: TLS-verbinding met een
   internetbroker, zonder credentials of woningidentiteit in bewijsstukken.

### M7 — gezamenlijke productievoorbereiding voor alle providers

**Scope, bevestigd door de gebruiker op 5 november 2026:** M7 omvat de
volledige Solesta-integratie met Web API, ESPHome Native en MQTT. Deze fase
werkt de resterende productievoorbereiding van het ESPHome-plan uit, inclusief
de MQTT-uitbreiding. Het resultaat is één samenhangende gebruikersdocumentatie
en releasevoorbereiding voor alle drie providers.

**Status:** uitgevoerd vanaf 5 november 2026 voor kandidaat **1.0.0**, door de
gebruiker gekozen. Het [M7-resultaat](../results/solesta-m7-release-preparation-2026-11-05.md)
legt de documentatie, actuele herstelkopieproef, lokale controles en resterende
publicatiepoorten vast. M1–M6 en hun aanvullende brokeracceptaties blijven
afgerond.

**Configuratieflow:** werk `README.md` en
[`../installation.md`](../installation.md) bij met concrete GUI-instructies
die overeenkomen met de actuele formulieren en veldnamen. Beschrijf ten minste:

- provider kiezen en hub aanmaken, met de vereisten en verbindingsvelden voor
  Web API, ESPHome Native en MQTT, inclusief authenticatie en TLS waar relevant;
- het onderscheid tussen lokale `provider_id`/`system_id`, permanente interne
  identiteit en de door de provider aangeboden `source_system_id`;
- een systeem toevoegen, de bron selecteren of handmatig opgeven, expressies
  live valideren, opslaan en het aanvankelijk uitgeschakelde systeem activeren;
- de verschillende bronkeuzes: aangeboden Web API-/Native-bronnen tegenover
  een handmatig ingevoerde MQTT-root-topic;
- herconfiguratie, herauthenticatie, duplicaten en providerwissels, inclusief
  het opnieuw controleren van de bron en expressies vóór heractivering;
- herkenbare formulierfouten en hun herstelroute. Een providerwissel past
  bestaande source-expressies niet automatisch aan.

**Source-expressions:** maak een afzonderlijke gebruikershandleiding
`docs/source-expressions.md`, bereikbaar vanuit README, installatiehandleiding
en entiteitenoverzicht. Bouw de uitleg op van een eenvoudige bronwaarde naar
afgeleide entiteiten en complexere expressies. Behandel ten minste:

- wat een source-expression doet en het verschil tussen een providerbronveld,
  een Solesta-entiteitswaarde en een constante;
- hoe de gebruiker de werkelijk aangeboden bronveldnamen vindt, met uitleg
  van gekwalificeerde bronpaden, kortste unieke namen en naamconflicten;
- toegestane syntax, typen, eenheden, conversies, afhankelijkheden en de
  relevante functies, onderbouwd met gecontroleerde voorbeelden voor alle drie
  providers. Providerpayloads en bronveldnamen worden niet als universele
  standaarden voorgesteld;
- ontbrekende waarden via `null()`/`null(field, ...)`, logische operatoren,
  de gewone veldnamen `None` en `none`, de beperking tot veldvrije berekeningen
  binnen functieargumenten en het zichtbaar blijven van oorspronkelijke fouten;
- `last_report()` tegenover `last_update()`, het verschil met gelijknamige
  bronvelden en de gevolgen van identieke en retained berichten volgens het
  actuele observatiecontract;
- de universele afleiding van pompstatus, rapportagestatus en alerts,
  inclusief het aanpassen van alertconstanten in de expressie;
- de verhouding tussen catalogusdefaults, handmatige expressiewijzigingen en
  instelbare entiteitswaarden; licht ook toe wat leeg invoeren of het handmatig
  instellen van een waarde doet;
- live validatie, ongeldige typen of bronverwijzingen, cyclische
  afhankelijkheden en de interne reservering van `drop()`;
- behoud van bestaande expressies bij herconfiguratie en providerwissels en
  de expliciete upgradegevolgen uit de geldende ontwerpbesluiten. Geen nieuwe
  automatische bronmapping of expressieherschrijving invoeren als onderdeel
  van de documentatie.

**Formules en verschillen met Solesta:** behoud de bestaande uitleg in
[`../energy-calculations.md`](../energy-calculations.md), inclusief aannames,
eenheden, afronding en instelbare waarden. De vergelijking tussen kWh via de
MJ-berekening en Solesta's factor `0.00116`, en tussen berekende douche-energie
en Solesta's vaste `1.20582 kWh`, moet expliciet blijven staan. Maak deze uitleg
vindbaar vanuit installatie, entiteiten en de source-expressionhandleiding.
Dezelfde universele berekeningen gelden bij alle drie providers; de
documentatiewijziging verandert de formules niet.

**Overige productievoorbereiding:** werk privacyuitleg, changelog en release
notes voor de volledige integratie bij, handel publicatiepunten R08/R09 af,
controleer definitieve versienummering en voer de productie-/HACS-validatie
uit. Een echte `solesta`-upgrade wordt opnieuw op een actuele herstelkopie
beproefd. Productieplaatsing en publicatie blijven aparte besluiten.

**Acceptatie:** een gebruiker kan met de handleiding elk van de drie providers
configureren, een systeem valideren en activeren, en de eigen bronexpressies
begrijpen en bewust wijzigen. Veldnamen en voorbeelden zijn tegen de actuele
code gecontroleerd; links zijn geldig; bronkeuze, foutafhandeling en
providerwissel worden consequent uitgelegd. De formulevergelijking met Solesta
is behouden en duidelijk vindbaar. De verplichte releasecontroles en
herstelkopieacceptatie moeten vervolgens voor de uiteindelijke kandidaat zijn
afgerond voordat productieplaatsing of publicatie aan de orde is.

## 6. Versie- en generatorbeleid

- De gezamenlijke releasekandidaat wordt 1.0.0, zoals op 5 november 2026
  expliciet gekozen. Manifest, kaart en automatisch geregistreerde
  resourceversie gebruiken hetzelfde nummer.
- De eerste code- of labwijziging na 0.2.5 wordt 0.2.6.
- Manifestversie, zichtbare kaartversie en resource-cacheversie blijven gelijk.
- Een labbuild houdt daarnaast zijn afzonderlijke herleidbare build-ID.
- Config-entry minor version, expressieschema, catalogusrevisie en
  providerpresetrevisie worden alleen verhoogd als hun eigen persistente
  contract werkelijk wijzigt.
- De toevoeging van `last_report()`, `last_update()`, gekwalificeerde
  bronpaden, kortste-unieke naamresolutie en volledige referenced-keymetadata
  wijzigt het expressiecontract; de expressieschemaversie stijgt bij
  implementatie van 7 naar 8. De migratie bewaart iedere bestaande
  expressietekst ongewijzigd.
- De fabrieksexpressie van `last_report` wordt in `EntityDescriptions.xlsx`
  `last_report()`; de catalogusrevisie stijgt daarom van 10 naar 11. De
  providerpreset blijft ongewijzigd zolang het Web API-wirecontract niet
  verandert.
- De historische variadische aanscherping van 30 oktober verhoogt het
  expressieschema verder van 8 naar 9. De gegroepeerde alertfabriek verhoogt
  de catalogusrevisie van 11 naar 12; migratie herschrijft ook hiervoor geen
  bestaande expressietekst.
- Het schrappen van de vier alertdrempelentiteiten verhoogt het
  expressieschema vervolgens naar 10 en de catalogusrevisie naar 13. De vier
  waarden staan als constanten in `alerts_system` en worden uitsluitend bij
  source-expressionvalidatie gecontroleerd. De config-entry-minorversie wordt
  hiervoor 7.
- De definitieve gelijkstelling van de ESPHome- en MQTT-pushcache verhoogt het
  config-entryschema naar 1.8 en het expressieschema naar 11. ESPHome biedt
  iedere ontdekte `object_id` als gewone bronkey aan en maakt geen
  synthetische bronvelden meer.
- MQTT voegt geen providerafhankelijke fabrieksexpressies toe; de enige
  fabriek blijft `EntityDescriptions.xlsx`.
- `thetruth.py` en `provider_defaults.py` worden nooit handmatig gewijzigd.
- De definitieve publieke productie-uitgave krijgt het nieuwe major
  versienummer 1.0.0 na een afzonderlijk releasebesluit.

## 7. Overkoepelende acceptatiecriteria

De MQTT-uitbreiding is pas technisch gereed wanneer:

- alle drie providers aantoonbaar dezelfde waarde-agnostische observatielaag
  en timestampregels gebruiken;
- Native en MQTT aantoonbaar dezelfde push-statecache gebruiken;
- MQTT alle states onder een handmatig geconfigureerde root mechanisch cachet
  zonder hun inhoud, eenheid of betekenis te interpreteren;
- `last_report()` op iedere succesvolle statuspoll of ieder ontvangen
  pushbericht voortschrijdt en
  `last_update()` uitsluitend op een gewijzigde, in source-expressies
  gebruikte state;
- identieke, ongebruikte en retained states het vastgelegde timestampcontract
  volgen;
- MQTT-systemen uitsluitend handmatig worden toegevoegd en live gevalideerd;
  er vindt geen source-system discovery plaats;
- alle drie providers hetzelfde zichtbare fout-, cachebehoud- en
  herstelcontract volgen, met transportspecifieke reconnectscheduling;
- de provider rechtstreeks met een standaardbroker binnen of buiten Home
  Assistant kan verbinden en geen HA MQTT-integratie nodig heeft;
- het opruimen van één provider geen andere Solesta-hub of MQTT-client raakt;
- lokale TCP- en correct gevalideerde TLS-verbindingen, inclusief een externe
  brokerroute, volgens het vastgelegde beveiligingscontract werken;
- permanente systeemidentiteit stabiel en onafhankelijk van topics,
  credentials en namen is, terwijl MQTT de root-topic direct als veranderlijke
  `source_system_id` gebruikt;
- alle bestaande expressies en permanente identiteiten iedere providerwissel
  overleven;
- ongeldige of uitgeschakelde zustersystemen gezonde systemen niet blokkeren;
- Web API en Native alle bestaande regressies blijven doorstaan;
- MQTT en Native over hetzelfde meetvenster dezelfde genormaliseerde publieke
  Solesta-waarden en universele afleidingen leveren, onafhankelijk van hun
  transportframing;
- transportmetadata en controllerstatus niet automatisch publieke
  Solesta-entiteiten worden en T4 gereserveerd blijft;
- installatie-, uitval-, herstel- en switchbewijs in Solesta Lab is vastgelegd;
- generatorchecks, Python-tests, kaarttests, Ruff, HA-contracttests en Hassfest
  slagen op de uiteindelijke kandidaat;
- productie 0.2.3 tot een afzonderlijk releasebesluit aantoonbaar ongewijzigd
  blijft.

## 8. Belangrijkste risico's en beheersing

| Risico | Beheersing |
| --- | --- |
| Provider gaat bronwaarden interpreteren | Gedeelde cache bewaart alleen basale states; alle betekenis blijft in source-expressies |
| Providers gaan verschillend vergelijken | Eén observatielaag voor Web API, Native en MQTT; één eventcache voor de twee pushadapters |
| Timestamps krijgen transportafhankelijke betekenis | Eén integratiecontract: iedere succesvolle statuspoll of ieder pushbericht voor `last_report()`, alleen gebruikte statewijziging voor `last_update()` |
| Retained replay verandert timestamps onjuist | Ontvangst telt voor `last_report()`; `last_update()` volgt uitsluitend de vergelijking met de bekende cachewaarde |
| Een korte bronnaam wordt later ambigu | Compiler bindt tegen een per configuratierevisie bevroren sourceveldnamentabel; nieuwe velden binden niet stilzwijgend en herconfiguratie weigert ambiguïteit |
| MQTT-/JSON-segmenten botsen na omzetting | Reversibele `_0HH`-segmentcodec, segmentgrensmatching en gereserveerd absoluut `_0R__`-anker |
| Topicnaam wordt per ongeluk identiteit | Permanente lokale MQTT-bron-UID; topic alleen als veranderlijke route |
| Eigen brokerclient lekt secrets of taken | Afgebakende hub-lifecycle, secretsredactie, cancellationtests en reauthcontract |
| Alleen HA OS-Mosquitto werkt | Geen HA MQTT-API gebruiken; contracttests plus acceptatie tegen een broker buiten HA |
| Internetbroker wordt onveilig gebruikt | TLS en hostnaamcontrole als standaard voor externe brokers; geen secrets in logs/bewijs |
| MQTT-uitval hindert Native of Web API | Dezelfde cacheklasse maar geïsoleerde providerinstanties en gerichte uitvaltests |
| Nieuwe flow wijzigt expressies | D-ESP-007 behouden; alleen `source_system_id` mag automatisch wijzigen |
| Wildcard leest te veel brokerdata | Geen discovery; uitsluitend `<root-topic>/#` voor handmatig geconfigureerde systemen |
| Fabrikant biedt geen extra metadata | Geen probleem: alle ontvangen topics zijn basale states en expressions bepalen het gebruik |
| MQTT-code belast Web API-/Native-gebruikers | MQTT-client pas voor een MQTT-hub bouwen; geen globale brokerafhankelijkheid |
| Live test raakt productie | Solesta Lab, preflight, back-up, herstelpad en expliciete faseopdracht |

## 9. Vastgelegde gebruikersbesluiten

Op 29 oktober 2026 zijn de twee resterende punten besloten:

1. M1 mag read-only onder de opgegeven testroot meeluisteren en een klein
   aantal geredigeerde cachefixtures vastleggen.
2. Deze release ondersteunt uitsluitend standaard MQTT over TCP of TLS, met
   anonieme of gebruikersnaam-/wachtwoordauthenticatie. Private CA's,
   clientcertificaten, WebSockets en leveranciersspecifieke uitbreidingen
   vallen buiten scope.

Daarna is aanvullend besloten dat `last_report()` en `last_update()` door alle
drie providers worden vastgesteld. Web API vergelijkt daarvoor iedere nieuwe
succesvolle complete statussnapshot met de vorige snapshot.

De gekwalificeerde bronnaam is eveneens definitief vastgesteld: paden worden
van blad naar buiten geschreven (`aaaa/bbbb/cccc` wordt
`cccc__bbbb__aaaa`) en expressies mogen de kortste unieke segmentprefix
gebruiken. Resolutie gebeurt tijdens configuratiecompilatie tegen een bevroren
sourceveldnamentabel; D-ESP-008 legt de botsingsvrije segmentcodec en het
absolute `_0R__`-anker vast.

Brokercredentials komen nooit in documentatie, broncode, fixtures,
diagnostiek of logs. Als een GUI-handeling door de gebruiker nodig is, wordt
die stap apart en precies beschreven voor de Home Assistant Companion-app of
ESPHome-interface.

## 10. Eerstvolgende stap

M7 wordt uitgevoerd voor Web API, ESPHome Native en MQTT samen. Het
[M7-resultaat](../results/solesta-m7-release-preparation-2026-11-05.md) bevat de
documentatie, actuele herstelkopieproef, lokale controles en nog openstaande
publicatiepoorten. De privéprojectbranch mag niet met zijn oorspronkelijke
bewijsstukken worden gepubliceerd; volg de schone publicatieroute uit
[Maintainer security](../maintainer-security.md#publish-the-100-candidate-without-private-project-history).
Een upgrade van de live `solesta`-installatie en publieke release blijven
afzonderlijke besluiten en vereisen een expliciete opdracht en actueel
herstelpad.
