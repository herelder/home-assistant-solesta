# Fase 4 — parallelle acceptatie in Home Assistant

> Publicatiekopie: installatie-, apparaat- en netwerkidentificatoren zijn
> consequent gepseudonimiseerd. Meetwaarden, tijden en uitkomsten zijn behouden.

Datum installatie: 22 oktober 2026

Datum eindcontrole: 23 oktober 2026

Resultaat: geslaagd; beide providers zijn afzonderlijk geaccepteerd voor fase 5

## Reikwijdte

Solesta Lab is naast de bestaande productie-integratie in de live Home
Assistant-omgeving geplaatst. In het lab zijn gelijktijdig één Web API-hub en
één ESPHome Native-hub geconfigureerd. Deze fase omvat geen providerwissel en
geen migratie van bestaande productie-entiteiten; die controles horen
uitsluitend bij fase 5.

De uitkomst combineert:

- de parallelle Home Assistant-meting van 22 oktober omstreeks 22:34 tot
  23 oktober omstreeks 01:00 CEST, ongeveer tweeënhalf uur;
- de eerdere empirische vergelijking over ruim 73 uur, inclusief meerdere
  echte pompruns;
- de afzonderlijke WAN-isolatietest van ongeveer drie uur;
- de omgekeerde isolatietest door de USB-voeding van de Nano weg te nemen en
  daarna weer aan te sluiten;
- visuele vergelijking van beide providers op het afzonderlijke Solesta
  Lab-dashboard;
- de fysieke native-API-acceptatie vanuit het gegenereerde Solesta Lab-pakket.

De parallelle eindcontrole viel in een nachtelijk venster zonder pomprun. Dat
is geen openstaand acceptatiepunt: de fractionele ESPHome-pompwaarden en hun
vergelijking met de Web API zijn al tijdens het langere empirische venster
bewezen.

## Baseline, versies en herstelpad

| Onderdeel | Vastgelegde toestand |
| --- | --- |
| Home Assistant Core | `2026.10.2` |
| Productie-integratie | `solesta` `0.2.3`, Web API, actief en ongewijzigd |
| Productie-update-interval | door de gebruiker ingesteld op 30 seconden |
| Solesta Lab | `solesta_lab` `0.2.3`, build `058df71e3b4d` |
| Lab Web API-hub | `lab-web-api`, systeem `sol_0217181ef299`, 15 seconden |
| Lab ESPHome Native-hub | `lab-esphome-native`, systeem `02_b6_a2_14_14_16_uart1`, 15 seconden |
| ESPHome-node | ESPHome `2026.9.1`, versleutelde native API op poort `6053` |
| ESPHome-clientbibliotheek | `aioesphomeapi==46.6.0`, passend bij Home Assistant `2026.10.2` |
| Nano-internettoegang | geblokkeerd; niet nodig voor de lokale dataroute |

Vóór plaatsing is een herstelkopie van de ongewijzigde productie-integratie
gemaakt onder
`work/phase4-recovery-20261022/custom_components/solesta`. De geïnstalleerde
productiecode is bij de eindcontrole nog bytegelijk aan deze herstelkopie,
afgezien van door Python gemaakte cachebestanden. Ook de geïnstalleerde
Solesta Lab-code is bytegelijk aan de gegenereerde build, opnieuw met uitsluiting
van cachebestanden.

Het herstelpad blijft:

1. schakel of verwijder uitsluitend de twee `solesta_lab`-configuraties via de
   Home Assistant-interface;
2. verwijder zo nodig uitsluitend de map
   `/config/custom_components/solesta_lab` en herstart Home Assistant;
3. laat de bestaande `solesta`-configuratie staan;
4. herstel productiecode alleen uit de bovengenoemde herstelkopie wanneer een
   afzonderlijk geverifieerde reden daarvoor bestaat.

Er is geen Recorderdatabase geopend en `.storage` is niet rechtstreeks
gewijzigd. Het dashboard is uitsluitend via de Home Assistant-interface
aangemaakt. Voor de eindcontrole zijn de config-entry- en entityregisters
alleen gelezen.

## Installatie en configuratie

Home Assistant is na de eerste plaatsing van Solesta Lab en opnieuw na de
clientbibliotheekcorrectie gecontroleerd herstart. De bestaande
Solesta-integratie kwam beide keren normaal terug en bleef haar
productiesysteem via de Web API bijwerken.

