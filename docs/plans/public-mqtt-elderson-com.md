# Publieke MQTT-TLS-route via `mqtt.example.com`

> Publicatiekopie: installatie-, apparaat- en netwerkidentificatoren zijn
> consequent gepseudonimiseerd. Meetwaarden, tijden en uitkomsten zijn behouden.

Datum nulmeting: 4 november 2026

Status: uitgevoerd en geaccepteerd

## Uitvoeringsstatus op 4 november 2026

Uitgevoerd en gecontroleerd:

- vóór de wijziging is in Home Assistant een volledige automatische back-up
  gemaakt en als beschikbaar bevestigd;
- het geldige RSA Let's Encrypt-certificaat voor `mqtt.example.com` is vanuit DSM
  geëxporteerd, inclusief keten gecontroleerd en onder afzonderlijke
  MQTT-bestandsnamen in Home Assistant `/ssl` geplaatst;
- Mosquitto gebruikt de nieuwe certificaatbestanden op 8883 en is als enige
  Home Assistant-app herstart;
- een afzonderlijke sterke login `mqtt_external` is toegevoegd; het wachtwoord
  staat in Apple Wachtwoorden en is niet in dit document of in loguitvoer
  opgenomen;
- TLS 1.3, de publieke certificaatketen en hostnaam `mqtt.example.com` zijn lokaal
  geverifieerd; login met de nieuwe credential slaagt en een anonieme login
  wordt met MQTT-code 5 geweigerd;
- interne MQTT op 1883 en de actuele `solesta_lab`-waarden van `nanoc6_01`
  bleven na de Mosquitto-herstart gezond;
- op de FRITZ!Box is exact één actieve handmatige regel toegevoegd: TCP 8883
  naar Home Assistant `192.0.2.10:8883`. Er is geen 1883-regel, geen
  UDP-regel, geen poortbereik, geen UPnP/zelfstandige vrijgave en geen Exposed
  Host geactiveerd;
- een controle vanaf het thuisnetwerk via `mqtt.example.com` bereikt 8883, weigert
  1883 en verifieert het publieke certificaat en de hostnaam zonder fout.

Externe acceptatietest via iPhone-hotspot:

- de Mac routeerde via de mobiele interface en het uitgaande publieke
  IPv4-adres week af van de thuisverbinding;
- `mqtt.example.com:8883` was via IPv4 bereikbaar; een standaardverbinding liep na
  de onbereikbare IPv6-route correct door naar IPv4;
- de externe TLS-controle verifieerde `mqtt.example.com`, de publieke Let's
  Encrypt-keten en TLS 1.3 zonder fout;
- de MQTT 3.1.1-login met `mqtt_external` slaagde via IPv4 en TLS; een tweede
  verbinding zonder credentials werd met CONNACK-code 5 geweigerd;
- `mqtt.example.com:1883` bleef via de mobiele route onbereikbaar.

De afsluitende controle bevestigde drie actuele en gezonde Solesta
Lab-providers. De Mosquitto-log bevestigde de geldige externe login en de
expliciete afwijzing van de anonieme testclient zonder nieuwe brokerfout. De
tijdelijke DSM-export, de Home Assistant-overdrachtsmap, het testprogramma en
de tijdelijke wachtwoordkopie zijn verwijderd. De volledige bewijsvoering en
het vernieuwingsrunbook staan in
[de acceptatierapportage](../results/public-mqtt-elderson-com-acceptance-2026-11-04.md).

## Doel en expliciete grenzen

Het kleinste beoogde eindresultaat is:

- één publieke TCP-route: `mqtt.example.com:8883` naar de bestaande Home
  Assistant Mosquitto-broker op `192.0.2.10:8883`;
- TLS met een publiek vertrouwd certificaat waarin `mqtt.example.com` als SAN
  staat en met verplichte certificaat- en hostnaamcontrole door clients;
