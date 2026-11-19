# Mosquitto — apparaatrapporttijd gekoppeld en offline bevestigd

Datum: 17 november 2026, Europe/Amsterdam (CET).

Status: uitgevoerd en geslaagd. De Solesta bleef uit; de Nano bleef aan.
De gebruiker heeft de Mosquitto-route zonder dashboardkaart gekozen om de
bedoelde werking ook via MQTT rechtstreeks in de entiteiten te controleren.

## Wijziging

Via de normale HA-systeemconfiguratie is in de hub **MQTT – HA Mosquitto**,
systeem **nanoc6_01_mosquitto**, uitsluitend deze bronexpressie gewijzigd:

| Expressie | Voor | Na |
| --- | --- | --- |
| `last_report` | `last_report()` | `state__last_report__sensor` |

De nieuwe expressie verwijst naar MQTT-bronpad `sensor/last_report/state`.
Dit is het door firmware 0.1.2 bepaalde tijdstip van het laatste geldige
UART-frame. De configuratieflow valideerde en bewaarde de wijziging terwijl
de Solesta uit was; de interface bevestigde **Het systeem is bijgewerkt**.

## Werkelijke entiteiten na opslaan

De Mosquitto-apparaatpagina is in de native Companion-app gecontroleerd.
De activiteit registreert de nieuwe toestanden om **23:35:04 CET**:

| Entiteit | Waargenomen toestand |
| --- | --- |
| `binary_sensor.nanoc6_01_mosquitto_reporting_status` | **Verbroken** |
| `sensor.nanoc6_01_mosquitto_report_delay` | `2026-11-17T21:47:15+00:00` — lokaal **22:47:15** |
| `sensor.nanoc6_01_mosquitto_alert_lines` | Offline-melding met ernst `danger` |
| Temperaturen, pomp en vatenergie | **Onbekend** |

De actuele diagnosegroep bevestigde eveneens **Reporting status: Verbroken**.
De oude apparaatrapporttijd bleef intact na retained replay en herladen van
de hub. De reeds meer dan 600 seconden oude rapportage leidde op de eerste
evaluatie na de wijziging tot offline. Deze stap meet niet opnieuw een hele
wachttijd van tien minuten; die grens was eerder via Native bevestigd.

Daarmee is de keten apparaatrapporttijd → MQTT-bronexpressie → normale
rapportagevertraging → offline-entiteiten live geverifieerd. Een MQTT-kaart
was hiervoor niet nodig. Ook het latere herstel na inschakelen is bevestigd;
de afzonderlijke MQTT-only-duurproef is daarna
[op 18 november geslaagd](nanoc6-mqtt-only-s100-01-acceptance-2026-11-18.md).

## Herstel bevestigd

Na inschakelen van de Solesta registreerden de entiteiten om **23:40:03 CET**
weer **Reporting status: Verbonden**, rapportagevertraging `[0,150]`, actuele
metingen en een verdwenen offline-melding. De Nano-rapporttijd liep weer op.
Zie de volledige [herstelcontrole](nanoc6-uart-recovery-2026-11-17.md).

## Behoud en herstelpad

Een read-only vergelijking met de nulmeting bevestigde:

- alle overige Mosquitto-bronexpressies zijn letterlijk gelijk;
- systeemidentiteit, bron-ID, ingeschakelde toestand en overige instellingen
  zijn behouden;
- alleen de expressie en de daarvan afgeleide veldlijsten en systeemrevisie
  veranderden; de systeemrevisie ging van 6 naar 7;
- de volledige entries van productie, Web API Lab, Native en EMQX zijn
  ongewijzigd.

Er is geen productcode, firmware of brokerconfiguratie gewijzigd. De eerder
onderzochte [EMQX-validatiebeperking](mqtt-reconfiguration-during-source-silence-2026-11-17.md)
blijft bestaan. Herstel van deze ene instelling gaat via dezelfde HA-flow:
zet uitsluitend de rapportage-expressie terug naar `last_report()`.

Credentialvrije nulmeting en controle-uitvoer staan in
`work/uart-outage-20261117/before-mosquitto-mapping.json` en
`after-mosquitto-mapping.json`. `.storage` is uitsluitend gelezen, de actieve
Recorderdatabase is niet benaderd. De Mac bleef wakker.
