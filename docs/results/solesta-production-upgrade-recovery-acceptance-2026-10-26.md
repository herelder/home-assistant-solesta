# Fase 6 — upgrade van productie-Solesta op een herstelkopie

> Publicatiekopie: installatie-, apparaat- en netwerkidentificatoren zijn
> consequent gepseudonimiseerd. Meetwaarden, tijden en uitkomsten zijn behouden.

Datum uitvoering: 26 oktober 2026

Resultaat: geslaagd; de echte productieconfiguratie is op een geïsoleerde
herstelkopie van Solesta `0.2.3` naar kandidaat `0.2.4` gemigreerd, opnieuw
gestart en teruggerold

## Reikwijdte en veiligheid

Deze proef gebruikt de echte `solesta`-config entry, registers,
dashboardresource en Recorderhistorie uit een door Home Assistant gemaakte
back-up. Dit is dus geen Solesta Lab-proef en geen synthetische nieuwe
configuratie.

Productie bleef gedurende de hele proef op Solesta `0.2.3` en de Web
API-provider draaien. Er is niet geschreven naar `/Volumes/config`, de live
Recorderdatabase of live `.storage`. De geïsoleerde Home Assistant-processen
luisterden uitsluitend op `127.0.0.1` en zijn na de controles gestopt.

Home Assistant maakte via **Instellingen → Systeem → Back-ups** een native
handmatige back-up met instellingen, geschiedenis en alle apps. De lokale
kopie had SHA-256
`17965f3c3c0fd6de3d7698e49a047f491c7242cb122ea065eb48f527e1cf6099`.
Media en de gedeelde map waren voor deze integratieproef niet geselecteerd.

| Onderdeel | Gevalideerde versie |
| --- | --- |
| Home Assistant Core | `2026.10.4` |
| Home Assistant Supervisor in back-upmetadata | `2026.10.3` |
| Productiebron | Solesta `0.2.3`, Web API |
| Upgradekandidaat | Solesta `0.2.4` |
| Config-entryschema | `1.1` → `1.3` |
| Expressieschema | `4` → `6` |
| Entiteitencatalogus kandidaat | revisie 9, 25 sleutels |
| ESPHome-clientbibliotheek in testomgeving | `aioesphomeapi==46.6.0` |

## Nulmeting uit de herstelkopie

De productie-identiteiten vóór de upgrade waren:

| Object | Nulmeting |
| --- | --- |
| Config-entry-ID | `649GD27H969CZRWMMXNHWVWC0N` |
| Hub-UID | `051b2230-786d-4c6d-8186-2b0fb086e33f` |
| Provider-ID / protocol | `provider_example` / `web_api` |
| Systeem-subentry-ID | `6HQJDT1PPY8D7B0NBJ69RM2KPA` |
| Systeem-UID | `40c5b86b-1eae-49bd-895a-a120a37e9550` |
| Publieke systeem-ID | `sol_0217181ef299` |
| Bron-systeem-ID | `SOL_0217181EF299` |
| Apparaat-ID | `1fe60450956c449b87c182f0c5a93b7d` |
| Entiteiten | 21, waarvan 2 door de integratie uitgeschakeld |
| Kaartresource | `/solesta/solesta-status-card.js?v=0.2.3` |

De 21 opgeslagen source-expressies waren bytegelijk aan de 0.2.3-
fabrieksinstellingen. De Recorderkopie bevatte voor 19 van de 21 entiteiten
historie: 119.436 state-rijen van `2026-10-05 09:03:02` tot
`2026-10-26 08:06:38` UTC. Alleen de twee reeds uitgeschakelde entiteiten
hadden geen historie.

## Uitvoering

1. De native back-up is lokaal uitgepakt en gecontroleerd op Solesta `0.2.3`,
   Home Assistant `2026.10.4`, de verwachte config entry, registers,
   dashboardopslag en Recorderdatabase.
