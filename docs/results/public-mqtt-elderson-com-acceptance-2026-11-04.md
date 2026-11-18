# Publieke MQTT-TLS-route — live acceptatie

> Publicatiekopie: installatie-, apparaat- en netwerkidentificatoren zijn
> consequent gepseudonimiseerd. Meetwaarden, tijden en uitkomsten zijn behouden.

Datum uitvoering: 4 november 2026

Status: geslaagd

## Geaccepteerde toestand

| Onderdeel | Geaccepteerde toestand |
| --- | --- |
| Publiek endpoint | `mqtt.example.com:8883` |
| Routerroute | uitsluitend TCP 8883 naar Home Assistant `192.0.2.10:8883` |
| Broker | Home Assistant Mosquitto 7.1.3 |
| TLS | publiek vertrouwde Let's Encrypt-keten; hostnaam `mqtt.example.com` |
| Certificaat geldig tot | 26 januari 2027 |
| Authenticatie | afzonderlijke login `mqtt_external`; geen anonieme toegang |
| Publieke poort 1883 | niet bereikbaar |
| Interne MQTT | bestaande LAN-route op 1883 behouden |

Vóór de wijziging is in Home Assistant een volledige automatische back-up
gemaakt en als beschikbaar bevestigd. Alleen Mosquitto is na de
configuratiewijziging herstart.

## Uitgevoerde controles

### Lokale regressie

- TCP 1883 en 8883 waren op het LAN bereikbaar;
- de 8883-listener presenteerde de publieke keten voor `mqtt.example.com` en
  doorstond systeemvertrouwen en hostnaamcontrole;
- de nieuwe login kreeg MQTT CONNACK-code 0;
- een verbinding zonder credentials kreeg MQTT CONNACK-code 5;
- de bestaande Home Assistant- en Solesta-MQTT-clients verbonden na de
  Mosquitto-herstart opnieuw;
- Web API, ESPHome Native en MQTT bleven in Solesta Lab actueel en normaal.

### Externe mobiele acceptatie

De Mac is voor de eindtest uitsluitend via de persoonlijke iPhone-hotspot en
het mobiele netwerk gerouteerd. Het uitgaande publieke IPv4-adres week af van
de thuisverbinding.

- `mqtt.example.com:8883` was via IPv4 bereikbaar;
- de TLS-handshake gebruikte TLS 1.3, verifieerde de Let's Encrypt-keten en
  bevestigde de hostnaam zonder fout;
- de MQTT 3.1.1-testclient logde met `mqtt_external` via IPv4 en TLS in;
- een tweede verbinding zonder credentials werd met CONNACK-code 5
  afgewezen;
- de Mosquitto-log bevestigde zowel de geauthenticeerde externe client als de
  afwijzing `not authorised` van de anonieme testclient;
- `mqtt.example.com:1883` bleef onbereikbaar;
- bij de standaard hostnaamroute liep de client na de onbereikbare IPv6-route
  correct door naar IPv4.

Na terugkeer op het thuisnetwerk toonde Solesta Lab drie actuele systemen:
Web API, ESPHome Native en `lab-mqtt/nanoc6_01`. Alle drie waren online en
rapporteerden normale, actuele waarden. De recente Mosquitto-logregels toonden
geen nieuwe brokerfout.

## Opruiming en geheimen

- het wachtwoord is niet in dit document, terminaluitvoer of de repository
  opgenomen en blijft uitsluitend in Apple Wachtwoorden bewaard;
- het tijdelijk gekopieerde wachtwoord is uit het klembord gewist;
- het tijdelijke MQTT-testprogramma is verwijderd;
- de DSM-exportmap in Downloads is na controle verwijderd;
- de tijdelijke overdrachtsmap in de Home Assistant-configshare is verwijderd;
- de actieve certificaatbestanden in Home Assistant `/ssl` zijn behouden.

## Vernieuwingsrunbook

Voer dit uiterlijk 27 december 2026 uit en daarna telkens uiterlijk dertig
dagen vóór de vervaldatum van de dan actieve kopie:

1. controleer in DSM dat het vernieuwde certificaat `mqtt.example.com` als SAN
   bevat en nog geldig is;
2. maak een actuele Home Assistant-back-up en leg de huidige Mosquitto-opties
   read-only vast;
3. exporteer alleen het bedoelde DSM-certificaat en controleer keten, SAN,
   vervaldatum en de overeenkomst tussen certificaat en private key;
4. vervang gecontroleerd de twee MQTT-specifieke bestanden in Home Assistant
   `/ssl`; laat de bestaande M4-testcertificaten ongemoeid;
5. herstart uitsluitend Mosquitto;
6. controleer lokaal TLS, hostnaam, geldige login, anonieme afwijzing, interne
   1883 en Solesta Lab;
7. herhaal de externe 8883-, 1883-, TLS- en authenticatietests via de
   iPhone-hotspot;
8. verwijder alle tijdelijke sleutelkopieën nadat de eindtest is geslaagd.

## Terugrol

Verwijder of deactiveer uitsluitend de nieuwe FRITZ!Box-regel `MQTT TLS`, zet
de Mosquitto-certificaatopties terug naar de vooraf vastgelegde toestand en
herstart alleen Mosquitto. Controleer daarna interne MQTT en Solesta Lab. De
vooraf gemaakte Home Assistant-back-up blijft het laatste herstelmiddel.
