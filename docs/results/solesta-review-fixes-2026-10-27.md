# Herstel na de review van de Solesta-releasekandidaat

> Historisch bewijs voor de toenmalige kandidaat. Voor de actuele taal geldt
> [D-ESP-014](../decisions/0014-null-fields-expression-contract.md): `null(...)`
> heeft uitsluitend veldargumenten of veldvrije berekeningen; `None`/`none`
> zijn veldnamen. De toenmalige algemene foutbeschermer is vervallen.


Datum: 27 oktober 2026

Bronbasis: `e023ba1dc36f94473f1fea777c9b5c9ea0df356d`, branch
`codex/esphome-provider`; wijzigingen in de werkmap.

Scope: de door de gebruiker opgedragen codecorrecties na de
[review van 26 oktober](solesta-hacs-release-candidate-review-2026-10-26.md),
volgens [D-ESP-007](../decisions/0007-provider-independent-expressions-and-optional-evaluation.md).
Er is geen live installatie, herstart, publicatie of push uitgevoerd.

Opvolging: op afzonderlijke gebruikersopdracht is deze code gecommit als
`5b20f00`, in Solesta Lab geïnstalleerd en is Home Assistant herstart. Zie het
[installatieverslag](solesta-lab-0.2.5-installation-2026-10-27.md).
De scope- en testuitspraken hieronder beschrijven de codecorrecties vóór die
installatie.

## Herstel per bevinding

| Bevinding | Uitvoering |
| --- | --- |
| R01 | Ontbrekende en niet-eindige native metingen worden `None`; zij verversen geen meettijd. Een onbekende waarde wist een eerdere echte waarde. Zonder barrières werkt een complete geldige meetgolf; een geldig-signaal alleen ververst de tijd niet. |
| R02 | `optional(expression)` behoudt waarde en type bij succes en geeft `None` bij evaluatiefouten. Optionele afhankelijkheden blokkeren de aanroep niet; oorspronkelijke entiteitsfouten blijven zichtbaar. Alleen uitsluitend optioneel gebruikte bronvelden vervallen uit de verplichte providercontrole. De nieuwe catalogusalertketen gebruikt dit. |
| R03 | Foutieve duplicaatkoppelingen blokkeren gezonde actieve systemen niet. Herconfiguratie biedt actuele echte providerbronnen aan; duplicaten kunnen hun communicatiebron veranderen met behoud van alias, UID en expressies. |
| R04 | Alle hardcoded providerexpressies en herschrijfregels zijn verwijderd. Upgrades bewaren iedere bestaande expressietekst en voegen alleen nieuwe ontbrekende catalogussleutels toe. |
| R05 | Gebruikersinvoer van `drop()` in een configureerbaar veld krijgt een expliciete formulierfout. Eerder opgeslagen onjuist gebruik blijft zichtbaar en corrigeerbaar. Interne archiefvelden blijven verborgen en behouden. |
| R06 | Provider-ID na verbindingsvalidatie opnieuw controleren en zonder tussenliggende asynchrone stap claimen/opslaan; claim vrijgeven bij mislukte opslag. Getest met twee gelijktijdige Web API-flows en met Web API/ESPHome samen. |
| R07 | Requirement gewijzigd in `aioesphomeapi>=46.2.0`. De minimum- en huidige HA/clientcombinatie krijgen tests met echte bibliotheken. |
| R08/R09 | Volgens opdracht behouden als nog uit te voeren publicatiewerk in fase 6. Gerichte uitleg van gewijzigde functies is bijgewerkt; de brede gebruikersdocumentatie en publicatiecontrole van historische rapporten zijn hiermee niet afgerond. |
| R10 | Gedeelde expliciete recordsplitter: RS indien aanwezig, anders uitsluitend CRLF/CR/LF. Unicode in één JSON-record blijft intact; frontend gebruikt dezelfde legacygrenzen. |

De aanvullende correctie voor `report_delay and not is_timestamp(report_delay)`
accepteert de `None`-uitkomst als onbekende binary-sensorwaarde. De
source-expression zelf is ongewijzigd.

