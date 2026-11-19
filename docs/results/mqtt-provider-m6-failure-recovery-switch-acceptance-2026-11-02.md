# MQTT-provider M6 — storings-, herstel- en switchacceptatie in Solesta Lab

> Publicatiekopie: installatie-, apparaat- en netwerkidentificatoren zijn
> consequent gepseudonimiseerd. Meetwaarden, tijden en uitkomsten zijn behouden.

Datum uitvoering: 2–3 november 2026

Status: afgerond binnen de beschikbare Home Assistant/Mosquitto-opstelling

## Reikwijdte en herstelpad

M6 beproeft echte uitval, automatisch herstel, retained herladen,
providerwissels en identiteit in de bestaande parallelle Solesta
Lab-opstelling. Web API, ESPHome Native en MQTT kijken naar dezelfde fysieke
zonneboiler. De productie-integratie `solesta` blijft ongewijzigd op 0.2.3.

| Onderdeel | Gevalideerde toestand |
| --- | --- |
| Home Assistant Core | 2026.10.4 |
| Solesta Lab | 0.2.6, eindbuild `a74cba23e0c9` |
| Web API | `lab-web-api/sol_0217181ef299` |
| ESPHome Native | `lab-esphome-native/02_b6_a2_14_14_16_uart1` |
| MQTT | `lab-mqtt/nanoc6_01` |
| Broker | Home Assistant Mosquitto, lokale TCP-route |
| Herstelkopie | `Voor Solesta MQTT M6 - 2026-11-02` |
| Back-uplocaties | Home Assistant en Synology DSM |

De integratiepagina rapporteerde bij de nulmeting en na de uitgevoerde
herstelproeven 3 apparaten en 63 entiteiten. `.storage` en de Recorderdatabase
zijn niet rechtstreeks geopend of gewijzigd.

## Broker onbereikbaar terwijl Native doorloopt

De Home Assistant Mosquitto-add-on is gestopt. De brokerpoort weigerde daarna
verbindingen, terwijl Web API en ESPHome Native zichtbaar `Alles werkt
normaal` bleven tonen. MQTT hield de laatste geldige cache tijdens de
vertragingszones vast. Na meer dan tien minuten toonde uitsluitend de
MQTT-kaart:

- `Systeem offline`;
- geïnvalideerde afhankelijke waarden;
- de melding `Systeem is offline`.

Na het starten van Mosquitto herstelde de MQTT-route binnen ongeveer dertig
seconden zonder handmatige herconfiguratie. De retained baseline vormde weer
een complete geldige cache; alle drie kaarten stonden daarna normaal. Dit
bevestigt brokerisolatie, reconnect en retained herstel voor de aanwezige
Mosquitto-opstelling.

## Home Assistant- en Companion-herstart

Bij de gecontroleerde HA-herstart is de door de gebruiker vastgelegde volgorde
aangehouden:

1. HA-herstart aangevraagd;
2. gewacht tot de verbinding werkelijk werd verbroken om 23:03:37 CET;
3. de native HA Companion volledig gestopt en `isRunning: false` bevestigd;
4. gewacht tot HA om 23:04:37 CET weer bereikbaar was;
5. de Companion opnieuw gestart en de geladen HA-interface gecontroleerd.

Alle drie providers kwamen automatisch terug. Er was geen handmatige
provider- of systeemherconfiguratie nodig.

## Native API onbereikbaar terwijl MQTT doorloopt

Voor deze proef is uitsluitend de Native-hub tijdelijk en via de officiële
configuratieflow naar een lokale, transparante TCP-doorstuurroute gezet. De
daadwerkelijke verbinding `HA -> tijdelijke route -> NanoC6:6053` is vooraf
op socketniveau vastgesteld. MQTT bleef rechtstreeks via Mosquitto lopen.

De tijdelijke route is om 23:12:28 CET gestopt. De controles bewezen toen
tegelijkertijd:

- de tijdelijke Native-poort was gesloten;
- de Mosquitto-route bleef bereikbaar;
- de fysieke NanoC6 bleef rechtstreeks op poort 6053 bereikbaar;
- Native ontving geen nieuwe states meer, terwijl MQTT bleef doorlopen.

Native behield de laatste geldige cache gedurende de twee vertragingszones.
Om 23:25:06 CET, na meer dan tien minuten, toonde uitsluitend de Native-kaart
`Systeem offline`, geïnvalideerde afhankelijke waarden en `Systeem is
offline`. Web API en MQTT bleven `Alles werkt normaal` tonen.

