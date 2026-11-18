# Implementatieresultaat D-ESP-006

Datum: 25 oktober 2026<br>
Scope: canonieke Solesta-bron; geen installatie of wijziging in live Home
Assistant

## Resultaat

Ontwerpbesluit D-ESP-006 is uitgevoerd:

- `state_pump` wordt uitsluitend uit `perc_pump_pwm > 0` afgeleid;
- `status_reporting` wordt universeel uit `report_delay` afgeleid: `None`
  blijft onbekend, een timestamp is onwaar en iedere overige niet-lege waarde
  is waar;
- `solar_thermal_alerts()` maakt de universele types `offline`,
  `collector_hot`, `pump_idle` en `pump_active`;
- aanvullende Web API-alerts worden genormaliseerd en samengevoegd; ESPHome
  Native werkt zonder bronalerts of barriervelden;
- alertrecords gebruiken `U+001E`, terwijl de kaart oude newlinegescheiden
  waarden blijft lezen;
- de dangergrens voor de collector staat standaard op 200 °C;
- vier Number-entiteiten maken de collectorgrenzen en pompdelta's instelbaar;
- een dangergrens die niet hoger is dan de warninggrens wordt geweigerd;
- bij provideruitval wordt de laatste complete meetset opnieuw tegen de lokale
  klok geëvalueerd. Na 600 seconden blijven alleen de afgesproken configuratie-
  en diagnosewaarden beschikbaar; een geldige nieuwe meetset herstelt de
  gewone waarden;
- de kaart behandelt `danger`, `error` en `critical` als foutniveau en
  kent het universele type `pump_active`.

## Opslag en compatibiliteit

- Entiteitencatalogus: revisie 9, 25 sleutels.
- Expressieschema: versie 6.
- Config-entryschema: versie 1.3.
- Product-, manifest- en kaartversie: 0.2.4.

Het migratiepad accepteert configuraties 1.1 en 1.2 en brengt ze atomair naar
1.3. Daarbij worden de vier instellingen toegevoegd en wordt de herkenbare
oude fabrieksexpressie voor rapportagestatus vervangen door
`report_delay and not is_timestamp(report_delay)`. Alleen herkenbare oude
fabrieksexpressies worden vervangen. Andere, ook handmatig aangepaste,
expressies blijven ongewijzigd. Permanente systeem- en entity-identiteiten
veranderen niet.

## Verificatie

- 244 Python-tests: geslaagd;
- 30 kaarttests: geslaagd;
- canonieke generatorcheck voor `thetruth.py` en `provider_defaults.py`:
  geslaagd;
- deterministische Solesta Lab-buildcheck: geslaagd;
- Ruff 0.16.7: geslaagd;
- controle op witruimtefouten in de diff: geslaagd.

De echte upgrade van `solesta` op een herstelkopie is op 26 oktober 2026 in
fase 6 geslaagd. Het resultaat staat in
[`solesta-production-upgrade-recovery-acceptance-2026-10-26.md`](solesta-production-upgrade-recovery-acceptance-2026-10-26.md).
Deze implementatie en herstelproef hebben geen live Home Assistant-bestanden
gewijzigd.
