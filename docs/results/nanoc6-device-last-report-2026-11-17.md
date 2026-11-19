# NanoC6-apparaatrapporttijd — firmware 0.1.2 en Native-mapping

Datum: 17 november 2026, Europe/Amsterdam.

Status: uitgevoerd. Firmware 0.1.2 is draadloos geïnstalleerd; uitsluitend de
Native-`last_report`-expressie is aangepast en gecontroleerd. EMQX blijft
ongewijzigd, zoals opgedragen.

## Uitvoering van het besluit

[D-ESP-020](../decisions/0020-firmware-device-last-report.md) vervangt de
eerdere S100-02-oplossing met een verplichte kitmapping van `data_valid`.
De integratie krijgt geen nieuw verplicht veld, transportinterpretatie of
heuristiek voor temperatuurmutaties. Providercontract, factory reporting,
rapportagegrenzen en `solar_thermal_alerts()` zijn ongewijzigd.

Firmware 0.1.2 biedt tekstveld `last_report`: ISO 8601 UTC van het laatste
complete geldige UART-statusframe, met secondenprecisie. Een volgend frame
met identieke meetwaarden is eveneens een nieuw rapport. Ongeldige invoer,
controllerregels, diagnostiek en reconnects verversen dit veld niet.
Zonder bekende klok wordt geen verzonnen tijd gepubliceerd. Een vroeg
ontvangen frame kan na kloksynchronisatie worden gedateerd met de bewaarde
64-bit monotone ontvangsttijd. Een eenmaal gepubliceerde rapporttijd blijft
bij UART-stilte ook na een klokcorrectie staan.

