# Solesta NanoC6 ESPHome firmware

This ESPHome configuration lets an M5Stack NanoC6 passively read the serial
debug output of a Solesta solar water heater. The parser is specific to the
Solesta protocol. Each user supplies their own network and connection details.

## Contents of this bundle

- `README.md` — installation, wiring, data, and troubleshooting instructions.
- `solesta-nanoc6.yaml` — the ESPHome configuration, including the serial
  parser, Native API, optional MQTT connection, and Dashboard import metadata.
- `secrets.example.yaml` — a template for the values needed in a local
  `secrets.yaml` file.

## Check the hardware first

Identify pin 1 (GND) and pin 5 (the continuous TX output) on the Solesta
PROGRAM/DEBUG header. Check the connector orientation against the markings
on the board; do not rely on wire colors alone. With the NanoC6 disconnected,
measure pin 5 relative to pin 1. This connection was designed for about
3.3 V logic. Stop if the measured level is above 3.6 V or the hardware differs
from the described setup.

Plan a receive-only connection: pin 1 to NanoC6 GND, and pin 5 to NanoC6
GPIO1/RX **through a 2.7 kΩ series resistor**. Do not connect a NanoC6 TX pin
or any other Solesta header pins. The UART settings are 57600 baud, 8N1. The
NanoC6 will be powered over USB-C, not from the debug header.

**Leave the NanoC6 disconnected from the Solesta header for the first flash.**
The physical connection is made in step 5 below, after the NanoC6 has started
successfully with the new firmware.

## Build and install

1. Create your own `secrets.yaml` using `secrets.example.yaml` as a guide. Fill
   in the device name, Wi-Fi credentials, and a unique API encryption key.
   Choose whether to enable MQTT as described below. If you already have an
   ESPHome `secrets.yaml`, add the example's keys to it instead of replacing it.
2. Place the completed `secrets.yaml` and `solesta-nanoc6.yaml` together in
   your ESPHome configuration directory.
3. Open `solesta-nanoc6.yaml` in ESPHome Device Builder, build the firmware,
   and flash the NanoC6 over USB. Keep the Solesta header disconnected. Check
   that the NanoC6 boots, joins Wi-Fi, and appears in the ESPHome logs.
4. Unplug the programming USB cable. Make sure the NanoC6 and Solesta
   controller are unpowered before attaching the header wires.
5. Connect Solesta pin 1 to NanoC6 GND and pin 5 to GPIO1/RX through the
   2.7 kΩ resistor, as checked above. Make sure unused 5 V and GPIO2 wires
   remain isolated.
6. Power the Solesta controller and then the NanoC6 via one USB-C supply.
   Never connect the external USB supply and a computer to the NanoC6 at the
   same time. Watch the ESPHome logs and confirm that `data_valid` becomes true
   and the raw values begin updating.
7. In Home Assistant, add the device under **Settings → Devices & services →
   Add integration → ESPHome** if you want its raw entities in Home Assistant.
   This is optional for the Solesta integration. The configuration also includes
   Dashboard import metadata for adopting a previously flashed device in
   ESPHome Device Builder after the YAML is published at the specified GitHub
   location.

For an existing, correctly wired NanoC6, the Solesta header may stay connected
during an OTA update. The readings pause while the device reboots and then
resume. Keep the same device name and `api_encryption_key` when updating it.

Set `mqtt_enabled: false` in `secrets.yaml` to use only the ESPHome Native API.
To publish to MQTT as well, set `mqtt_enabled: true` and fill in `mqtt_broker`,
`mqtt_port`, `mqtt_username`, `mqtt_password`, and `mqtt_topic_prefix`. With
`mqtt_enabled: false`, the MQTT client does not start or publish messages.
MQTT discovery is disabled to avoid creating a second set of Home Assistant
entities alongside the Native API connection.

Both the API and MQTT connection reboot timers are disabled. The node can
therefore run through MQTT without a Native API client or log viewer connected;
a missing client does not periodically restart the UART reader.

## Use with Solesta for Home Assistant

Install the [Solesta integration](../../docs/installation.md) separately. For
Native, connect a Solesta provider hub directly to the NanoC6 using the API
encryption key from your local `secrets.yaml`, then add the offered source and
apply the source expressions below before enabling the system.
The ESPHome integration in Home Assistant is not required for this connection.
For MQTT, connect a Solesta MQTT provider hub to the same broker and enter the
NanoC6 `mqtt_topic_prefix` as the system's root topic and apply the MQTT column
below. The ESPHome project version `0.1.2` is independent of the Solesta
integration version `1.0.0`.

### Source expressions

On **Configure system** or **Reconfigure system**, enter the expression from
the column for your chosen provider. The MQTT paths are relative to
`mqtt_topic_prefix`, for example `sensor/temperature_1_raw/state` and
`text_sensor/last_report/state`. The firmware's `last_report` is the UTC
timestamp of the last complete valid status frame from the Solesta controller.

