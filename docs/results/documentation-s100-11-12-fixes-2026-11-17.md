# Documentatie — herstel S100-11 en S100-12

Datum: 17 november 2026.

Basis: branch `codex/esphome-provider`, commit
`a4214fd871675b5f176db542d8946eed56935e42`, inclusief de eerder lokaal
herstelde S100-01 tot en met S100-10. Deze stap wijzigt uitsluitend documentatie.

## Correcties

| Bevinding | Correctie |
| --- | --- |
| S100-11 | De tabel in [Entities and settings](../entities.md) beschrijft alerts als uitvoer van de geconfigureerde expressie en lokale alerts als fabrieksinstelling. De nadere uitleg benoemt de eigen bronalertexpressie, bijvoorbeeld `join_lines(alerts)`, en het letterlijke behoud van bestaande Web API-expressies bij upgrade. |
| S100-12 | De uitleg van de interne catalogusfunctie is verwijderd uit [Entities and settings](../entities.md), [Troubleshooting](../troubleshooting.md) en de eveneens aangetroffen passage in [Weekly source archives](../archive.md). De archiefhandleiding beschrijft alleen dat de archiefmanager de diagnostische waarden automatisch levert. |

De uitleg is vergeleken met de werkelijke alertfunctie, de bestaande
volledige-catalogustest en de [expressiehandleiding](../source-expressions.md#universal-alerts).
Deze correctie verduidelijkt de bestaande besluiten
[D-ESP-013](../decisions/0013-production-baseline-compatibility-cleanup.md) en
[D-ESP-007](../decisions/0007-provider-independent-expressions-and-optional-evaluation.md).
Zij introduceert geen nieuw ontwerp, automatische alertmerging of migratie.
Interne contracten en historische bewijsdocumenten blijven intact.

## Verificatie

Een vergelijking met een momentopname vóór deze taak bevestigt dat alleen de
drie gebruikershandleidingen en de changelog zijn gewijzigd, naast dit nieuwe
herstelrapport. Runtime, firmware, tests, generatoren en werkboeken blijven
bytegelijk aan die momentopname.

Op een schone kopie van de huidige bron zijn opnieuw uitgevoerd:

| Controle | Resultaat |
| --- | --- |
| Canonieke generatorcheck | Beide runtimecatalogi reproduceerbaar |
| Labgeneratorcheck | Deterministisch; build-ID `1d51d2a91264` |
| Ruff | Geslaagd |
| Python-suite | **310 tests geslaagd** |
| Kaart | **38 callbacks met hun assertions geslaagd** via de tijdelijke Node REPL-harness; geen native `node --test`-claim |
| Gebruikershandleidingen | Geen interne functie-uitleg of vervallen automatische-alertmergingclaim meer aangetroffen |
| Markdown-bestandslinks en witruimte | Gecontroleerd; geen ontbrekende lokale bestandsdoelen of witruimtefouten. Externe URLs en headingankers niet volledig gevalideerd |

De HA-contractsuites zijn bij het aansluitende [kaartherstel](card-s100-08-10-fixes-2026-11-17.md)
geslaagd op HA 2026.9.0 en 2026.10.4, elk met 40 tests. Zij zijn voor deze
uitsluitend tekstuele wijziging niet opnieuw uitgevoerd.

Lokale controle-uitvoer staat onder
`/private/tmp/solesta-doc-review-fixes-20261117/`.

## Afsluiting van de reviewbevindingen

Hiermee zijn alle twaalf bevindingen uit de
[projectreview](solesta-1.0.0-full-project-review-2026-11-16.md) lokaal hersteld:

- S100-01/02: [NanoC6-firmware en bronvaliditeit](nanoc6-s100-01-02-fixes-2026-11-17.md);
- S100-03/04: [kopieën en bronbinding](source-binding-s100-03-04-fixes-2026-11-17.md);
- S100-05/06/07: [MQTT-validatie, roots en credentials](mqtt-s100-05-07-fixes-2026-11-17.md);
- S100-08/09/10: [kaartgeschiedenis, kalendergrenzen en meetvolledigheid](card-s100-08-10-fixes-2026-11-17.md);
- S100-11/12: de documentatiecorrecties in dit rapport.

Dit sluit de genoemde lokale bevindingen af, niet de afzonderlijke
releaseacceptatie. Er is niets geïnstalleerd, gecommit, gepusht of gepubliceerd;
de schone releasecheckout en live Home Assistant zijn niet gewijzigd.
