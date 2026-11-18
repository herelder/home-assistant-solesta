# MQTT-provider M3 — implementatieresultaat

> Historisch bewijs voor de toenmalige kandidaat. Voor de actuele taal geldt
> [D-ESP-014](../decisions/0014-null-fields-expression-contract.md): `null(...)`
> heeft uitsluitend veldargumenten of veldvrije berekeningen; `None`/`none`
> zijn veldnamen. De toenmalige algemene foutbeschermer is vervallen.


Datum: 29 oktober 2026

Aangescherpt: 30 oktober 2026 — taalneutrale lokale alertrecords,
Home Assistant-vertaling in de statuskaart en gegroepeerde optionele
alertargumenten; ESPHome volledig waarde-agnostisch gemaakt

Status: afgerond in de canonieke bron; nog niet geïnstalleerd

## Resultaat

M3 voegt MQTT als derde expliciete provider toe naast Web API en ESPHome
Native. De implementatie volgt D-ESP-008, D-ESP-009 en het M3-deel van
D-ESP-010:

- één waarde-agnostische observatielaag bewaart per communicatiebron de ruwe
  states, `last_report` en de wijzigingstijd per key;
- Web API voert complete snapshots door die laag; ESPHome Native en MQTT
  voeren losse events door dezelfde pushcache;
- `last_report()` en `last_update()` zijn nul-argumentfuncties in de
  evaluatiecontext en geen nagemaakte providerstates;
- geneste Web API-velden en relatieve MQTT-topics gebruiken dezelfde
  reversibele, blad-naar-buiten gekwalificeerde bronnamen en kortste-unieke
  compile-time binding;
- MQTT gebruikt rechtstreeks `aiomqtt==2.5.1` met MQTT 3.1.1, TCP of TLS via
  de systeemvertrouwensketen, anonieme of gebruikersnaam-/wachtwoordtoegang,
  QoS 0–2, een schone sessie en begrensde reconnect;
- MQTT-systemen worden handmatig met een permanente lokale bron-UID en een
  veranderlijk exact root-topic toegevoegd en live gevalideerd;
- de provider interpreteert payloads niet, vereist geen statusregel,
  availability-/LWT-topic, barrier, retain, discovery of firmwarewijziging;
- bestaande source-expressies blijven bij migratie bytegelijk behouden, met
  als gerichte uitzondering de oude synthetische Native-fabrieksexpressie
  `last_report = last_update`, die `last_report()` wordt.

De configuratie-entry-minorversie is 8, het expressieschema 11 en de
catalogusrevisie 13. De canonieke spreadsheet levert voor nieuwe systemen
`last_report()` en de gegroepeerde vorm
`solar_thermal_alerts(optional(status_reporting, state_pump, temp_collector,
temp_tank_top, alerts), 90, 200, 10, 10)` als fabrieksexpressies. De vier
vroegere drempelentiteiten zijn verwijderd. Manifest, kaart en resourcecontract
staan synchroon op kandidaatversie 0.2.6.

## Belangrijkste bronwijzigingen

- `custom_components/solesta/observation.py`: gedeelde cache en
  timestampregels;
- `custom_components/solesta/source_fields.py`: reversibele padcodec en
  kortste-unieke binding;
- `custom_components/solesta/mqtt.py`: standaard MQTT-transport, subscriptions,
  cachebehoud en reconnect;
- provider-, compiler-, evaluator-, coordinator- en configuratielagen:
  onveranderlijke snapshots, referenced-keymetadata en evaluatiecontext;
- config flow: brokerconfiguratie, reauth, handmatige MQTT-bron,
  rootvalidatie en systeemherconfiguratie;
- Web API en ESPHome Native: dezelfde observatiecontracten zonder
  publisherbarrière als voorwaarde; Native publiceert iedere ontdekte
  `object_id` en interpreteert geen veldnamen of waarden.
- integratie-eigen alerts: taalneutrale vertaalsleutels en parameters; de
  statuskaart resolveert de gebruikerszin via Home Assistant in de actieve
  gebruikerstaal, terwijl vrije providerteksten ongewijzigd blijven.

## Uitgevoerde M3-controles

De volledige Python-suite is uitgevoerd vanuit een schone tijdelijke
bronkopie, zodat genegeerde herstel- en ontwikkelbestanden in de werkmap niet
zijn verwijderd en de repositoryhygiënetest zuiver bleef.

| Controle | Resultaat |
| --- | --- |
| `python3 tools/build.py --check` | groen — beide generatorproducten correct |
| `python3 tools/build_lab.py --check` | groen — deterministische labbuild `db45db236b1c` |
| Gerichte provider-/observatie-/regressietests | groen — 127 tests |
| Volledige Python-suite in schone bronkopie | groen — 282 tests |
| Dashboardkaart | groen — 33 tests |
| JSON-validatie en whitespacecontrole | groen |

De toegevoegde tests dekken onder meer reversibele bronnamen,
kortste-unieke binding, typegevoelige snapshotvergelijking, complete
Web API-snapshots, losse pushstates zonder barrier, MQTT-subscriptions,
payloadbehoud, QoS/retain-metadata, retained replay, ongeldige UTF-8,
cachebehoud en opnieuw abonneren na reconnect. De expressieregressies dekken
ook het scalaire en variadische `optional()`-resultaat, onafhankelijke
`None`-posities, de gegroepeerde alertaanroep en compatibiliteit met opgeslagen
negenargumentenexpressies. De validator- en migratietests dekken daarnaast de
vier constante alertargumenten, hun onderlinge voorwaarden en het verwijderen
van de vier vervallen drempelentiteiten uit configuratie en entiteitenregister.
De kaarttest legt vast dat het
dashboard zelf de reporting-entity als identiteitsbron selecteert.

## Grens en volgende fase

M3 heeft `/Volumes/config` en de live Home Assistant-installatie niet gelezen
of gewijzigd. Er is niets geïnstalleerd, herstart of aan een broker
gepubliceerd.

M4 voert de bredere lokale contractmatrix uit, waaronder Ruff, echte Home
Assistant-/aioesphomeapi-combinaties, alle providerwisselrichtingen en
Hassfest. M5 en M6 vereisen daarna afzonderlijke expliciete toestemming voor
installatie en live uitval-/herstelproeven.