- uitsluitend geauthenticeerde MQTT-clients; anonieme toegang blijft
  onmogelijk;
- **geen** publieke route naar MQTT 1883 of WebSocketpoorten 1884/8884;
- de bestaande interne MQTT-route op LAN-poort 1883 blijft in gebruik en de
  bestaande `solesta_lab` MQTT-provider blijft ongewijzigd werken;
- geen wijziging van DNS. De gebruiker heeft gekozen voor het bestaande
  apex-domein `mqtt.example.com` in plaats van een nieuw `mqtt`-subdomein.

Dit plan publiceert Home Assistant zelf, de Recorderdatabase, `.storage`,
SMB, SSH en de Solesta-integraties niet.

## Read-only nulmeting

### Home Assistant en Mosquitto

| Onderdeel | Vastgesteld |
| --- | --- |
| Home Assistant OS | 18.4 |
| Home Assistant Core | 2026.10.4 |
| HA LAN-adres | `192.0.2.10/24` |
| Mosquitto-app | 7.1.3; actief, start bij systeemstart en watchdog actief |
| Interne MQTT | TCP 1883 vanaf het LAN bereikbaar |
| MQTT-TLS | TCP 8883 vanaf het LAN niet bereikbaar |
| Authenticatie | lokale login aanwezig; Mosquitto-app ondersteunt geen anonieme logins |
| TLS-configuratie | standaardnamen `fullchain.pem` en `privkey.pem`, maar deze bestanden ontbreken in `/ssl` |
| Bestaande testcertificaten | alleen `solesta-m4-fullchain.pem` en `solesta-m4-privkey.pem`; dit is de private M4-test-CA-route en niet geschikt als publiek certificaat |

De netwerkkaart van de Mosquitto-app heeft 1883, 1884, 8883 en 8884 lokaal
toegewezen. De TLS-listeners worden door de officiële app alleen geactiveerd
wanneer een geldig certificaat en sleutel beschikbaar zijn. Er is geen
publieke port-forwarding vastgesteld; zonder FRITZ!Box-login kan de bestaande
forwardinglijst nog niet gezaghebbend worden gelezen.

### Bestaande Solesta Lab MQTT-route

De nulmeting in de native Home Assistant-app toonde:

- Solesta Lab 0.2.6;
- drie hubs/apparaten en 63 entiteiten;
- MQTT-hub `lab-mqtt` met systeem `nanoc6_01` en 21 entiteiten;
- actuele MQTT-waarden en recente events op 4 november 2026, waaronder
  collector 17 °C, vat boven/onder 22 °C en report delay `[0,150]` seconden.

Dit is het regressieanker voor de controle na iedere Mosquitto-herstart.

### Domein, certificaat en router

| Onderdeel | Vastgesteld |
| --- | --- |
| DNS-beheer | Soverin; DNS-wijzigingen blijven op verzoek van de gebruiker buiten scope |
| `mqtt.example.com` A | aanwezig en gelijk aan de actuele publieke IPv4-route |
| `mqtt.example.com` AAAA | aanwezig; vanaf de huidige testlocatie niet bereikbaar |
| Publieke MQTT 8883 | via IPv4 en IPv6 niet bereikbaar vóór de wijziging |
| Bestaande website | HTTP en HTTPS op `mqtt.example.com` werken over IPv4 |
| Publiek webcertificaat | Let's Encrypt, beheerd op Synology; SAN's `mqtt.example.com` en `henk.mqtt.example.com`; geldig tot 26 januari 2027 |
| Router | FRITZ!Box 7590 AX op `192.0.2.11`; beheerroute geverifieerd |

Home Assistant heeft alleen een link-local IPv6-adres. Daarom is de eerste
publieke route bewust IPv4. Het bestaande AAAA-record wordt niet gewijzigd;
de externe acceptatietest moet expliciet aantonen dat de gekozen MQTT-client
naar IPv4 terugvalt. Als een doelclient uitsluitend het onbereikbare
AAAA-record probeert, is betrouwbare toegang zonder DNS-correctie niet
haalbaar en wordt de wijziging niet als volledig aanvaard beschouwd.