2. In een aparte Home Assistant `2026.10.4`-omgeving is uitsluitend de echte
   productie-Solesta-entry uit de kopie geladen. De originele register- en
   dashboardbestanden vormden de starttoestand.
3. De 0.2.3-component is in die kopie vervangen door kandidaat `0.2.4`.
4. Home Assistants eigen config-entrymigratie en opslaglaag hebben de upgrade
   uitgevoerd. Daarna is de kandidaat volledig gestart en heeft de bestaande
   Web API-provider met één actief systeem succesvol gegevens opgehaald.
5. De kandidaat is gestopt en een tweede keer gestart om idempotentie en
   duplicaatvorming te controleren.
6. Ten slotte zijn de oorspronkelijke 0.2.3-component en -opslag vanuit de
   herstelkopie in een nieuwe geïsoleerde omgeving gestart om het terugrolpad
   te controleren.

## Configuratie- en expressiemigratie

De opgeslagen migratie was atomair en had exact de verwachte wijzigingen:

| Veld | Voor | Na eerste start | Na tweede start |
| --- | ---: | ---: | ---: |
| Config-entryversie | `1` | `1` | `1` |
| Config-entry minor | `1` | `3` | `3` |
| Configuratierevisie hub | `1` | `2` | `2` |
| Expressieschema systeem | `4` | `6` | `6` |
| Configuratierevisie systeem | `4` | `5` | `5` |

Entry-ID, hub-UID, provider-ID, protocol, verbinding, subentry-ID,
systeem-UID, publieke systeem-ID en `source_system_id` bleven ongewijzigd.
De tweede start wijzigde geen configuratieveld of revisie opnieuw.

Omdat productie de herkenbare 0.2.3-fabrieksexpressies gebruikte, heeft de
schema-upgrade uitsluitend die fabriekswaarden naar het overeengekomen
D-ESP-006-contract gebracht. Daaronder vallen:

- `status_reporting = report_delay and not is_timestamp(report_delay)`;
- `state_pump = perc_pump_pwm > 0`;
- `alerts_system = solar_thermal_alerts(...)` met behoud van de aanvullende
  Web API-bronalerts;
- nieuwe fabrieksinstellingen 90 °C, 200 °C, 10 K en 10 K voor de vier
  alertdrempels.

Dit is een versieschemamigratie en geen providerremapping. De
providerwissellogica verandert geen bronexpressies en mag alleen een nieuwe
`source_system_id` invullen. De regressietests bevestigen daarnaast dat een
niet-fabrieksmatige, handmatig aangepaste expressie tijdens de
versieschemamigratie bytegelijk blijft.

## Identiteit, entiteiten en dashboard

Alle 21 bestaande registryrecords behielden exact hun registry-ID, entity-ID,
unique ID, config-entry-ID, subentry-ID, apparaat-ID en `disabled_by`-waarde.
Er ontbrak geen bestaande entiteit en er ontstond geen vervangende entiteit.

De vier nieuwe Number-entiteiten zijn eenmaal toegevoegd aan hetzelfde
apparaat:

- collector-warninggrens;
- collector-dangergrens;
- pomp-inactief temperatuurdelta;
- pomp-actief temperatuurdelta.

Na de upgrade waren er precies 25 verschillende entity-ID's en 25
verschillende unique ID's. Geen entity-ID kreeg een ongewenst numeriek
achtervoegsel zoals `_2`. De vier nieuwe namen volgen de actuele Home
Assistant-regel voor nieuwe entity-ID's en kregen daarom de bestaande
ruimteprefix `voorzolder`; dit verandert geen oude entity-ID.

Het bestaande apparaat behield ID
`1fe60450956c449b87c182f0c5a93b7d` en identifier
`(solesta, 40c5b86b-1eae-49bd-895a-a120a37e9550)`. Er is geen tweede apparaat
aangemaakt.

