# Fase 5 — providerwissel binnen Solesta Lab

> Publicatiekopie: installatie-, apparaat- en netwerkidentificatoren zijn
> consequent gepseudonimiseerd. Meetwaarden, tijden en uitkomsten zijn behouden.

Datum uitvoering: 24 oktober 2026

Resultaat: geslaagd; de Web API-labhub is heen en terug gewisseld zonder
verlies van identiteit, entiteiten of historie

## Reikwijdte

Deze fase beproeft uitsluitend de providerwissel van de bestaande
`lab-web-api`-hub binnen **Solesta Lab**. De productie-integratie `solesta`
bleef gedurende de hele proef actief op de Web API-provider. De tweede,
afzonderlijke labhub `lab-esphome-native` bleef als referentie naast de
gewisselde hub bestaan.

De uitgevoerde route was:

1. baseline van de Web API-labhub vastleggen;
2. foutafhandeling van de ESPHome Native-verbinding controleren;
3. dezelfde hub naar ESPHome Native wisselen;
4. de bestaande systeemkoppeling handmatig controleren en inschakelen;
5. identiteit, entiteiten, actuele waarden en historie controleren;
6. dezelfde hub terugwisselen naar de Web API-provider;
7. de oorspronkelijke bronkoppeling handmatig herstellen en opnieuw
   controleren.

## Herstelpad en versies

Vóór de wissel was de Home Assistant-back-up
`Custom backup 2026.10.2` beschikbaar op Synology DSM. Deze back-up bevat de
instellingen en historie die nodig zijn om de volledige proefopstelling te
herstellen. De fase-4-codekopie en het daar beschreven herstelpad bleven
eveneens beschikbaar.

| Onderdeel | Gevalideerde versie of toestand |
| --- | --- |
| Home Assistant Core | `2026.10.2` |
| Home Assistant Supervisor | `2026.10.3` |
| Home Assistant OS | `18.3` |
| Python in Home Assistant | `3.14.6` |
| Productie-integratie | `solesta` `0.2.3`, Web API, 30 seconden |
| Solesta Lab | `solesta_lab` `0.2.3`, build `058df71e3b4d` |
| Lab-update-interval | 15 seconden |
| ESPHome-clientbibliotheek | `aioesphomeapi==46.6.0` |
| Config-entryschema | `1.1` |
| Expressieschema | `4` |

Er is voor deze acceptatie geen publiek versienummer verhoogd. De test gebruikt
de herleidbare labbuild bij dezelfde bronversie `0.2.3`; een eventuele
publieke release blijft voorzien als `0.3.0`, tegelijk voor manifest en kaart.

## Identiteitsbaseline

De blijvende identiteit van de te wisselen hub en het systeem is vóór de
eerste wissel vastgelegd:

| Object | Baseline |
| --- | --- |
| Hub-ID en titel | `lab-web-api` |
| Config-entry-ID | `32NKT535009PKT8CXHNDNVAGQM` |
| Systeem-UID | `78d76d9b-c1fc-4348-a3e2-1b6fc65b7951` |
| Publieke systeem-ID | `sol_0217181ef299` |
| Web API-bron-ID | `SOL_0217181EF299` |
| Home Assistant-apparaat-ID | `1281fcb3cf57458aa2d4b97c7e8d9713` |
| Aantal entiteiten op de hub | 21 |
| Controle-entiteit | `sensor.sol_0217181ef299_collector_temperature_2` |
| Configuratie-/providerrevisie | `1` / `1` |

Solesta Lab bevatte bij de baseline in totaal twee apparaten en 42 entiteiten.
De controle-entiteit had al historie van vóór 24 oktober; de daggrafiek vormde
daarmee een zichtbare historiebaseline voor de wissel.

De integratie baseert entity unique ID's op de permanente systeem-UID en het
vaste entiteitscontract, niet op providercredentials, endpoint of zichtbare
naam. De live controle hieronder gebruikt daarnaast de ongewijzigde config
entry, apparaat-ID, entity-ID en entiteitsaantallen als registerbewijs dat
Home Assistant geen vervangende of dubbele entiteiten heeft gemaakt.

