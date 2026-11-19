# D-ESP-012 — Publieke MQTT-TLS-route via `mqtt.example.com`

> Publicatiekopie: installatie-, apparaat- en netwerkidentificatoren zijn
> consequent gepseudonimiseerd. Meetwaarden, tijden en uitkomsten zijn behouden.

Datum: 4 november 2026

Status: aanvaard en live geverifieerd

## Besluit

De bestaande Home Assistant Mosquitto-broker is voor externe MQTT-clients
bereikbaar via één handmatige IPv4-portforwarding:

`mqtt.example.com:8883` → Home Assistant `192.0.2.10:8883`

De route gebruikt uitsluitend MQTT over TLS met publieke certificaat- en
hostnaamcontrole en een afzonderlijke sterke username/password-login. Poort
1883, MQTT-WebSockets, UDP, UPnP/zelfstandige poortvrijgave en Exposed Host
worden niet gepubliceerd. De bestaande interne MQTT-route op 1883 blijft
ongewijzigd.

Er wordt geen nieuw DNS-record toegevoegd. Het bestaande apex-domein blijft
ook de Synology-website bedienen via de bestaande 80/443-regels. De
onbereikbare AAAA-route blijft een bekende grens; externe MQTT-clients moeten
naar de werkende IPv4-route kunnen terugvallen.

## Certificaatbron en vernieuwing

Synology DSM blijft de uitgevende en automatisch vernieuwende host voor het
Let's Encrypt-certificaat van `mqtt.example.com`. Mosquitto gebruikt een
gecontroleerde momentopname van dat certificaat en de bijbehorende sleutel in
Home Assistant `/ssl`:

- `mqtt-elderson-fullchain.pem`;
- `mqtt-elderson-privkey.pem`.

Deze kopie vernieuwt niet automatisch mee met DSM. Daarom moet uiterlijk
dertig dagen vóór de vervaldatum opnieuw worden geëxporteerd, gecontroleerd,
geplaatst en extern getest. De huidige kopie verloopt op 26 januari 2027; de
volgende onderhoudscontrole is uiterlijk 27 december 2026 nodig.

Automatische sleutelsynchronisatie tussen DSM en Home Assistant valt buiten
dit minimale besluit. Zo'n synchronisatie vereist een afzonderlijk ontwerp
voor authenticatie, minimale rechten, atomische plaatsing, herstart en
foutafhandeling.

## Beveiligingscontract

- het publieke endpoint accepteert alleen geauthenticeerde MQTT-clients;
- credentials worden niet gebruikt als identiteit en komen niet in
  projectbestanden, diagnostiek of archieven;
- de externe login staat in Apple Wachtwoorden;
- alleen de nieuwe 8883-regel wordt bij terugrol verwijderd;
- tijdelijke certificaat- en sleutelkopieën worden na plaatsing en acceptatie
  verwijderd;
- de bestaande website, DNS, productie-integratie, `.storage` en Recorder
  blijven buiten scope.

## Acceptatie en terugrol

De live acceptatie is vastgelegd in
[de acceptatierapportage](../results/public-mqtt-elderson-com-acceptance-2026-11-04.md).
Het volledige uitvoerings- en terugrolpad staat in
[het wijzigingsplan](../plans/public-mqtt-elderson-com.md).
