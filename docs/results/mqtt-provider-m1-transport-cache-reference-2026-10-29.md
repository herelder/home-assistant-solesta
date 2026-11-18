# MQTT-provider M1 — transport- en cachereferentie

Datum: 29 oktober 2026

Status: afgerond

## 1. Doel en begrenzing

M1 verifieert read-only of de bestaande MQTT-teststroom voldoende is om een
broker-onafhankelijke Solesta-provider en de gedeelde pushcache te ontwerpen.
Er is niet onderzocht wat individuele waarden inhoudelijk betekenen. De
waargenomen payloads zijn uitsluitend als ondoorzichtige strings behandeld.

Tijdens M1 zijn geen broker-, ESPHome-, Home Assistant- of
Solesta-instellingen gewijzigd. Er is niets gepubliceerd en geen dienst
gestopt of herstart. De actieve luisterabonnementen zijn na de proef gesloten.

## 2. Gecontroleerde uitgangssituatie

De opnieuw gekoppelde, read-only gelezen Home Assistant-share bevestigde:

- Home Assistant `2026.10.4`;
- productie-integratie `solesta` `0.2.3`;
- `solesta_lab` `0.2.5`, build `ddcbfd4ceef5`;
- een bestaande ESPHome-MQTT-configuratie met standaard MQTT over TCP op
  poort 1883 en gebruikersnaam-/wachtwoordauthenticatie;
- een expliciete topic-prefix en `discovery: false`;
- geen expliciete QoS- of retain-override in de gelezen ESPHome-configuratie.

Brokerhost, gebruikersnaam, wachtwoord en de lokale node-/rootnaam zijn niet
in dit verslag of de fixture opgenomen. Credentials zijn alleen kortstondig
in procesgeheugen gebruikt voor de toegestane read-only subscriptie.

De Home Assistant-MQTT-integratie met Mosquitto is hiermee alleen het huidige
testdoel. De beoogde Solesta-provider mag er niet van afhankelijk worden.

## 3. Waarneming via Home Assistant

Via de al aangemelde Home Assistant Companion-app is geluisterd op
`<root>/#`, met subscriber-QoS 0. De pagina ontving direct een beginset en
daarna doorlopende updates. Bij het stoppen stond de teller op 401 ontvangen
berichten. De pagina bevestigde topic, ruwe payload, ontvangsttijd en
ontvangstvolgorde, maar toonde de MQTT-QoS en RETAIN-vlag per bericht niet.

Daarom is aanvullend één begrensde, rechtstreekse read-only subscriptie met
MQTT 3.1.1 uitgevoerd. Er is QoS 2 gevraagd en door de broker toegekend, zodat
een lagere feitelijke leverings-QoS niet door het abonnement werd afgekapt.
Binnen zes seconden zijn waargenomen:

| Eigenschap | Waarneming |
| --- | --- |
| Abonnement | `<root>/#` |
| Gevraagde/toegekende QoS | 2 / 2 |
| Ontvangen berichten | 36 |
| Unieke relatieve topics | 17 |
| QoS 0, RETAIN=true | 17 |
| QoS 0, RETAIN=false | 19 |
| Andere QoS | niet waargenomen |

De 17 eerste retained berichten vormden één basale state per waargenomen
topic. Daarna volgden live berichten met RETAIN=false. Dat laatste is normale
MQTT-leversemantiek: de RETAIN-vlag op een live levering aan een bestaand
abonnement zegt niet dat de broker die publicatie niet als nieuwe retained
state opslaat.

Omdat het abonnement QoS 2 toestond en alle PUBLISH-berichten als QoS 0 werden
geleverd, publiceert deze teststroom haar states feitelijk met QoS 0. Dit is
een eigenschap van deze testpublisher, geen eis aan andere publishers of
brokers.

## 4. Geredigeerde pushfixture

De bijbehorende machineleesbare fixture staat in
`mqtt-provider-m1-redacted-push-sequence-2026-10-29.json`. Het is een
gefilterde representatieve deelsequentie; tussen de opgenomen events kwamen
ook berichten op andere topics binnen.

| Volgorde in gefilterde reeks | Relatief topic | Ruwe payload | QoS | RETAIN |
| ---: | --- | --- | ---: | --- |
| 1 | `sensor/frame_sequence/state` | `7947` | 0 | true |
| 2 | `binary_sensor/data_valid/state` | `ON` | 0 | true |
| 3 | `sensor/frame_sequence/state` | `7948` | 0 | false |
| 4 | `sensor/frame_sequence/state` | `7949` | 0 | false |

Deze selectie legt geen domeinbetekenis vast. Ook de leesbare namen en
payloads blijven voor de provider gewone topic-sleutels en strings.

## 5. Gevolgen voor het ontwerp

M1 ondersteunt de volgende reeds gekozen richting:

1. Een abonnement op `<root>/#` levert voldoende basale input voor een
   pullable statecache; er is geen statusregel, barrièretopic of
   firmwarewijziging nodig.
2. De eerste waarde per topic kan na een lege procescache de baseline vormen.
   Dat event telt volgens het afgesproken contract als update.
3. Ieder ontvangen bericht kan lokaal `last_report` bijwerken, ongeacht topic,
   payload, QoS of RETAIN.
4. Alleen een vergelijking van de ruwe gecachete waarde van een in
   source-expressies gebruikte sleutel kan `last_update` bijwerken. MQTT
   levert zelf geen oorspronkelijk publicatietijdstip mee.
5. Een retained replay volgt dezelfde vergelijkingsregel. Bij een lege cache
   ontstaat een baseline; bij een al gevulde cache verandert een identieke
   replay alleen `last_report`.
6. De ontvangen volgorde mag niet als coherente meetcyclus worden uitgelegd.
   Losse topics worden onafhankelijk verwerkt.
7. Availability-, log-, teller- en samengestelde topics krijgen in de
   provider geen bijzondere rol. Alleen source-expressies bepalen of en hoe
   een topic wordt gebruikt.
8. De handmatige configuratieflow kan een root valideren door tijdelijk op
   `<root>/#` te abonneren. Zij hoeft geen systemen of topicbetekenissen te
   ontdekken.

De cachetechniek kan hiermee voor MQTT en ESPHome Native gelijk worden
ontworpen; alleen de transportadapter en de bron-sleutelvorming verschillen.

## 6. Niet uitgevoerd

M1 omvatte uitdrukkelijk niet:

- broker-, netwerk-, publisher- of Home Assistant-uitval;
- geforceerde reconnect of herstart;
- wijzigen van QoS-, retain-, LWT-, discovery- of publisherinstellingen;
- inhoudelijke validatie van topicwaarden;
- automatische bron- of systeemdiscovery;
- implementatie van de MQTT-provider.

Actieve storings- en herstelacceptatie hoort in M6, na het ontwerp, de
implementatie en de lokale regressietests.

## 7. Conclusie

M1 is voldoende afgerond om M2 te starten. De testbroker accepteert een
standaard, geauthenticeerde MQTT-verbinding en een wildcardabonnement onder de
handmatig gekozen root. De stroom levert retained baselines en losse live
updates als ruwe strings. Daarmee zijn het topic-sleutelcontract, de lokale
timestampregels en de minimale pushcache-input vastgesteld zonder eisen aan
de publisher toe te voegen.