Tijdens het toevoegen van het vergelijkingsdashboard bleek de oorspronkelijke
pin `aioesphomeapi==46.2.0` te botsen met de ESPHome-integratie van Home
Assistant `2026.10.2`: Home Assistant kon `SerialProxyIdentity` daardoor niet
importeren. De pin is afgestemd op de Core-versie en verhoogd naar
`aioesphomeapi==46.6.0`. Na een deterministische herbouw van Solesta Lab en een
Home Assistant-herstart waren zowel de reguliere ESPHome-integratie als beide
Solesta Lab-hubs zonder configuratiefout actief.

De gegenereerde labintegratie registreert haar kaart onder het eigen type
`custom:solesta-lab-status-card` en het eigen resourcepad `/solesta_lab/`.
Daardoor kunnen de productiekaart en de labkaart tegelijk worden geladen
zonder een botsing tussen custom-elementnamen. Het Home Assistant-dashboard
**Solesta Lab** toont de Web API- en ESPHome Native-kaarten naast elkaar.

Beide labhubs zijn actief en hun systemen zijn expliciet ingeschakeld:

| Provider | Gevalideerde bronidentiteit | Publieke systeemidentiteit |
| --- | --- | --- |
| Web API | `SOL_0217181EF299` | `sol_0217181ef299` |
| ESPHome Native | `02:b6:a2:14:14:16/uart1` | `02_b6_a2_14_14_16_uart1` |

Beide configuraties gebruiken config-entryschema `1.1`, expressieschema `4`,
configuratierevisie `2` en gevalideerde providerrevisie `1`. Gevoelige
inloggegevens en de Noise-PSK zijn alleen via de Home Assistant-interface
ingevoerd en zijn niet in projectbestanden of dit verslag opgenomen.

## Parallelle waarneming

De drie temperaturen, het pomppercentage en de rapportagestatus zijn in de
native Home Assistant-app per provider naast elkaar in Geschiedenis gelegd.

| Signaal | Waarneming | Beoordeling |
| --- | --- | --- |
| Collectortemperatuur | de reeksen volgden dezelfde overgangen van 11 naar 10 naar 9 °C; kortstondig liep één route 1 °C voor | passend bij verschillende bemonsteringsmomenten en Web API-polling |
| Tank boven | beide routes eindigden op 25 °C en volgden dezelfde overgang van 26 naar 25 °C | gelijkwaardig |
| Tank onder | 23–24 °C; kortstondige verschillen van 1 °C bij overgangen | gelijkwaardig binnen bemonstering en gehele-gradenresolutie |
| Pomppercentage | beide routes bleven in dit nachtelijke venster op 0% | geen tegenstelling; echte en fractionele pompruns zijn in de 73-uursproef al geaccepteerd |
| Rapportagestatus | beide routes bleven `Verbonden`; er waren geen onderbrekingen of `Niet beschikbaar`-segmenten in het labvenster | geslaagd |

Een representatieve momentopname tijdens de parallelle controle gaf voor
ESPHome Native respectievelijk 10 °C, 26 °C en 24 °C voor collector, tank boven
en tank onder. De Web API gaf op vrijwel hetzelfde moment 10 °C, 25 °C en
23 °C. Het verschil van één graad bewoog mee met de latere overgangen en wijst
niet op een vaste schaal- of mappingfout.

De Home Assistant Core-log bevatte bij de eindcontrole geen fout of waarschuwing
van `solesta_lab`. De enige zichtbare Core-waarschuwing was een algemene
opstartmelding over andere, bestaande integraties. Beide labproviders en de
productie-integratie waren daarna operationeel.

## Entiteitscontract

Het Home Assistant-entityregister bevat na installatie 42
`solesta_lab`-entiteiten: 21 voor iedere providerroute. De expliciete
grenscontrole gaf:

- geen entity-ID of unique ID voor `flow_raw`;
- geen entity-ID of unique ID voor `frame_sequence`;
- geen entity-ID of unique ID voor controllerstatus;
- precies één gereserveerde T4-entiteit per provider, met de bestaande naam
  `Unused temperature`, door de integratie uitgeschakeld én verborgen;
- geen wijziging van deze regels door het naast elkaar activeren van beide
  providers.