| Entity key | ESPHome Native | MQTT |
| --- | --- | --- |
| `temp_collector` | `to_number(temperature_1_raw)` | `to_number(state__temperature_1_raw__sensor)` |
| `temp_tank_top` | `to_number(temperature_2_raw)` | `to_number(state__temperature_2_raw__sensor)` |
| `temp_tank_bottom` | `to_number(temperature_3_raw)` | `to_number(state__temperature_3_raw__sensor)` |
| `perc_pump_pwm` | `to_number(pump_raw) * 100` | `to_number(state__pump_raw__sensor) * 100` |
| `last_report` | `last_report` | `state__last_report__text_sensor` |
| `status_reporting` | `report_delay and not is_timestamp(report_delay)` | `report_delay and not is_timestamp(report_delay)` |

Keep the factory Report delay expression
`delay_zone(last_report, 2*60+30, 10*60)`, Pump status `perc_pump_pwm > 0`,
and the other shared calculations/settings. The current local-alert recipe is:

```text
solar_thermal_alerts(null(status_reporting, state_pump, temp_collector, temp_tank_top), 90, 200, 10, 10)
```

Review the [source-expression guide](../../docs/source-expressions.md) for
field binding, adjustable settings and alerts. Check actual source names if
you change the firmware's entity names or MQTT topics. An existing system
keeps its stored expressions: installing new firmware does not apply this
table automatically. Review and save the chosen mappings explicitly.

The bare Native expression `last_report` reads the source field with the same
name. The function `last_report()` instead observes transport activity. They
have different meanings. Temperature and pump fields remain sufficient for
the integration's generic route; no particular diagnostic field is required.
The table explicitly chooses this firmware's optional device timestamp.

Only a complete valid status frame advances the firmware timestamp, including
a frame whose values are identical to the previous frame. Invalid records,
controller text, diagnostic updates, reconnects and clock synchronization do
not advance it. During UART silence it stays at the last frame time. The
unchanged factory Report delay and Reporting status then mark the system
offline after 600 seconds, at the next system update, and suppress current
measurements. A new valid frame restores reporting through the same mapping.

The clock synchronizes through SNTP or a registered Home Assistant ESPHome
connection. Both are configured in UTC. SNTP defaults can be replaced with
local time servers in the YAML. Before the first valid frame and a valid
clock are available, no timestamp is published. A frame received before
clock synchronization is dated using its monotonic receipt time, to whole
seconds; synchronizing the clock is not reported as a new frame. The ordinary
local data path remains usable without internet access when a local clock
source is available. Standalone MQTT can use SNTP without a Native client.

Raw measurements and `data_valid` remain available as firmware diagnostics.
`data_valid` becomes false after 15 seconds without a complete valid status
frame; it is not an integration mapping requirement. Existing systems keep
their configured expressions, including an existing `last_report()` mapping.
Updating the firmware does not change EMQX or other MQTT system mappings.
Retained replay does not prove a new physical frame. See
[report-time semantics](../../docs/source-expressions.md#report-time-change-time-and-retained-messages).

### Check loss and recovery

After installing the firmware and explicitly saving the mappings:

1. Confirm that valid frames increase the frame count and advance the device's
   `last_report`, and that Solesta shows current measurements.
2. Test loss of the UART source using an isolated test feed or a safe,
   powered-down disconnect/reconnect procedure. Never move header wires on
   powered hardware. With the node still reachable, verify that `last_report`
   freezes while data age may keep arriving. After the unchanged 600-second
   report-age limit, verify Reporting status off, the offline alert and
   unavailable current measurements.
3. Restore the source safely and verify a new complete frame and timestamp
   and recovery of the same Solesta entities and card.
4. For MQTT-only use, close Native API/log clients and observe more than
   30 minutes of MQTT data. Frame counts must continue without resetting.

## Data and known limits

The parser publishes raw T1–T4 temperatures, flow, pump output, controller
state, and diagnostics. In the observed installation, T1, T2, and T3 matched
the collector, tank top, and tank bottom temperatures. The pump value is a
fraction; the Solesta Home Assistant integration converts it to a percentage.
The meaning of T4 and flow has not been confirmed, so do not treat them as
verified physical measurements.

Diagnostics include `last_report`, `data_valid`, data age, frame counters, and rejected
records. The local path from the NanoC6 to Home Assistant does not require an
internet connection.

## Troubleshooting

- **No MQTT messages:** Check that `mqtt_enabled` is `true` and verify the
  broker settings.
- **No serial updates:** Check header pin 1/GND, pin 5 to GPIO1/RX, the series
  resistor, and the 57600 8N1 settings.
- **No Native API connection:** Check local network access and the API
  encryption key.
- **OTA update fails:** Check the device name and API encryption key. Use USB
  to recover if OTA is no longer available.
