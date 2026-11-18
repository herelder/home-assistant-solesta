# Onderzoek — MQTT-herconfiguratie tijdens bronstilte

Datum: 17 november 2026, Europe/Amsterdam.

Status: oorzaak gereproduceerd; voorstel voor correctie uitgewerkt.
Er is geen productcode, brokerinstelling of opgeslagen HA-configuratie gewijzigd.
De Solesta is op verzoek van de gebruiker uit gebleven; de Nano bleef aan.

## Bevinding

De systeemflow valideert een expressiewijziging altijd met een nieuwe,
tijdelijke provider. Zij gebruikt de waarden uit de actieve providercache niet.
Deze nieuwe MQTT-verbinding start leeg. Als een publisher tijdens de uitval
alleen diagnostiek publiceert en de broker geen retained meetwaarden
nastuurt, ontbreken de velden voor de compiler en evaluator.

Dat is hier daadwerkelijk gebeurd. De actieve EMQX-provider heeft de vereiste
velden al, maar de tijdelijke validatieprovider krijgt alleen data-ouderdom.
Het is daarom geen bewijs dat de nieuwe firmware geen MQTT-rapporttijd levert
of dat de bestaande systeemconfiguratie haar meetvelden mist.

## Live bewijs zonder wijzigingen

De waarnemingen zijn gedaan tijdens de
[fysieke uitvalproef](nanoc6-uart-outage-2026-11-17.md), met Nano-firmware 0.1.2
en Solesta Lab 0.2.9, build `c40b390f17e2`.

- De direct door de Nano gebruikte broker leverde retained
  `sensor/last_report/state` met `2026-11-17T21:47:15Z`, plus temperatuur- en
  pompvelden. Het canonieke MQTT-veld is `state__last_report__sensor`.
- Een nieuwe verbinding op EMQX ontving onder dezelfde bestaande systeemroot
  alleen `sensor/data_age/state`; de bewaarde meetwaarden werden niet
  nagespeeld. De oorzaak in de broker-/bridgeconfiguratie is niet vastgesteld.
- De diagnostiek van de **actieve** EMQX-hub bevat alle vijf vereiste velden:
  drie temperaturen, pomp en `state__last_report__sensor`. Providerfout en
  evaluatiefouten zijn leeg. De laatst gewijzigde gerefereerde waarde dateert
  van 22:47:10.667954; de generieke transportrapporttijd loopt door.
- De diagnostiek toont veldnamen en generieke observatietijden, geen ruwe
  veldwaarden. De exacte inhoud van het `last_report`-veld in de actieve
  EMQX-cache is hiermee niet afzonderlijk uitgelezen.

Dezelfde geïnstalleerde provider-, compiler- en evaluatorcode is vervolgens
alleen-lezen op beide brokers toegepast met de voorgestelde expressie.

| Broker | Uitkomst | Tijd |
| --- | --- | ---: |
| Mosquitto | Alle benodigde velden; geen evaluatiefouten; apparaatrapporttijd 22:47:15; `status_reporting = false` | 0,19 s |
| EMQX | Alleen data-ouderdom; ontbrekende velden bij rapporttijd, drie temperaturen en pomp | 20,04 s |

Mosquitto slaagt dus ook terwijl de Solesta uit is. EMQX loopt tegen de
bestaande discoverydeadline aan; langer wachten levert tijdens deze
bronstilte geen ontbrekende meetframes op.

## Codepad en lokale reproductie

In `config_flow.py`:

1. `async_step_reconfigure()` eist live validatie bij gewijzigde expressies,
   met `allow_offline_contract=False`.
2. `_async_live_validate_system()` maakt altijd een tijdelijke provider.
   Voor de gekozen MQTT-bron wordt bovendien de opgeslagen veldtabel verwijderd
   voordat actuele veldnamen worden ontdekt.
3. De nieuwe verbinding wacht maximaal twintig seconden op ontbrekende
   vereiste namen. Daarna weigert de compiler de niet aangeboden velden.
4. De tijdelijke provider wordt gesloten; het actieve systeem blijft intact.

Een lokale reproductie met de **geïnstalleerde** HA-flow, MQTT-provider,
compiler, observationcache en evaluator bevestigt dit los van de brokers.
Alleen netwerk-IO en de testdeadline zijn vervangen. Een reeds actieve cache
bevat vijf geldige fictieve velden met een apparaatrapporttijd van twintig
minuten geleden. De nieuwe validatieprovider ontvangt alleen data-ouderdom.

Assertions bevestigen dat de huidige flow toch een nieuwe provider maakt en
alle vijf bronafhankelijke expressies afwijst. Dezelfde expressies evalueren
op de aanwezige cache zonder fout tot `status_reporting = false`. De oude
apparaatrapporttijd en de actieve provider blijven behouden. Deze proef
implementeert of accepteert nog geen gewijzigde configuratieflow.

De live onderzochte bestanden `config_flow.py`, `configuration.py`, `mqtt.py`,
`provider.py` en `observation.py` zijn bytegelijk aan het eerder geplaatste
Lab-pakket. Dit is geen verschil tussen lokale bron en geïnstalleerde code.

