# MQTT-provider M2 — ontwerp- en testcontract

Datum: 29 oktober 2026

Status: definitief afgerond; implementatie niet gestart

## Resultaat

M2 heeft de MQTT-uitbreiding omgezet in drie duurzame, implementeerbare
besluiten:

- [D-ESP-008](../decisions/0008-provider-observation-and-timestamps.md): één
  waarde-agnostische observatielaag en hetzelfde `last_report()`-/
  `last_update()`-contract voor Web API, ESPHome Native en MQTT;
- [D-ESP-009](../decisions/0009-standard-mqtt-provider-and-manual-sources.md):
  standaard MQTT 3.1.1 met een eigen `aiomqtt`-client, handmatige bronnen,
  brokeronafhankelijke TLS/authenticatie en geen discovery;
- [D-ESP-010](../decisions/0010-three-provider-observation-test-contract.md):
  de volledige observatie-, transport-, lifecycle-, configuratie-,
  providerwissel- en regressiematrix voor M3–M6.

De aanvulling van de gebruiker is bindend verwerkt: Web API registreert iedere
succesvolle gevalideerde statuspoll als report en vergelijkt de nieuwe
complete raw-statesnapshot met de vorige snapshot. Alleen wijzigingen van keys
die ergens in de source-expressies van het actuele systeem worden gebruikt,
inclusief uitsluitend optionele keys, bepalen `last_update()`.

## Belangrijkste ontwerpuitkomsten

- Timestamps zijn integratie-eigen evaluatiecontext, geen providerstates.
- Web API gebruikt complete-snapshotvergelijking; Native en MQTT gebruiken
  losse events door dezelfde observatiekern.
- JSON-objectkeys en relatieve MQTT-topiclevels worden één gekwalificeerd
  bronpad. `aaaa/bbbb/cccc` wordt canoniek `cccc__bbbb__aaaa`; expressies mogen
  de kortste unieke kwalificatie gebruiken.
- De compiler bindt die naam tijdens configuratievalidatie aan één volledig
  bronpad. Segmentmatching, een botsingsvrije codec, het absolute `_0R__`-
  anker en een per configuratierevisie bevroren sourceveldnamentabel voorkomen
  ambiguïteit of latere stille herbinding.
- `last_report()` en `last_update()` zijn statisch valideerbare
  contextfuncties; bestaande gelijknamige bronkeys zonder haakjes blijven
  gewone states.
- Bestaande source-expressies worden nooit herschreven.
- Voor nieuwe systemen wordt de fabrieksexpressie van entiteit `last_report`
  `last_report()`; implementatie verhoogt daarom expressieschema 7 → 8 en
  catalogusrevisie 10 → 11 via de canonieke spreadsheet en generator.
- MQTT-systemen worden uitsluitend handmatig toegevoegd en krijgen een
  permanente lokale bron-UID; broker, credentials, root en naam zijn geen
  identiteit.
- `aiomqtt==2.5.1` en MQTT 3.1.1 zijn voor de eerste implementatie gekozen;
  de requirementpin wordt in M3 nog tegen Home Assistant en Hassfest
  geverifieerd.
- Een statusregel, availability-/LWT-topic, barrier, retain of
  firmwarewijziging is niet vereist.

D-ESP-002 en D-ESP-006 bevatten een expliciete verwijzing naar D-ESP-008 waar
hun oudere Native-/complete-meetset-timestampregels zijn vervangen.

## Uitgevoerde controles

De vaste projectcontroles zijn in een schone tijdelijke bronkopie uitgevoerd:

| Controle | Resultaat |
| --- | --- |
| `python3 tools/build.py --check` | groen — `thetruth.py` correct |
| `python3 tools/build_lab.py --check` | groen — deterministische labbuild `ddcbfd4ceef5` |
| Python-tests | groen — 262 tests |
| Kaarttests | groen — 31 tests |
| Relatieve documentlinks | groen |
| Whitespacecontrole | groen |
| Redactie brokerhost, account, wachtwoord en lokale root | groen |
| Reversibiliteit en botsingsvrijheid segmentcodec | groen — 2.801 samengestelde voorbeeldsegmenten plus vaste randgevallen |

De standaardshell miste aanvankelijk de testdependencies en zag de vervuilde
ontwikkelwerkmap. De definitieve resultaten hierboven komen uit de bestaande
project-test-venv met `PYTHONDONTWRITEBYTECODE=1` en de gebundelde
Node-runtime, in de door het project voorgeschreven schone bronkopie.

## Niet uitgevoerd

M2 heeft geen Python-/JavaScriptimplementatie, gegenereerd bestand,
spreadsheet, manifest, kaartversie, configuratie-entry of live Home Assistant-
omgeving gewijzigd. Installatie, reconnect-/uitvalproeven en providerwissels
blijven voor M3–M6 en vereisen waar van toepassing afzonderlijke toestemming.
