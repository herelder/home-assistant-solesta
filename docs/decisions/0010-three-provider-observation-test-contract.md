# D-ESP-010 — Testcontract voor observatie en MQTT-provider

Datum: 29 oktober 2026

Status: aanvaard; M3-implementatie en M4-lokale contractacceptatie uitgevoerd,
live parallel-, storings- en switchacceptatie volgen in M5–M6

## Doel

Dit contract maakt D-ESP-008 en D-ESP-009 toetsbaar. Unit- en contracttests
gebruiken een injecteerbare klok en exact dezelfde observatieklasse voor Web
API, ESPHome Native en MQTT. Transporttests bewijzen alleen adaptergedrag; zij
mogen de timestampregels niet opnieuw implementeren.

## Canonieke observatiereeks

Begin met een lege providerlifecycle en de volgende expressionmetadata:

```text
volledige keys = {used, optional_used}
verplichte keys = {used}
```

| Stap | Report | Inhoud | `last_report()` | `last_update()` |
| ---: | --- | --- | --- | --- |
| 0 | geen | lege cache | `None` | `None` |
| 1 | ja | eerste `used=A` | t1 | t1 |
| 2 | ja | opnieuw `used=A` | t2 | t1 |
| 3 | ja | `unused=X` | t3 | t1 |
| 4 | ja | `unused=Y` | t4 | t1 |
| 5 | ja | eerste `optional_used=1` | t5 | t5 |
| 6 | ja | `used=B` | t6 | t6 |
| 7 | mislukt | geen geaccepteerde state | t6 | t6 |
| 8 | ja | replay `used=B` | t8 | t6 |
| 9 | ja | replay `used=C` | t9 | t9 |

Deze reeks draait als losse events voor Native en MQTT. Voor Web API worden
equivalente complete snapshots aangeboden. Iedere succesvolle poll verzet
`last_report`, ook wanneer de snapshot gelijk is. Een gebruikte key die uit
een nieuwe snapshot verdwijnt en later terugkomt, moet beide keren
`last_update` verzetten.

Aanvullende gelijkheidstests omvatten minstens:

- `True` tegenover `1`;
- lijst tegenover tuple;
- gelijkwaardige mappings met andere invoegvolgorde;
- twee NaN-floats;
- bytes tegenover tekst;
- geneste waarden zonder mutatie door een later gewijzigde invoerreferentie.

## Lifecyclegevallen

Voor alle providers wordt getest:

- een gefaalde reportpoging verandert geen cache of timestamp;
- herevaluatie van de coordinatorcache verandert geen report- of update-tijd;
- transient reconnect behoudt waarden en `changed_at`;
- een identieke eerste replay na reconnect verzet alleen `last_report`;
- een gewijzigde eerste replay verzet beide tijden wanneer de key gebruikt is;
- een nieuwe providerinstantie begint leeg en vestigt een nieuwe baseline;
- twee lokale systemen met dezelfde communicatiebron delen reports maar
  berekenen `last_update()` met hun eigen volledige referenced-keyset;
- unload en dubbel unload laten geen taken, callbacks of sockets achter.

Voor Web API wordt apart bewezen:

- identieke complete polls: report wel, update niet;
- gewijzigde gebruikte waarde: beide;
- uitsluitend gewijzigde ongebruikte waarde: alleen report;
- aanwezig → ontbrekend → aanwezig voor een gebruikte key: iedere overgang
  een update;
- HTTP-/JSON-/auth-/timeoutfout: geen timestampwijziging;
- succesvolle reauth gevolgd door statusresponse: report op de response, niet
  op de login.

## Expressiecontract

Compiler- en evaluatortests bewijzen:

- `last_report()` en `last_update()` accepteren geen argumenten of keywords;
- beide functies leveren `datetime | None` uit de expliciete
  evaluatiecontext;
- de functienamen komen niet in `source_keys` of `available_keys`;
- de bronidentifier `last_update` zonder haakjes blijft een gewone raw key;
- `aaaa/bbbb/cccc` canoniek `cccc__bbbb__aaaa` wordt;
- een unieke bladnaam als `cccc` naar het volledige pad bindt;
- `cccc` wordt geweigerd zodra ook `cccc__dddd__aaaa` bestaat;
- `cccc__bbbb` alleen op een hele segmentgrens matcht;
- een exacte korte naam geen voorrang krijgt op een langere kandidaat;
- `_0R__cccc` exact een top-level `cccc` kan selecteren;
- `_0R__cccc__bbbb__aaaa` exact het genoemde volledige pad selecteert;
- een onbekende verplichte naam faalt, terwijl een uitsluitend binnen `null(...)`
  gebruikt onbekend veld ook met een korte naam null kan opleveren;
- `null(cccc__bbbb)` de opgeloste volledige key optioneel maakt maar haar
  wel laat meetellen voor `last_update()`;
