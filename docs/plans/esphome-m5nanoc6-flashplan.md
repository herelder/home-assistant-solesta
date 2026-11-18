# Flash- en validatieplan ESPHome op M5Stack NanoC6

Status: flash-, plaatsings- en empirische hardwareacceptatie afgerond; stap C
draait permanent in de Solesta-opstelling.
Oorspronkelijk: 5 oktober 2026; bijgewerkt tot en met 21 oktober 2026

Leidend hardwarecontract: de montage-instructie
`Solesta_M5NanoC6_montage_instructie_externe_USB_voeding.pdf`, versie 2.0 van
1 oktober 2026. Bij verschil tussen dit flashplan en die mechanische
montage-instructie wordt eerst het verschil opgelost; er wordt niet op basis
van een van beide documenten doorgebouwd.

## 1. Doel en afbakening

Het doel van deze fase is een M5Stack NanoC6 veilig van ESPHome te voorzien,
de seriele Solesta-uitvoer passief te ontvangen en acht inhoudelijke
Solesta-sensorentiteiten in Home Assistant zichtbaar te maken:

- vier temperatuurvelden uit groep `T`;
- een flowveld uit groep `F`;
- een pompveld uit groep `PWM`;
- de numerieke controllerstate-code uit een `Z`-regel;
- de bijbehorende controllerstate-tekst uit dezelfde `Z`-regel.

De eerste zes zijn meetwaarden; de laatste twee beschrijven de toestand van de
controller. Alle acht verschijnen als sensorentiteit in Home Assistant. In de
ESPHome-configuratie is de tekstuele controllerstate technisch een
`text_sensor`, terwijl de overige zeven een numerieke `sensor` zijn.

Deze fase verandert de bestaande Solesta-integratie niet. Zij levert bewijs
over de elektrische aansluiting, het berichtenformaat, de schaal en het gedrag
van de acht bronentiteiten. Dat bewijs is inmiddels verwerkt in het afzonderlijke
functionele ontwerp voor de ESPHome-provider; de providerimplementatie volgt
pas na deze hardwarefase.

## 2. Vastgestelde uitgangspunten

De seriele inventarisatie van 1 oktober 2026 heeft vastgesteld:

- Solesta PROGRAM/DEBUG pin 1 is GND;
- Solesta pin 5 is de continue TX-uitgang;
- de verbinding is `57600` baud, 8 databits, geen parity, 1 stopbit en geen
  flow control;
- een voorbeeldstatusregel is
  `T|47|34|34|309_F|0.000000_PWM|0.000000`;
- de regel bevat exact drie groepen, gescheiden door `_`, en exact zes waarden;
- de vier ruwe T-velden in dit voorbeeld zijn exact `47`, `34`, `34` en `309`;
- `309` is de uitzonderlijke ruwe waarde van het voorlopige Temp04-veld. De
  interpretatie als 30,9 graden Celsius is niet bevestigd en wordt niet in de
  parser opgenomen. Dit veld wordt door de Solesta Web API wel doorgegeven,
  maar daar niet gevuld; betekenis, schaal en eenheid moeten daarom empirisch
  worden onderzocht;
- de precieze functionele betekenis van alle posities is nog niet volledig
  bevestigd;
- ESPHome moet uitsluitend luisteren en mag niets naar de Solesta zenden.

De CoolTerm-capture van 8 oktober 2026 heeft het seriele contract verder
aangescherpt. De capture duurde op basis van bestandsnaam en wijzigingstijd
ongeveer 2 uur en 13 minuten en bevatte 1.453 volledig geldige statusregels:

- alle statusregels voldeden aan dezelfde grammatica en gebruikten `CRLF`;
- Temp04 was in alle 1.453 frames exact `309` en flow exact `0.000000`;
- PWM was niet binair: naast `0.000000` en `1.000000` kwamen onder meer
  `0.751801`, `0.754609`, `0.757539` en `0.760347` voor;
