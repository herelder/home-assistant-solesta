# D-ESP-001 — Lokaal serieel recordcontract

Datum: 8 oktober 2026<br>
Status: aanvaard

## Besluit

De ESPHome-bridge verwerkt inhoudelijk uitsluitend deze twee recordtypen uit de
passief beluisterde Solesta-stream:

1. een volledig statusrecord `T|t1|t2|t3|t4_F|flow_PWM|pump`;
2. een controllerstatusrecord `Z|code|tekst`.

De twee recordtypen leveren samen acht zichtbare inhoudelijke
Solesta-sensorentiteiten in Home Assistant: zes meetwaarden, de numerieke
`controller_state_code` en de tekstuele `controller_state_text`. In ESPHome is
de laatste technisch een `text_sensor`; de overige zeven zijn numerieke
`sensor`-componenten.

Een statusrecord publiceert de zes meetwaarden als één gevalideerd frame.
Daarna wordt `frame_sequence` verhoogd. Een controllerstatusrecord publiceert
code en tekst direct na elkaar uit dezelfde gevalideerde Z-regel. Er komt geen
`controller_state_sequence`.

Alle `updated!`-, `Failed!`-, MQTT-, HTTP-, netwerk- en overige tekstlogging
wordt genegeerd. Zij verandert de zes meetwaarden, controllerstatus en
`data_valid` niet en krijgt geen eigen ESPHome- of Solesta-providerentiteiten.

## Onderbouwing

De CoolTerm-capture van 8 oktober 2026 bevatte 1.453 geldige statusrecords en
geen syntactisch beschadigd statusrecord. De `updated!`- en `Failed!`-meldingen
bleken onderdeel van de MQTT-publicatielogging. Alle zes `Failed!`-varianten
kwamen in dezelfde aantallen en geclusterd rond MQTT-verbindingsproblemen voor,
terwijl geldige lokale statusrecords bleven binnenkomen.

De Z-regels leverden steeds een numerieke code en brontekst. Beide onderdelen
zijn nuttig zonder een extra volgnummer; alleen omringende formatteringsspaties
van het tekstveld worden verwijderd. De PWM-bron bleek numeriek en niet binair:
naast 0 en 1 kwamen waarden rond 0,75 voor.

## Gevolgen

- Beschikbaarheid wordt uitsluitend bepaald door geldige statusframes en hun
  ouderdom.
- Alle acht inhoudelijke Solesta-sensorentiteiten worden via de ESPHome native
  API aangeboden; zij zijn niet `internal` en niet standaard uitgeschakeld.
- Code en tekst worden direct na elkaar gepubliceerd. Zonder volgnummer bestaat
  geen atomaire garantie over de twee afzonderlijke Home Assistant-state-events.
- De parser synchroniseert na een te lange of niet-ASCII regel pas opnieuw na
  de volgende `LF`.
- `pump_raw` behoudt in de onderzoeksfirmware zes decimalen en wordt niet in de
  firmware naar procenten omgerekend.
- Een syntactisch geldig frame wordt niet op onbewezen plausibiliteitsgrenzen
  gefilterd.
- Alleen de laatste geldige ruwe statusregel mag als begrensde diagnostische
  tekst worden bewaard; willekeurige bronlogging wordt niet gepubliceerd.
- De toekomstige ESPHome-provider kan de ruwe PWM-fractie na afzonderlijke
  bevestiging naar het bestaande Solesta-pomppercentage normaliseren.

## Bewijs en verificatie

- Ruwe broncapture buiten de repository, in de projectomgeving onder
  `output/captures/solesta-coolterm-2026-10-08-131925.txt`.
- Geschoonde regressiefixture:
  `tests/fixtures/solesta_coolterm_excerpt.txt`.
- Uitvoerbaar referentiecontract:
  `tools/solesta_stream_parser.py` en
  `tests/test_solesta_stream_parser.py`.
