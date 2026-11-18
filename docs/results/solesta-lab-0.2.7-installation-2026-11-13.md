# Solesta Lab 0.2.7 — installatie, herstart en statuscontrole

Datum: 13 november 2026, Europe/Amsterdam (CET)

Status: geïnstalleerd en gecontroleerd. Home Assistant en Companion zijn
opnieuw gestart volgens de expliciete opdracht van de gebruiker.

## Geplaatst pakket

| Onderdeel | Waarde |
| --- | --- |
| Home Assistant | 2026.11.1 |
| Productie-Solesta | 0.2.3, ongewijzigd |
| Oude labversie | 0.2.6, build `6f56712656b6` |
| Nieuwe labintegratie en kaart | 0.2.7 |
| Nieuwe labbuild | `58f5834a4ca6` |
| Installatiedoel | `/config/custom_components/solesta_lab` |
| Plaatsing voltooid | 21:39:10 CET |
| Webserver weer bereikbaar | 21:42:25 CET |
| Dashboardcontrole | circa 21:43–21:44 CET |

De functionele bron is de lokaal gewijzigde 1.0.0-kandidaat, beschreven in het
[opschoningsverslag](compatibility-cleanup-2026-11-13.md). Voor deze
labinstallatie zijn uitsluitend de manifest- en kaartversie op een afzonderlijke
bronkopie naar 0.2.7 gezet, waarna de bestaande labgenerator het pakket maakte.
De canonieke releasekandidaat blijft 1.0.0. Er is geen commit of release gedaan.

## Voorcontrole en herstelpad

- De gegenereerde labbuild is deterministisch en valideert als `solesta_lab`,
  met eigen kaartresource en uitgeschakelde archivering.
- Alle 104 modeltests zijn geslaagd tegen het daadwerkelijke 0.2.7-labpakket.
  De overige code-/kaart-/HA-controles staan in het opschoningsverslag.
- De oude 51 labbestanden zijn buiten de live share bytegelijk bewaard in de
  genegeerde werkmap `work/deployment-20261113-cleanup/solesta_lab-0.2.6-before`.
  De nulmeting en installatiegegevens staan daarnaast in `deployment.json`.
- Oud en nieuw gebruiken beide config-entryschema 1.9 en expressieschema 11.
  Deze plaatsing vereist geen configuratiemigratie. Herstel bestaat uit het
  terugplaatsen van de gecontroleerde oude labmap en een gecontroleerde
  HA-herstart. Dit is een codeherstelpad, geen algemene HA-back-up.

## Plaatsing en herstart

Het complete pakket is naast de oude labmap opgebouwd en gecontroleerd, waarna
een directorywissel de 51 nieuwe programmabestanden publiceerde. Een automatisch
macOS-bestand `.DS_Store` verhinderde aanvankelijk de kopieeractie; toen was de
oude labmap nog niet vervangen. Dit bestand is uitgesloten. Alle geplaatste
programmabestanden zijn daarna bytegelijk aan de voorbereide build bevonden.

De gebruiker had de herstart uitdrukkelijk opgedragen. Deze is uitgevoerd via
**Systeem → Herstart Home Assistant → Herstart** in de native Companion-app.
Zodra **Je hebt geen verbinding meer** verscheen, is Companion via **Stop Home
Assistant** volledig afgesloten. De appinventaris bevestigde dat het proces
niet meer draaide. Daarna is de app opnieuw gestart. Toen HA weer antwoordde,
is de weergave vernieuwd en verscheen **Home Assistant is gestart!**.

## Gecontroleerde status

- De integratiepagina toont **Solesta Lab 0.2.7**, vier hubs, vier apparaten en
  84 entiteiten, zonder foutkaart: ESPHome Native, MQTT via Mosquitto, MQTT via
  EMQX en Web API.
- De drie bestaande vergelijkingskaarten tonen **v0.2.7**, **Online** en
  **Alles werkt normaal** voor Web API, ESPHome Native en MQTT via EMQX.
  Bij de eerste dashboardcontrole rond 21:43 toonden alle drie 15 °C,
  0,35 kWh en 1,26 MJ. De bestaande historie is zichtbaar.
- Het productiedashboard toont **v0.2.3**, **Online** en **Alles werkt normaal**,
  met dezelfde actuele temperatuur- en energiewaarden bij die controle.
- Het vernieuwde Core-log toont alleen een algemene bootstrapwaarschuwing over
  nog startende integraties. Daarna was de opstart voltooid. Er staat geen
  Solesta Lab-fout in de bekeken meldingen.
- Het labdashboard is geopend achtergelaten in Companion.

Er zijn geen systeemformulieren opgeslagen, bronexpressies aangepast,
dashboardconfiguraties gewijzigd of bestanden onder `.storage` rechtstreeks
bewerkt. De actieve Recorderdatabase is niet geopend of gekopieerd. Dit is
een installatie-/opstartcontrole; het vervangt geen volledige productie-upgrade-
of providerwisselproef.
