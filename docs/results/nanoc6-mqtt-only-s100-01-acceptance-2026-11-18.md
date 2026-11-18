# S100-01 — fysieke MQTT-only-duurproef geslaagd

Datum: 18 november 2026. Alle tijden zijn CET, Europe/Amsterdam.

Status: **geslaagd en hersteld**. De Nano werkte 31 minuten via MQTT zonder
de bekende Native API-/logclients, met doorlopende geldige frametellers.
Beide tijdelijk gestopte HA-clients zijn daarna weer ingeschakeld en hun
werking en oorspronkelijke configuratie zijn gecontroleerd.

## Opstelling en veilig herstel

De gebruiker gaf expliciet opdracht alle bekende Native API-/logclients te
stoppen, dertig minuten te observeren, daarna alles te herstellen en de
slaapblokkade van de Mac vrij te geven.

Vooraf is een credentialvrije nulmeting met volledige entryhashes,
instellingshashes, subentryhashes en de oorspronkelijke ingeschakelde toestand
vastgelegd. Via de normale HA-interface zijn uitsluitend gestopt:

1. **Solesta Lab — ESPHome Native – ESPHome Solesta**;
2. de gewone **ESPHome-integratie — Solesta serial bridge**.

Beide entries stonden vervolgens `disabled_by=user`; hun verbinding,
bronexpressies, identiteiten en systeeminstellingen bleven gelijk.
Productie, Web API en de twee MQTT-hubs bleven actief en ongewijzigd.
Eerdere losse Native-observers waren al beëindigd. Er waren geen andere
bekende Native/logclients of open logvensters. Een socketcontrole op de Mac
vond geen verbinding met Native API-poort 6053.

De fysieke Solesta en Nano bleven gedurende deze proef aan. De Nano draait
firmware **0.1.2**, gebouwd met **ESPHome 2026.10.2**. De live firmware-YAML is
bytegelijk aan de canonieke publieke bron en bevat zowel
`api.reboot_timeout: 0s` als `mqtt.reboot_timeout: 0s`. YAML-SHA-256:
`efb3f90c0049945bb3ac3b478d9c985cbf4d1bd502d1ef8b5fa166e3b3a2b041`.

## Werkelijke duur en resultaten

De observer gebruikte uitsluitend MQTT-subscripties op de bestaande Nano-root
van Mosquitto en EMQX. Hij publiceerde niets en opende geen Native API.
Iedere dertig seconden legde hij een snapshot vast en controleerde hij
read-only dat beide HA-clients nog uitgeschakeld waren. De geselecteerde
MQTT-counterevents zijn ook afzonderlijk opgeslagen.

| Gegeven | Resultaat |
| --- | --- |
| Start | **17 november 23:59:16** |
| Einde | **18 november 00:30:16** |
| Gemeten duur | **1860,14 seconden — 31 minuten** |
| Frame sequence, beide brokers | **671 → 1271** |
| Valid frame count, beide brokers | **671 → 1271** |
| Nieuwe geldige frames | **600** |
| Tellerresets | **0** |
| MQTT-verbindingsfouten | **0** |
| Waargenomen Native API-verbindingsgebeurtenissen via MQTT-log | **0** |
| Grootste tussenpoos tussen verse counterberichten | Mosquitto **4,098 s**, EMQX **4,095 s** |
| Ouderdom apparaatrapport bij einde | **4,17 s** |
| Native-clients bij einde van het meetvenster | Beide nog uitgeschakeld |

De vijftienminuten- en dertigminutengrens zijn zonder herstart of tellerreset
gepasseerd. De apparaatrapporttijd bleef oplopen en beide brokers leverden
door. Er zijn tijdens dit venster geen Native API-observers, logviewers,
firmwarewijzigingen of herstarts gestart om de proef te beïnvloeden.

Dit sluit de fysieke acceptatie van **S100-01** voor deze Nano, firmware en
opstelling af. Het is een afgebakende duurproef en geen uitspraak over
onbegrensde toekomstige uptime of willekeurige netwerkomstandigheden.

## Herstel na het meetvenster

Na voltooiing van de observer zijn beide hierboven gestopte HA-clients via
**Inschakelen** hersteld. De gewone ESPHome-integratie leverde weer actuele
ruwe meetwaarden en toonde firmware 0.1.2. De volledige opgeslagen entries
van productie, Web API Lab, Native Lab, Mosquitto, EMQX en ESPHome kwamen bij
de controle om **00:32:24** weer overeen met de volledige nulmeting.

Om **00:32:56** toonden Web API, ESPHome Native en EMQX op het
vergelijkingsdashboard alle **Online**, actuele waarden en **Alles werkt normaal**.
De MQTT-routes waren gedurende de proef actief gebleven. Er is geen andere
bronexpressie, koppeling, secret, firmware of productcode gewijzigd.

Na een onderbreking is de slotrapportage in de ochtend afgerond. De nieuwe
read-only controle bevestigde opnieuw dezelfde configuraties. De twee eerder
gestarte tijdelijke `caffeinate`-processen waren inmiddels geëindigd; geen
eigen wakkerhoudassertie was nog actief. Permanente energie-instellingen
zijn niet aangepast.

## Bewijs en grenzen

Private bewijsbestanden staan in de genegeerde werkmap
`work/mqtt-only-20261117/`:

- `restoration-baseline.json` en `clients-stopped.json`;
- `firmware-check.json`;
- `selected-mqtt-events.jsonl` en `endurance-observations.json`;
- `endurance-result.json`;
- `restoration-verification.json` en `completion-check.json`.

De observer is na de 31 minuten beëindigd en zijn MQTT-subscripties zijn
gesloten. Er is niets rechtstreeks in `.storage` geschreven en de actieve
Recorderdatabase is niet benaderd. Omdat geen productcode is gewijzigd, zijn
geen nieuwe generator-, Python- of kaarttests uitgevoerd; deze acceptatie
bestaat uit de beschreven fysieke duurproef en herstelcontroles.

De eerdere [UART-uitval en het herstel](nanoc6-uart-recovery-2026-11-17.md)
betreffen S100-02. De onderzochte
[EMQX-herconfiguratiebeperking](mqtt-reconfiguration-during-source-silence-2026-11-17.md)
is door deze S100-01-proef niet gewijzigd.
