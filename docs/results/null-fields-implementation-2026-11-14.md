# Uitvoering van het null()-veldcontract

Datum: 14 november 2026

Status: code, canoniek werkboek en documentatie aangepast; onderstaande controles geslaagd.

## Uitvoering

De opdracht is uitgevoerd volgens
[D-ESP-014](../decisions/0014-null-fields-expression-contract.md).

- `null()` ondersteunt nul, één en meerdere argumenten. Meerdere argumenten
  geven een lijst met behouden waarden en null voor ontbrekende velden.
- De compiler staat per argument één veld of een veldvrije expressie/constante
  toe. Berekeningen met velden binnen een argument worden afgewezen.
- De algemene foutvangende hulp, uitgestelde argumenten en oude functienaam
  zijn uit de uitvoering verwijderd. Rekenfouten blijven diagnostische fouten.
- De tokens `None` en `none` worden als gewone, hoofdlettergevoelige veldnamen
  verwerkt, ook in afhankelijkheden en bij gekwalificeerde bronbinding.
- Ontbrekende korte velden kunnen binnen `null(...)` worden gelezen;
  dubbelzinnige namen blijven fouten. Geen bestaande bronexpressie wordt
  automatisch aangepast.
- `EntityDescriptions.xlsx` heeft catalogusrevisie 16. De pomp- en
  alertfabrieksexpressies en de alertomschrijving zijn aangepast. `thetruth.py`
  is via de canonieke generator opnieuw geschreven.
- De opgeslagen expressies, config-entryversie 1.9 en expressieschema 11
  veranderen niet door een nieuwe migratie: die is niet gemaakt.
- De actuele bronexpressie-, entiteiten-, release- en probleemoplossingsuitleg
  en relevante ontwerpverwijzingen zijn bijgewerkt. De eerdere foutieve
  functiebeschrijving is uit de actuele uitleg verwijderd. Historische
  resultaatverslagen zijn als verouderd taalbewijs gemarkeerd.

Het werkboek is vóór en na de edit gecontroleerd. Er zijn alleen vier
celwaarden veranderd: revisie D1, alertomschrijving B16 en fabrieksexpressies
T15/T16. Alle andere celwaarden, stijlen, tabvolgorde, verborgen tab,
rij-/kolominstellingen en negen gegevensvalidaties zijn behouden. De gewijzigde
expressiecellen zijn ook visueel vergeleken; de bestaande indeling is behouden.

## Verificatie

| Controle | Resultaat |
| --- | --- |
| Volledige Python-suite op schone projectkopie | 298 tests geslaagd, inclusief repositoryhygiëne |
| Kaarttests | 33 tests geslaagd |
| HA-contracttests met 2026.9.0 | 23 tests geslaagd |
| HA-contracttests met 2026.10.4 | 23 tests geslaagd |
| Canonieke generatorcheck | Beide runtimecatalogi reproduceerbaar |
| Labgeneratorcheck | Deterministische overlay, build-ID `497f3e0ed4c9`; niet geplaatst |
| Ruff en diff-witruimtecontrole | Geslaagd |
| Werkboekbehoud | Vier verwachte celwijzigingen; overige waarden en opmaak gelijk |

De regressies omvatten nul/één/meerdere argumenten, behouden types en falsy
waarden, nullable bron-/entiteitvelden, onbekende korte en absolute namen,
weigeren van ambiguïteit, expliciete bronreferenties, `None`/`none` als
verplichte én nullable velden, veldvrije berekeningen, behoud van oorspronkelijke
entiteitsfouten en niet-onderdrukte rekenfouten. Veldberekeningen binnen een
argument, keywordargumenten, cycles, onveilige syntax en de vervallen functie
worden afgewezen. De echte HA-flow accepteert bovendien een ontbrekend kort
nullable bronveld tijdens MQTT-validatie.

De volledige nieuwe catalogus houdt onafhankelijke alerts bij ontbrekende of
ongeldige pomp-/temperatuurwaarden. De echte 0.2.3-expressiefixture blijft
ongewijzigd compileerbaar/evalueerbaar en haar metadata-upgrade bewaart alle
expressieteksten. Bestaande kaartpresentatie en de drie providercontracten zijn
via hun regressies gecontroleerd. Er is geen nieuwe live acceptatieproef gedaan.

## Afbakening

De bestaande productie-0.2.3-metadata-upgrade en het verbod op herschrijven van
opgeslagen expressies zijn behouden. De taalwijziging betekent wel dat een nog
opgeslagen vervallen aanroep bij een latere installatie/configuratie handmatig
moet worden aangepast. Er is geen compatibiliteitsalias gemaakt.

Er is voor deze opdracht niets in de live Home Assistant-configuratie geplaatst,
geen HA- of Companion-herstart uitgevoerd, geen commit gemaakt en niets gepusht.
Solesta Lab blijft de eerder geïnstalleerde versie 0.2.7 gebruiken.

Latere aanvulling, 15 november: na een afzonderlijke installatieopdracht is
Solesta Lab 0.2.8 geplaatst. Alle vier systemen zijn expliciet via de
configuratieflow aangepast en geactiveerd; zie het
[installatieverslag](solesta-lab-0.2.8-installation-2026-11-15.md).
De bovenstaande afbakening beschrijft de oorspronkelijke ontwikkelopdracht.
