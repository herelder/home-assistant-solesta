# Eerste live resultaat ESPHome M5Stack NanoC6 - stap B

Datum: 18 oktober 2026<br>
Status: eerste live UART-proef geslaagd; stap B nog niet volledig afgerond

## Proefopstelling

- De NanoC6 draaide op de in de Solesta ingebouwde, extern via USB gevoede
  opstelling.
- De Solesta was ingeschakeld en functioneerde volgens de gebruiker normaal.
- De MacBook was niet als voedingsbron of seriele bron op de NanoC6 aangesloten.
- Solesta pin 5 werd uitsluitend passief ontvangen op NanoC6 GPIO1; in de
  ESPHome-configuratie was geen `tx_pin` aanwezig.
- De ESPHome-logs zijn via wifi bekeken en als tijdelijk testlog gedownload.

De tijdelijke stap-B-configuratie gebruikte `57600 8N1`, een RX-buffer van
1.024 bytes en de UART-debugger met `dummy_receiver: true` en newline als
delimiter. De USB-console bleef op USB Serial/JTAG.

## Waarneming

Het bewaarde venster bevat 16 volledige statusregels van 16:35:17.916 tot en
met 16:36:04.369, dus 15 intervallen over 46,453 seconden. De gemiddelde
herhalingsperiode was daarmee ongeveer 3,10 seconden.

Voorbeelden uit het venster:

```text
T|45|22|21|309_F|0.000000_PWM|0.000000\r\n
T|44|23|21|309_F|0.000000_PWM|0.000000\r\n
T|44|22|21|309_F|0.000000_PWM|0.000000\r\n
```

Alle 16 statusregels:

- waren volledig en leesbaar;
- voldeden aan de verwachte `T|..._F|..._PWM|...`-grammatica;
- eindigden met `CRLF`;
- bevatten vier T-velden, een F-veld en een PWM-veld;
- behielden Temp04 exact als de onbewerkte waarde `309`;
- hadden in dit stilstandsvenster flow `0.000000` en PWM `0.000000`.

De eerste drie temperatuurvelden varieerden beperkt tussen `44`/`45`,
`22`/`23` en `21`. Het fragment bevatte daarnaast 30 MQTT-gerelateerde
`updated!`-regels. Die bevestigen de eerdere classificatie als te negeren
nevengeluid en vormen geen onderdeel van het lokale sensorcontract.

In het bewaarde venster traden geen ESPHome-waarschuwingen, ESPHome-fouten,
`Failed!`-meldingen, zichtbare framingschade of onverwachte herstarts op.

## Z-regels

In dit korte venster met een stabiele controllerstand kwam geen `Z|code|tekst`
voor. Daardoor is nog niet met deze NanoC6-proef vastgesteld of een Z-regel
alleen bij een toestandsovergang of volgens een ander ritme wordt uitgezonden.
De eerdere CoolTerm-capture blijft het bewijs voor de grammatica en beide
brononderdelen van Z-regels; een live toestandsovergang moet dit op de NanoC6
nog bevestigen.

## Beoordeling

De gekozen GPIO, baudrate, framing, gemeenschappelijke massa en passieve
luisterrichting werken in de ingebouwde opstelling. Er is op basis van dit
fragment geen aanleiding om de stap-B-UART-configuratie te veranderen.

Stap B is nog niet volledig afgerond. Nog te meten zijn minimaal:

1. een live Z-regel tijdens een natuurlijke controllertoestandsovergang;
2. statusframes met werkelijke flow en niet-nul-PWM;
3. gedrag bij Solesta-opstart, ESP-opstart en tijdelijk wegvallen van data;
4. een duurproef van minimaal 24 uur op onverwachte reboots, framingfouten en
   bufferproblemen.

Ruwe UART-logging blijft uitsluitend tijdelijk voor dit onderzoek. De
gedownloade volledige ESPHome-log wordt niet in het project opgenomen, omdat
zo'n log ook netwerk- en apparaatmetadata kan bevatten; alleen de relevante,
geschoonde waarnemingen staan hierboven.