- controllerstatusregels hebben de vorm `Z|code|tekst`, met in deze capture de
  codes 0 tot en met 4;
- `updated!`, `Failed!`, MQTT-, HTTP- en verbindingsmeldingen behoren tot de
  MQTT-logging van de Solesta en niet tot het lokale meetcontract;
- een lange niet-ASCII opstartregel toont dat de parser na corrupte of te lange
  invoer tot de volgende `LF` moet weggooien voordat hij opnieuw begint;
- een syntactisch geldige Temp01-reeks `56, 37, 38, 59` wordt niet op basis van
  plausibiliteit gefilterd zolang timing en oorzaak niet aanvullend zijn
  vastgesteld.

Het lokale contract bestaat daarmee uitsluitend uit volledige statusregels en
controllerstatusregels. Samen leveren die acht inhoudelijke
Solesta-sensorentiteiten. MQTT-specifieke regels worden genegeerd en krijgen
geen ESPHome-entiteiten of providercontract.

De NanoC6 gebruikt een ESP32-C6FH4 met 4 MB flash. Op de Grove-connector zijn
GND, 5 V, GPIO2 en GPIO1 beschikbaar. Voor dit plan wordt GPIO1 als RX gekozen;
GPIO2 blijft vrij. GPIO1 is geen ESP32-C6-strappingpin en de USB-logger van de
ESP32-C6 gebruikt USB Serial/JTAG, zodat deze keuze de bootmodus en de
USB-console niet hoort te verstoren.

De definitieve hardware gebruikt externe USB-voeding. Een USB-C-paneelmodule
in het witte Solesta-deksel voert zowel 5 V als USB-data door naar de USB-C-
aansluiting van de NanoC6. Daardoor kan dezelfde buitenpoort voor normaal
bedrijf en voor programmeren worden gebruikt. Er wordt niets aangesloten op
Solesta 12 V, CTRL of andere voedingsbedrading.

## 3. Stopvoorwaarden voor elektrische veiligheid

Sluit Solesta pin 5 nog niet rechtstreeks op de NanoC6 aan voordat de volgende
controles zijn afgerond.

1. De projectmetingen en montage-instructie kwalificeren pin 5 als ongeveer
   3,3 V-logica. Bevestig voor de eerste definitieve aansluiting dat deze
   meetbasis nog geldt en stop wanneer hardware, print of gemeten niveau
   afwijkt.
2. Een ESP32-C6-GPIO mag bij 3,3 V voeding volgens de datasheet niet boven
   ongeveer `VDD + 0,3 V` komen. Bij een gemeten niveau boven 3,6 V of
   onverwachte overshoot wordt de verbinding niet in gebruik genomen en moet
   het hardwareontwerp eerst worden herzien.
3. Plaats de voorgeschreven weerstand van 2,7 kOhm in serie tussen Solesta pin
   5 en NanoC6 GPIO1/RX. Deze weerstand is geen spanningsdeler, maar begrenst
   de foutstroom wanneer bedrading of firmware onverwacht verkeerd staat.
4. Verbind nooit een NanoC6-TX-pin met de Solesta-header. Laat in ESPHome ook
   `tx_pin` volledig weg.
5. Solesta pin 1 en Grove zwart/NanoC6 GND blijven rechtstreeks verbonden,
   omdat het UART-signaal ondanks de externe Nano-voeding dezelfde elektrische
   referentie nodig heeft.

Gebruik voor normaal bedrijf een deugdelijke, geisoleerde 5 V USB-voeding met
voldoende marge voor Wi-Fi-stroompieken. De externe USB-C-voeding gaat via de
paneelmodule rechtstreeks naar de USB-C-poort van de NanoC6. Er is geen
buckconverter en er is geen verbinding met Solesta 12 V of CTRL.

Wanneer de NanoC6 via USB wordt gevoed, kan Grove rood zelf 5 V voeren. Daarom
wordt de rode draad op een eigen, verder volledig lege breadboardrij geplaatst.
Ook Grove geel/GPIO2 krijgt een eigen lege rij. Sluit geen van beide aan op de
Solesta of op een andere breadboardverbinding.