De FRITZ!Box bevat negen bestaande portforwardings, allemaal naar Synology
`mainserver` op `192.0.2.12`. Daaronder vallen HTTP 80, HTTPS 443 en de
bestaande Synology-diensten. Home Assistant heeft geen portforwarding. De
FRITZ!Box rapporteert nul actieve zelfstandig aangevraagde portforwardings;
er is dus geen bestaande UPnP-regel voor MQTT.

Synology DSM beheert het certificaat voor `mqtt.example.com` op de originele
uitgevende host. DSM biedt `Certificaat exporteren`; de export bevat volgens
Synology de certificaatketen en private key. De bestaande poort-80-regel naar
Synology blijft nodig voor automatische Let’s Encrypt-vernieuwing en wordt niet
gewijzigd.

## Beoogde minimale wijziging

1. Maak eerst een actuele Home Assistant-back-up met de Mosquitto-appconfiguratie
   en verifieer dat de back-up beschikbaar is. Noteer daarnaast de huidige
   Mosquitto-opties en FRITZ!Box-portforwardings read-only.
2. Exporteer in DSM uitsluitend het geselecteerde Let’s Encrypt-certificaat
   `mqtt.example.com`. Bewaar of toon de private key niet in projectdocumentatie,
   chat, terminaluitvoer of logboeken.
3. Pak de export in een tijdelijke lokale map uit, verifieer keten, SAN,
   geldigheidsduur en dat certificaat en private key bij elkaar horen. Plaats
   alleen de benodigde keten en sleutel onder nieuwe, MQTT-specifieke
   bestandsnamen in Home Assistant `/ssl`; overschrijf de bestaande
   M4-bestanden en algemene standaardnamen niet stilzwijgend. Verwijder de
   tijdelijke lokale sleutelkopie na byte-/inhoudscontrole en geslaagde
   plaatsing via een herstelbare lokale prullenbakroute.
4. Laat de Mosquitto-app naar deze twee bestanden verwijzen, laat
   `require_certificate` uit voor normale username/password-clients en herstart
   uitsluitend Mosquitto.
5. Controleer lokaal op 8883: vertrouwde keten, SAN/hostnaam, geldigheidsduur,
   TLS-versie, succesvolle login en verwachte afwijzing zonder geldige login.
   Controleer daarna dat 1883 intern nog werkt en `solesta_lab` actuele MQTT-
   reports blijft ontvangen.
6. Voeg op de FRITZ!Box precies één handmatige TCP-forwarding toe:
   extern 8883 naar `192.0.2.10:8883`. Voeg geen regel voor 1883 toe en
   gebruik geen exposed-host- of UPnP-regel.
7. Verbind de Mac voor de externe acceptatietest via de persoonlijke hotspot
   van de iPhone met het mobiele netwerk. Controleer vooraf dat de Mac niet meer
   via het thuis-LAN of de thuis-Wi-Fi routeert en dat het zichtbare publieke
   IP-adres afwijkt van de thuisverbinding. Test daarna met een MQTT 3.1.1-client:
   TLS-verificatie aan, host `mqtt.example.com`, poort 8883 en username/password.
   Test tevens afwijzing zonder credentials en bevestig extern dat 1883 dicht
   blijft. Leg vast of de client IPv4 gebruikt of na een mislukte IPv6-poging
   correct naar IPv4 terugvalt.
8. Controleer opnieuw de Solesta Lab-nulmeting en de Mosquitto-/HA-logboeken op
   nieuwe fouten. Leg certificaatvernieuwing en de externe testopstelling vast.

## Certificaatbesluit vóór uitvoering

