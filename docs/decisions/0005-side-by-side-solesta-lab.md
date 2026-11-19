# D-ESP-005 — Gegenereerde Solesta Lab-integratie naast productie

Datum: 22 oktober 2026
Status: aanvaard

## Besluit

Ontwikkeling en acceptatie van de nieuwe provider vinden plaats in een
afzonderlijke Home Assistant-integratie met domein `solesta_lab` en zichtbare
naam **Solesta Lab**. De bestaande integratie onder domein `solesta` blijft
daardoor ongewijzigd naast de labintegratie werken.

`solesta_lab` wordt niet als tweede bronboom onderhouden. Het installabele
labpakket wordt reproduceerbaar gegenereerd uit de canonieke map
`custom_components/solesta`. De generator past uitsluitend een gecontroleerde
overlay toe voor:

- het Home Assistant-domein en de zichtbare integratienaam;
- een geïsoleerde labfrontend en uitgeschakelde archiefinitialisatie;
- reproduceerbare lab-buildmetadata in de diagnostiek.

De Web API blijft ook in de labintegratie beschikbaar. Zodra
`esphome_native` in de canonieke bron is geïmplementeerd, komt die provider
automatisch in een opnieuw gegenereerd labpakket terecht. Zo worden beide
providers met dezelfde runtime-, systeem- en entiteitscode getest.

## Isolatiecontract

- Productie gebruikt uitsluitend domein `solesta`; het lab gebruikt
  uitsluitend `solesta_lab`.
- Config entries, config subentries, devices, entity-registryidentiteiten,
  services, issues en `hass.data`-sleutels worden door het domein gescheiden.
- De automatische dashboardkaartregistratie gebruikt in het lab een eigen
  resourcepad en custom element. Daardoor registreren productie en lab niet
  hetzelfde element `solesta-status-card`.
- De archiefmanager en archiefservice worden in het lab niet gestart. Daardoor
  schrijft de labintegratie niet in het productiearchief. Als archivering later
  expliciet voor het lab wordt geactiveerd, maakt het bestaande generieke
  padcontract de bestemming `/config/archives/solesta_lab`.
- De labgenerator leest geen credentials, config entries, Recorderdata of
  bestanden uit `/Volumes/config`.
- Het gegenereerde pakket is een lokaal ontwikkelartefact en geen HACS-release.

De frontend- en archiefbestanden blijven onderdeel van het gegenereerde
pakket. De lab-bootstrap activeert de geïsoleerde dashboardkaart, maar niet de
archiefmanager. Archivering wordt pas voor het lab geactiveerd na een
afzonderlijk besluit en opslagtests.

## Identiteit en migratie

Een parallelle labinstallatie bewijst domeinisolatie en providerswitching
binnen `solesta_lab`. Zij bewijst niet dat een bestaande productie-entry onder
`solesta` correct naar een volgende release migreert. Die migratie wordt later
afzonderlijk getest in een geïsoleerde Home Assistant-herstelomgeving met het
echte productiedomein.

Bij providerswitching binnen het lab blijven de bestaande identiteitsregels
gelden: `hub_uid`, subentry-ID, `system_uid` en entity unique ID blijven
ongewijzigd; alleen providerverbinding, `source_system_id` en waar nodig de
source-expressies wijzigen.

## Versies en herleidbaarheid

De manifestversie van het labpakket volgt exact de versie van de canonieke
integratiebron. De generator verhoogt dus geen publieke SemVer en maakt geen
release-tag. Daarnaast bevat ieder labpakket:

- de volledige SHA-256 van de canonieke componentboom;
- een korte, daaruit afgeleide `LAB_BUILD_ID`;
- het brondomein en de bronversie;
- de expliciete beleidswaarden dat de frontend actief en archivering
  uitgeschakeld is.

Deze metadata verschijnt in gedownloade labdiagnostiek. Daardoor blijft een
waarneming aan de exacte broninhoud te koppelen, ook wanneer meerdere lokale
labbuilds dezelfde nog niet verhoogde manifestversie hebben.

Sinds de geïsoleerde labfrontend in fase 4 is geactiveerd, blijft de SemVer in
de resource-URL gelijk aan de canonieke manifestversie en wordt de
`LAB_BUILD_ID` als afzonderlijke `build`-queryparameter toegevoegd. Daardoor
laadt Home Assistant na installatie van een nieuwe labbuild aantoonbaar de
bijbehorende kaartmodule, zonder voor labwerk een publieke releaseversie te
simuleren. De productie-resource krijgt deze labparameter niet.

## Bouw- en verificatiecontract

De standaarduitvoer staat onder de genegeerde ontwikkelmap:

```text
work/solesta_lab/custom_components/solesta_lab
```

De generator wordt vanuit de repository-root gebruikt:

```text
python3 tools/build_lab.py --check
python3 tools/build_lab.py --write
```

`--check` schrijft niets en valideert de bron, overlay en reproduceerbaarheid.
`--write` publiceert pas na volledige validatie een nieuwe labmap en vervangt
een eerder gegenereerde labmap met een herstelbare directorywissel. Tests
controleren ten minste domein, naam, versiebehoud, uitgeschakelde globale
bijwerkingen, diagnostische buildmetadata, syntactisch geldige Python en
byte-identieke herhaalbaarheid.

In VS Code zijn dezelfde handelingen beschikbaar via **Terminal → Run Task**
als `Solesta Lab: controleren` en `Solesta Lab: bouwen`.

## Gevolgen

- Wijzigingen worden altijd eerst in de canonieke `solesta`-bron gemaakt.
- Een labpakket wordt nooit teruggekopieerd naar
  `custom_components/solesta`.
- Productie en lab mogen tegelijkertijd dezelfde Web API-credentials
  gebruiken, maar de vergelijkingsproef begint met één systeem en een rustig
  pollinterval om extra cloudbelasting te begrenzen.
- Installatie in live Home Assistant valt buiten dit besluit en vereist een
  afzonderlijke expliciete opdracht, back-up-/herstelpad en verificatie.
