# D-ESP-020 — Apparaatrapporttijd uit de NanoC6-firmware

Datum: 17 november 2026.

Status: uitgevoerd en op de NanoC6 geïnstalleerd; de Native-labmapping is
gevalideerd en opgeslagen. Vervangt de S100-02-validiteitsmapping uit
D-ESP-016. Fysieke UART-uitval en herstel zijn voor Native en MQTT/Mosquitto bevestigd.

## Ontwerp en risico's

De integratie legt Native- en MQTT-bronnen geen specifieke velden of semantiek
op. Temperatuur- en pompwaarden volstaan voor de praktische basisroute.
Met uitsluitend sensorwaarden kan de integratie niet betrouwbaar vaststellen
of de meetbron nog rapporteert: constante waarden kunnen zowel geldig als
stilgevallen zijn. Eventuele fysische aannames horen bij alerts en worden
niet toegevoegd in deze release.

De eerdere kitoplossing maakte `status_reporting` afhankelijk van
firmwarediagnostiek `data_valid`. De gebruiker heeft besloten deze oplossing
te vervangen door een door de firmware bepaalde apparaatrapporttijd.
De bestaande generieke functies `last_report()` en `last_update()` houden hun
transportbetekenis; een bronveld `last_report` is daarvan te onderscheiden.

## Besluit

- Firmware 0.1.2 publiceert het tekstveld `last_report` als ISO 8601 UTC met
  secondenprecisie. Het hoort bij het laatste complete, geldige UART-statusframe.
  Ook een identiek volgend frame is een nieuw rapport. Afgekeurde regels,
  controllertekst, diagnostiek, reconnects en kloksynchronisatie vormen geen
  nieuw apparaatrapport.
- Het tijdstempel wordt één keer per frame vastgelegd. Zonder bekende klok
  wordt geen epoch-1970-waarde of opstarttijd gepubliceerd. Na vertraagde
  kloksynchronisatie kan het laatste frame op basis van de bewaarde monotone
  ontvangsttijd worden gedateerd, met maximaal één seconde afrondingsverschil.
  Een eenmaal gepubliceerd tijdstip blijft bij UART-stilte ook na een
  kloksynchronisatie staan. De monotone ontvangsttijd gebruikt 64 bits.
- SNTP en de bestaande HA-klokroute kunnen de systeemklok synchroniseren.
  SNTP kan zelfstandig werken zonder Native-client. De standaardservers zijn
  configureerbaar in de firmware-YAML; voor volledig lokaal bedrijf kunnen
  lokale tijdservers of de HA-klok worden gebruikt. Zonder enige beschikbare
  tijdbron blijft de rapporttijd onbekend totdat de klok bekend is.
- `data_valid` blijft interne firmwarediagnostiek; de integratie krijgt geen
  aparte interpretatie of eis voor dit veld. `status_reporting`, Report delay
  en de lokale alertfunctie behouden hun fabrieksexpressies. UART-stilte laat
  de bronrapporttijd verouderen volgens de bestaande grenzen van 150/600 s.
- Na flashen wordt uitsluitend de `last_report`-bronexpressie van het
  ESPHome Native-labsysteem op `last_report` gezet. De compiler bindt deze
  eigennaam aan het bronveld. Alle overige expressies, inclusief die van EMQX
  en Mosquitto, blijven letterlijk behouden. Er is geen expressiemigratie.
- Het nieuwe veld is via Native beschikbaar en wordt via de bestaande
  MQTT-configuratie ook als tekstsensor gepubliceerd. Een MQTT-bron kan het
  expliciet mappen, maar de bestaande EMQX-mapping blijft op gebruikersopdracht
  ongewijzigd en behoudt dus haar huidige transportbetekenis.
- API- en OTA-encryptie, apparaatidentiteit, parsergrammatica en ruwe waarden
  blijven behouden. De S100-01-API-herstarttimer blijft uitgeschakeld.

## Verificatie

Toets de werkelijke firmwarelambdas met onbekende klok, vertraagde sync,
identieke frames, ongeldige regels, UART-stilte, klokcorrectie en herstel.
Toets bronveld `last_report` tegenover functie `last_report()` door de echte
compiler, observationcache, evaluator en coordinator. De basisroute zonder
extra diagnostiek blijft geldig. Voer de generator-, Python-, kaart- en
HA-contractchecks uit en bouw de exacte firmware vóór OTA-installatie.

Voor plaatsing komen herstelkopieën van firmware-YAML en Native-configuratie.
Vergelijk na afloop de andere systemen en productieconfiguratie met hun
nulmeting. Historische review- en installatieverslagen blijven historisch.

De [uitvalproef van 17 november](../results/nanoc6-uart-outage-2026-11-17.md)
bevestigt een stilstaande apparaatrapporttijd en Native offline na 608 seconden,
terwijl de Nano bereikbaar blijft. De gebruiker heeft tijdens die proef ook
opdracht gegeven EMQX naar hetzelfde apparaatveld te mappen. Deze aanvullende
configuratieopdracht staat nog open door de onderzochte
[validatiebeperking bij bronstilte](../results/mqtt-reconfiguration-during-source-silence-2026-11-17.md).
De oorspronkelijke keuze om EMQX bij de eerste plaatsing ongewijzigd te laten
is dus opgevolgd door deze nieuwe opdracht; er is nog niets aan EMQX opgeslagen.

Vervolgens heeft de gebruiker de Mosquitto-route zonder kaart gekozen voor
dezelfde uitvaltest. De rapportage-expressie is daar expliciet gewijzigd naar
`state__last_report__sensor`. De [live entiteitscontrole](../results/mosquitto-device-last-report-2026-11-17.md)
bevestigde direct offline met de oorspronkelijke apparaatrapporttijd. De
Native- en MQTT-uitvalwerking zijn daarmee geverifieerd. Na weer inschakelen
is ook het [automatische herstel](../results/nanoc6-uart-recovery-2026-11-17.md)
van deze routes bevestigd.

Primaire technische bronnen:
[ESPHome-klok en UTC](https://esphome.io/components/time/),
[SNTP](https://esphome.io/components/time/sntp/),
[HA-tijdbron](https://esphome.io/components/time/homeassistant/).