Er draait op Synology een geldige Let’s Encrypt-route voor `mqtt.example.com`.
Synology DSM vernieuwt Let’s Encrypt-certificaten automatisch na geslaagde
domeinvalidatie; de bestaande routerregel voor poort 80 maakt die validatie
mogelijk. Het opnieuw uitgeven van een tweede certificaat op Home Assistant
zou dat web-/vernieuwingspad onnodig verstoren.

De gekozen route is daarom de DSM-export als bron voor Mosquitto. Een export
is een momentopname: na iedere DSM-vernieuwing moet de nieuwe keten en sleutel
opnieuw veilig naar Home Assistant worden geplaatst en Mosquitto gecontroleerd
worden herstart. De eerste productieplaatsing wordt alleen aanvaard met een
vastgelegde vervaldatumcontrole en een herhaalbaar vernieuwingsrunbook. Volledig
automatische sleutelsynchronisatie tussen Synology en Home Assistant is een
afzonderlijke hardeningstap; die wordt niet stilzwijgend toegevoegd aan deze
minimale wijziging.

Als de DSM-export niet veilig kan worden geplaatst, is een afzonderlijk
certificaat via DNS-01 het terugvalalternatief. Eventuele DNS-challenge-
handelingen worden dan door de gebruiker uitgevoerd; DNS-beheer door de agent
blijft buiten scope.

## Risico's en beheersing

| Risico | Beheersing |
| --- | --- |
| Onversleutelde MQTT wordt publiek | alleen TCP 8883 forwarden; extern 1883 voor en na testen |
| Credentialaanval op publieke broker | unieke sterke login voor publiek gebruik; geen bestaande firmwarecredential hergebruiken; geen credential loggen |
| Publieke login ziet meer topics dan bedoeld | behandel topic-ACL als afzonderlijk te bewijzen beveiligingscontract; vertrouw niet alleen op een onbeproefde custom ACL |
| Certificaatkopie op HA verloopt na DSM-vernieuwing | vervaldatum vastleggen; uiterlijk 30 dagen voor afloop export/plaatsing/herstart herhalen en opnieuw extern testen |
| Verkeerde certificaatnaam/keten | lokaal en extern verifiëren tegen `mqtt.example.com` met systeem-CA en hostnaamcontrole |
| Bestaande MQTT valt uit bij Mosquitto-herstart | back-up, korte wijzigingsvolgorde, lokale 1883- en Solesta Lab-regressietest |
| Routerregel opent te veel | één TCP-poort naar één vast LAN-adres; geen range, UDP, UPnP of exposed host |
| AAAA-route wijst niet naar HA | externe clientfamilie vastleggen; IPv4-fallback bewijzen of wijziging niet volledig aanvaarden |
| Bestaande website/certificaatvernieuwing wordt geraakt | poorten 80/443 en bestaande webcertificaatroute ongemoeid laten |

## Terugrolpad

Terugrol gebeurt in omgekeerde volgorde:

1. verwijder of deactiveer uitsluitend de nieuwe FRITZ!Box TCP-8883-regel;
2. zet de Mosquitto-certificaatopties terug naar de vastgelegde nulmeting;
3. herstart uitsluitend Mosquitto en bevestig interne 1883 en Solesta Lab;
4. verwijder pas daarna de nieuw geplaatste MQTT-certificaatkopieën wanneer de
   vorige configuratie actief en getest is;
5. herstel zo nodig de Mosquitto-app uit de vooraf gemaakte HA-back-up.

DNS, website, productie-Solesta 0.2.3, `.storage`, Recorder en archieven worden
door deze terugrol niet gewijzigd.

## Afsluiting

Alle stopvoorwaarden zijn opgelost en alle geplande controles zijn geslaagd.
Het blijvende onderhoudspunt is de handmatige certificaatkopie: de huidige
kopie verloopt op 26 januari 2027 en moet uiterlijk 27 december 2026 volgens
het vernieuwingsrunbook worden vervangen en opnieuw extern worden getest.
