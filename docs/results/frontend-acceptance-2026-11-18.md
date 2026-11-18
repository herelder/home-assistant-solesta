# Front-endacceptatie — 18 november 2026

Status: **functionele controles geslaagd; twee visuele bevindingen blijven open**.
De correcties S100-08, S100-09 en S100-10 slagen. De kaart is nog niet volledig
visueel geaccepteerd door afkapping van de bovenbalk en de statusuitleg.
Er is tijdens deze test geen productcode of live configuratie gewijzigd.

## Opstelling

Getest vanaf circa 13:21 tot 13:36 CET op HA 2026.11.1 en de geïnstalleerde
Solesta Lab-kaart 0.2.9. In de native Home Assistant-app zijn de drie bestaande
kaarten Web API, ESPHome Native en Synology EMQX/nanoc6_01 gebruikt.

De geïnstalleerde JavaScript-bundel heeft SHA-256
`e3b8729eb3f83c682500c7c6fbc6395beef50711f6354f19fe193db006877de9`.
Deze is bytegelijk aan de huidige canonieke kaart na uitsluitend vervanging
van de versieconstante 0.2.9 door 1.0.0.

Aanvullend is die exacte geïnstalleerde bundel in een lokale browserfixture
geladen, met de geïnstalleerde Nederlandse vertalingen en het logo. De fixture
gebruikt echte browser-DOM, CSS, custom elements en gebruikersinteractie, met
synthetische HA-registry-, status- en Recorderantwoorden. HA-container- en
icoonelementen zijn eenvoudige lokale vervangers; dit is geen tweede volledig
draaiende Home Assistant. De live app levert de afzonderlijke visuele controle
van het echte dashboard. De fixture heeft geen verbinding met HA of brokers.

## Geslaagde controles

| Onderdeel | Uitkomst |
| --- | --- |
| S100-08 | Alle 7.141 historiepunten behouden; tijdgewogen gemiddelde **49,548333 °C**; volledige dagen hebben datzelfde gemiddelde en extrema 20/80 °C. Korte piek blijft beschikbaar voor de aanwijzer. 1.600 afwisselend bekende/onbekende punten behouden 800 lijnonderbrekingen. Ook in de echte browser geslaagd. |
| S100-09 | Santiago geeft voor de volgende dag vanaf 5 september de grens `2026-09-06T04:00:00Z`. Vandaag- en weekweergave renderen zonder browserfout. De permanente kaarttests dekken aanvullend Amsterdam, Havana, Goose Bay, Apia en onberekenbare grenzen. |
| S100-10 | In de browser geven 36 varianten van ontbrekende/ongeldige kernwaarden een incompletestatus. Onafhankelijke ernstige meldingen krijgen voorrang; offline krijgt vervolgens voorrang; herstel geeft weer normaal. |
| Live dashboard | Alle drie kaarten laden dag- en weekhistorie. Muis en toetsenbord verplaatsen de aanwijzer. Providerlabels en actuele meetwaarden blijven zichtbaar. Alle drie systemen tonen online en **Alles werkt normaal**. |
| Grafiekbediening | Echte schakelaar wisselt vandaag/week. Home geeft begin zonder meting correct als onbekend; End keert terug naar het einde. ArrowLeft verschuift in weekmodus één uur en toont de bijbehorende meetwaarde. |
| Historie-uitval | Een opzettelijk mislukte historieaanvraag behoudt de geladen reeks en toont een waarschuwing. Een volgende geslaagde aanvraag herstelt de normale grafiek. |
| Editor | Naamwijziging en schermhoogtekeuze leveren de verwachte configuratiegebeurtenissen. Systeemselectie en overige, onbekende configuratievelden blijven behouden. Alleen de lokale fixture is bewerkt. |
| Schermpassing en sluiten | Automatisch aanpassen past het kaartframe binnen de beschikbare testhoogte. De echte sluitknop activeert het ingestelde lokale terugkeerpad `/klaar`. |
| Browserfouten | Geen console-errors, ongehanteerde fouten of promise-rejections tijdens de functionele fixtureproeven. |

De gemeten grafiekaanwijzertijd is een geselecteerd historisch moment en is
geen bewijs van de laatste apparaatrapportage.

## Open visuele bevindingen

### F01 — Bovenbalk valt buiten een smalle kaart

**Prioriteit: P2.** In het bestaande dashboard met drie kolommen is de klok
gedeeltelijk afgesneden en staat de sluitknop buiten het zichtbare kaartvlak.
Dit is zichtbaar bij alle drie providers.

Reproductie: open het vergelijkingsdashboard en bekijk de bovenkant van de
kaarten. De lokale browserfixture reproduceert dit met een kaartbreedte van
235 CSS-pixels in een viewport van 1.200 pixels: de klok eindigt circa 39 pixels
en de sluitknop circa 81 pixels voorbij de rechterrand. Bij een mobiele
viewport van 320 pixels en een kaart van 280 pixels steekt de sluitknop nog
circa 18 pixels uit. Bij de geteste kaarten van 320/360/440 pixels in de brede
viewport vallen klok en sluitknop binnen de kaart.

