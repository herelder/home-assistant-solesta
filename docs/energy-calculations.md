# Energy calculations

The integration calculates stored heat above the configured cold-water
temperature. It uses the configured tank capacity in litres and the average of
the measured top and bottom tank temperatures.

## Integration formulas

```text
energy_tank_mj = round(
  volume_tank × (temp_tank_average − temp_coldwater) × 4.186 / 1000,
  4
)

energy_tank_kwh = round(energy_tank_mj / 3.6, 3)

energy_shower_kwh = round(
  5 minutes × 8 litres/minute ×
  (38 °C − temp_coldwater) × 4.186 / 3600,
  5
)

energy_tank_showers = round(
  energy_tank_kwh / energy_shower_kwh,
  2
)
```

The factor 4.186 is the specific heat capacity of water in kJ/(kg·°C). For
this calculation, one litre of water is treated as one kilogram. Dividing by
1,000 converts kJ to MJ; dividing by 3.6 converts MJ to kWh.

A standard shower is defined as five minutes at eight litres per minute and a
delivered temperature of 38 °C. This is a comparison unit, not a prediction of
actual household consumption.

`temp_coldwater`, `volume_tank` and `energy_shower_kwh` are adjustable
configuration entities. The initial shower-energy expression follows the
formula above. Setting the entity manually replaces that expression with the
chosen fixed value.

## Intentional difference from dashboard.solesta.nl

The Solesta web dashboard uses this direct kWh approximation:

```text
round(
  0.00116 × volume_tank ×
  (temp_tank_average − temp_coldwater),
  3
)
```

It also uses a fixed value of 1.20582 kWh for one standard shower.

The Home Assistant integration intentionally does not use those two values as
its defaults. It derives kWh from the more precise MJ result and calculates
shower energy from the currently configured cold-water temperature. MJ, kWh
and the number of standard showers therefore remain internally consistent,
but a value can differ slightly from the Solesta web dashboard.

This difference is shown while a solar water heater is first configured.
