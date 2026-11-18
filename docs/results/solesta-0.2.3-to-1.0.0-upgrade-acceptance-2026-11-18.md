# Upgradeproef Solesta 0.2.3 → 1.0.0

Datum: 18 november 2026, circa 18:25–18:44 CET.

## Oordeel

**Geslaagd binnen de hieronder beschreven geïsoleerde Home Assistant
Core-omgeving.** De actuele 1.0.0-kandidaat kan de echte productieconfiguratie
van 0.2.3 laden, met behoud van alle bronexpressies, identiteiten,
gebruikersinstellingen, dashboardconfiguratie en bestaande historie. Een
tweede start is idempotent. Herstel van de oorspronkelijke 0.2.3-back-up is
eveneens beproefd en geslaagd.

Er is geen blokkerende fout in de Solesta-upgrade gevonden. Deze uitkomst
bewijst de upgrade van de bestaande Web API-configuratie; het is geen nieuwe
acceptatieproef van alle provider-, firmware- en dashboardfuncties.

Productie is niet vervangen en draait nog op Solesta **0.2.3**. Solesta Lab
blijft **0.2.9**. De componentbestanden en de zes relevante live
configuratie-entries zijn na afloop ongewijzigd ten opzichte van de nulmeting.
Home Assistant bleef bereikbaar.

## Geteste bron en herstelkopie

- Home Assistant in productie en in de aparte testomgeving: **2026.11.2**.
- Testomgeving: macOS, een nieuwe Python **3.14.10**-omgeving; echte HA
  bootstrap, configuratie-entrymigratie, platforms, coordinator, HTTP-resource
  en Recorder. Er is geen migratie of provider nagebootst.
- Kandidaat: bevroren kopie van de actuele projectbron, inclusief de reeds
  aangebrachte reviewcorrecties. De bron was deels nog niet gecommitteerd;
  daarom is de geteste inhoud met bestandshashes vastgelegd.
- SHA-256 van de gesorteerde kandidaat-bestandshashes:
  `1f5fb7424cc3ba7a9cd237ee13f334084a0599e4e02f020f3e7fe997fd6f904b`.
  De geteste bron kwam bij de eindcontrole overeen met de projectbron.
- Nieuwe native HA-back-up, gemaakt via de Companion-app:
  **Solesta 0.2.3 upgradeproef 1.0.0 2026-11-18**, back-up-ID `8beefcfa`.
  Instellingen, geschiedenis en apps waren geselecteerd; opslag op het eigen
  HA-systeem. De export is lokaal bewaard.
- Exportgrootte: **352.399.360 bytes**. SHA-256:
  `83fe602a4a1ed60d61ef5d3de492daee006c44060a41ca227fe04667df6a9f44`.

Alleen gegevens uit deze afgeronde back-upexport zijn gebruikt. De actieve
Recorderdatabase is niet via SMB geopend of gekopieerd. De originele export
en testgegevens blijven in de genegeerde privéwerkmap
`work/upgrade-20261118/`; configuraties en geheimen zijn niet in dit verslag
opgenomen.

## Uitvoering

De herstelkopie is beperkt tot de bestaande productie-entry van `solesta`,
de bijbehorende registraties en herstelstates, de bestaande
dashboardconfiguratie, archieven en de volledige Recorderdatabase. Andere
opgeslagen integratie-entries en automatiseringen zijn niet gestart.

Een minimale testconfiguratie gebruikt uitsluitend een HTTP-luisteradres op
`127.0.0.1`. De bestaande Web API wordt werkelijk uitgelezen. Recorder-purge
staat in de kopie uit. APFS-kopieën delen aanvankelijk opslagblokken maar
hebben onafhankelijke inhoud; de originele herstelgegevens blijven intact.

Eerst is de nieuwe HA-runtime afzonderlijk op normaal starten en stoppen
getest. Daarna zijn de volgende stappen uitgevoerd:

| Stap | Component | Entryversie | Expressieschema | Entiteiten | Beschikbaar, ingeschakeld |
| --- | --- | --- | --- | --- | --- |
| Nulmeting op herstelkopie | 0.2.3 | 1.1 | 4 | 21 | 19/19 |
| Upgrade van dezelfde kopie | 1.0.0 | 1.9 | 11 | 21 | 19/19 |
| Tweede start na upgrade | 1.0.0 | 1.9 | 11 | 21 | 19/19 |
| Herstel van oorspronkelijke back-up in aparte kopie | 0.2.3 | 1.1 | 4 | 21 | 19/19 |

In iedere stap laadde de entry succesvol, was de coordinator succesvol en
bleef hetzelfde Solesta-apparaat aanwezig. De twee uitgeschakelde entiteiten
bleven uitgeschakeld. Alle vier HA-processen stopten normaal en eindigden met
exitcode 0; de eerder bij oude Mac-proeven opgetreden native Python-crash bij
afsluiten is hier niet gereproduceerd.

## Behoud en wijzigingen

De volgende controles slagen voor nulmeting, upgrade, tweede start en herstel:

- Hub- en systeemidentiteit, entry- en subentry-ID, entity-ID, unique ID,
  registry-ID, apparaatbinding en `disabled_by` blijven behouden.