De bovenbalk bevat een niet-afbrekende merknaam/versie en vaste actieruimte.
De bestaande compacte CSS reageert op viewportbreedte, terwijl het live
dashboard smalle kaarten binnen een breder venster heeft. Deze oorzaak is
consistent met de waarneming; er is nog geen correctie toegepast.

Bewijs: `work/frontend-acceptance-20261118/live-header.png` en de geometrische
metingen in `final-verification.json`.

### F02 — Statusuitleg overschrijdt de linkerrand

**Prioriteit: P2.** De informatieknop opent de juiste Nederlandse uitleg, maar
de tekstballon steekt links buiten de kaart. In het echte vergelijkingsdashboard
wordt de tekst daardoor aan het begin van iedere regel afgesneden. Bevestigd
op de Web API- en Native-kaart.

Reproductie: scroll naar de groene totaalstatus en open de informatieknop.
In de browserfixture steekt de ballon bij een kaart van 235 pixels circa
106 pixels links uit. Bij de geteste kaarten van 320/360/440 pixels in de
brede viewport is dit circa 43 pixels. Ook de mobiele viewport van 360 pixels
met een kaart van 320 pixels reproduceert de overschrijding. Bij de geteste
viewport van 320 pixels past de smallere ballon wel binnen de kaart.

De ballon wordt relatief aan de informatieknop naar links geplaatst met een
breedte op basis van de viewport. Er wordt geen rekening gehouden met de
beschikbare ruimte binnen de kaart en de positie van die knop. Er is nog geen
correctie toegepast.

Bewijs: `work/frontend-acceptance-20261118/live-tooltip.png` toont de echte
afkapping; `tooltip-235.jpg` toont de overschrijding in de lokale fixture.

## Regressies en testgrenzen

| Controle | Resultaat |
| --- | --- |
| Canonieke kaart, echte Node 24.22.1-test runner | **38 tests geslaagd** |
| Exact geïnstalleerde kaart, dezelfde suite | **38 tests geslaagd**, na aanpassing van uitsluitend de gekopieerde testverwachting voor logo-versie 1.0.0 naar de geïnstalleerde 0.2.9 |
| Canonieke generator | Beide catalogi reproduceerbaar |
| Labgenerator | Deterministisch, build-ID `1d51d2a91264` |
| Python, schone kandidaat met 187 publieke bronbestanden | **311 tests geslaagd** |
| Diffcontrole | Geen witruimtefouten |

De browserlog bevat 89 records, waaronder herhaalde opstartmeldingen,
bedieningsgebeurtenissen en breedtemetingen. Dit zijn geen 89 afzonderlijke
regressietests. Acht geometrische afwijzingen vallen onder de twee bevindingen
hierboven. De 38 permanente kaarttests gebruiken lichte DOM-doubles; hun
geslaagde resultaat sluit deze visuele fouten dus niet uit.

De eerste ongewijzigde run tegen de geïnstalleerde kaart struikelde uitsluitend
over de vaste versie 1.0.0 in de logo-assertie. De productbundel is niet aangepast.
De eerste Python-run vond de spreadsheetafhankelijkheid niet vanuit een
subproces; met een absoluut afhankelijkhedenpad slaagden alle 311 tests.
De oorspronkelijke uitvoer en de geslaagde herhalingen zijn apart bewaard.

Er is geen echte apparaatuitval of providerherconfiguratie uitgelokt. Deze test
herhaalt de eerdere firmware-/netwerkacceptatie niet. De actieve Recorderdatabase
is niet geopend; de live kaart haalt historie via de normale HA-interface op.

## Eindtoestand

Alle zes oorspronkelijke Solesta-, Lab- en ESPHome-configuratieentries zijn
volledig gelijk aan de nulmeting. Alle 54 gecontroleerde geïnstalleerde
Lab-bestanden en dashboard-/resourcebestanden hebben dezelfde hash.
`.storage` is uitsluitend gelezen.

Het dashboard staat weer bovenaan, alle kaarten in vandaagmodus en alle
informatieballonnen gesloten. De lokale testtab is gesloten, de tijdelijke
browserafmetingen zijn hersteld en de lokale testserver is gestopt. De Mac is
tijdens de hele test wakker gehouden; de tijdelijke slaapblokkade is om 13:36 CET opgeheven en gecontroleerd. Permanente energie-instellingen zijn niet gewijzigd.

Private fixtures, logs, hashes en schermafbeeldingen staan onder
`work/frontend-acceptance-20261118/`. Er is niets geïnstalleerd, gecommit,
gepusht of gepubliceerd.