De doorstuurroute is omstreeks 23:25:20 CET opnieuw gestart. Home Assistant
maakte binnen acht seconden automatisch opnieuw verbinding en de Native-kaart
herstelde zonder handmatige systeemwijziging. Daarna is de hub via de gewone
configuratieflow teruggezet op `solesta-nanoc6-demo.local`. Beide tijdelijke
listeners zijn gestopt; om 23:27:19 CET waren alle drie kaarten nog steeds
gezond en actueel. Daarmee is ook het rechtstreekse Native-herstel bewezen.

## Testpublisher onbereikbaar en herstart

De fysieke NanoC6 is om 23:31:16 CET uitgeschakeld en ruim tien minuten uit
gebleven. Daarmee verloren Native en MQTT gelijktijdig hun eigen route, terwijl
de Web API dezelfde zonneboiler via de externe infrastructuur bleef volgen.

Na ongeveer drie minuten hielden beide lokale providers conform ontwerp nog
hun laatste geldige cache vast en toonden zij niet voortijdig offline. Om
23:41:58 CET was het verwachte eindbeeld zichtbaar:

- Web API: `Alles werkt normaal`;
- ESPHome Native: `Systeem offline`, alle afhankelijke waarden
  geïnvalideerd en `Systeem is offline`;
- MQTT: dezelfde offline-uitkomst, dezelfde geïnvalideerde afhankelijke
  waarden en dezelfde melding.

De NanoC6 is om 23:44:53 CET weer ingeschakeld. Om 23:44:54 CET stonden zowel
Native als MQTT zonder handmatige herconfiguratie alweer op `Alles werkt
normaal`. Na een volledige volgende rapportagecyclus bleven beide routes
actueel. Dit bewijst gezamenlijke publisheruitval, provideronafhankelijke
vertragingszones en automatisch herstel van zowel de Native API-sessie als de
MQTT-statecache.

## Retained replay en sessieherstel

De brokeruitval, brokerherstart en HA-herstart hebben ieder een nieuwe
MQTT-sessie afgedwongen. Na iedere sessiewissel bouwde de provider de cache
opnieuw op uit de retained states onder de geconfigureerde root. De
afhankelijke entiteiten werden pas weer normaal nadat een complete geldige
cache beschikbaar was. Er was geen handmatige herpublicatie of systeemwijziging
nodig. Hiermee zijn retained replay, sessiewissel en herstel naar een complete
cache gezamenlijk beproefd.

## Web API naar MQTT en terug

De bestaande Web API-hub is via de gewone configuratieflow naar MQTT omgezet,
waarbij uitsluitend de brokerverbinding en de handmatige root
`solar/bridge_demo` zijn opgegeven. De eerste systeemherconfiguratie na deze
wissel legde een fout bloot: de drie-wegmerge nam een nieuw MQTT-root-topic nog
niet over als dat veld in de oude providerconfiguratie ontbrak. Daardoor trad
een `KeyError: 'mqtt_root_topic'` op.

De fout is in de canonieke configuratieflow gecorrigeerd, voorzien van de
regressietest
`test_first_system_reconfigure_after_switch_to_mqtt_stores_root`, als build
`a74cba23e0c9` in Solesta Lab geïnstalleerd en na een gecontroleerde
HA-/Companion-herstart opnieuw live beproefd. Dezelfde Web API → MQTT-wissel
slaagde daarna. Vervolgens is dezelfde hub via de gewone flow teruggezet naar
Web API en opnieuw met de fabrieksbronexpressies geactiveerd.

Voor en na de volledige ronde bleven gelijk:

- config-entry-ID `32NKT535009PKT8CXHNDNVAGQM`;
- apparaat-ID `1281fcb3cf57458aa2d4b97c7e8d9713`;
- permanente systeem-UID `78d76d9b-c1fc-4348-a3e2-1b6fc65b7951`;
- systeem-ID `sol_0217181ef299`;
- 21 entiteiten.

## ESPHome Native naar MQTT en terug

De bestaande Native-hub is via de gewone configuratieflow naar MQTT omgezet.
Het systeem werd zoals ontworpen eerst uitgeschakeld. Daarna zijn de actuele
MQTT-communicatiebron, de handmatige root `solar/bridge_demo` en de passende
`state__...`-bronexpressies live gevalideerd en opgeslagen. Vervolgens is
dezelfde hub via mDNS en de versleutelde Native API teruggezet naar
`solesta-nanoc6-demo.local:6053`; het systeem is opnieuw gekoppeld aan
`02:b6:a2:14:14:16/uart1` en met de Native-bronexpressies geactiveerd.

