# Uitvoeringsverslag ESPHome M5Stack NanoC6 - stap C

Datum: 18 oktober 2026<br>
Resultaat: geslaagd voor implementatie, OTA en eerste live ontvangst; de
latere duurproef en controllerovergangen zijn op 21 oktober 2026 eveneens
geslaagd

## Doel

Stap C vervangt de tijdelijke UART-debugger door een begrensde, strikt
validerende parser en maakt de acht inhoudelijke Solesta-bronvelden als Home
Assistant-entiteit beschikbaar. De bestaande Solesta-integratie is hierbij
niet gewijzigd.

## Gebruikte versies en configuratie

| Onderdeel | Vastgesteld |
| --- | --- |
| ESPHome | 2026.9.1 |
| ESP-IDF | 5.5.5 |
| Board | M5Stack NanoC6, ESP32-C6FH4, 4 MB |
| UART | GPIO1 RX, 57600 8N1, buffer 1024 bytes |
| Projectconfiguratie | `esphome/solesta-nanoc6-demo.yaml` |
| SHA-256 projectconfiguratie | `a9c4dfd3c28be7f358f31795d357fd4db3c1f144a6eefdc0be940f66aa07e830` |

De live API-encryptiesleutel en wifi-geheimen zijn niet in de projectkopie of
dit verslag opgenomen. Er is geen `tx_pin`, `uart.write`, webserver of open
fallback-accesspoint toegevoegd.

## Gepubliceerde inhoudelijke entiteiten

| Entiteit | Type | Eerste live waarneming |
| --- | --- | --- |
| `temperature_1_raw` | numerieke sensor | `39` |
| `temperature_2_raw` | numerieke sensor | `22` |
| `temperature_3_raw` | numerieke sensor | `21` |
| `temperature_4_raw` | numerieke sensor | `309`, ongeschaald |
| `flow_raw` | numerieke sensor | `0.0` |
| `pump_raw` | numerieke sensor | `0.000000` |
| `controller_state_code` | numerieke sensor | entiteit aanwezig; geen nieuwe Z-regel in het korte controlevenster |
| `controller_state_text` | tekstsensor | entiteit aanwezig; geen nieuwe Z-regel in het korte controlevenster |

Daarnaast zijn diagnostische entiteiten aanwezig voor `frame_sequence`,
geldige en afgekeurde records, ontvangen controllerstates, data-ouderdom,
`data_valid` en de laatste geldige statusregel.

Home Assistant registreerde in totaal zestien ESPHome-entiteiten: de vijftien
expliciet gedeclareerde inhoudelijke en diagnostische entiteiten plus de door
ESPHome aangeboden firmware-update-entiteit. De vier tellers worden bij boot
expliciet op nul gepubliceerd; controllercode en -tekst blijven terecht
onbekend tot de eerste geldige Z-regel.

## Parser- en beschikbaarheidscontract

- Alleen volledige `T|t1|t2|t3|t4_F|flow_PWM|pump`-records publiceren de zes
  meetwaarden.
- Alleen volledige `Z|code|tekst`-records publiceren code en tekst.
- Numerieke tokens moeten volledig parseerbaar en eindig zijn.
- Niet-ASCII en regels langer dan 256 tekens worden tot de volgende `LF`
  weggegooid; daarna synchroniseert de parser opnieuw.
- MQTT-, HTTP-, `updated!`-, `Failed!`- en overige logregels worden genegeerd.
- Ongeldige records laten de laatst geldige waarden intact en verhogen alleen
  de afwijzingsteller.
- De vier tellers starten zichtbaar op nul en lopen pas daarna op basis van
  ontvangen records op.
- Zonder geldig statusrecord gedurende 15 seconden wordt `data_valid` onwaar.
- Temp04 blijft exact `309`; in de firmware vindt geen schaalconversie plaats.

## Live verificatie

