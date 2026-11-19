# D-ESP-009 — Standaard MQTT-provider en handmatige bronnen

Datum: 29 oktober 2026

Status: aanvaard en geïmplementeerd in de 0.2.6-kandidaat (M3);
volledige contractacceptatie volgt in M4–M6

Aanscherping op 4 november 2026: [D-ESP-011](0011-provider-source-identities-and-neutral-metadata.md)
vervangt de lokale MQTT-bron-UUID plus afzonderlijke root door de root-topic
zelf als `source_system_id`.

Aanvulling op 14 november 2026: het toevoegen van een uitgeschakeld MQTT-
systeem of een systeemkopie volgt dezelfde regel als Native. Een mislukte
live bron-/waardeverificatie blokkeert het aanmaken niet; activeren vereist
wel een geslaagde live validatie. Syntax en interne afhankelijkheden worden
ook bij het aanmaken gecontroleerd.

## Besluit

`mqtt` wordt een derde expliciet providerprotocol naast `web_api` en
`esphome_native`. De provider maakt zelf verbinding met de door de gebruiker
gekozen broker. De Home Assistant-MQTT-integratie, Mosquitto add-on en MQTT
Discovery zijn geen runtime-afhankelijkheden.

De huidige HA OS-Mosquitto-broker blijft een testdoel. Dezelfde provider moet
zonder codewijziging met een standaardbroker buiten Home Assistant en, via
TLS, op internet kunnen werken.

## Clientbibliotheek en protocol

De eerste implementatie gebruikt de stabiele `aiomqtt==2.5.1`-reeks en MQTT
3.1.1. `aiomqtt` biedt een asyncio-interface, TLS, MQTT 3.1.1 en nette
disconnectsemantiek en steunt op `paho-mqtt`, zonder interne Home Assistant-
MQTT-API te gebruiken. De 3.0.0-alpha wordt niet gebruikt.

Bronnen:

- <https://pypi.org/project/aiomqtt/2.5.1/>
- <https://github.com/empicano/aiomqtt>

De exacte requirementpin wordt vóór M3-acceptatie opnieuw door Hassfest en de
ondersteunde Home Assistant-/Python-combinaties gecontroleerd. Een toekomstige
major upgrade is een afzonderlijk besluit.

## Ondersteund verbindingsprofiel

Deze release ondersteunt uitsluitend:

- MQTT 3.1.1 over TCP;
- TCP met TLS via de normale systeemvertrouwensketen;
- verplichte servercertificaat- en hostnaamcontrole bij TLS;
- anonieme toegang of gebruikersnaam en wachtwoord als paar;
- brokerhost of IP-adres en een valide poort;
- configureerbare keepalive met een veilige standaard van 60 seconden;
- subscription-QoS 0, 1 of 2, standaard 0;
- één geïsoleerde client per Solesta-hub.

Niet ondersteund in deze release zijn private CA-import, clientcertificaten,
WebSockets, brokerplugins, cloudvendorspecifieke tokens en een schakelaar om
TLS-validatie uit te zetten.

TLS gebruikt een standaard `SSLContext` met `CERT_REQUIRED` en
hostnaamcontrole. Onversleuteld TCP is alleen mogelijk na een expliciete keuze
in de configuratieflow; het formulier waarschuwt dat credentials en states dan
niet versleuteld zijn. De integratie probeert niet te raden of een hostname
"lokaal" of "internet" is.

Credentials worden nooit identiteit, logveld, diagnostiekveld, fixture of
archiefdata. Een brokerweigering wegens credentials wordt als authenticatiefout
geclassificeerd en gebruikt de bestaande Home Assistant-reauthroute. Host-,
poort-, TLS- en protocolfouten zijn configuratie- of communicatiefouten zonder
credentials in de melding.

## Clientidentiteit, sessie en QoS

De client-ID wordt stabiel uit de lokale `hub_uid` afgeleid met een korte
neutrale prefix. Zij bevat geen brokerhost, account, topic of zichtbare naam en
is zelf geen systeemidentiteit.

De eerste versie gebruikt geen persistente brokersessie als correctheidsbasis:
na iedere connect wordt met een schone MQTT 3.1.1-sessie opnieuw op alle
actieve roots geabonneerd. Retained states mogen de cache opnieuw vullen, maar
de provider vereist niet dat publishers retain gebruiken.

De gekozen subscription-QoS is alleen de bovengrens die de subscriber vraagt.
De feitelijke levering blijft het minimum van publish- en subscription-QoS.
De provider publiceert zelf geen states en wijzigt publisher-QoS of retain
niet.

## Handmatige MQTT-bronnen

Deze release ontdekt geen MQTT-systemen. De gebruiker:

1. configureert en valideert de brokerhub;
2. voegt een MQTT-systeem handmatig toe;
3. voert een concrete root-topic in; die waarde is rechtstreeks de
   `source_system_id`;
4. voert de source-expressies in;
5. laat de flow tijdelijk op `<root>/#` luisteren voor live validatie;
6. slaat het systeem uitgeschakeld op, ook als live validatie nog mislukt;
7. activeert het pas na geslaagde live bron- en expressievalidatie.

Bij mislukte live validatie worden geen geldige validatiestempels opgeslagen.
De ingevoerde expressies blijven behouden voor handmatige vervolginrichting.
Deze werkwijze geldt ook voor een MQTT-systeemkopie.

De provider retourneert uitsluitend deze lokaal geconfigureerde bronnen via
`systems()`. Hij scant geen broker, analyseert geen topicstructuur en bouwt
geen discoverykeuzelijst.

