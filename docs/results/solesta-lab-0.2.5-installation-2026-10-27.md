# Solesta Lab 0.2.5 — installatie en herstart

Datum: 27 oktober 2026, Europe/Amsterdam (CET)

Opdracht: commit de reviewcorrecties, installeer in `solesta_lab` en herstart
Home Assistant. Deze handelingen zijn uitgevoerd. De productie-integratie
`solesta` blijft op 0.2.3 en is bytegelijk aan de nulmeting.

## Geplaatste versie

| Onderdeel | Waarde |
| --- | --- |
| Codecommit | `5b20f008ee2cee82bd3a04dd53312425e8fa012a` |
| Integratie en dashboardkaart | `0.2.5` |
| Labbuild | `ddcbfd4ceef5` |
| SHA-256 canonieke componentboom | `ddcbfd4ceef561facff18ec10c6f14f607a35aa84c2f222cfedc83e18c36113f` |
| Doel | `/config/custom_components/solesta_lab` |
| Home Assistant | `2026.10.4` |
| Codeplaatsing voltooid | `00:30:22 CET` |
| Herstart via Companion bevestigd | rond `00:31 CET` |

De schema's en regressieresultaten staan in het
[herstelrapport](solesta-review-fixes-2026-10-27.md). Het labpakket is opnieuw
gegenereerd uit de gecommitte bron; er is geen tweede bronboom onderhouden.

## Back-up en herstelpad

Vóór plaatsing is via de native Home Assistant-app de handmatige back-up
**Voor Solesta Lab 0.2.5 - 2026-10-27** gemaakt, met Home Assistant-instellingen,
geschiedenis en de geselecteerde apps. De voltooide back-up van **209,42 MB**
staat volgens de HA-back-uplijst zowel op **Dit systeem** als op **Synology DSM**.

Daarnaast zijn de 48 bestanden van de oude labcomponent buiten de live share
gekopieerd naar de genegeerde lokale ontwikkelmap
`work/deployment-20261027/solesta_lab-0.2.4-before`. De kopie is bytegelijk
gecontroleerd. De nulmeting en bestandscontroles staan lokaal in
`work/deployment-20261027/deployment.json`; deze ontwikkelartefacten worden niet
meegecommit.

Bij terugkeer na de schema-upgrade is de native back-up het herstelpad voor
code en opgeslagen HA-configuratie. Alleen de oude componentbestanden
terugzetten is geen volledige schema-terugrol. Voor herstel vóór een eerste
start van de nieuwe code is ook de afzonderlijke codekopie beschikbaar.
Er is geen herstel nodig geweest.

## Plaatsing en verificatie

1. De nieuwe labmap is volledig naast de bestaande labmap opgebouwd en
   gecontroleerd, waarna een directorywissel haar op het doelpad publiceerde.
   Tijdelijke oude en nieuwe mappen zijn daarna verwijderd; de lokale
   herstelkopie blijft beschikbaar.
2. Alle 48 geïnstalleerde bestanden zijn bytegelijk aan de gegenereerde build.
   De 45 productiecomponentbestanden zijn vóór en na de wijziging gelijk.
3. Home Assistant is via **Systeem → Herstart Home Assistant** in de native
   Companion-app opnieuw gestart. De herverbinding is afgewacht; HA meldde
   vervolgens dat het opstarten voltooid was.
4. Het labdashboard toont op beide kaarten **v0.2.5**. Web API en ESPHome Native
   hebben actuele waarden en normale systeemstatus. Bij de controle rond
   00:33 toonden beide 17 °C op de bovenste tegel en 0,58 kWh / 2,09 MJ.
   De bestaande provider-/systeemnamen worden weergegeven.
5. Het productiedashboard blijft functioneren en meldt **Alles werkt normaal**.
6. Het opstartlog bevat bij de controle geen Solesta- of Solesta Lab-fout.
   Een afzonderlijke waarschuwing betrof wachten op Synology DSM tijdens de
   algemene HA-opstart. Een melding over ongeldige authenticatie op `/api/`
   kwam van de eenmalige, ongeauthenticeerde bereikbaarheidscontrole door de
   agent; er zijn daarbij geen inloggegevens gebruikt.

Er zijn geen source-expressies via de systeemformulieren veranderd. De
agent heeft `.storage` niet rechtstreeks gewijzigd en de actieve
Recorderdatabase niet via SMB geopend of gekopieerd. Schema-opslag wordt door
de ondersteunde integratiemigratie en Home Assistant zelf afgehandeld.

## Afbakening

Dit is de installatie- en opstartcontrole van de nieuwe labkandidaat. De
nieuwe standaardexpressies worden niet automatisch in bestaande systemen
ingevoerd. De gebruiker kan ze desgewenst bewust aanpassen. Dit verslag is
geen nieuwe volledige providerwissel-, fysieke storings- of
productie-upgradeacceptatie. R08/R09 en de overige releasewerkzaamheden in
fase 6 blijven open. Er is geen push of HACS-release uitgevoerd.