## Fout- en herstelroutes

Vóór de geslaagde wissel zijn twee echte verbindingsfouten via de Home
Assistant-interface aangeboden:

- een handmatige host `192.0.2.1` op poort `6053`, die niet bereikbaar is;
- de fysieke Nano via mDNS met een syntactisch geldige maar onjuiste
  Noise-encryptiesleutel.

Beide verbindingen werden geweigerd voordat gegevens werden opgeslagen. De
hub bleef in beide gevallen op de bestaande Web API-provider staan, met twee
labapparaten en 42 labentiteiten. Het geheim werd niet in diagnostiek,
projectbestanden of dit verslag opgenomen.

Een afwijkend MAC-adres kon niet verantwoord met een tweede fysiek apparaat
worden aangeboden: in het netwerk was slechts één geschikte ESPHome-node
beschikbaar en rechtstreeks wijzigen van `.storage` is uitgesloten. Dit deel
is daarom als contracttest uitgevoerd. De tests bewijzen dat het verwachte
MAC-adres zonder scheidingstekens aan `aioesphomeapi` wordt doorgegeven en dat
een `BadMACAddressAPIError` als verbindingsfout wordt afgehandeld. Dezelfde
gerichte suite controleert ook de authenticatiefout bij een onjuiste
Noise-sleutel.

Tijdens de foutproeven bleef één configuratiestroom in de Home
Assistant-interface hangen. Home Assistant Core is tweemaal gecontroleerd
herstart om zo'n verweesde stroom op te ruimen. Na beide herstarts kwamen de
productie-integratie en beide labhubs normaal terug. Dit is een operationeel
aandachtspunt voor een toekomstige gebruikershandleiding, maar geen verlies
van opgeslagen configuratie of identiteit.

## Heenwissel naar ESPHome Native

De hub `lab-web-api` is via **Herconfigureer** gewijzigd van Web API naar
ESPHome Native. De fysieke Nano is geselecteerd als
`02:b6:a2:14:14:16/uart1`; de versleutelde verbinding en het verwachte
MAC-adres zijn gevalideerd.

Zoals ontworpen werd het bestaande systeem na de providerwissel eerst
uitgeschakeld. Het formulier behield de permanente systeem-UID, de publieke
systeem-ID en de bestaande source-expressies. Na handmatige controle zijn de
providerafhankelijke koppelingen ingesteld op:

| Solesta-doel | ESPHome Native-expressie |
| --- | --- |
| laatste rapportage | `last_update` |
| collectortemperatuur | `to_number(temperature_1_raw)` |
| temperatuur boven in vat | `to_number(temperature_2_raw)` |
| temperatuur onder in vat | `to_number(temperature_3_raw)` |
| gereserveerde temperatuur | `to_number(temperature_4_raw)` |
| pomppercentage | `to_number(pump_raw) * 100` |
| systeemmeldingen | `""` |
| rapportagestatus | `data_valid` |

De overige afgeleide expressies en het interval van 15 seconden bleven
ongewijzigd. Na inschakelen leverde de gewisselde hub onmiddellijk actuele
waarden. De controle omstreeks 09:29 CEST toonde op beide labkaarten 18 °C,
dezelfde normale systeemstatus en hetzelfde actuele rapportagevenster.

Na de heenwissel golden nog steeds:

- config-entry-ID `32NKT535009PKT8CXHNDNVAGQM`;
- apparaat-ID `1281fcb3cf57458aa2d4b97c7e8d9713`;
- systeem-UID `78d76d9b-c1fc-4348-a3e2-1b6fc65b7951`;
- publieke systeem-ID `sol_0217181ef299`;
- één apparaat en 21 entiteiten voor de gewisselde hub;
- twee apparaten en 42 entiteiten in heel Solesta Lab.

De diagnostiek rapporteerde configuratie-/providerrevisie `2` / `2`, één
systeem, geen evaluatiefouten en uitsluitend de verwachte ESPHome-bronvelden.
De bestaande daggrafiek liep zichtbaar door over het wisselmoment. Er ontstond
geen entity-ID met een numeriek achtervoegsel en geen extra apparaat of
entiteit.