Het begrensd waarnemen van topics onder één al handmatig gekozen root om de
sourceveldnamentabel te valideren is geen source-system discovery. Het levert
geen voorstel voor andere roots of systemen op.

De volgende velden zijn veranderlijke routeconfiguratie en geen identiteit:

- brokerhost en poort;
- TLS- en authenticatieprofiel;
- subscription-QoS;
- zichtbare systeemnaam.

De root-topic is wél de door de MQTT-provider aangeboden bronidentiteit. De
permanente lokale systeemidentiteit blijft daarvan onafhankelijk `system_uid`.

Een root-topic is niet leeg, bevat geen NUL, `+` of `#`, eindigt niet op `/` en
past na UTF-8-encoding binnen de MQTT-lengtegrens. De runtime schrijft exact
`<root>/#` in. Het technische bronpad bestaat uit de exacte, op `/` gesplitste
levels van het relatieve topic na `<root>/`, inclusief eventuele lege levels.
De sourceveldnamentabel en omgekeerde kortste-unieke kwalificatie volgen
D-ESP-008; er vindt geen semantische topicmapping plaats.

Binnen één hub mogen twee echte handmatige bronnen niet dezelfde genormaliseerde
root gebruiken. Duplicaten blijven lokale Solesta-aliassen naar één bestaande
communicatiebron en openen geen tweede abonnement.

## Validatieflow

Hubvalidatie bewijst alleen dat de kandidaatclient kan verbinden en de
broker het authenticatie-/TLS-profiel accepteert. Zij publiceert niets.

Systeemvalidatie gebruikt een tijdelijke subscriptie op precies `<root>/#`.
Zij behandelt payloads als ruwe tekst, bouwt dezelfde observatiecache als de
runtime en valideert vervolgens:

- dat ten minste één report binnen de begrensde wachttijd aankomt;
- dat de waargenomen relatieve topics samen met expliciet absoluut
  gedeclareerde optionele paden een eenduidige sourceveldnamentabel vormen;
- dat alle verplichte expressionkeys beschikbaar zijn;
- dat de complete expressiongraph met de ontvangen snapshot kan evalueren;
- dat uitsluitend optionele ontbrekende keys de activering niet blokkeren.

Een timeout of fout laat de actieve configuratie ongemoeid. Annuleren sluit de
tijdelijke client en verwijdert geen bestaande bron.

## Lifecycle en reconnect

Iedere MQTT-hub bezit precies één client, ontvangsttaak, reconnecttaak en
observatiecache. De zichtbare lifecycle sluit aan op Native:

1. open lokale resources;
2. verbind en authenticeer;
3. abonneer op alle actieve geconfigureerde roots;
4. publiceer ieder ontvangen key/value-event naar de gedeelde observatielaag;
5. behoud cache en timestamps bij transient verbindingsverlies;
6. reconnect met exponentiële backoff vanaf 1 seconde tot maximaal 60
   seconden, met begrensde jitter;
7. schrijf na iedere reconnect alle abonnementen opnieuw in;
8. reset backoff pas na een succesvolle connect plus subscriptions;
9. beëindig ontvangst, reconnect, abonnementen en client idempotent bij unload.

Een disconnect- of reconnectpoging is geen report. Pas een nieuw ontvangen
PUBLISH-bericht hervat `last_report()`. Een retained replay verzet
`last_update()` alleen wanneer de ruwe state afwijkt van de behouden cache.

`async_disconnect()` en `async_close()` raken uitsluitend de eigen hubclient.
Zij stoppen geen broker, Home Assistant-MQTT-integratie, andere Solesta-hub of
Native-verbinding.

Web API heeft geen achtergrondabonnement. Daar blijft de coordinatorpoll de
hersteltrigger: een mislukte poll behoudt cache en timestamps; de volgende
geplande poll probeert volgens het bestaande connect-/reauthcontract opnieuw.
Het zichtbare cache-, fout- en herstelcontract blijft daarmee gelijk, terwijl
de transportscheduling verschilt.

## Providerwissel en herconfiguratie

D-ESP-003 en D-ESP-007 blijven ongewijzigd van kracht voor alle zes gerichte
wissels tussen Web API, Native en MQTT:

- kandidaatverbinding eerst valideren;
- annuleren of falen verandert niets;
- na opgeslagen protocolwissel alle systemen deactiveren;
- `hub_uid`, `provider_id`, subentry, `system_uid`, entiteitsidentiteiten,
  historie en source-expressies behouden;
- alleen een ondubbelzinnige `source_system_id` eventueel invullen;
- ieder systeem afzonderlijk live valideren en activeren.

Herconfiguratie binnen MQTT behoudt `system_uid` en de entiteitsidentiteiten.
Een wijziging van de root wijzigt ook `source_system_id`; de wijziging wordt
alles-of-niets gepubliceerd en oude abonnementen worden pas na een geldige
kandidaat opgeruimd.

## Gevolgen

- Er is geen firmwarewijziging, statusregel, availabilitytopic, LWT of
  barrièretopic vereist.
- Retain is toegestaan maar niet vereist.
- De provider kent geen topicwaarden of fabrikantsemantiek.
- MQTT-specifieke code blijft in configuratie, providerbedrading en de
  transportadapter; entiteiten, kaart en archief blijven generiek.
- De implementatie is in M3 uitgevoerd. Installatie, brokeruitval en live
  providerwissels vallen buiten M3 en vereisen de volgende fasen.