De klok gebruikt de geconfigureerde
[SNTP-bron](https://esphome.io/components/time/sntp/) of
[Home Assistant-tijdbron](https://esphome.io/components/time/homeassistant/).
API- en OTA-encryptie, identiteit, ruwe meetwaarden en de uitgeschakelde
API-herstarttimer blijven behouden.

## Verificatie vóór en tijdens plaatsing

| Controle | Resultaat |
| --- | --- |
| Generatorcheck | Beide runtimecatalogi reproduceerbaar |
| Labgeneratorcheck | Deterministisch, ongewijzigde componentbuild `1d51d2a91264` |
| Ruff | Geslaagd |
| Python-suite | **311 tests geslaagd** |
| HA 2026.9.0-contractsuite | **43 tests geslaagd** |
| HA 2026.10.4-contractsuite | **43 tests geslaagd** |
| Kaart | **38 callbacks met assertions geslaagd** via de tijdelijke Node REPL-harness; geen native `node --test`-claim |
| Firmwareprofielen | Native en MQTT valideren met ESPHome 2026.9.1 |
| Werkelijke firmwarelambdas | Hostcompilatie en uitvoering met AddressSanitizer en UndefinedBehaviorSanitizer geslaagd |
| Definitieve apparaatbuild | ESPHome **2026.10.2**, ESP-IDF **5.5.6**, succesvolle versleutelde OTA |

De lambda-test voert de werkelijke parser-, rapporttijd-, ouderdoms- en
validiteitscode uit de publieke YAML uit met gesimuleerde IO en klok. Zij
toetst onder andere onbekende tijd, vertraagde sync, gelijke opeenvolgende
frames, corrupte invoer, UART-stilte, klokcorrectie, herstel en lange uptime.
De HA-tests gebruiken de echte observationcache, compiler, evaluator en
coordinator. De generieke route slaagt met uitsluitend drie temperatuurvelden
en een pompveld, zonder extra diagnostiek of apparaatrapporttijd.

De eerste doelbuild wees een const-kwalificatie af bij `ESPTime.strftime`.
Dat gebeurde vóór flashen. De fout is gereproduceerd met een aangescherpte
interface-double en gecorrigeerd; alle controles zijn daarna herhaald.
Een lokale generatiepoging werd beperkt door pakketregistrytoegang. De
definitieve volledige build en installatie zijn via Device Builder uitgevoerd.

De draaiende Nano-log bevestigde projectversie **0.1.2**, nieuwe UART-frames
en oplopende UTC-rapporttijden, bijvoorbeeld `2026-11-17T21:32:42Z` en
`2026-11-17T21:32:45Z`. Om **22:33:00 CET** bevestigde de firmware een
geslaagde boot en reset van de bootloopcounter. Device Builder toonde daarna
een online apparaat en gesynchroniseerde versie en configuratiehash.

## Native-aanpassing en behoud

Na flashen is via de normale HA-configuratieflow gewijzigd:

| Systeem | Expressie | Voor | Na |
| --- | --- | --- | --- |
| ESPHome Native in Solesta Lab | `last_report` | `last_report()` | `last_report` |

De gebruiker heeft deze ene veldwijziging opgeslagen nadat de automatische
formulierbediening bij een onopgeslagen poging een verkeerd veld raakte.
Een read-only controle bevestigde vóór die handmatige stap dat de opgeslagen
systeemidentiteit nog gelijk was. Na opslag zijn alle bronexpressies vergeleken:
alleen `last_report` verschilt. De UID's, systeem-ID, bron-ID, overige expressies
en ingeschakelde toestand zijn behouden. De flow bevestigde dat het systeem
was bijgewerkt; de Native-kaart toont actuele gegevens en online status.

Volledige opgeslagen entries van EMQX, Mosquitto, Web API en productie zijn
met hun nulmeting vergeleken en gelijk gebleven. Firmware-YAML is bytegelijk
aan de geteste bron; ESPHome-secrets zijn ongewijzigd. De integratie blijft
kandidaat 1.0.0 en de geïnstalleerde Lab-code blijft 0.2.9. Er was geen
HA-herstart of nieuwe Lab-codeplaatsing nodig.

Herstelgegevens staan in de genegeerde werkmap
`work/firmware-last-report-20261117/`: oorspronkelijke YAML 0.1.1,
credentialvrije subentrysnapshot, hashes en controle-uitvoer. Teruggaan naar
firmware 0.1.1 vereist ook herstel van de Native-expressie naar `last_report()`
via de configuratieflow. `.storage` is uitsluitend read-only gecontroleerd;
de actieve Recorderdatabase is niet benaderd.

## Fysieke uitval en herstel bevestigd

De aanvullende [UART-uitvalproef](nanoc6-uart-outage-2026-11-17.md) is uitgevoerd
met de Solesta uit en de Nano aan. De apparaatrapporttijd bleef op 22:47:15
staan. Native werd om 22:57:23 offline: **608 seconden** later, binnen de grens
van 600 seconden plus de volgende systeemupdate. Web API werd eveneens offline;
EMQX bleef online met haar toen ongewijzigde transportmapping.

De gebruiker heeft daarna ook opdracht gegeven EMQX naar het apparaatveld te
mappen en de Solesta uit te laten. Die aanvullende opdracht staat open door
een [onderzochte beperking van de configuratievalidatie](mqtt-reconfiguration-during-source-silence-2026-11-17.md).
De afzonderlijke [MQTT-only-duurproef voor S100-01](nanoc6-mqtt-only-s100-01-acceptance-2026-11-18.md)
is op 18 november geaccepteerd.

Op de daaropvolgende gebruikersopdracht is de rapporttijdmapping van
Mosquitto via de normale flow gewijzigd. De [controle in de werkelijke
MQTT-entiteiten](mosquitto-device-last-report-2026-11-17.md) bevestigde offline
met behoud van het rapporttijdstip 22:47:15, terwijl de Solesta uit bleef.

Na inschakelen van de Solesta zijn nieuwe geldige frames, oplopende
apparaatrapporttijd en [automatisch herstel van Native en Mosquitto](nanoc6-uart-recovery-2026-11-17.md)
bevestigd. De Web API-kaart herstelde eveneens; alle vergelijkingskaarten tonen
weer actuele waarden en normale status.