Sluit nooit de vaste USB-voeding en een MacBook of tweede USB-bron tegelijk
aan. Trek voor programmeren eerst de USB-lader uit de buitenpoort en sluit pas
daarna de MacBook met een geschikte USB-datakabel op diezelfde buitenpoort aan.

De NanoC6 is door M5Stack gespecificeerd voor 0 tot 40 graden Celsius. Meet of
schat de temperatuur op de montageplek; kies bij kans op meer dan 40 graden een
koelere plaats of andere hardware.

## 4. Beoogde bedrading

| Bron | Via | NanoC6 Grove | Functie |
| --- | --- | --- | --- |
| Solesta pin 1 | zwarte jumper, breadboardrij 1 | zwart, GND | gemeenschappelijke massa |
| Solesta pin 5 | signaaljumper en 2,7 kOhm serie, breadboardrij 12 naar 10 | wit, GPIO1 | uitsluitend UART RX |
| externe 5 V USB-voeding | USB-C-paneelmodule en interne USB-C-kabel | NanoC6 USB-C | voeding in normaal bedrijf |
| geen externe verbinding | eigen lege breadboardrij 3 | rood, 5 V | isoleren; kan 5 V voeren |
| geen externe verbinding | eigen lege breadboardrij 5 | geel, GPIO2 | isoleren en reserveren |

Controleer de connectororientatie aan de hand van de printmarkering en meet de
continuiteit naar GND nogmaals voordat er spanning wordt aangelegd. Vertrouw
niet alleen op draadkleur.

## 5. Firmwarestrategie in drie stappen

### Stap A - kale NanoC6 valideren

Maak eerst firmware zonder seriele Solesta-parser. Gebruik de stabiele ESPHome-
versie die op de uitvoeringsdatum beschikbaar en met Home Assistant compatibel
is; noteer en borg die versie bij het testresultaat.

De basisconfiguratie bevat:

- `esp32.variant: esp32c6` en `flash_size: 4MB`;
- het verplichte ESP-IDF-framework voor ESP32-C6;
- de USB Serial/JTAG-logger;
- 2,4 GHz Wi-Fi via `secrets.yaml`;
- de native ESPHome API met een unieke encryptiesleutel;
- versleutelde native ESPHome-OTA met dezelfde API-sleutel;
- geen webserver en geen open fallback-accesspoint.

Conceptuele basis, nog te valideren met de ESPHome-versie van de
uitvoeringsdatum:

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

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password

api:
  encryption:
    key: !secret solesta_nanoc6_demo_api_key

ota:
  - platform: esphome
    encryption:
```

Acceptatie van stap A:

- configuratie valideert en compileert zonder waarschuwingen die de gekozen
  chip, flash of USB-console betreffen;
- eerste USB-flash werkt;
- het apparaat start drie keer achter elkaar normaal op;
- Wi-Fi, versleutelde API en Home Assistant-discovery werken;
- een OTA-update op de werkbank slaagt;
- herstel via USB/downloadmodus is aantoonbaar mogelijk.

Stap A is op 18 oktober 2026 uitgevoerd en aan alle bovenstaande criteria
voldaan. Versies, firmware-hash, testbewijs en de gecontroleerde OTA-herstart
staan in
[`../results/esphome-m5nanoc6-step-a-2026-10-18.md`](../results/esphome-m5nanoc6-step-a-2026-10-18.md).

### Stap B - ruwe seriele regels vastleggen

Voeg daarna alleen de RX-bus toe. Gebruik eerst de ESPHome UART-debugger om
regels op newline-grenzen te verzamelen. Omdat nog geen UART-devicecomponent
de bytes leest, moet de debug-dummyreceiver actief zijn.

```yaml
uart:
  id: solesta_uart
  rx_pin: GPIO1
  baud_rate: 57600
  data_bits: 8
  parity: NONE
  stop_bits: 1
  rx_buffer_size: 1024
  debug:
    direction: RX
    dummy_receiver: true
    after:
      delimiter: "\n"
    sequence:
      - lambda: UARTDebug::log_string(direction, bytes, debug_prefix);