## Ook de publicatie van een wijziging moet worden aangepast

Alleen validatie uit de actieve cache laten lezen is onvoldoende.
De systeemflow schrijft nu de gewijzigde subentry, waarna
`HubRuntime.schedule_reconcile()` een afwijkende systeemrevisie detecteert
en de volledige hub herlaadt. De nieuwe provider heeft daarna opnieuw een
lege observationcache. Ook na succesvolle validatie zou deze route dus weer
op nieuwe MQTT-berichten of retained replay moeten wachten.

De bestaande `async_write_source_expression()` voor configuratie-entiteiten
vervangt de systeemruntime al onder een lock en behoudt daarbij de provider.
Die route verbiedt bewust nieuwe vereiste providerkeys. De nieuwe
rapporttijdmapping voegt zo'n key toe; deze functie mag daarom niet als
omweg worden gebruikt om de ontbrekende configuratievalidatie te passeren.

## Voorgestelde correctie en risico's

Voor een expressiewijziging aan een actief systeem met dezelfde hub,
providerrevisie en communicatiebron:

1. Lees een consistente, defensieve bronveldtabel en snapshot van de huidige
   provider. Compileer en evalueer de kandidaat daartegen. Ontbrekende,
   dubbelzinnige of ongeldige waarden blijven fouten.
2. Behoud oorspronkelijke bronwaarden en observatie-/apparaattijden. Evalueren
   of opslaan vormt geen nieuw apparaatrapport. Een oud rapport mag een geldige
   configuratie met offline-uitkomst opleveren.
3. Publiceer de gevalideerde systeemconfiguratie atomisch in opslag en runtime,
   met behoud van de bestaande provider en cache. Vraag alleen een evaluatie
   van het gewijzigde systeem aan.
4. Controleer identiteit, providerrevisie, systeemrevisie en runtimegeneratie
   opnieuw onder de mutatielock. Gelijktijdige wijzigingen moeten worden
   samengevoegd of als conflict afgewezen.

Bij een nieuwe bron, gewijzigde verbinding/provider, ontbrekende runtime of
nooit ontvangen vereiste velden blijft afzonderlijke bronvalidatie nodig.
Gegevens van verschillende bronnen of oude providerrevisies mogen niet
worden samengevoegd. Het voorstel legt geen retain-, heartbeat- of
herpublicatie-eis aan MQTT- of Native-bronnen op.

Retained replay is een bruikbare bron van gegevens voor een nieuwe verbinding;
de integratie mag daar voor een bestaande actieve bron geen stilzwijgende
voorwaarde van maken. De MQTT 3.1.1-specificatie onderscheidt retained replay
bij inschrijven van live levering aan bestaande abonnees; de retain-vlag van
een live ontvangen bericht bewijst op zichzelf niet wat de publisher heeft
meegegeven. Zie [OASIS MQTT 3.1.1, §3.3.1.3](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html).

Voor implementatie zijn gerichte regressies nodig voor een stille bestaande
MQTT-bron zonder retained replay, een nieuw gecachet veld, direct offline
evalueren, ontbrekende/ongeldige velden, vaste binding en ambiguïteit,
provider-/bronwissels, gelijktijdige wijzigingen en behoud van Web API en
Native. Ook moet worden bewezen dat alleen het gewijzigde systeem ververst
en de provider niet wordt herladen of door validatie gesloten.

## Toestand na het onderzoek

De afgewezen, onopgeslagen formulierpoging is gesloten. EMQX gebruikt nog
`last_report()`. De opdracht om dit naar `state__last_report__sensor` te
wijzigen en het offline-effect te controleren staat open. Herstel na weer
inschakelen en de afzonderlijke MQTT-only-duurproef zijn eveneens nog open.
De Solesta bleef uit en de Mac bleef wakker.

Private bewijzen en alleen-lezen onderzoeksscripts staan onder
`work/uart-outage-20261117/`, waaronder `active-emqx-diagnostics.json`,
`installed-validation-comparison.json` en `validation-cache-reproduction.json`.
Er is niets naar een broker gepubliceerd, geen actieve Recorderdatabase
geopend en niets rechtstreeks in `.storage` gewijzigd.

## Vervolg: uitvaltest via Mosquitto geslaagd

De gebruiker heeft daarna de route zonder kaart gekozen om het firmwareveld
via MQTT in de echte entiteiten te toetsen. De Mosquitto-expressie is via de
normale configuratieflow naar `state__last_report__sensor` gewijzigd en het
systeem werd direct offline met behoud van de rapporttijd 22:47:15. Zie de
[uitgevoerde Mosquitto-proef](mosquitto-device-last-report-2026-11-17.md).
Daarvoor was geen codecorrectie nodig. De onderzochte EMQX-beperking is hiermee
niet gewijzigd; de uitvalwerking via MQTT is nu afzonderlijk live bewezen.
Na weer inschakelen van de Solesta is ook het
[herstel van Native en Mosquitto](nanoc6-uart-recovery-2026-11-17.md) bevestigd.
