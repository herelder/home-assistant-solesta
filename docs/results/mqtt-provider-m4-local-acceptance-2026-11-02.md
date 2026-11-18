# MQTT-provider M4 — lokale regressie- en contractacceptatie

> Publicatiekopie: installatie-, apparaat- en netwerkidentificatoren zijn
> consequent gepseudonimiseerd. Meetwaarden, tijden en uitkomsten zijn behouden.

Datum: 2 november 2026

## Uitkomst

M4 is lokaal afgerond. De drie providers voldoen aan hetzelfde
observatiecontract, ESPHome Native en MQTT doorlopen dezelfde
pushcachegevallen en de MQTT-configuratie-, transport-, reconnect-,
identiteits- en protocolwisselcontracten zijn afgedekt. De bestaande Web API-
en Native-routes blijven groen in beide vastgelegde Home Assistant-matrices.

De brokerproeven zijn, conform de opdracht, uitsluitend uitgevoerd tegen de
bestaande Home Assistant Mosquitto broker op `192.0.2.10`. Er is in M4
geen tweede broker en geen broker buiten Home Assistant geclaimd.

## Bevinding en correctie

De uitgebreide migratietest bracht één bestaand isolatielek aan het licht:
een syntactisch ongeldige opgeslagen source-expression kon de volledige
hubmigratie al tijdens het vervangen van oude alertdrempels afbreken. De
migratie bewaart zo'n expressie nu ongewijzigd, waarna de bestaande
per-systeemvalidatie en -isolatie haar afhandelen. Een ongeldig systeem kan
daardoor geldige buur-systemen niet meer tegenhouden.

De officiële Hassfest-controle vond daarnaast punthaken rond `root` in een
configuratietekst. Home Assistant beoordeelde die als HTML. De tekst gebruikt
nu `root-topic/#`, zonder de abonnementssemantiek te wijzigen.

## Contractdekking

De lokale tests bewijzen onder meer:

- de volledige canonieke reportreeks voor Web API, ESPHome Native en MQTT,
  inclusief eerste state, identieke report, ongebruikte en optionele key,
  mislukte reportpoging, retained replay en nieuwe providerinstantie;
- een eigen `last_update()` per systeem op basis van de volledige werkelijk
  gebruikte keyset, ook wanneer systemen dezelfde pushcache delen;
- waardetransparante vergelijking voor mappings, NaN, boolean tegenover getal,
  lijst tegenover tuple en bytes tegenover tekst;
- Web API-verwijdering en -terugkeer van een gebruikte key;
- MQTT hostname/IP, poort, QoS 0/1/2, keepalive, TLS-context,
  gebruikersnaam/wachtwoord, anoniem gebruik, authweigering, lege payload,
  exacte topicpaden, RETAIN/QoS-metadata, reconnect, retained replay,
  idempotent sluiten en isolatie tussen hubs;
- handmatig toevoegen en herconfigureren zonder discovery, inclusief live
  source-expressionvalidatie en optionele ontbrekende keys;
- behoud van hub-, systeem-, device- en entity-identiteit en bytegelijk behoud
  van source-expressions in alle zes providerwisselrichtingen, voor gewone en
  dubbele systemen.

## Mosquitto- en TLS-proef

Voor de TLS-proef is lokaal een tijdelijke RSA-test-CA en een tijdelijk
brokercertificaat gegenereerd. Het brokercertificaat bevat:

- DNS-SAN `homeassistant.local`;
- IP-SAN `192.0.2.10`;
- SHA-256-vingerafdruk
  `02:C9:91:93:4D:2F:02:56:A3:76:43:4C:02:D0:B9:67:6D:2D:02:C1:8D:76:22:E5:02:4B:A3:9E:AC:9E:FF:AC`.

Alleen de brokerketen en brokersleutel zijn voor de proef naar de HA
`/ssl`-share gekopieerd als `solesta-m4-fullchain.pem` en
`solesta-m4-privkey.pem`. De CA-private sleutel is lokaal in de genegeerde
werkmap gebleven. De opgeslagen Mosquitto-configuratie is na de proef
teruggezet op de oorspronkelijke bestandsnamen `fullchain.pem` en
`privkey.pem`; de twee testbestanden zijn niet verwijderd.

De Mosquitto-log en directe probes bevestigen:

- listeners op 1883, 1884, 8883 en 8884 tijdens de proef;
- herstel van de bestaande ESP-publisher, de HA MQTT-client, het ESPHome
  dashboard en de Solesta MQTT-provider na de brokerherstart;
- TLS 1.3 met de test-CA voor zowel DNS-naam als IP-adres;
- verwachte afwijzing zonder de test-CA en bij een verkeerde hostnaam;
- een echte `MqttProvider`-verbinding over 8883 bereikte na geslaagde
  certificaat- en hostnaamcontrole de authenticatiegrens;
- de bestaande gebruikersnaam-/wachtwoordroute werkte na herstel op 1883.

Er is bewust geen bestaand wachtwoord uit Home Assistant uitgelezen en geen
tijdelijk brokeraccount aangemaakt. Daardoor is niet afzonderlijk geclaimd dat
dezelfde live sessie zowel TLS als een succesvolle brokerlogin doorliep. De
combinatie is wel gedekt door provider-/flowtests; live zijn de TLS-route en de
bestaande geauthenticeerde route afzonderlijk bewezen. Het product heeft
conform besluit geen eigen private-CA-invoer: de lokale providerproef gebruikte
`SSL_CERT_FILE` om opname van de test-CA in de systeemvertrouwensopslag te
modelleren.

## Uitgevoerde controles

Alle controles zijn uitgevoerd op een schone bronkopie:

| Controle | Resultaat |
| --- | --- |
| `tools/build.py --check` | groen; `thetruth.py` en `provider_defaults.py` actueel |
| `tools/build_lab.py --check` | groen; lab-build `51e7fce38228` |
| volledige Python-suite | 297 tests groen |
| kaarttests | 33 tests groen |
| Ruff | groen |
| HA 2026.9.0 / aioesphomeapi 46.2.0 | 20 contracttests groen |
| HA 2026.10.4 / aioesphomeapi 46.6.0 | 20 contracttests groen |
| Hassfest uit HA Core 2026.10.4 | 1 integratie, 0 ongeldig |

## Grens na M4

M4 heeft niets in Home Assistant of `solesta_lab` geïnstalleerd en geen
providerwissel of uitvalproef uitgevoerd. Normale parallelle live-acceptatie
blijft M5; broker-/publisheruitval, herstel en switchacceptatie blijven M6 en
vereisen opnieuw expliciete toestemming.

## Latere aanvullende brokeracceptatie

Op 5 november 2026 is buiten de oorspronkelijke M4-grens aanvullend live
geaccepteerd tegen een afzonderlijke EMQX-broker op de Synology. Zie
[`mqtt-provider-emqx-acceptance-2026-11-05.md`](mqtt-provider-emqx-acceptance-2026-11-05.md).
Daarmee is de oorspronkelijke beperking tot Home Assistant Mosquitto niet
langer een open acceptatiepunt.