```

Voer deze proef uit met de externe USB-lader via de paneelpoort en bekijk de
ESPHome-logs over Wi-Fi. De MacBook blijft dan losgekoppeld. Leg minimaal vast:

- bevestiging dat de op 8 oktober waargenomen `CRLF` ook via de NanoC6 gelijk
  blijft;
- herhalingsfrequentie van de statusregel;
- volgorde en timing van statusregels en Z-regels;
- gedrag bij Solesta-opstart, ESP-opstart en tijdelijk wegvallen van data;
- voorbeelden tijdens stilstand, zoninstraling, flow en pompbedrijf;
- afwijkende, incomplete of onbekende regels.

De eerste ingebouwde live proef op 18 oktober 2026 bevestigde over 16 frames
een schoon `CRLF`-signaal, de verwachte statusgrammatica en een gemiddelde
periode van circa 3,10 seconden. In het korte venster met stabiele
controllerstand kwam geen Z-regel voor. Resultaat en resterende meetpunten
staan in
[`../results/esphome-m5nanoc6-step-b-initial-2026-10-18.md`](../results/esphome-m5nanoc6-step-b-initial-2026-10-18.md).

Ruwe logging is alleen voor deze onderzoeksfase. Zij wordt later uitgezet of
sterk beperkt om logspam en onnodige blootstelling van bronwaarden te
voorkomen.

### Stap C - acht Solesta-sensorentiteiten publiceren

Voeg na bevestiging van stap B een kleine, strikt validerende parser toe. De
parser accepteert uitsluitend regels met deze vorm:

```text
T|t1|t2|t3|t4_F|flow_PWM|pump
```

Daarnaast accepteert hij controllerstatusregels met exact twee
brononderdelen:

```text
Z|code|tekst
```

Publiceer voorlopig deze acht technische, niet-semantische
Solesta-sensorentiteiten:

| Stabiele sleutel | ESPHome-type | Bronpositie | Voorlopige verwerking |
| --- | --- | --- | --- |
| `temperature_1_raw` | numerieke template-`sensor` | `T[1]` | exact bronveld `47`; geen impliciete schaalconversie |
| `temperature_2_raw` | numerieke template-`sensor` | `T[2]` | exact bronveld `34`; geen impliciete schaalconversie |
| `temperature_3_raw` | numerieke template-`sensor` | `T[3]` | exact bronveld `34`; geen impliciete schaalconversie |
| `temperature_4_raw` | numerieke template-`sensor` | `T[4]` | exact bronveld `309`; voorlopig Temp04, niet delen door tien |
| `flow_raw` | numerieke template-`sensor` | `F[1]` | exact bronveld `0.000000`; eenheid nog niet bevestigd |
| `pump_raw` | numerieke template-`sensor` | `PWM[1]` | exacte fractie, waaronder `0.000000`, `0.757539` en `1.000000`; geen omzetting in de firmware |
| `controller_state_code` | numerieke template-`sensor` | `Z[1]` | geheel getal, ook bij een toekomstige onbekende code |
| `controller_state_text` | template-`text_sensor` | `Z[2]` | niet-lege afdrukbare ASCII-tekst, met alleen omringende formatteringsspaties verwijderd |

Noem temperatuurvelden nog niet `collector`, `vat_boven`, `vat_onder` of
vergelijkbaar. Zulke functionele namen worden pas gekozen nadat vergelijking
met display en installatie de betekenis per positie heeft bewezen. Temp04
blijft in deze fase nadrukkelijk een onverklaarde ruwe waarde. Behoud in de
onderzoeksfirmware tevens de laatste geldige ruwe statusregel en, waar nuttig
voor analyse, de zes oorspronkelijke teksttokens.

Het onderscheid tussen de eerste zes en de laatste twee is uitsluitend nodig
voor de parser- en updateafhandeling: de zes meetwaarden worden gezamenlijk uit
een volledig statusframe gepubliceerd, terwijl beide controllerstates uit een
afzonderlijke, volledig gevalideerde Z-regel komen.

Er komt geen `controller_state_sequence`. Code en tekst worden vanuit dezelfde
volledig gevalideerde Z-regel direct na elkaar gepubliceerd. Omdat ESPHome twee
afzonderlijke API-states verstuurt, wordt geen onjuiste atomaire garantie aan
Home Assistant beloofd.

Hoewel alle acht in Home Assistant als sensorentiteit zichtbaar worden, vereist
ESPHome voor de tekstuele state een afzonderlijke `text_sensor`-declaratie.
Conceptuele ESPHome-declaratie voor de twee controllerstate-entiteiten:

```yaml
sensor:
  - platform: template
    id: controller_state_code
    name: "Controller state code"
    accuracy_decimals: 0
    entity_category: diagnostic
    update_interval: never

