# Solesta Lab 0.2.9 en NanoC6 0.1.1 — installatie

Datum: 17 november 2026, Europe/Amsterdam.

Opdracht: installeer de herstelde reviewkandidaat in `solesta_lab` en ESPHome.
Status: geplaatst, Nano draadloos bijgewerkt, HA en Companion herstart en
de actuele werking gecontroleerd.

## Pakketten en herstelpad

| Onderdeel | Voor | Geïnstalleerd |
| --- | --- | --- |
| Home Assistant | 2026.11.1 | Zelfde HA-versie, Core herstart |
| Labintegratie en kaart | 0.2.8, build `c17cd0b42797` | **0.2.9**, build `c40b390f17e2` |
| NanoC6-firmware | 0.1.0 | **0.1.1** |
| Productie-Solesta | 0.2.3 | Code en volledige opgeslagen configuratie ongewijzigd |

De Lab-bronkopie bevat de [correcties voor S100-01 tot en met S100-12](documentation-s100-11-12-fixes-2026-11-17.md).
Alleen de manifest- en kaartversie zijn in die afzonderlijke bronkopie op
0.2.9 gezet. De canonieke kandidaat blijft 1.0.0, bronhash
`1d51d2a9126446daf4009c00ce27fce86e8f1f5858625d6559c4caca9758e085`.
De Labgenerator bouwt deterministisch 51 bestanden en houdt archivering uit.
Alle **106 modeltests** slagen ook op het werkelijk geïnstalleerde Lab-pakket.

Vóór plaatsing bevestigde de native HA-app een geslaagde automatische back-up
op één locatie. De oude 51 Lab-programmabestanden staan daarnaast bytegelijk
onder `work/deployment-20261117-review-fixes/solesta_lab-0.2.8-before`.
De oorspronkelijke live map is bewaard als
`/config/.solesta_lab-previous-20261117-c17cd0b42797`.
De oude firmware-YAML staat in dezelfde lokale werkmap als
`solesta-nanoc6-0.1.0-before.yaml`.

Codeherstel kan door de oude Lab-map terug te plaatsen en HA opnieuw te
starten. Het configuratieschema blijft 1.9 met expressieschema 11, en alle
opgeslagen subentries zijn gelijk gebleven. De native HA-back-up blijft het
volledige herstelpad. Firmwareherstel kan door de bewaarde oude YAML met
de bestaande secrets opnieuw te bouwen en via OTA te installeren; bij een
onbereikbare OTA-route blijft USB-herstel beschikbaar.

## Uitvoering en controle

- Lab en de publieke firmware-YAML zijn met gecontroleerde staging geplaatst.
  De 51 live Lab-bestanden zijn vóór en na de herstart bytegelijk aan het
  geteste pakket. De geplaatste YAML is bytegelijk aan de publieke 0.1.1-bron.
- ESPHome Device Builder 1.25.0 bouwde en installeerde de firmware via het
  netwerk met **ESPHome 2026.10.2 / ESP-IDF 5.5.6**. De log bevestigde de
  draaiende projectversie **0.1.1**, een geslaagde API-handshake en nieuwe
  UART-frames met doorlopende frameteller. Om 16:57:31 volgde de expliciete
  bevestiging dat de boot geslaagd was en de bootloopcounter werd gereset.
  Device Builder toonde daarna een online apparaat en gesynchroniseerde
  versie en configuratiehash.
- De firmwarewijziging behoudt de bestaande identiteit en versleutelde
  API-/OTA-route. De bestaande secrets zijn met hun hash vergeleken en
  ongewijzigd. De API-herstarttimer staat nu, net als die van MQTT, op nul.
- HA is via de native app herstart. Na de waargenomen verbindingsonderbreking
  is Companion volledig afgesloten en opnieuw geopend.
- De integratiepagina toont **0.2.9**, **vier apparaten** en **84 entiteiten**.
  Alle vier bestaande labsystemen zijn ingeschakeld gebleven met exact hun
  eerdere subentries en bronexpressies.
- De Web API-, Native- en EMQX-vergelijkingskaarten tonen **v0.2.9**, online,
  actuele meetwaarden en normale status. Zowel vandaag- als zevendaagse
  historie is bekeken; de Native-kaart is daarna op vandaag teruggezet.
  Het extra Mosquitto-systeem is op zijn apparaatpagina afzonderlijk
  gecontroleerd: actuele temperaturen, rapportagevertraging `[0,150]` en
  rapportagestatus **Verbonden**. Ook EMQX is afzonderlijk zo gecontroleerd.
- Het vernieuwde Core-log bevat bij de eindcontrole geen Solesta Lab-fout.
  Er staat één algemene opstartwaarschuwing over integraties die tijd nodig
  hadden voor hun initialisatie; die is niet gewist.
- Een eindvergelijking bevestigt dat productiecode, de volledige opgeslagen
  productieconfiguratie, de vier Lab-subentries en de ESPHome-secrets behouden
  zijn. De actieve Recorderdatabase is niet geopend of gekopieerd en
  `.storage` is uitsluitend read-only gecontroleerd.

Companion is achtergelaten op het Lab-vergelijkingsdashboard. De lokale
installatieadministratie en testuitvoer staan onder
`work/deployment-20261117-review-fixes/`; deze werkbestanden worden niet
gepubliceerd. De kennisbasis en de schone releasecheckout zijn niet aangepast.
Er is niets gecommit of gepusht.

Dit is een installatie- en opstartcontrole. De bestaande bronexpressies zijn
bewust behouden; de nieuwe kitmappings uit de handleiding zijn niet automatisch
op bestaande systemen toegepast. Een fysieke UART-uitvalproef en een proef
van meer dan dertig minuten uitsluitend via MQTT zijn hiermee niet herhaald.