- de bindings gedurende een configuratierevisie niet veranderen wanneer later
  een colliderend topic verschijnt;
- herconfiguratie met die nieuwe sourceveldnamentabel de nu ambigue korte naam
  weigert;
- JSON-mappings en MQTT-topiclevels dezelfde pad-/naamlogica gebruiken;
- JSON-lijsten ondoorzichtige waarden blijven;
- de segmentcodec leegte, leidende cijfers, interne underscores, dubbele
  underscores, `_0`, een underscore vóór een te escapen teken,
  ASCII-interpunctie en Unicode reversibel verwerkt;
- niet-canonieke escapes, ongeldige absolute ankers en canonical-namecollisies
  worden geweigerd;
- alle bestaande expressieteksten blijven bytegelijk na migratie;
- nieuwe catalogusconfiguraties gebruiken voor entiteit `last_report` de
  fabrieksexpressie `last_report()`.

## MQTT-transportcontract

Tests met een fake client en waar passend een lokale standaardbroker omvatten:

- MQTT 3.1.1 connect via hostname en IP, alternatieve poort en keepalive;
- TCP en TLS met systeem-CA, correcte hostnaam en geldig certificaat;
- afwijzing van ongeldig certificaat, verkeerde hostnaam en niet-ondersteunde
  private-CA-/clientcertificaatconfiguratie;
- anonieme toegang en gebruikersnaam/wachtwoord;
- authweigering via de reauthclassificatie, zonder secret in fout of
  diagnostiek;
- subscription-QoS 0, 1 en 2 en behoud van de feitelijk ontvangen QoS- en
  RETAIN-metadata voor diagnostische tests;
- exact abonnement op `<root>/#` en afwijzing van lege/wildcardroots;
- exacte relatieve topicsegmenten, omgekeerde kwalificatie en kortste-unieke
  binding zonder semantische mapping;
- strikte UTF-8-decoding zonder strippen of JSON-/nummerconversie;
- invalid UTF-8: report wel, expression-visible cache niet vervangen;
- lege payload als lege string;
- retained baseline, identieke retained replay en gewijzigde replay;
- losse topics zonder statusregel, barrier, LWT of discovery;
- reconnectbackoff, opnieuw abonneren, cancellation en idempotent sluiten;
- één hub verwijderen zonder andere clients of de HA MQTT-integratie te
  beïnvloeden;
- geen publishactie vanuit de provider.

Configuratieflowtests omvatten:

- brokerkandidaat eerst valideren en bij falen niets opslaan;
- handmatig systeem met permanente lokale bron-UID en veranderlijke root;
- tijdelijke rootsubscriptie en live validatie van verplichte keys;
- optionele ontbrekende keys blokkeren niet;
- geen broker-/topicscan en geen discoverylijst;
- gelijke roots voor twee echte bronnen binnen één hub blokkeren;
- reconfiguratie behoudt bron-UID, systeem-UID, expressies en identiteiten;
- tijdelijke clients worden ook na annuleren of fout gesloten.

## Providerwissel- en regressiematrix

Alle zes gerichte wissels worden getest:

```text
web_api -> esphome_native
web_api -> mqtt
esphome_native -> web_api
esphome_native -> mqtt
mqtt -> web_api
mqtt -> esphome_native
```

Iedere richting bewijst:

- kandidaatfalen is zonder effect;
- succesvol opslaan deactiveert systemen;
- `hub_uid`, `provider_id`, subentry-ID, `system_uid`, lokale `system_id`,
  device-/entity-unique-ID, historie en expressies blijven behouden;
- activeren vereist een actuele live validatie;
- gewone systemen en duplicaten blijven van elkaar geïsoleerd.

Bestaande Web API- en Native-regressies blijven onderdeel van de volledige
suite. De nieuwe observatielaag mag hun responsevalidatie, identiteit,
universele afleiding, Recorderhistorie, kaart- of archiefcontract niet
veranderen.

## Verplichte uitvoercontroles

M3/M4 zijn pas lokaal gereed na minimaal:

```text
python3 tools/build.py --check
python3 tools/build_lab.py --check
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_card.mjs
Ruff
relevante Home Assistant-contracttests
Hassfest
```

De snelle volledige suite draait in een schone bronkopie. Genegeerde
ontwikkel-, herstel- en Office-lockbestanden worden niet verwijderd.

## Live acceptatiegrens

M2 voert geen installatie of uitvalproef uit. M5 controleert normale parallelle
werking in `solesta_lab`; M6 controleert pas na afzonderlijke toestemming
broker-/publisheruitval, reconnect, retained replay, providerwissels en een
broker buiten Home Assistant. Productie 0.2.3 blijft tot een afzonderlijk
releasebesluit ongewijzigd.
