# S100-03 t/m S100-07 — netwerkacceptatie

Datum: 18 november 2026, Europe/Amsterdam.

Status: **alle vijf punten slagen in de uitgevoerde controles**. De
geïnstalleerde Lab-code is getest met echte Native- en MQTT-verbindingen en
geïsoleerde HA-configuratieopslag. Bestaande HA-configuraties en geïnstalleerde
bestanden zijn volledig ongewijzigd gebleven.

## Opstelling en testgrens

Live draait HA **2026.11.1**, Solesta Lab **0.2.9**, build `c40b390f17e2`, met
Nano-firmware **0.1.2**. Een exacte read-only kopie van het geïnstalleerde
Lab-pakket is gebruikt. De zeven betrokken bestanden — `compile.py`,
`configuration.py`, `config_flow.py`, `mqtt.py`, `provider.py`, `source_fields.py`
en `evaluator.py` — zijn ook bytegelijk aan de canonieke kandidaatbron.

De echte HA-flowhandlers, providers, compiler, observationcache, runtimeopbouw
en evaluator zijn uitgevoerd. Alleen de opslag van de testentries is
geïsoleerd in het onderzoeksproces. Native maakte echte versleutelde
verbindingen met de bestaande Nano, met identiteitscontrole en zonder tijd of
apparaatopdrachten te sturen. MQTT gebruikte echte Mosquitto-/EMQX-verbindingen
en unieke testroots, uitsluitend met **`retain=False`**.

Er is geen productie-entiteit aangemaakt, geen live configuratie
geherconfigureerd en geen volledige HA-herstart uitgevoerd. Een nieuwe
providerlifecycle betekent hier een nieuwe echte netwerkverbinding en
runtimeopbouw. Bestaande credentials zijn alleen voor hun bestaande broker
gebruikt; wisselgevallen op de anonieme broker gebruiken waar nodig fictieve
secrets. Echte accounts, wachtwoorden en brokerinstellingen zijn niet gewijzigd.

## Resultaten

| Punt | Controles | Uitkomst |
| --- | --- | --- |
| **S100-03** | Native-kopieën met gewone/absolute namen bij eerste opbouw en nieuwe lifecycle. MQTT-kopieën met korte/volledige/absolute namen op beide brokers bij eerste opbouw, nieuwe lifecycle en herkoppeling naar een tweede echte testroot. | **22 netwerkcontroles geslaagd**. Validatie en runtime gebruiken dezelfde canonieke doelbinding; alias, UID en expressies blijven behouden. |
| **S100-04** | Echte geneste MQTT-eigenvelden tegenover apostrofvorm; ambiguïteit, ook nullable; ontbrekende required/nullable invoer; hoofdlettergevoelige `None`/`none` en entiteitsafhankelijkheden. | **Beide brokers geslaagd**. Unieke eigenvelden leveren de juiste waarde, ambiguïteit wordt afgewezen en expressietekst blijft gelijk. |
| **S100-05** | Vier niet-retained velden met 300 ms tussenruimte; ontbrekende velden onder doorgaande andere berichten; late ambiguïteit; vaste binding na een nieuw gelijknamig topic. | **Zes controles geslaagd**. Geldige streams valideren op EMQX in **1,232 s**, op Mosquitto in **1,239 s**. Ontbrekende velden worden na **20,030 / 20,032 s** afgewezen; andere berichten verlengen de deadline niet. |
| **S100-06** | Exacte roots met randspaties, 300/305 tekens en Unicode met meer dan 256 UTF-8-bytes. Flow-aanmaak, activering/herconfiguratie, twee providerlifecycles en providerwisselmetadata. | **Zes rootgevallen plus controle op ongeldige roots geslaagd**. Communicatiedoel blijft letterlijk behouden; lokale alias en identiteit blijven apart. |
| **S100-07** | Anoniem → authenticatie, authenticatie → anoniem, gelijkblijvende gebruiker met leeg wachtwoord, gebruikersnaamwissel zonder/met nieuw wachtwoord, wachtwoordvervanging, genormaliseerde gebruikersnaam, halve credentialset en echte brokerafwijzing. | **Negen gevallen geslaagd**. Credentialset wordt correct behouden, vervangen of verwijderd; afgewezen kandidaten veranderen geen opgeslagen configuratie of systeemstempels. |

