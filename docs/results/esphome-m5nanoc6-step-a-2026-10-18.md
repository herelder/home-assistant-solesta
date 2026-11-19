# Uitvoeringsverslag ESPHome M5Stack NanoC6 - stap A

Datum: 18 oktober 2026<br>
Resultaat: geslaagd

## Doel

Stap A van het flashplan valideert de kale M5Stack NanoC6 voordat de Solesta-
UART en parser worden toegevoegd. Er zijn in deze stap daarom bewust nog geen
Solesta-sensoren of seriele RX-configuratie aanwezig.

## Gebruikte versies en hardware

| Onderdeel | Vastgesteld |
| --- | --- |
| Home Assistant | 2026.10.1 |
| ESPHome Device Builder | 1.14.9 |
| ESPHome | 2026.9.1 |
| ESP-IDF | 5.5.5 |
| Chip | ESP32-C6FH4, revisie 0.2 |
| Flash | 4 MB |
| USB-interface | ingebouwde USB Serial/JTAG |
| Seriele poort tijdens de proef | `/dev/cu.usbmodem1101` |

De gegenereerde factory-image heet
`solesta-nanoc6-demo-firmware.factory.bin`, is 893.136 bytes groot en heeft
SHA-256:

```text
3f3a10a1114c9b2ba8d58047028e184ccafc3b5e93b88e24d97b41b256afca7c
```

## Effectieve basisconfiguratie

De configuratie is opgeslagen als `solesta-nanoc6-demo.yaml` in de ESPHome-
configuratiemap van Home Assistant. Geheimen en netwerknamen zijn hieronder
bewust weggelaten.

```yaml
esphome:
  name: solesta-nanoc6-demo
  friendly_name: Solesta serial bridge

esp32:
  variant: esp32c6
  flash_size: 4MB
  framework:
    type: esp-idf

logger:
  hardware_uart: USB_SERIAL_JTAG
  level: DEBUG

api:
  encryption:
    key: <niet opgenomen>

ota:
  - platform: esphome
    encryption:

wifi:
  ssid: <via secrets.yaml>
  password: <via secrets.yaml>
```

Er is geen webserver, captive portal of open fallback-accesspoint toegevoegd.
De NanoC6 is tijdens deze proef met een 2,4GHz-netwerk verbonden; de ESP32-C6
ondersteunt geen 5GHz-wifi.

## Verificatie

| Acceptatiecriterium | Bewijs | Resultaat |
| --- | --- | --- |
| Configuratie valideert | Device Builder meldde `Configuratie is geldig!` | geslaagd |
| Compilatie voor C6/4 MB/USB-console | build voltooid met ESP-IDF 5.5.5; USB-logger rapporteerde `USB_SERIAL_JTAG` | geslaagd |
| Eerste USB-flash | factory-image volledig geschreven; flash-hash door het flashgereedschap geverifieerd | geslaagd |
| Drie normale starts | drie opeenvolgende starts met nul mislukte pogingen, voltooide `setup()` en de veilige 60-secondenmarkering | geslaagd |
| Wifi | verbinding kwam na iedere start terug; het apparaat werd online in Device Builder | geslaagd |
| Versleutelde native API | log rapporteerde `Noise encryption: YES`; Home Assistant maakte opnieuw verbinding | geslaagd |
| Home Assistant-discovery | `Solesta serial bridge (solesta-nanoc6-demo)` werd ontdekt en als ESPHome-apparaat toegevoegd | geslaagd |
| Versleutelde OTA | netwerkupdate voltooid; log rapporteerde `Encryption: required`; OTA-start doorstond 60 seconden | geslaagd |
| OTA blijft actief | na een aanvullende normale reset startte het apparaat opnieuw zonder rollback, verbond met wifi en Home Assistant en werd na 60 seconden succesvol gemarkeerd | geslaagd |
| USB/downloadmodus | ROM-verbinding en `chip-id` werkten voor en na de factory-flash | geslaagd |

De HA-apparaatpagina toont firmware `2026.9.1`, gebouwd op
18 oktober 2026 om 15:03:58 +0200. Omdat stap A nog geen bronentiteiten bevat,
zijn er terecht nog geen Solesta-sensorwaarden in Home Assistant.

## Waarnemingen

- Bij een vroege OTA-proef werd het apparaat tijdens de eerste 60 seconden
  bewust opnieuw gestart. De ESP-IDF-rollbackbeveiliging zette de vorige
  partitie daarop correct terug. Dit was door de testvolgorde veroorzaakt en
  geen crash. De definitieve OTA-proef is vervolgens volledig doorlopen en na
  een extra reset opnieuw succesvol gestart.
- Bij enkele starts mislukte de eerste wifi-authenticatiepoging; de tweede
  poging maakte direct verbinding. Dit verhinderde geen van de
  acceptatieproeven, maar is een nuttig aandachtspunt bij plaatsing in de
  Solesta-behuizing.
- De versleutelsleutel is niet in dit verslag opgenomen. De actuele sleutel
  blijft onderdeel van de live ESPHome-configuratie.

## Conclusie en vervolg

Stap A is geaccepteerd. De NanoC6 kan nu als gevalideerde basis voor stap B
worden gebruikt. Stap B voegt uitsluitend de passieve UART-RX en tijdelijke
ruwe regellogging toe, nadat de in het flashplan genoemde elektrische
veiligheidscontroles en de 2,7 kOhm-serieweerstand zijn bevestigd.
