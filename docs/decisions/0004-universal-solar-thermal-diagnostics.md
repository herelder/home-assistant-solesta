# D-ESP-004 — Universele afgeleide zonneboilerdiagnostiek

Datum: 19 oktober 2026<br>
Status: aanvaard

Opvolging: het provider-onafhankelijke architectuurprincipe blijft gelden. De
nog niet geïmplementeerde functiesignatuur, tijdssemantiek en instelbare
grenzen zijn op basis van empirische alertdata aangescherpt in
[`D-ESP-006`](0006-universal-local-derived-diagnostics.md).

## Besluit

Tekstuele status- en alarmdiagnostiek wordt provider-onafhankelijk afgeleid in
expliciete functies van de expression-evaluator. Source-expressies bedraden
alleen bronvelden, reeds genormaliseerde entiteitsvelden en constanten. De
beslislogica, prioriteit, uitsluiting, formattering, begrenzing en
deduplicatie zitten volledig in de diagnostische functie.

Het hoofdcontract wordt:

```text
solar_thermal_alerts(
    status_reporting,
    controller_state_code,
    temp_collector,
    temp_tank_top,
    temp_tank_bottom,
    perc_pump_pwm,
    source_lines=None,
    alert_level="info",
)
```

De evaluator ondersteunt alleen positionele functieargumenten. Een expressie
die alleen een strengere ondergrens wil instellen, geeft daarom expliciet
`None` door voor `source_lines`.

## Alertcontract

- `alert_level` is de minimale opgenomen ernst en staat standaard op `info`.
- De geordende ernstniveaus zijn `info`, `warning`, `error`, `critical`.
- Ongeldige niveaus veroorzaken een geclassificeerde expressiefout.
- `source_lines` mag ontbreken, `None`, één scalar of een vlakke lijst/tuple
  met regels zijn.
- JSON-objectregels met `type`, `message` en `severity` worden genormaliseerd.
- Een niet-lege kale tekstregel zonder severity krijgt `warning`, gelijk aan
  de bestaande dashboardfallback.
- De functie combineert bronregels met zelf afgeleide meldingen, normaliseert,
  dedupliceert en sorteert ze deterministisch.
- De uitkomst is een begrensde reeks compacte JSON-objecten. D-ESP-006
  vervangt de voorlopige newline-scheiding door ASCII Record Separator
  (`U+001E`), zodat newlines in tekstvelden geen extra records vormen.
- Een lege string betekent dat er geen actuele meldingen zijn.

`solar_thermal_alerts()` krijgt geen rapportagevertragingen of tijdsgrenzen.
Rapportagebeschikbaarheid wordt afzonderlijk genormaliseerd, bijvoorbeeld via
`status_reporting` en waar nodig een aparte functie zoals
`reporting_status()`. De al bestaande `delay_zone()` blijft verantwoordelijk
voor de presentatie van rapportagevertraging.

## Fout- en beschikbaarheidspad

Diagnostiek moet ook kunnen worden geëvalueerd wanneer een providerupdate
mislukt. De coordinator krijgt daarom een afgebakend diagnostisch fallbackpad:
gewone meetwaarden worden niet als actueel gepresenteerd, terwijl technische
beschikbaarheidsinvoer als onwaar/ontbrekend aan de diagnostische expressies
wordt aangeboden. Zo kunnen `status_reporting` en `alerts_system` een storing
tonen zonder oude meetwaarden als vers te presenteren.

## Gevolgen

- De functies worden toegevoegd aan de toegestane evaluatorfuncties en krijgen
  deterministische unit tests.
- De canonieke standaardexpressie voor `alerts_system` wordt in
  `EntityDescriptions.xlsx` gewijzigd; `thetruth.py` wordt uitsluitend via de
  generator bijgewerkt.
- De kaart leest de recordgescheiden JSON-uitkomst en blijft voor bestaande
  waarden newlinegescheiden JSON en kale bronregels accepteren.
- Providers leveren technische brondata, geen provider-specifiek gerenderde
  eindtekst voor de Solesta-entiteit.
