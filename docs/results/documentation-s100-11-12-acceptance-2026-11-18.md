# S100-11 en S100-12 — documentatieacceptatie

Datum: 18 november 2026. Status: **beide punten akkoord en afgesloten**.

De huidige gebruikersdocumentatie is opnieuw vergeleken met de oorspronkelijke
reviewcriteria, de alertfunctie, compiler en bestaande regressies.

- **S100-11:** de entiteitentabel beschrijft alerts uit de geconfigureerde
  expressie, met lokale alerts als fabrieksinstelling. De entiteitenhandleiding
  en expressiehandleiding leggen de afzonderlijke bronalertoptie
  `join_lines(alerts)` uit. De releasehandleiding bevestigt letterlijk behoud
  van bestaande expressies bij upgrade. De functie accepteert vier lokale
  invoerwaarden en vier vaste drempels; extra bronalerts worden niet automatisch
  samengevoegd. Dit komt overeen met de code en de geslaagde regressies voor
  genegeerde ongebruikte bronalerts en behouden 0.2.3-bronalertrecepten.
- **S100-12:** de interne catalogusfunctie wordt niet meer genoemd in de
  gebruikershandleidingen. Bij deze nacontrole is nog één vermelding gevonden
  in de publieke changelog. Die is vervangen door een algemene beschrijving
  van verbeterde expressievalidatie. Historische plannen, resultaten, interne
  ontwerpbesluiten en tests behouden hun context. Het interne functiecontract
  en de afwijzing in gebruikersformulieren zijn niet gewijzigd.

## Verificatie

| Controle | Resultaat |
| --- | --- |
| Publieke Markdown buiten historische/interne documentatie | 20 bestanden gecontroleerd; geen vermelding van de interne functie |
| Lokale Markdown-bestandslinks | 65 doelen gecontroleerd; geen ontbrekende bestanden; externe URLs en headingankers niet opnieuw getest |
| Canonieke generator | Beide catalogi reproduceerbaar |
| Labgenerator | Deterministisch, build-ID `1d51d2a91264` |
| Python-suite, schone bronkopie | **311 tests geslaagd** |
| Kaart, echte Node-test runner | **38 tests geslaagd** |
| Diffcontrole | Geen witruimtefouten |
| Runtimevergelijking met de eerdere front-endacceptatie | Alle 50 componentbestanden ongewijzigd |

Deze stap wijzigt alleen de changelog en voegt dit acceptatierapport toe.
Er is geen live Home Assistant benaderd of gewijzigd en niets geïnstalleerd,
gecommit, gepusht of gepubliceerd. Controle-uitvoer staat in
`work/documentation-acceptance-20261118/`.

Dit sluit S100-11 en S100-12 af. De twee visuele bevindingen uit de afzonderlijke
[front-endacceptatie](frontend-acceptance-2026-11-18.md) blijven open en vallen
buiten deze documentatiecontrole.
