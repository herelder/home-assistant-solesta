# D-ESP-014 — nullwaarden en veldinvoer in bronexpressies

Datum: 14 november 2026

Status: uitgevoerd; op 15 november 2026 geïnstalleerd en gecontroleerd in
Solesta Lab 0.2.8. Bestaande labexpressies zijn daarna expliciet via de
configuratieflow aangepast, zonder migratie.

## Aanleiding en risico's

De gebruiker vervangt de eerdere algemene argumentbeschermer door een beperkte,
uitlegbare functie voor veldwaarden. De eerdere uitleg hiervan is ingetrokken.
Voornaamste risico's zijn dat een ontbrekend veld de hele alertketen blokkeert,
dat een echte rekenfout ongemerkt verdwijnt, of dat de Pythonparser de veldnaam
`None` onbedoeld als een nullconstante behandelt.

Daarom worden het invoercontract, de veldbinding en de foutgrens bij compilatie
getoetst. De bestaande beveiligings-/resourcegrenzen, afhankelijkheidsgraaf,
provideronafhankelijkheid en diagnostiek blijven gelden.

## Contract

1. `null()` geeft de interne afwezige waarde terug, in Python `None` genoemd.
2. `null(veld)` geeft de waarde van dat bron- of entiteitveld terug. Een
   ontbrekend of waardeloos veld geeft de interne nullwaarde.
3. `null(veld, ...)` geeft een lijst met één resultaat per argument in dezelfde
   volgorde. Geldige nul, `False`, lege tekst en lijstwaarden blijven behouden;
   bronlijsten worden niet platgemaakt.
4. Ieder argument is één veld, of een constante/expressie zonder velden.
   `null(to_number(veld))`, `null(veld + 1)` en `null(veld > 0)` zijn compilefouten.
   Een conversie kan buiten de functie: `to_number(null(veld))`.
5. Veldvrije berekeningen zoals `null(10 * 2, round(12.25, 1))` zijn toegestaan.
   Hun normale reken-/conversiefouten blijven fouten: `null(1 / 0)` is geen
   manier om deling door nul te verbergen. Keywordargumenten zijn niet toegestaan.
6. De vroegere functie en haar generieke foutvangende uitvoering verdwijnen
   volledig. Er is geen alias en geen nieuwe migratie of expressieherschrijving.

## None en none zijn veldnamen

De Pythonparser produceert voor het token `None` een constante. De compiler
zet juist dat parserresultaat vóór validatie/naamresolutie terug naar de gewone
veldnaam `None`. Daarna gelden precies dezelfde bron-/entiteit-/eigenveldregels
als voor andere namen. `none` was en blijft eveneens een gewone naam. Namen
zijn hoofdlettergevoelig. Tekst als `"None"` blijft een string; uitsluitend een
functieaanroep `null()` produceert zonder brondata de interne nullwaarde.

Een kaal ontbrekend `None` of `none` is een ontbrekend verplicht veld en kan
geen succesvolle evaluatie met een verzonnen nullconstante opleveren.
`null(None)` en `null(none)` verklaren juist die velden als nullable.

## Binding en afhankelijkheden

Een onbekende korte naam binnen `null(...)` mag ontbreken. Een beschikbare
korte naam bindt nog steeds alleen bij precies één match; dubbelzinnigheid
blijft een configuratiefout. Een absoluut pad blijft een exacte veldkeuze.
Bindings veranderen niet binnen een configuratierevisie.

Een bronveld dat ook buiten `null(...)` wordt gebruikt blijft verplicht.
Alle nullable bronreferenties blijven meetellen voor `last_update()`.
Entiteitsafhankelijkheden blijven deel van de evaluatievolgorde en
cycluscontrole. Een foutieve entiteit levert haar interne onbekende resultaat
aan een nullable consument, zonder dat diens hele evaluatie wordt geblokkeerd.
De oorspronkelijke fout blijft zichtbaar; de eigen verplichte invoer van die
entiteit wordt hierdoor niet optioneel.

## Canonieke fabriek

De gebruiker vraagt wijziging van het werkboek en hergeneratie, zonder migratie.
De catalogusrevisie wordt 16, met dezelfde 21 entiteiten. Alleen de volgende
fabrieksexpressies wijzigen:

```text
state_pump = perc_pump_pwm > 0
alerts_system = solar_thermal_alerts(
    null(status_reporting, state_pump, temp_collector, temp_tank_top),
    90, 200, 10, 10)
```

De directe pompvergelijking maakt een ontbrekend/ongeldig percentage onbekend
via de gewone evaluatiediagnostiek. De nullable veldinvoer van de alertfunctie
laat onafhankelijke collectorregels werken. De gereserveerde temperatuur houdt
haar bestaande `null()`-fabriek. De alertomschrijving in het werkboek beschrijft
uitsluitend lokaal afgeleide regels. De generator schrijft `thetruth.py`.

Het opslagformaat blijft config-entry 1.9 / expressieschema 11; er wordt geen
nieuwe opslagmigratie toegevoegd. Manifest/kaartversie blijven in deze
onuitgebrachte bronkandidaat 1.0.0. De bestaande productie-upgrade wijzigt geen
opgeslagen expressie, ook niet na deze taalwijziging.

## Gevolgen en verificatie

Bestaande labexpressies worden niet stilzwijgend omgezet. Een nog opgeslagen
vervallen aanroep moet bij een latere installatie/configuratie bewust worden
aangepast; deze opdracht installeert niets. Actuele gebruikershandleidingen en
relevante ontwerpverwijzingen zijn op dit contract gebracht. Historische
acceptatieverslagen blijven herkenbaar als bewijs voor hun toenmalige code.

Regressies toetsen de drie aanroepvormen, nul/False/lege tekst, ontbrekende en
ambigue namen, velden `None`/`none`, expliciete bronreferenties, entiteitsfouten,
cycles, toegestane veldvrije berekeningen en niet-onderdrukte rekenfouten.
De volledige catalogusalertketen, productie-0.2.3-expressies, werkboekstructuur,
generatoren, providerflows en kaarttests worden opnieuw gecontroleerd; zie het
[uitvoeringsverslag](../results/null-fields-implementation-2026-11-14.md).

De latere, afzonderlijk opgedragen labplaatsing en bewuste herconfiguratie
staan in het [installatieverslag van 15 november](../results/solesta-lab-0.2.8-installation-2026-11-15.md).