## Versies

| Onderdeel | Nieuwe bronkandidaat |
| --- | --- |
| Integratie/manifest/dashboardkaart/resource | `0.2.5` |
| Config-entryschema | `1.4` |
| Expressieschema | `7` |
| Entiteitencatalogus | revisie `10` |
| Providerpreset | revisie `3`, ongewijzigd |

De canonieke werkmap wijzigt alleen de catalogusrevisie en de standaardteksten
voor `state_pump` en `alerts_system`. Een vergelijking met de Git-bron bevestigt
precies drie gewijzigde celwaarden: D1, T15 en T16. Het runtimebestand is
opnieuw gegenereerd. Er zijn geen providerafhankelijke standaardwaarden in de
systeemlaag. De deterministische labbuildcontrole geeft build-ID
`ddcbfd4ceef5`; er is geen installatie uitgevoerd.

## Verificatie

| Controle | Resultaat |
| --- | --- |
| Runtimegenerators `tools/build.py --check` | `thetruth.py` en `provider_defaults.py` reproduceerbaar |
| Labgenerator `tools/build_lab.py --check` | deterministische overlay geslaagd |
| Volledige snelle Python-suite | 262 tests geslaagd |
| Dashboardkaart | 31 tests geslaagd |
| HA 2026.9.0 / aioesphomeapi 46.2.0 | 13 contracttests geslaagd |
| HA 2026.10.4 / aioesphomeapi 46.6.0 | dezelfde 13 contracttests geslaagd |
| Ruff | geen lintfouten in integratie, tests en tools |
| Officiële Hassfest van HA 2026.10.4 | 1 integratie gecontroleerd, 0 ongeldige integraties |
| `git diff --check` | geen whitespacefouten |

De volledige snelle suite en kaarttests draaien op een schone bronkopie van
de werkmap, inclusief de nieuwe bestanden en lokale wijzigingen. Genegeerde
ontwikkelomgevingen, herstelkopieën en lokale databases worden niet
meegenomen. Zo wordt ook de repositoryhygiëne getest zonder gebruikersdata
te verwijderen of mee te publiceren.

De nieuwe proeven dekken onder meer onbekend/NaN/oneindig en herstel van
ESPHome-metingen, metingen zonder barrières, een los geldig-signaal,
ontbrekende framebarrières, optionele en verplichte bronverwijzingen,
behouden foutdiagnostiek, danger/offlinealerts bij een defecte andere invoer,
onbekende rapportagestatus, schema's 4/5/6 naar 7 zonder expressievervanging,
idempotentie, duplicaatbronkeuze en isolatie inclusief aliasbotsing,
formulierfouten bij `drop()`, gelijktijdige ID-claims en Unicode-alertrecords.

De HA-matrix is aan GitHub Actions toegevoegd voor toekomstige runs. De lokale
contracttests gebruiken echte HA-klassen en native ESPHome-statemodellen;
de snelle suite heeft geen HA-installatie nodig.

## Grenzen en vervolg

Bestaande installaties krijgen de nieuwe optionele alert- en pompexpressies
**niet automatisch**. De gebruiker moet ze desgewenst bewust aanpassen.
Ook een nieuw ESPHome-systeem krijgt de universele catalogusdefaults en vereist
dus handmatige bronmapping als de bronveldnamen afwijken.

De geautomatiseerde HA-contracten gebruiken echte bibliotheken met geïsoleerde
flow-, opslag- en netwerkfixtures. Zij zijn geen nieuwe fysieke Nano-test,
draaiende HA-upgrade of Recorderacceptatie. De eerdere herstelkopieproef van
0.2.4 wordt niet als bewijs voor de gewijzigde 0.2.5-kandidaat gepresenteerd.

Voor release blijven de publicatiewerkzaamheden R08/R09, definitieve
majorversie en uiteindelijke externe releasechecks nodig. Er is geen GitHub
Actions-run gestart; HACS en CodeQL zijn in dit herstel niet extern uitgevoerd.