## Terugwissel naar Web API

Dezelfde config entry is daarna teruggewisseld naar Web API. De verbinding is
vóór opslag opnieuw gevalideerd met de bestaande Solesta-accountgegevens. Het
systeem werd opnieuw eerst uitgeschakeld en daarna handmatig gekoppeld aan de
oorspronkelijke bron `SOL_0217181EF299`.

De providerafhankelijke koppelingen zijn teruggezet op:

| Solesta-doel | Web API-expressie |
| --- | --- |
| laatste rapportage | `last_update` |
| collectortemperatuur | `to_number(temp1)` |
| temperatuur boven in vat | `to_number(temp2)` |
| temperatuur onder in vat | `to_number(temp3)` |
| gereserveerde temperatuur | `to_number(temp4)` |
| pomppercentage | `to_number(pump)` |
| systeemmeldingen | `join_lines(alerts)` |
| rapportagestatus | `status=="online"` |

Ook hier bleven de afgeleide expressies en het interval van 15 seconden
ongewijzigd. De einddiagnostiek rapporteerde configuratie-/providerrevisie
`3` / `3`, één systeem, geen evaluatiefouten en de oorspronkelijke Web
API-bronvelden.

Bij de eindcontrole omstreeks 09:38 CEST:

- stond de hub zichtbaar als **Web API – lab-web-api**;
- waren dezelfde config entry, hetzelfde apparaat, dezelfde systeem-UID en
  dezelfde publieke systeem-ID aanwezig;
- had de hub nog steeds 21 entiteiten en Solesta Lab nog steeds 42;
- toonde de controle-entiteit geen duplicaat en liep de daghistorie door over
  beide wissels;
- gaven de Web API- en ESPHome Native-kaart beide 18 °C en
  **Alles werkt normaal**;
- rapporteerden beide labroutes hetzelfde actuele venster
  `09:36:07`–`09:38:37`.

De afzonderlijke productiekaart bleef ondertussen via de Web API actief en
toonde om 09:38 CEST eveneens een actuele normale toestand. De productiehub,
haar systeemconfiguratie en haar update-interval van 30 seconden zijn niet
gewijzigd.

## Geautomatiseerde verificatie

Na het vastleggen van dit resultaat zijn de verplichte controles opnieuw
uitgevoerd:

- canonieke generatorcheck: `thetruth.py` en `provider_defaults.py` actueel;
- labgeneratorcheck: deterministisch, build-ID `058df71e3b4d`;
- volledige Python-suite: 225 tests geslaagd;
- dashboardkaart: 27 tests geslaagd;
- repository- en koppelingencontrole: geen onverwachte gegenereerde of
  private bestanden en geen ongeldige lokale documentlinks.

## Beoordeling en productieadvies

Fase 5 is geslaagd. De expliciete providerwissel werkt heen en terug en de
veiligheidskeuze om systemen na iedere wissel uitgeschakeld te laten, dwingt de
bedoelde handmatige controle van bron-ID en providerafhankelijke expressies af.
De permanente hub-, systeem-, apparaat- en entiteitsidentiteiten bleven
behouden; Home Assistant-historie bleef aan dezelfde entiteiten gekoppeld.

De test onderbouwt dat de wissel technisch geschikt is als basis voor een
productie-upgrade. Zij is nog geen opdracht of vrijgave om productie om te
schakelen. Fase 6 moet eerst de upgrade op een herstelkopie, de
gebruikersdocumentatie, releaseversie `0.3.0`, HACS-validatie en Hassfest
afronden. Tot een afzonderlijk migratiebesluit blijft de productie-integratie
op versie `0.2.3` en de Web API-provider.

## Gerelateerde resultaten

- [`esphome-provider-phase4-parallel-acceptance-2026-10-23.md`](esphome-provider-phase4-parallel-acceptance-2026-10-23.md)
- [`esphome-native-provider-physical-acceptance-2026-10-22.md`](esphome-native-provider-physical-acceptance-2026-10-22.md)