De bestaande resource met ID `f5a7c0f567c7446db079b90f8723172a` is in
plaats bijgewerkt naar `/solesta/solesta-status-card.js?v=0.2.4`. Er bleef
precies één productie-Solesta-resource over; de afzonderlijke Solesta
Lab-resource bleef ongemoeid.

## Historie en herstart

De 19 bestaande entity-ID's met historie zijn na de upgrade identiek aan de
ID's in de Recorderkopie. Een read-only query op die consistente kopie vond
opnieuw exact 119.436 state-rijen binnen hetzelfde tijdvenster. Omdat zowel de
entity-ID's als de registry unique ID's behouden bleven, blijft die historie
aan dezelfde entiteiten gekoppeld. De vier nieuwe Number-entiteiten beginnen
zoals verwacht zonder oude historie.

Bij de tweede start:

- bleven minorversie, schema en revisies ongewijzigd;
- bleven er precies 25 unieke entiteiten en één apparaat;
- ontstonden geen duplicaten;
- registreerde de kaart opnieuw dezelfde ene 0.2.4-resource;
- haalde de Web API-provider opnieuw succesvol gegevens op.

## Terugrolcontrole

Een afzonderlijke kopie is hersteld met de originele bestanden uit de native
back-up en daarna gestart met Solesta `0.2.3`. De provider laadde één actief
systeem en haalde succesvol gegevens op. De toestand was opnieuw:

- config entry `1.1`, hubrevisie `1`;
- expressieschema `4`, systeemrevisie `4`;
- dezelfde hub-, systeem- en apparaatidentiteiten;
- precies 21 entiteiten, zonder duplicaten;
- kaartresource `/solesta/solesta-status-card.js?v=0.2.3`.

Daarmee is zowel het voorwaartse upgradepad als het herstelpad met dezelfde
native back-up aantoonbaar uitvoerbaar.

## Meldingen uit de tijdelijke Mac-omgeving

De minimale lokale Home Assistant-installatie meldde ontbrekende optionele
pakketten van niet-geteste ingebouwde componenten, waaronder multimedia-,
Bluetooth- en discoveryonderdelen. Een eerste start binnen de afgeschermde
uitvoeringsomgeving mocht bovendien geen lokale poort openen. Deze meldingen
zijn gescheiden van de Solesta-uitkomst: na het lokaal beschikbaar maken van
de exacte Solesta-afhankelijkheden startte Solesta op `127.0.0.1`, migreerde
de entry, registreerde de platforms en haalde de Web API-provider succesvol
gegevens op. In de kandidaat- en terugrollogboeken stond geen Solesta-fout.
Er zijn geen macOS-instellingen gewijzigd.

## Geautomatiseerde verificatie

Na de herstelproef zijn de publicatiecontroles in een schone kopie van de
repository uitgevoerd:

- canonieke generatorcheck: geslaagd;
- deterministische Solesta Lab-buildcheck: geslaagd, build-ID
  `30b6fffb240a`;
- volledige Python-suite: 244 tests geslaagd;
- dashboardkaart: 30 tests geslaagd.

De eerste lokale aanroep zonder de vastgelegde testafhankelijkheden miste
`openpyxl`, SQLAlchemy en Node.js. Na uitvoering met `requirements-test.txt`
en de gebundelde Node-runtime waren alle verplichte controles groen; dit was
een eigenschap van de lokale ontwikkelomgeving, geen codefout.

## Beoordeling

Het upgradecriterium van fase 6 is geslaagd. Kandidaat `0.2.4` migreert de
echte productieconfiguratie en registers zonder verlies van identiteit,
entiteiten, dashboardbinding of historie, is idempotent bij herstart en heeft
een werkend herstelpad naar 0.2.3.

Dit resultaat is geen installatieopdracht voor productie en nog geen publieke
releasevrijgave. Voor afronding van fase 6 blijven gebruikersdocumentatie,
changelog, definitieve releaseversie, HACS-validatie en Hassfest over.