text_sensor:
  - platform: template
    id: controller_state_text
    name: "Controller state"
    entity_category: diagnostic
    update_interval: never
```

De productieparser roept na een geldige Z-regel achtereenvolgens
`id(controller_state_code).publish_state(code)` en
`id(controller_state_text).publish_state(text)` aan. Beide declaraties hebben
een `name` en zijn niet `internal`, zodat de native API ze aan Home Assistant
aanbiedt.

Parserregels:

- verwijder uitsluitend afsluitende `CR`/`LF` en geen inhoudelijke tekens;
- begrens de regelbuffer; gooi na een te lange of niet-ASCII regel alle bytes
  weg tot en met de volgende `LF` en begin pas daarna opnieuw;
- eis exact drie groepen met de labels `T`, `F` en `PWM`;
- eis exact vier T-waarden, een F-waarde en een PWM-waarde;
- accepteer alleen volledig parseerbare, eindige getallen;
- publiceer de zes waarden als een geheel, pas nadat de hele regel geldig is;
- publiceer daarna een oplopende `frame_sequence`, zodat afnemers een compleet
  statusframe ondubbelzinnig kunnen herkennen;
- laat bij een ongeldige regel de laatste geldige waarden staan;
- houd tellers bij voor geldige en afgekeurde frames;
- leg reden en een begrensde weergave van een foutieve kandidaat-status- of
  Z-regel alleen op debugniveau vast;
- voeg een ouderdoms- of beschikbaarheidsindicatie toe zodat een stilgevallen
  UART niet als actuele meting wordt gepresenteerd;
- baseer `data_valid` uitsluitend op geldige statusframes en ouderdom; MQTT-,
  HTTP-, `updated!`- en `Failed!`-regels veranderen de beschikbaarheid niet;
- negeer alle regels die noch een statusregel noch een Z-regel zijn en bewaar
  daarvan geen tekst in Home Assistant.

Gebruik voor de zes waarden geen `force_update`; identieke frames hoeven geen
extra Home Assistant-state-event te veroorzaken. Stel voor `pump_raw` in de
onderzoeksfirmware expliciet `accuracy_decimals: 6` in, zodat de waargenomen
fractionele waarden niet vóór gebruik of opslag worden afgerond. De uiteindelijke
Solesta-provider kan, na definitieve bevestiging, de ruwe fractie met 100
vermenigvuldigen voor het bestaande pomppercentage. De firmware blijft de
bronwaarde publiceren.

Er vindt in deze fase geen schaalconversie plaats. Een latere schaalfactor moet
per positie door herhaalde, onafhankelijke waarnemingen worden bewezen. Gebruik
geen regel als "drie cijfers betekent delen door tien".

Maak in tests onderscheid tussen bronrepresentatie en numerieke waarde. De
bronrepresentatie bewaart bijvoorbeeld exact `0.000000`. Na omzetting naar een
getal zijn `0`, `0.0` en `0.000000` numeriek gelijk en zijn de afsluitende
nullen niet meer aanwezig. Forceer daarom niet automatisch zes decimalen voor
alle velden. `pump_raw` is tijdens het onderzoek de bewuste uitzondering om de
waargenomen fractionele bronwaarden niet kwijt te raken; dat is geen claim dat
de fysieke PWM zes decimalen nauwkeurig is. Kies de uiteindelijke
weergaveprecisie per veld pas nadat de werkelijke resolutie bekend is.

Stap C is op 18 oktober 2026 via OTA geplaatst. De NanoC6 publiceerde direct
geldige statusframes en de acht inhoudelijke entiteiten zijn in Home Assistant
geregistreerd. Implementatie, testbewijs, herstelpad en de nog openstaande
duur- en overgangsmetingen staan in
[`../results/esphome-m5nanoc6-step-c-2026-10-18.md`](../results/esphome-m5nanoc6-step-c-2026-10-18.md).

## 6. Eerste flashprocedure

1. Werk lokaal op de Mac en schrijf niets naar `/Volumes/config`. Bewaar de
   uiteindelijke YAML en parser in een aparte `esphome/`-map van dit project;
   `secrets.yaml` blijft genegeerd en wordt nooit gecommit.
2. Installeer of open een lokale, stabiele ESPHome Device Builder/omgeving en
   noteer de gebruikte ESPHome-versie.
3. Valideer en compileer de kale configuratie uit stap A.
4. Test eerst de complete paneelmodule en interne USB-C-kabel met alleen de
   NanoC6. De 6-polige Solesta-plug blijft los. Controleer zowel voeding als
   USB-data via de buitenpoort en, indien omkeerbaar, beide orientaties van de
   buitenste USB-C-stekker.
5. Trek een eventueel aangesloten USB-lader los. Verbind daarna uitsluitend de
   MacBook via een bekende USB-C-datakabel met de paneelpoort.
6. Als de NanoC6 niet automatisch in downloadmodus verschijnt: houd de knop
   aan de voorzijde ingedrukt, sluit USB-C aan en laat de knop na inschakelen
   los. Dit is de door M5Stack beschreven downloadprocedure.
7. Flash de firmware via de buitenpoort en bewaar buildlog,
   configuratieversie en hash van de gebruikte bron.
8. Controleer bootlog, Wi-Fi en native API. Voeg het apparaat via de normale
   ESPHome-discovery aan Home Assistant toe; wijzig `.storage` niet handmatig.
9. Test eenmaal OTA terwijl het board nog op de werkbank en fysiek bereikbaar
   is.
10. Test vervolgens herstel via USB door de paneelpoort voordat het board
    wordt ingebouwd.
11. Trek de MacBook los, sluit de externe USB-lader aan en controleer dat de
    NanoC6 normaal start. Sluit nog steeds geen Solesta-header aan.
12. Ga pas na acceptatie van stap A en controle van de 2,7 kOhm-serieweerstand
    door naar de aansluiting op Solesta pin 1 en 5 en naar stap B.

## 7. Testset voor parser en gedrag

De parsergrammatica en streamframing kunnen al zonder ESP32 worden getest. Een
geschoonde uitsnede van de CoolTerm-waarnemingen is daarom als fixture opgenomen
in `tests/fixtures/solesta_coolterm_excerpt.txt`. De ruwe capture wordt niet als
fixture gecommit, omdat daarin netwerknaam, lokaal IP-adres en MQTT-client-ID
voorkomen. De host-side referentie-implementatie in
`tools/solesta_stream_parser.py` speelt de geschoonde bytes in wisselende
brokgroottes af en bewaart zowel de zes oorspronkelijke tokens als hun numerieke
omzetting. De hardwareproef blijft nodig om timing en gedrag op de NanoC6 zelf
vast te stellen.

Minimaal te automatiseren testgevallen:

| Test | Verwacht resultaat |
| --- | --- |
| `T|47|34|34|309_F|0.000000_PWM|0.000000` | exacte tokens: `T=["47","34","34","309"]`, `F=["0.000000"]`, `PWM=["0.000000"]` |
| numerieke omzetting van dezelfde regel | `47.0`, `34.0`, `34.0`, `309.0`, `0.0`, `0.0`; geen schaalconversie |
| `T|37|34|34|309_F|0.000000_PWM|0.757539` | PWM-token en numerieke waarde blijven exact `0.757539`; niet reduceren tot binair |
| dezelfde regel met `LF` | geaccepteerd |
| dezelfde regel met `CRLF` | geaccepteerd |
| `Z|3|Run State` | `controller_state_code=3` en `controller_state_text="Run State"` |
| onbekende geldige Z-code en tekst | beide brononderdelen publiceren; niet op een vaste enumeratie afwijzen |
| MQTT-, HTTP-, `updated!`- en `Failed!`-regels | volledig negeren; geen entiteit, sensorupdate of wijziging van `data_valid` |
| lange binaire opstartregel gevolgd door een statusregel | opstartregel tot `LF` weggooien; daaropvolgende volledige statusregel accepteren |
| ontbrekende T-waarde | hele regel afgekeurd |
| extra groep of veld | hele regel afgekeurd |
| verkeerd groepslabel of verkeerde volgorde | hele regel afgekeurd |
| niet-numeriek, `NaN` of oneindig | hele regel afgekeurd |
| afgebroken regel door reboot | afgekeurd; volgende volledige regel herstelt |
| syntactisch geldige grote temperatuursprong | accepteren en ongefilterd publiceren; geen onbewezen plausibiliteitsfilter |
| data valt weg | beschikbaarheid/ouderdom wordt zichtbaar |

Hardwareacceptatie:

- de Solesta blijft normaal functioneren met de passieve luisterverbinding;
- geen TX- of andere headerpin is aangesloten;
- header pin 5 meet via ongeveer 2,7 kOhm uitsluitend naar GPIO1/RX en header
  pin 1 uitsluitend naar GND;
- Grove rood en geel staan elk op een eigen verder lege breadboardrij;
- de NanoC6 reboot niet door Wi-Fi-stroompieken;
- na spanningsuitval hervat de NanoC6 zelfstandig ontvangst en publicatie;
- gedurende minimaal 24 uur ontstaan geen parserfouten, bufferoverschrijdingen
  of onverwachte reboots die niet uit de brondata verklaarbaar zijn;
- Home Assistant toont acht stabiele inhoudelijke Solesta-sensorentiteiten en
  de diagnostische beschikbaarheid;
- gemeten waarden zijn op relevante momenten met het Solesta-display of een
  andere betrouwbare waarneming vergeleken.

## 8. Beslismoment na de hardwareproef

Het flash-, plaatsings- en hardwareacceptatieproject is afgerond. De
elektrische aansluiting, het seriele recordcontract, de object-ID's, native
API-ontsluiting, framebarriere en beschikbaarheidsbewaking zijn bewezen.

De meerdaagse praktijkmeting heeft daarnaast bevestigd:

1. ruim meer dan 24 uur zonder onverwachte reboot, parserafwijzing of
   bufferprobleem;
2. natuurlijke Z-overgangen met synchroon gevulde code en tekst;
3. rechtstreekse mapping van `T1`, `T2` en `T3` naar collector, tank boven en
   tank onder in graden Celsius;
4. pompbedrijf met zowel `1.000000` als fractionele waarden rond `0.74`, met
   providerconversie naar procent via maal 100;
5. een ruime beschikbaarheidsmarge: statusframes ongeveer iedere drie
   seconden tegenover een grens van 15 seconden.

De proef heeft ook begrensd vastgesteld dat `temperature_4_raw` exact `309`
en `flow_raw` exact `0` blijven, ook tijdens pompbedrijf. Hun betekenis en
eenheid zijn dus niet bevestigd. Het bestaande, standaard uitgeschakelde en
verborgen Solesta-contract voor T4 blijft ongewijzigd. `flow_raw` en
`frame_sequence` worden geen Solesta-entiteiten; `frame_sequence` mag hooguit
privaat als technische transportsynchronisatie dienen. Controllercode en
-tekst blijven eveneens buiten de eerste Solesta-entiteitsset, in afwachting
van een besluit of zij in een bestaande Solesta-entiteit thuishoren. Ook de
overige hoogfrequente diagnostiek wordt niet als reguliere Solesta-entiteit
opgenomen.

Het volledige meetbewijs en de vergelijking met de lopende Web API-integratie
staan in
[`../results/esphome-m5nanoc6-empirical-acceptance-2026-10-21.md`](../results/esphome-m5nanoc6-empirical-acceptance-2026-10-21.md).

De bestaande Web API-provider blijft ongewijzigd totdat de nieuwe
providerimplementatie, regressietests en lokale acceptatieroute afzonderlijk
zijn afgerond.

## 9. Belangrijkste risico's en maatregelen

| Risico | Maatregel |
| --- | --- |
| afwijkend spanningsniveau op Solesta TX beschadigt de ESP32 | eerder vastgestelde circa 3,3 V voor ingebruikname bevestigen; bij meer dan 3,6 V stoppen en hardwareontwerp herzien |
| onbedoeld zenden naar de Solesta | geen draad en geen `tx_pin` configureren |
| firmware configureert RX onverwacht als uitgang | 2,7 kOhm serieweerstand begrenst foutstroom; firmwaretest met header los |
| twee USB-bronnen voeden elkaar terug | lader eerst losnemen en pas daarna de MacBook aansluiten |
| Grove rood veroorzaakt kortsluiting | rode draad alleen op een eigen lege breadboardrij; rij markeren en controleren |
| Wi-Fi-piek veroorzaakt brownout | deugdelijke 5 V USB-voeding met voldoende stroommarge, testen onder belasting |
| verkeerde betekenis aan velden gegeven | technische sleutels en ruwe bron bewaren tot praktijkvalidatie |
| een beschadigde regel geeft gemengde sensorstanden | volledige regel valideren en atomair publiceren |
| stilgevallen UART blijft schijnbaar actueel | ouderdom/beschikbaarheid publiceren |
| onderzoekslogs blijven permanent aan | ruwe logging na analyse verwijderen of begrenzen |
| montageplek overschrijdt 40 graden Celsius | temperatuur beoordelen en hardware zo nodig verplaatsen |
| secrets belanden in Git | alleen `!secret`; `secrets.yaml` blijft genegeerd |

## 10. Officiele technische bronnen

- [M5Stack NanoC6-productpagina, pinmap en downloadmodus](https://docs.m5stack.com/en/core/NanoC6)
- [M5Stack NanoC6-schema](https://m5stack-doc.oss-cn-shenzhen.aliyuncs.com/505/Sch_M5NanoC6_v0.0.1.pdf)
- [ESPHome ESP32-platform en ESP32-C6/ESP-IDF](https://esphome.io/components/esp32/)
- [ESPHome UART-bus en UART-debugger](https://esphome.io/components/uart/)
- [ESPHome eerste installatie](https://esphome.io/install/getting-started/)
- [ESPHome beveiligingsadviezen](https://esphome.io/guides/security_best_practices/)
- [Espressif ESP32-C6-datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-c6_datasheet_en.pdf)

Projectspecifieke mechanische bron: montage-instructie externe USB-voeding,
versie 2.0 van 1 oktober 2026. Deze beschrijft de 6-polige headerplug, het
2,7 kOhm-seriepad, de geisoleerde Grove-draden, de USB-C-paneelmodule,
trekontlasting, montage, testvolgorde en veilige terugbouw.
