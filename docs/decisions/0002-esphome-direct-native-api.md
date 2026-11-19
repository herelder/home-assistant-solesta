# D-ESP-002 — Rechtstreekse ESPHome native-API-provider

Datum: 19 oktober 2026<br>
Status: aanvaard

Aanscherping op 4 november 2026: [D-ESP-011](0011-provider-source-identities-and-neutral-metadata.md)
vervangt de vaste `<mac>/uart1`-bronidentiteit door `<mac>` voor het
hoofddevice en `<mac>/<device_id>` voor expliciet gemelde ESPHome-subdevices.

Aanscherping op 29 oktober 2026:
[D-ESP-008](0008-provider-observation-and-timestamps.md) vervangt de
Native-specifieke regels voor synthetische timestamps, complete meetgolven en
framebarrières. Iedere Native-statecallback gaat als basale key/value-
waarneming door de gedeelde observatielaag. Barrière-, `data_valid`- en
data-agevelden mogen gewone bronkeys blijven, maar sturen `last_report()` en
`last_update()` niet. De identiteits-, discovery-, beveiligings- en
providercontracten hieronder blijven gelden.

## Besluit

De Solesta-integratie krijgt naast `web_api` een providerprotocol
`esphome_native`. Deze provider maakt zelf een versleutelde verbinding met de
ESPHome native API van de gekozen node. Een Home Assistant-config-entry van de
officiële ESPHome-integratie is daarvoor niet vereist en wordt niet als
gegevensbron gebruikt.

De gebruiker start de hubconfiguratie handmatig. Binnen die stroom toont de
integratie een dropdown van op dat moment via mDNS/zeroconf gevonden ESPHome-
nodes. De selectie is een bedieningshulp, geen identiteit. De provider valideert
de gekozen node daarna zelf via de native API en bewaart ten minste host, poort,
Noise-PSK en het verwachte MAC-adres in zijn eigen protocolspecifieke
hubconfiguratie. Een handmatig adres blijft een herstelroute voor netwerken
waar mDNS niet bruikbaar is.

De officiële ESPHome-integratie mag tijdens ontwikkeling of diagnose naast de
Solesta-provider actief zijn, maar maakt dan eigen ruwe Home Assistant-
entiteiten aan. De beoogde productieopstelling vereist haar niet. De Solesta-
provider registreert de ruwe ESPHome-bronvelden niet als HA-entiteiten; alleen
de bestaande genormaliseerde Solesta-entiteiten worden gepubliceerd.

## Identiteit en discovery

- `hub_uid` blijft de permanente lokale identiteit van de providerhub.
- `provider_id` blijft een expliciet gekozen lokale provideridentiteit.
- Het via de API bevestigde MAC-adres is apparaatcontrole en geen vervanging
  voor `hub_uid`.
- Host, poort, mDNS-naam, friendly name en projectnaam zijn veranderlijke
  verbindings- of beschrijvingsgegevens.
- Een mDNS-adresupdate wordt alleen geaccepteerd nadat de versleutelde API-
  verbinding hetzelfde MAC-adres bevestigt.
- Een ander MAC-adres wordt nooit stilzwijgend geadopteerd.

De configuratiestroom filtert niet uitsluitend op de projectnaam van de eigen
NanoC6-firmware. Daardoor kunnen later ook door fabrikanten geleverde ESPHome-
nodes worden gekoppeld. Geschiktheid wordt bepaald door live bronontdekking en
validatie van de gekozen systeemconfiguratie en source-expressies.

## Broncontract

Na `device_info_and_list_entities()` bouwt de provider per verbinding een
vertaling van de vluchtige numerieke API-key naar de stabiele
ESPHome-`object_id`. De `object_id` is de bronveldnaam die aan
`get_system_status()` en de source-expressies wordt aangeboden. Zichtbare
namen, Home Assistant entity-ID's en numerieke API-keys worden niet duurzaam
opgeslagen.

Voor de huidige bridge retourneert `systems()` één bronidentiteit:

```text
<genormaliseerd MAC-adres>
```

Een toekomstige node met expliciete ESPHome-subdevices retourneert daarnaast
`<genormaliseerd MAC-adres>/<device_id>` zonder wijziging van de
entiteitsplatformen.

## Losse bronvelden zonder synchronisatiecontract

De provider publiceert iedere door ESPHome ontdekte `object_id` als afzonderlijk
bronveld en voert iedere native statecallback onmiddellijk als één basale
key/value-waarneming door de gedeelde pushcache. Hij kent geen verplichte
veldset en interpreteert namen of waarden niet.

`frame_sequence`, `data_valid`, `data_age`, `data_age_seconds`, `flow_raw` en
vergelijkbare velden zijn, wanneer de node ze aanbiedt, gewone bronvelden. Zij
worden niet verborgen, samengevoegd of als barrière gebruikt. De provider maakt
geen synthetische `data_valid`- of `last_update`-bronvelden. `last_report()` en
`last_update()` worden uitsluitend door de gedeelde observatielaag bepaald uit
ontvangst en typegevoelige statewijzigingen.

Een ontbrekende native state wordt als de basale waarde `None` gecachet. Ook
niet-eindige of anderszins opvallende waarden blijven ondoorzichtig voor de
provider; de source-expressie en de entiteitsvalidatie bepalen pas hun
betekenis. Bij een tijdelijke reconnect blijft de bestaande observatiecache
behouden, gelijk aan MQTT.

## Gevolgen

- `aioesphomeapi` wordt een protocolspecifieke runtime-afhankelijkheid.
- De provider beheert connect, reconnect, state-subscription, cancellation en
  disconnect zelf.
- De bestaande systeemlaag, coordinator, entiteitsplatformen, dashboardkaart,
  Recorderhistorie en archivering blijven provider-onafhankelijk.
- Fabrikantspecifieke bronveldnamen worden niet in de provider genormaliseerd;
  die mapping hoort in de source-expressies.
- Noise-PSK en andere secrets worden niet opgenomen in diagnostiek, logs of
  archieven.
