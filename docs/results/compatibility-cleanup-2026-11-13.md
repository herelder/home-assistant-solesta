# Opschoning van overbodige compatibiliteitscode

> Historisch bewijs voor de toenmalige kandidaat. Voor de actuele taal geldt
> [D-ESP-014](../decisions/0014-null-fields-expression-contract.md): `null(...)`
> heeft uitsluitend veldargumenten of veldvrije berekeningen; `None`/`none`
> zijn veldnamen. De toenmalige algemene foutbeschermer is vervallen.


Datum: 13 november 2026

Status: code en documentatie aangepast; onderstaande controles geslaagd.

Vervolgopdracht: de wijzigingen zijn daarna als Solesta Lab 0.2.7 geïnstalleerd.
De gevraagde HA-herstart, volledige Companion-stop/start en statuscontrole staan
in het [installatieverslag](solesta-lab-0.2.7-installation-2026-11-13.md).

## Opdracht en afbakening

De door de gebruiker bijgestelde bevindingen zijn verwerkt volgens
[D-ESP-013](../decisions/0013-production-baseline-compatibility-cleanup.md).
De laatste verduidelijking luidt: corrigeer de uitleg van `optional()`.
Dit werk omvat geen installatie, HA-herstart, productie-upgrade of publicatie.

## Uitgevoerde wijzigingen

- Eén alertfunctie met vier gegroepeerde optionele invoerwaarden en vier
  constante thresholds. Oude negenargumentvorm en extra bronalertargument,
  inclusief hun normalisatie-/mergecode, zijn verwijderd.
- Alleen de metadata-upgrade van productie 0.2.3 blijft bestaan. Iedere
  expressietekst, ook `last_update`, wordt exact behouden. Geen aanvulling,
  threshold-inlining, bron-ID-herschrijving of registerverwijdering.
- De labmigraties voor schema's 5–10 en MQTT/Native bron-ID's zijn verwijderd.
- Oude statusdicts en uitwijkroutes voor oude runtimevelden zijn verwijderd;
  de tests gebruiken nu het huidige snapshotcontract.
- Pushcachelezingen voegen geen transportafgeleide compatibiliteitswaarden
  meer toe. Alleen ontvangen events bepalen rapport-/wijzigingstijden.
- Expliciete kaartnamen blijven altijd behouden. Zonder naam blijft de
  provider-/systeemidentiteit dynamisch zichtbaar.
- Alleen het canonieke resourcepad wordt bijgewerkt/ontdubbeld. Historische
  paden worden niet meer herkend of geregistreerd.
- De publieke uitleg van `optional()` beschrijft nu de foutgrens per argument
  en het verschil tussen absolute bronvelden en korte naamresolutie.
- Release-, entiteiten-, dashboard-, installatie- en probleemoplossingsuitleg
  zijn aangepast. De vergelijking met Solesta's eigen energieformules blijft
  behouden. Oude ontwerpbesluiten en het M7-verslag verwijzen naar dit besluit
  als opvolger van hun historische labcompatibiliteit.

## Bewust behouden

De kaart ondersteunt bestaande JSON-/Python-dictalerttekst, CR/LF en
`pump_wrong`. `join_lines(alerts)` blijft beschikbaar voor bronalerts. Het
recordformaat en de Unicode-splitter blijven intact. De canonieke resource uit
0.2.3 krijgt nog steeds de huidige versie. Permanente systeem-/entiteitidentiteit,
Recorderhistorie en de generieke laag voor externe waarden veranderen niet.

## Verificatie

De volledige Python-suite is getest vanuit een schone kopie van alle
bijgehouden/niet-genegeerde projectbestanden; lokale werkmappen en hersteldata
zijn geen test- of publicatie-inhoud. Kaart-, generator- en HA-contractcontroles
zijn uitgevoerd tegen dezelfde gewijzigde projectbron. De bronbasis is commit
`3fed75a`; de wijzigingen zijn lokaal.

| Controle | Resultaat |
| --- | --- |
| Canonieke generatorcheck | `thetruth.py` en `provider_defaults.py` reproduceerbaar |
| Gegenereerde Solesta Lab-build | Deterministisch; build-ID `b17dbc319840` |
| Volledige Python-suite | 297 tests geslaagd, inclusief repositoryhygiëne |
| Dashboardkaart | 33 tests geslaagd |
| Echte HA-contracttests, HA 2026.9.0 | 23 tests geslaagd |
| Echte HA-contracttests, HA 2026.10.4 | 23 tests geslaagd |
| Ruff en diff-witruimtecontrole | Geslaagd |

De productiefixture bevat alle 21 expressies uit de echte 0.2.3-catalogus,
afkomstig van commit `bccaee942ec20fe906f7ea3dd4a9978f1abba0b6`. De tests
controleren letterlijk behoud, inclusief aangepaste tekst/spaties en
`last_update`, idempotentie, behoud van identiteit en weigering zonder writes
bij ongeldige metadata of oude labschema's. De volledige oude catalogus wordt
ook geëvalueerd: ruwe rapporttijd, bronalerts, pomp, T4 en energie blijven werken.

De huidige alertregels blijven onafhankelijk bij ontbrekende of ongeldige
pomp-/temperatuurwaarden. Oude aanroepvormen worden expliciet afgewezen.
De nieuwe `optional()`-voorbeelden zijn met compiler/evaluator uitgevoerd:
ontbrekend absoluut veld, onbekende korte naam en een wrapper rondom de hele
functie versus een wrapper om alleen de falende invoer.

Kaarttests behouden bestaande alerttekst, Unicode, `pump_wrong`, de dynamische
identiteit en vaste expliciete namen. Resourcetests controleren het bijwerken
van het 0.2.3-pad, ontdubbelen van alleen het huidige pad en volledig negeren
van historische routes. De provider-/observationtests en HA-contracttests
behouden de bestaande cache-, foutisolatie- en providerwisselcontrole.

## Grenzen voor vrijgave

Het M7-upgradebewijs van 5 november behoort bij de toenmalige kandidaat; het
herschreef nog een exacte `last_update`-expressie. Dat gedrag is nu verwijderd.
De eerdere proef kan daarom niet als een nieuwe volledige upgradeproef van deze
kandidaat worden gepresenteerd. Een hernieuwde volledige HA-upgrade-/dashboardproef
op een herstelkopie blijft een vrijgavecontrole. De bestaande beperking van een
volledige lokale HA-start op deze Mac wordt met deze codecontrole niet opnieuw
beproefd. Live systemen zijn voor deze opdracht niet gewijzigd.
