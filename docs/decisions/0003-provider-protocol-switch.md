# D-ESP-003 — Providerprotocol wijzigen met behoud van systeemidentiteit

Datum: 19 oktober 2026; aangescherpt op 25 oktober 2026
Status: aanvaard

Aanscherping op 4 november 2026: [D-ESP-011](0011-provider-source-identities-and-neutral-metadata.md)
vervangt de hieronder genoemde Native-bron-ID door het MAC-adres van het
hoofddevice en, waar van toepassing, `MAC/device_id` voor subdevices.

## Besluit

Een bestaande providerhub mag van `web_api` naar `esphome_native` of terug
worden gewijzigd zonder de lokale hub en systemen te verwijderen. Er komt
vooralsnog geen automatische migratie van bronvelden, source-systemen of
source-expressies.

Eventuele automatisering in een latere productiemigratie is strikt beperkt tot
het invullen van `source_system_id`. De integratie mag geen relatie tussen
bronvelden veronderstellen en mag source-expressies bij een providerwissel
nooit automatisch afleiden, vervangen of wijzigen. Die expressies blijven
ongewijzigd opgeslagen totdat de gebruiker ze afzonderlijk beoordeelt en waar
nodig handmatig aanpast.

Een protocolwijziging verloopt als volgt:

1. De nieuwe providerverbinding wordt als kandidaat opgebouwd en gevalideerd.
2. Annuleren of mislukte validatie verandert niets aan de actieve configuratie.
3. Bij succesvol opslaan worden de nieuwe hubgegevens gepubliceerd en worden
   in dezelfde configuratietransactie alle systeemsubentries van de hub
   gedeactiveerd.
4. `hub_uid`, `provider_id`, subentry-ID, `system_uid`, lokale `system_id` en
   bestaande source-expressies blijven bewaard.
5. De gebruiker herconfigureert daarna ieder systeem afzonderlijk: een
   `source_system_id` kiezen uit `provider.systems()`, source-expressies waar
   nodig aanpassen, live valideren en activeren.

De deactivering is het eerste effect van een **opgeslagen** protocolwijziging,
niet van het openen van de configuratiestroom. Zo kan de gebruiker de flow
veilig annuleren.

## Identiteitscontinuïteit

De permanente entiteitsidentiteit blijft:

```text
<system_uid>_<entity_key>
```

Daarom blijven registry-records, door de gebruiker gewijzigde entity-ID's,
dashboardkoppelingen, Recorderhistorie en archiefidentiteit behouden. Tijdens
de gedeactiveerde tussenfase zijn de systeem-entiteiten niet actief; na
heractivering verschijnen dezelfde entiteiten opnieuw.

`source_system_id` is uitsluitend de veranderlijke koppeling naar het gekozen
providersysteem. Voor de huidige NanoC6-bridge is dat het genormaliseerde
MAC-adres.

## Gevolgen

- De bestaande reconfigure-flow krijgt een afzonderlijke tak voor een
  protocolwijziging; zij probeert oude broncontracten dan niet tegen de nieuwe
  provider te valideren of automatisch om te zetten.
- Ook als `source_system_id` later automatisch wordt ingevuld, blijven alle
  source-expressies byte voor byte ongewijzigd en blijft het systeem
  gedeactiveerd tot handmatige controle en live validatie.
- Reconfiguratie binnen hetzelfde protocol mag actieve systemen wel volgens
  het bestaande alles-of-niets-contract behouden.
- Iedere heractivering gebruikt de gewone systeemvalidatie en schrijft een
  validatiestempel voor de actuele providerrevision.
- Tests moeten aantonen dat een protocolwissel geen nieuwe `hub_uid`,
  `system_uid`, subentry of entity unique ID aanmaakt.