De eerste OTA met de volledige parser startte normaal en ontving onmiddellijk
geldige statusrecords. Onder meer de volgende regel werd ongewijzigd als
laatste geldige statusregel gepubliceerd:

```text
T|39|22|21|309_F|0.000000_PWM|0.000000
```

De zes numerieke waarden kwamen daarmee overeen. `valid_frame_count` en
`frame_sequence` liepen gelijk op (onder meer 4, 5, 6 en 7) en `data_age`
bleef tussen opeenvolgende frames laag (onder meer 0,4 en 2,3 seconde). Dit
bevestigt ontvangst, volledige-framevalidatie en publicatie op de NanoC6 zelf.

Na de definitieve OTA met nulinitialisatie bleef het apparaat langer dan een
minuut stabiel online. ESPHome meldde firmware en configuratiehash als
gesynchroniseerd. In Home Assistant stonden `controller_state_count` en
`rejected_record_count` beide op `0,0`, `data_valid` op verbonden en
`data_age` op `0,3 s`. `frame_sequence` en `valid_frame_count` stonden beide
op `37,0` en liepen daarna samen verder op. Controllercode en -tekst bleven,
zoals verwacht zonder verse Z-regel, onbekend.

Een eerste configuratie van de logfilters met globaal `INFO` en
tag-specifiek `DEBUG` werd door ESPHome terecht bij validatie afgewezen. De
definitieve configuratie gebruikt globaal `DEBUG` en zet de terugkerende
`sensor`, `text_sensor`- en `binary_sensor`-categorieen afzonderlijk op
`INFO`. Daardoor blijven parserafwijzingen diagnostisch beschikbaar zonder
continue state-publicatielogging.

## Geautomatiseerde verificatie

| Controle | Resultaat |
| --- | --- |
| Generatorcontrole `tools/build.py --check` | geslaagd; `thetruth.py` en `provider_defaults.py` actueel |
| Volledige Python-suite | 205 tests geslaagd |
| Dashboardkaart | 26 tests geslaagd |
| Projecthygiëne in de Python-suite | geslaagd; geen gegenereerde cachebestanden achtergebleven |

De Python-suite is met tijdelijke, buiten de projectmap geplaatste
testafhankelijkheden uitgevoerd; de repository zelf is daarvoor niet met
afhankelijkheden of gegenereerde bestanden vervuild.

## Herstelpad

Voor de live wijziging is een alleen voor de eigenaar leesbare kopie van de
stap-B-configuratie bewaard op:

```text
/private/tmp/solesta-step-c.EMlde8/solesta-nanoc6-demo.pre-step-c.yaml
```

SHA-256 van die herstelkopie:

```text
43afa5149bbbe84cbece3fa2520910d126ac9c9ba7ac231fc3f7c12751e37739
```

Terugzetten is alleen nodig wanneer de live proef onverwacht verslechtert;
het bestand bevat de bestaande live geheimen en mag daarom niet in Git of een
rapportagebundel terechtkomen.

## Latere hardwareacceptatie

De aanvankelijk openstaande duurproef, natuurlijke controllerovergangen,
fractionele PWM en vergelijking met de bestaande Solesta-entiteiten zijn op
21 oktober 2026 uitgevoerd. Het volledige bewijs, inclusief de begrensde
conclusie dat `temperature_4_raw` en `flow_raw` semantisch onbewezen blijven,
staat in
[`esphome-m5nanoc6-empirical-acceptance-2026-10-21.md`](esphome-m5nanoc6-empirical-acceptance-2026-10-21.md).

De daaropvolgende ontwerpkeuze is dat flow, frame sequence en controllerstatus
geen nieuwe Solesta-entiteiten worden. Het bestaande gereserveerde T4-contract
blijft ongewijzigd.

De NanoC6 blijft een onafhankelijke bron totdat de ESPHome-provider met eigen
regressietests en de lokale acceptatieroute is geimplementeerd. De bestaande
Solesta-integratie is bij deze hardwareacceptatie niet gewijzigd.
