# D-ESP-019 — Kaartgeschiedenis, kalendergrenzen en meetvolledigheid

Datum: 17 november 2026.

Status: uitgevoerd in de lokale kandidaat voor S100-08, S100-09 en S100-10.

## Ontwerp en risico's

De kaart gebruikte een tot 720 punten gereduceerde reeks als volledige
stapfunctie. Daardoor veranderde de duur van korte extrema, werden
tijdgewogen gemiddelden onjuist en konden korte hiaten verdwijnen. De eis
van een exacte lokale 00:00 liet geldige tijdzones met een overgeslagen
middernacht bovendien tijdens het renderen vastlopen. De groene totaalstatus
controleerde niet alle benodigde meetwaarden.

## Besluiten

- Bewaar alle chronologisch geordende Recorderveranderingen. Bij identieke
  tijdstempels geldt, zoals voorheen, het laatste ontvangen punt.
  Dagstatistieken, schaal en interactieve aanwijzer gebruiken deze volledige
  reeks, inclusief alle onbekende intervallen.
- Reduceer uitsluitend de tekengeometrie. Tijdvakken bewaren hun eerste en
  laatste punt, minimum en maximum en de directe opvolgers van geselecteerde
  punten. Alle overgangen naar en vanuit onbekend blijven aanwezig. De
  gebruikelijke begroting van 720 tekenpunten is daarom geen harde limiet bij
  veel hiaten. Een harde limiet zou ontbrekende perioden kunnen overbruggen.
- Gebruik voor grote reeksen iteratieve minimum-/maximumbepaling en
  arrayconcatenatie; geef geen volledige meetreeksen als losse functieargumenten
  door. Het Recorderverzoek blijft begrensd tot het bestaande weekvenster.
- Bepaal kalenderdagen los van strikte tijdstempelinterpretatie. Zoek bij
  herhaalde middernachten de vroegste geldige 00:00 met de offsets rond de
  datum. Zoek bij een overgeslagen middernacht de eerste geldige seconde van
  de lokale dag. Een volledig overgeslagen datum levert geen grens op.
  Bestaande niet-bestaande lokale tijdstempels blijven ongeldig.
- Controleer iedere volgende grafiekgrens op geldigheid en voortgang.
  Een onberekenbare grens geeft uitsluitend een melding in de grafiek en
  wist het oude aanwijzermodel; de rest van de kaart blijft beschikbaar.
  Het linkse tijdlabel toont de werkelijke lokale begintijd.
- Vereis geldige gemiddelde/bovenste/onderste vattemperatuur, collector,
  koudwater, MJ, kWh en douches, plus bekende pomp-, rapportage- en alertstatus,
  voordat de totaalstatus normaal kan zijn. Offline blijft vóór onafhankelijke
  ernstige alerts gaan; beide blijven vóór onvolledige metingen gaan.

## Verificatie en grenzen

Blijvende kaartregressies toetsen 7.141 minuutpunten met korte pieken, meerdere
korte hiaten rond een daggrens, volledige aanwijzerwaarden en een dicht patroon
van onderbrekingen. Kalenderproeven omvatten Amsterdam (23/25 uur), Santiago
(overgeslagen middernacht), Havana en Goose Bay (herhaalde middernacht) en
Apia (volledig overgeslagen datum). Werkelijke renderaanroepen controleren
ontbrekende kernmetingen, herstel en de voorrang van danger/offline.

Dit verandert geen providercontract, entiteitsidentiteit, expressie,
archiefgegevens of configuratieschema. De bestaande warmte-indicatie blijft
in de kaart. Integratie, kaart en resource blijven kandidaat 1.0.0. Er is geen
installatie in live Home Assistant en geen publicatie onderdeel van dit besluit.