Daarmee blijven flow, framediagnostiek en controllerstatus buiten Solesta en
blijft T4 uitsluitend het bestaande gereserveerde contract.

## Lokale werking zonder internet

Tijdens de eerdere WAN-isolatietest was de internettoegang van zowel de Nano
als de Solesta-installatie ongeveer drie uur geblokkeerd. De Web API-route
rapporteerde het Solesta-systeem daardoor zoals verwacht als offline. De Nano
bleef ondertussen lokaal seriële metingen ontvangen en via ESPHome Native aan
Home Assistant leveren. Ook tijdens de uiteindelijke fase-4-opstelling had de
Nano geen internettoegang en bleef deze lokale route normaal werken.

Daarmee is bevestigd dat de ESPHome Native-route niet afhankelijk is van de
Solesta Web API, van de Solesta-cloudverbinding of van internettoegang voor de
Nano.

## Uitval en automatisch herstel van de Nano

Op 23 oktober is ook de omgekeerde storingsrichting getest door de
USB-voeding van de Nano weg te nemen. Na ongeveer één minuut waren de actuele
ESPHome Native-waarden niet meer beschikbaar. De labkaart toonde streepjes
voor temperatuur en energie, de systeemstatus werd onbekend en de laatst
geldige rapportageperiode bleef zichtbaar als `20:55:47`–`20:58:17`. De
historische temperatuurgrafiek bleef behouden. De Web API-route bleef tegelijk
normaal werken en toonde onder meer 19 °C, 0,76 kWh, Online en Stand-by.

Na het opnieuw aansluiten van USB herstelde de reguliere ESPHome-integratie
automatisch. Home Assistant toonde de Nano opnieuw als één apparaat met 16
entiteiten. De relevante directe ESPHome-entiteiten kwamen om `21:04:11`
gezamenlijk beschikbaar, waaronder:

- vattemperatuur 18,5 °C;
- vatenergie 0,756 kWh en 2,7209 MJ;
- pompstatus uit;
- rapportagestatus aan.

De collectortemperatuur wijzigde daarna opnieuw om `21:08:26`, waarmee ook is
bevestigd dat de doorlopende meetstroom was hervat. Om `21:11:08` toonden beide
labkaarten dezelfde actuele toestand en hetzelfde rapportagevenster
`21:08:38`–`21:11:08`. Er was geen herlaadactie, herconfiguratie of herstart
nodig.

De twee storingsproeven bewijzen daarmee beide onafhankelijkheidsrichtingen:

- bij uitval van internet en de Web API blijft de lokale ESPHome-route werken;
- bij uitval van de Nano blijft de Web API-route werken en herstelt ESPHome
  automatisch zodra de Nano terugkeert.

## Afwijkingen en besluit

Er zijn geen blokkerende afwijkingen gevonden. De waargenomen verschillen zijn
beperkt tot verwachte timing- en afrondingsverschillen van maximaal één graad
bij temperatuurveranderingen. Het specifieke labvenster bevatte geen pomprun;
dat punt wordt afgedekt door de langere empirische acceptatie waarin zowel
100% als fractionele afloopwaarden zijn waargenomen.

Een niet-blokkerend tekstueel aandachtspunt is dat de kaart bij volledige
uitval van de ESPHome-bron meldt dat *een deel* van de systeemstatus niet
beschikbaar is. De technische toestand wordt veilig weergegeven en er worden
geen oude waarden als actueel gepresenteerd, maar een toekomstige
tekstverbetering kan explicieter melden dat de ESPHome-bron niet bereikbaar
is.

Fase 4 is daarmee afgerond. De productie-integratie blijft ongewijzigd actief,
Solesta Lab blijft met beide afzonderlijk geaccepteerde providers beschikbaar
en de volledige heen-en-terugwissel mag pas na een afzonderlijke opdracht in
fase 5 worden uitgevoerd. Voor die wissel moeten vooraf de blijvende
config-entry-, hub-, systeem-, apparaat-, entity- en unique-ID-identiteiten en
een historiebaseline worden vastgelegd.

## Gerelateerde resultaten

- [`esphome-m5nanoc6-empirical-acceptance-2026-10-21.md`](esphome-m5nanoc6-empirical-acceptance-2026-10-21.md)
- [`esphome-native-provider-physical-acceptance-2026-10-22.md`](esphome-native-provider-physical-acceptance-2026-10-22.md)
