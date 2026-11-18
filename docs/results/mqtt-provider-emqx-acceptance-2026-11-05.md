# MQTT-provider — aanvullende EMQX-acceptatie

> Publicatiekopie: installatie-, apparaat- en netwerkidentificatoren zijn
> consequent gepseudonimiseerd. Meetwaarden, tijden en uitkomsten zijn behouden.

Datum: 5 november 2026

## Uitkomst

De brokeronafhankelijkheid is aanvullend live geaccepteerd tegen EMQX op de
Synology (`192.0.2.12:1884`). Deze broker draait lokaal zonder TLS en zonder
verplichte authenticatie en is gebridged met de Home Assistant
Mosquitto-opstelling. De beheerpoort `18083` was bereikbaar, maar voor de
acceptatie was geen beheerlogin nodig.

De test bewijst dat de provider niet afhankelijk is van Mosquitto of de Home
Assistant MQTT-integratie. Er waren geen codewijzigingen nodig.

## Onafhankelijke MQTT-proeven

MQTTX verbond rechtstreeks en zonder credentials met EMQX en abonneerde op
`solesta/#` en de geïsoleerde testnamespace `solesta-test/#`. Daarmee zijn
bevestigd:

- actuele, niet alleen retained, bronberichten onder `solar/bridge_demo/#`;
- publicatie en ontvangst met QoS 0;
- publicatie met QoS 1 en QoS 2, geleverd met QoS 0 aan het QoS 0-abonnement,
  conform de MQTT-QoS-onderhandeling;
- retained opslag en replay na verbreken en opnieuw opbouwen van de
  MQTTX-sessie.

De retained proef staat onder de afgebakende testtopic
`solesta-test/emqx-acceptance/retained` en raakt het broncontract niet.

## End-to-end Solesta Lab

De bestaande MQTT-providerhub in `solesta_lab` is tijdelijk omgezet van de
publieke TLS-route naar EMQX:

- host `192.0.2.12`;
- poort `1884`;
- TLS uit;
- keepalive 60 seconden;
- abonnements-QoS 0.

De opgeslagen gebruikersnaam en het opgeslagen wachtwoord zijn ongewijzigd
gelaten om de terugweg naar de publieke broker niet te beschadigen. EMQX
vereist geen authenticatie en accepteerde deze clientverbinding.

De MQTT-provider initialiseerde zonder fout en leverde op het
vergelijkingsdashboard dezelfde genormaliseerde waarden als Web API en ESPHome
Native. Na de normale losse-topicconvergentie toonden alle drie routes dezelfde
temperatuur en energie-uitkomst en bleven alle drie online.

Na de proef is de MQTT-hub teruggezet naar `mqtt.example.com:8883` met TLS. De
configuratieflow bevestigde de update en het dashboard toonde daarna opnieuw
drie online routes met gelijke actuele waarden.

## Conclusie

Het resterende acceptatiepunt voor een afzonderlijke, niet-Mosquitto broker
buiten Home Assistant is afgerond. Samen met de eerder aanvaarde publieke
TLS-route is zowel brokeronafhankelijkheid als gebruik buiten de lokale Home
Assistant-broker live aangetoond.
