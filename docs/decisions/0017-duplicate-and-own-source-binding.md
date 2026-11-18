# D-ESP-017 — Bronbinding voor kopieën en eigenveldreferenties

Datum: 17 november 2026.

Status: uitgevoerd in de lokale kandidaat, als herstel van S100-03 en
S100-04 uit de [volledige review](../results/solesta-1.0.0-full-project-review-2026-11-16.md).

## Ontwerp en risico's

Live validatie gebruikt voor een kopie de echte communicatiebron. De runtime
vroeg de bronveldtabel daarentegen op onder de lokale alias. Per-bronproviders
kennen daar geen tabel: korte namen en absolute bronpaden konden na geslaagde
validatie alsnog ongebonden blijven. Een eigen entiteitsnaam als bronreferentie
passeerde bovendien de normale resolver en daarmee de pad- en ambiguïteitscontrole.

De correctie moet binding gelijk maken zonder identiteit, expressietekst,
providerprotocol of de betekenis van `null(...)` te veranderen. Belangrijkste
regressierisico's zijn verkeerde bronkeuze na herkoppeling, een kopie die een
gezond systeem blokkeert, en een eigenveldreferentie die onbedoeld een
entiteitscyclus wordt.

## Besluit

- `build_system_runtimes()` controleert eerst de bestaande directe
  duplicaatkoppeling tegen providerdiscovery en de geregistreerde aliasmapping.
  Daarna compileert het de expressies tegen de veldtabel van het
  communicatiedoel, precies zoals live validatie en hubherconfiguratie.
- De runtime behoudt de lokale alias als `source_system_id`; de provider
  vertaalt die bij het ophalen van waarden. Permanente systeem-/entiteits-UIDs
  blijven ongewijzigd. De correctie is provideronafhankelijk.
- Een eigen naam in de eigen expressie blijft een bronreferentie, maar gaat
  nu door dezelfde canonieke resolver als expliciete en overige bronverwijzingen.
  Een unieke korte naam bindt, ambiguïteit blijft een fout en uitsluitend
  nullable ontbrekende velden mogen ontbreken.
- Andere entiteitsnamen blijven entiteitsafhankelijkheden. De veldnamen
  `None` en `none` blijven hoofdlettergevoelig en volgen dezelfde regels.
- Er is geen opslagmigratie, expressieherschrijving of nieuw configuratieschema.
  Integratie, kaart en resource blijven de onuitgebrachte kandidaat `1.0.0`.
  Een eerder ten onrechte geaccepteerde ambigue eigenbron vereist expliciete
  kwalificatie door de gebruiker; de integratie kiest geen veld voor hem.

## Verificatie

Regressies toetsen voor Native en MQTT dezelfde binding bij live validatie en
runtimeopbouw, na een nieuw providerlifecycle en na herkoppeling. Native gebruikt
gewone en absolute namen; MQTT korte, volledige en absolute namen. Zij
controleren het echte doel, de veldtabel, resultaten en ongewijzigde opslag/UIDs.

Compilerregressies toetsen unieke geneste eigenbronnen, ambiguïteit binnen en
buiten `null(...)`, ontbrekende vereiste/nullable velden en `None`/`none` naast
gewone entiteitsafhankelijkheden. De volledige suites blijven het productie-
0.2.3-contract en isolatie van foutieve kopieën toetsen.

## Netwerkacceptatie op 18 november 2026

De [aanvullende acceptatie](../results/s100-03-07-network-acceptance-2026-11-18.md)
met de geïnstalleerde Lab-code, echte Native-/MQTT-verbindingen en geïsoleerde
HA-opslag bevestigt de bronbinding van kopieën en de eigenveldresolver.
Nieuwe providerlifecycles zijn echt opnieuw verbonden; Native-subdevices
en herkoppeling zijn daarnaast door de HA-contractfixtures gedekt.
Er is geen volledige HA-procesherstart beproefd.
