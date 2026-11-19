# D-ESP-011 — Providerbronidentiteit en neutrale metadata

> Actualisering 13 november 2026: [D-ESP-013](0013-production-baseline-compatibility-cleanup.md)
> vervangt de hieronder beschreven labcompatibiliteit en expressie-/bron-ID-migraties.
> Alleen productie 0.2.3 is een oud upgradepad; alle opgeslagen expressies blijven
> letterlijk behouden. De historische onderbouwing hieronder blijft leesbaar.


Datum: 4 november 2026
Status: aanvaard

## Besluit

`source_system_id` is de identiteit die de bronprovider zelf aanbiedt. De
integratie maakt daarvoor geen extra lokale route-ID en bewaart geen tweede
veld dat weer naar dezelfde bron wordt vertaald.

Voor MQTT is de concrete root-topic daarom rechtstreeks `source_system_id`.
Het systeemformulier toont diezelfde waarde als root-topic, de provider
abonneert zich op exact `<source_system_id>/#` en in de subentry bestaat geen
afzonderlijk `mqtt_root_topic`-veld. De waarde wordt bytegelijk behandeld,
binnen de MQTT-lengtegrens; betekenisvolle spaties worden niet gestript.

Voor ESPHome Native is de hoofdidentiteit het door de versleutelde API
bevestigde, genormaliseerde MAC-adres. Alleen expliciet door ESPHome gemelde
subdevices krijgen een onderliggende identiteit:

```text
<mac>
<mac>/<device_id>
```

Een entity met `device_id == 0` hoort bij het hoofddevice. Een andere
`device_id` is alleen geldig wanneer `DeviceInfoResponse.devices` die
subdevice-ID expliciet meldt. Numerieke API-keys blijven vluchtige routes;
`object_id` blijft de bronveldnaam binnen het bijbehorende device. Dezelfde
`object_id` mag daardoor op verschillende subdevices voorkomen zonder dat de
caches of timestamps worden vermengd.

## Providerprofiel en metadata

MQTT en ESPHome Native zijn neutrale doorgeefluiken en leveren zolang geen
eigenaarprofiel bekend is een leeg providerprofiel. De Web API-route blijft
ongewijzigd, omdat haar profiel de door de geconfigureerde externe aanbieder
geleverde systems-list bevat.

Generieke apparaatmetadata gebruikt geen vaste fabrikantnaam: onbekende
fabrikant is de lege waarde. Taaknamen, clientinformatie, logmeldingen en
archief-/backupmeldingen gebruiken waar een technische integratienaam nodig
is `DOMAIN`; commentaar, docstrings en gebruikersuitleg zijn merkneutraal.

## Migratie

Config-entryschema `1.9` zet bestaande bronnen als volgt om:

- MQTT: de opgeslagen `mqtt_root_topic` vervangt de lokale MQTT-bron-UUID en
  het oude rootveld wordt verwijderd; een vroege configuratie waarin de root
  al rechtstreeks stond blijft geldig;
- ESPHome Native: alleen de historische suffix `/uart1` wordt van bestaande
  hoofdbron-ID's verwijderd;
- duplicate systems die naar zo'n communicatiebron wijzen worden in dezelfde
  migratie naar de nieuwe bron-ID omgezet;
- een door de omzetting nieuw veroorzaakte identiteitsbotsing laat de migratie
  veilig mislukken; al bestaande ongerelateerde configuratiefouten worden niet
  door deze migratie uitgebreid beoordeeld.

`hub_uid`, `system_uid`, subentry-ID, lokale `system_id`, entity unique ID's en
source-expressies veranderen niet.

## Gevolgen

- MQTT-bronselectie en rootconfiguratie kunnen niet uit elkaar lopen.
- De actuele NanoC6 zonder expliciete ESPHome-subdevices levert alleen zijn
  MAC-adres als bron-ID; de firmware- of kanaalnaam speelt geen rol.
- Een toekomstige ESPHome-node kan meerdere echte devices aanbieden zonder
  providerspecifieke logica in entiteiten, coordinator of dashboard.
- D-ESP-002, D-ESP-003 en D-ESP-009 blijven gelden, behalve waar hun oude
  `/uart1`- of lokale MQTT-UUID-model door dit besluit is vervangen.