- **Alle 21 opgeslagen bronexpressies blijven letterlijk gelijk.** Ook de
  bestaande verwijzing naar het bronveld `last_update` blijft behouden.
  Er zijn geen velden gemapt, expressies geconverteerd of extra
  drempelentiteiten toegevoegd.
- Provider-, bron- en systeeminstellingen, opties en overige
  gebruikersinstellingen blijven behouden, waaronder de ingestelde
  updatefrequentie.
- De upgrade wijzigt alleen de entry-/expressieschemaversie en verhoogt de
  configuratierevisies eenmaal. De volledige entry is na de tweede start
  gelijk aan die na de eerste upgrade. Ook entityregistraties, apparaten en
  dashboardresources veranderen dan niet opnieuw.
- De bestaande dashboardconfiguratie blijft exact gelijk. De bestaande
  kaartresource behoudt zijn resource-ID en krijgt versie `1.0.0`, zonder
  duplicaat. De daadwerkelijk via HTTP geleverde kaart is bytegelijk aan de
  meegeleverde kaartbron. Bij herstel wordt weer de 0.2.3-kaart aangeboden.

### Recorder en archieven

Vóór de eerste start zijn vaste grenzen voor de bestaande databaseregels
vastgelegd. Na de proef zijn de volledige oorspronkelijke regels tot die
grenzen gehasht en vergeleken, inclusief BLOB-velden. Het betreft:

| Tabel | Oorspronkelijke regels behouden |
| --- | ---: |
| `states` | 3.383.676 |
| `state_attributes` | 578.907 |
| `states_meta` | 433 |
| `statistics` | 111.678 |
| `statistics_short_term` | 363.597 |
| `statistics_meta` | 105 |

Daaronder vallen **77.891 oorspronkelijke Solesta-state-regels**. Alle
vergeleken inhoud blijft gelijk; er komen uitsluitend nieuwe regels bij.
SQLite `quick_check` slaagt en de laatste Recorder-run is in iedere proef
correct gesloten.

De **11 bestaande vaste archiefbestanden** blijven bytegelijk. De **91
bestaande bronjournaalregels** blijven inhoudelijk behouden. Het
bronjournaalbestand en de operationele `status.json` worden tijdens normaal
bedrijf bijgewerkt; daarvoor is dus geen onjuiste eis van een identieke
bestandshash toegepast. Het journaal is na de laatste teststart en na herstel
op behoud van de oorspronkelijke regels gecontroleerd.

Bij de eerste start van een back-upkopie meldt Recorder dat een in de
productieback-up nog lopende sessie wordt afgesloten. Dat betreft de
overgenomen sessie; de nieuwe test-runs sluiten vervolgens correct af.

## Aanvullende controles en grenzen

- **311 Python-tests geslaagd**, uitgevoerd op de schone, bevroren bronkopie
  zonder private werkbestanden of bytecode. Een eerste run vanuit de brede
  projectwerkmap trof uitsluitend de twee verwachte publicatiehygiënefouten
  door genegeerde lokale bestanden; de publiceerbare bronkopie slaagt volledig.
- **38 kaarttests geslaagd**.
- Beide generatoruitkomsten zijn bytegelijk aan de bestaande gegenereerde
  bestanden: `thetruth.py` en `provider_defaults.py`.
- Productie- en Lab-componenthashes en alle zes relevante live entries zijn
  ongewijzigd. Productie antwoordt met HTTP 200. Beide lokale testluisterpoorten
  zijn na afloop gesloten.

Deze proef draait op HA Core onder macOS, niet op een tweede HA OS-installatie
met Supervisor. De beperkte testomgeving mist enkele optionele bibliotheken
voor onder andere camera, spraak en niet-geteste netwerkdetectieflows. De logs
bevatten daarvoor omgevingsfouten, ook bij de oorspronkelijke 0.2.3. De
Solesta-entry en zijn benodigde platforms, Recorder en kaartresource laden
wel correct; er is geen Solesta-setup- of migratiefout gevonden. Een brede
HA OS-/Supervisoracceptatie kan hieruit niet worden afgeleid.

De kaart is bij deze proef technisch op resource, configuratie en tests
gecontroleerd. Er is geen nieuwe visuele schermacceptatie uitgevoerd. De
afzonderlijke smalle-schermbevindingen F01/F02 uit de
[frontendacceptatie van 18 november](frontend-acceptance-2026-11-18.md) zijn
met deze upgradeproef niet opnieuw beoordeeld.

## Herstelpad en bewijs

Een terugkeer na een echte productie-upgrade moet de **oorspronkelijke
back-up inclusief configuratie en database** herstellen. Alleen de oude
componentcode over de gemigreerde configuratie kopiëren is niet de hier
geteste herstelroute. De native back-up staat in HA en de export is lokaal
bewaard; de aparte herstelproef gebruikt daarvan de originele 0.2.3-gegevens.

Privébewijs staat onder `work/upgrade-20261118/`, met onder meer
`preparation.json`, `candidate-hashes.json`, de vier runtimeverslagen,
`verification.json`, `final-status.json`, testlogs en de oorspronkelijke en
latere snapshots in `private-evidence/`. De oorspronkelijke Recorderregels,
expressies en configuraties zijn daar vergelijkbaar zonder ze openbaar te
maken.

Deze opdracht heeft geen productie-installatie, firmwareflash, publicatie of
commit uitgevoerd.