Voor, tijdens en na deze ronde bleven gelijk:

- config-entry-ID `4QWK5EBY9Z9Z197C23ZWCDMMM7`;
- apparaat-ID `d941fb3cace0469f9d22c1dad4c667e3`;
- permanente systeem-UID `c8bf2d7d-c75a-472b-82d9-58d23265ff48`;
- systeem-ID `02_b6_a2_14_14_16_uart1`;
- 21 entiteiten.

Na terugkeer naar Native toonden alle drie dashboardkaarten gelijktijdig
dezelfde actuele uitkomst: 19 °C, 0,76 kWh, 2,72 MJ en `Online`.

## Duplicaat, handmatige bron en historie

Onder de bestaande MQTT-hub is tijdelijk het duplicaatsysteem `m6_duplicate`
aangemaakt. De lokale alias werd gekoppeld aan de enige actuele
MQTT-communicatiebron en kreeg dezelfde handmatig gevalideerde
`state__...`-bronexpressies. Conform contract werd het duplicaat uitgeschakeld
aangemaakt; de drie bestaande apparaten en 63 entiteiten bleven ongewijzigd.
Na controle is uitsluitend deze tijdelijke koppeling via de gewone UI weer
verwijderd.

De gewone MQTT-systemen bleven volledig handmatig: er is geen brondiscovery
uit brokerdata uitgevoerd. Root-topic en bronexpressies zijn bij iedere
MQTT-activering expliciet ingevuld en tegen de actuele topiccache gevalideerd.

De Native-collectorentiteit bleef over de providerwissels exact
`sensor.02_b6_a2_14_14_16_uart1_collector_temperature`. Home Assistant toonde
op 3 november na de terugwissel één doorlopende historische meetreeks met
5-minutenaggregatie over de hele testperiode. Er zijn geen nieuwe entiteiten
voor het gewone systeem aangemaakt en de Recorderhistorie bleef aan dezelfde
entity-ID gekoppeld.

## Regressiecontroles

Na de laatste correctie zijn de canonieke generatoren en de labbuild opnieuw
gecontroleerd. `thetruth.py` en `provider_defaults.py` zijn gelijk aan de
uitvoer van hun generatoren; de Solesta Lab-build is deterministisch en heeft
build-ID `a74cba23e0c9`.

De lokaal beschikbare controles gaven het volgende resultaat:

- 145 MQTT-, Native-, model- en labbuildtests geslaagd;
- 16 generator- en bronbouwtests geslaagd;
- 24 review- en releasecontracttests geslaagd;
- 33 kaarttests geslaagd;
- geen whitespace- of patchfouten volgens `git diff --check`.

De nieuwe configuratieflowregressie staat in `ha_release_contracts.py`. Die
complete module kon in de aanwezige lokale testomgeving niet afzonderlijk
worden geladen omdat daar `aioesphomeapi` ontbreekt. Hetzelfde concrete
Web API → MQTT-scenario is na installatie van de correctie wel live voltooid,
inclusief opslag van het nieuwe root-topic, terugwissel en identiteitsbehoud.

## Niet beschikbare externe varianten

Een afzonderlijke tweede broker buiten Home Assistant is niet beschikbaar.
De gebruiker heeft voor M6 bepaald dat de aanwezige Home Assistant
Mosquitto-opstelling de testbroker blijft. Een TLS-route tegen diezelfde
Mosquitto-opstelling is al in M4 beproefd met zelf gegenereerde
testcertificaten. Een internetbroker wordt niet als vervanging verzonnen en
blijft wegens het ontbreken van een geschikt testendpoint buiten deze live
acceptatie.

## Eindbeoordeling

M6 is binnen de beschikbare labopstelling geslaagd:

- broker- en Native-uitval bleven providerlokaal;
- gezamenlijke publisheruitval gaf dezelfde vertraging en offline-uitkomst;
- broker, publisher, Native API en HA herstelden automatisch;
- retained replay herstelde de volledige MQTT-cache;
- beide MQTT-providerwisselrondes behielden permanente identiteit, apparaten,
  entiteiten en historie;
- handmatige MQTT-bronvalidatie en duplicaatkoppeling werkten;
- na alle proeven rapporteerde Solesta Lab weer 3 apparaten en 63 entiteiten;
- de actuele Home Assistant Core-logpagina meldde `Er zijn geen problemen!`.

De expliciet niet beschikbare externe broker- en internet-TLS-varianten zijn
hierboven als begrenzing vastgelegd en vormen geen onbeproefd verondersteld
bewijs.