In totaal zijn **46 geslaagde controle-uitkomsten** vastgelegd binnen zeven
gerichte netwerkscenariogroepen.

Anoniem ↔ geauthenticeerd en behoud van de echte credentialset zijn met de
echte Mosquitto-/EMQX-profielen getest. Mosquitto wees een bewust fout wachtwoord
af als `invalid_auth`; de geïsoleerde opslag bleef exact gelijk. Een andere
gebruikersnaam met leeg wachtwoord en een halve credentialset werden lokaal
afgewezen als `invalid_provider_config`.

Positieve vervangingsgevallen met fictieve gebruikersnamen/secrets op EMQX
toetsen de samenstelling en publicatie van de credentialset. EMQX staat anonieme
toegang toe; deze gevallen bewijzen geen aanmaak of rotatie van echte accounts.

De fysieke Nano biedt één communicatiebron. Native met meerdere subdevices en
herkoppeling naar een ander Native-subdevice is aanvullend gedekt door de
HA-contractsuite met afzonderlijke discoverycatalogi. Echte herkoppeling naar
een andere bron is tijdens deze acceptatie via MQTT uitgevoerd.

## Aanvullende regressies

| Controle | Resultaat |
| --- | --- |
| Canonieke generatorcheck, schone kandidaat | Beide catalogi reproduceerbaar |
| Labgeneratorcheck, schone kandidaat | Deterministisch, build-ID `1d51d2a91264` |
| Python-suite, schone kandidaat | **311 tests geslaagd** |
| HA 2026.9.0-contractsuite | **43 tests geslaagd** |
| HA 2026.11.1-contractsuite | **43 tests geslaagd** |
| Kaart | **38 tests geslaagd met de echte `node --test`-runner**, Node 24.22.1 |

De schone kandidaat bevatte 186 niet-genegeerde bronbestanden. De eerste
Python-run nam ten onrechte de volledige werkmap mee en markeerde lokale
werk-/privéartefacten als publicatiefouten. De suite is vanuit de schone
kandidaat herhaald. Privébestanden zijn niet verwijderd of gekopieerd.

De eerste netwerkharness had drie testopstellingsproblemen: een assertie vóór
ontvangst van het ambiguïteitstopic, een ongeldige lokale systeemslug en een
ontbrekende mappingadapter in de geïsoleerde entryfixture. Alleen de betrokken
proeven zijn na correctie gericht herhaald. Er is geen productcode gecorrigeerd.
Mislukte runs en geslaagde herhalingen zijn apart bewaard; de 46 uitkomsten
hierboven zijn de uiteindelijk geslaagde controles.

## Opruiming en eindtoestand

Alle tijdelijke providers, Native-clients en MQTT-publishers zijn gesloten.
Nieuwe subscripties op alle gebruikte testnamespaces, inclusief de varianten
met randspaties, vonden op beide brokers **geen retained testberichten en geen
nog actieve testpublisher**.

Alle oorspronkelijke Solesta-, Solesta Lab- en ESPHome-entries zijn volledig
gelijk aan hun nulmeting. Alle geïnstalleerde Lab-bestanden hebben dezelfde
hash. Om **09:53:29** toonden Web API, Native en EMQX op het normale dashboard
alle **Alles werkt normaal**. Geen bestaande koppeling hoefde te worden hersteld.

De Mac is tijdens het werk wakker gehouden. De tijdelijke wakkerhoudclient is
na de eindcontroles beëindigd en de eigen slaapblokkade is opgeheven.
Permanente energie-instellingen zijn niet gewijzigd.

Private plannen, snapshots, scripts en bewijslogs staan in
`work/s100-03-07-acceptance-20261118/`, waaronder `installed-file-hashes.json`,
`network-results*.json`, `acceptance-summary.json` en de suite-uitvoer.
Secrets zijn niet in de resultaten opgenomen. `.storage` is uitsluitend
gelezen; de actieve Recorderdatabase is niet benaderd. Er is niets gecommit,
gepusht of uitgebracht.
