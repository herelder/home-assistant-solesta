# D-ESP-013 — Productiebasis en verwijdering van labcompatibiliteit

Datum: 13 november 2026

Status: door gebruiker opgedragen; uitgevoerd in de onuitgebrachte kandidaat 1.0.0

## Ontwerp en risicoanalyse

De ondersteunde oude installatie is productieversie 0.2.3, commit
`bccaee942ec20fe906f7ea3dd4a9978f1abba0b6`. Tussentijdse labversies zijn geen
te ondersteunen productiereleases. De extra paden hiervoor vergrootten de
expressietaal en konden opgeslagen bronvelden of namen ongevraagd wijzigen.

De gebruiker heeft de opschoning goedgekeurd met drie expliciete grenzen:
alle bestaande bronexpressies blijven letterlijk behouden, bestaande
alerttekst blijft ondersteund en historische resourcepaden vervallen volledig.
De toen aangepaste invoerfunctie is inmiddels vervangen door het expliciete
[nullcontract van D-ESP-014](0014-null-fields-expression-contract.md).

Belangrijkste risico's zijn een onbedoelde wijziging van productieconfiguratie,
verlies van alertpresentatie en timestamps die bij cachelezing doorschuiven.
Daarom toetsen we tegen bevroren echte 0.2.3-expressies, behouden kaarttests voor
oude alerttekst en behouden de observation-/providerwisseltests voor alle drie
providers. Oude labconfiguraties worden expliciet geweigerd in plaats van
stilzwijgend anders geïnterpreteerd.

## Ondersteund upgradepad

- Alleen Web API-configuratie 1.1 met expressieschema 4 uit productie 0.2.3
  wordt omgezet naar config-entryschema 1.9 / expressieschema 11.
- De migratie actualiseert schema-/revisie- en vereiste-bronveldmetadata.
  Alle opgeslagen expressies worden gekopieerd zonder vervanging, aanvulling
  met fabriekswaarden, tokenherschrijving of normalisering. Ook de exacte
  expressie `last_update` blijft een bronveld, geen functieaanroep.
- UIDs, systeem- en bron-ID's, instellingen en entiteitidentiteiten blijven
  intact. De migratie verwijdert geen entiteiten uit het register.
- Een reeds foutieve expressie blijft bewaard en wordt gelogd; die fout mag
  gezonde systemen niet blokkeren. Ongeldige opslagmetadata voorkomt alle
  writes vóór publicatie. Reeds actuele entries vereisen geen migratie.
- Labmigraties voor schema's 5–10, aparte alertinstellingen, MQTT UUID/root en
  Native `/uart1` vervallen. Herstel daarvan vereist bijpassende oude code en
  back-up, of een schone configuratie.

Dit is een noodzakelijke migratie van opslagmetadata, geen migratie van de
betekenis of tekst van bronexpressies.

## Eén alertfunctie en behoud van bestaande tekst

`solar_thermal_alerts(null(reporting, pump, collector, tank_top), hot,
danger, idle_delta, active_delta)` is de enige vorm. De vier thresholds zijn
constante expressies en de vier invoerwaarden worden onafhankelijk optioneel
gemaakt. De helper geeft uitsluitend lokaal afgeleide regels terug.

De negenargumentvorm, het vijfde gegroepeerde bronalertargument en de bijbehorende
bronalertnormalisatie/merging verdwijnen. Bestaande `join_lines(alerts)`-
expressies blijven werken. De kaart blijft JSON, bestaande Python-dicttekst,
CR/LF-records en de presentatienaam `pump_wrong` ondersteunen. Unicode in JSON
blijft ongewijzigd; de huidige recordseparator is U+001E.

## Eén intern runtimecontract

Alle systemen leveren `ProviderStatusSnapshot` met bronwaarden, rapporttijd en
wijzigingstijd. De oude dict-statuswrapper, dict-uitwijkroute van de coordinator
en runtime-uitwijkroutes voor de oude afhankelijkheidsvelden verdwijnen.
Pushproviders vullen uitsluitend via echte callbacks/PUBLISH-events de
gemeenschappelijke observationcache; een periodieke cachelezing voegt geen
transportafgeleide compatibiliteitsvelden toe en verschuift geen timestamps.
De bestaande 0.2.3-contracten voor externe entiteitswaarden blijven intact.

## Kaart en resources

Iedere expliciete kaartnaam blijft behouden, ook `Web API` en `ESPHome Native`.
Zonder expliciete naam toont de kaart dynamisch `provider_id/system_id` in
kop en footer. Voor resources beheert de integratie uitsluitend het huidige
`/solesta/solesta-status-card.js`-pad: versie bijwerken en duplicaten van dat
pad verwijderen. De oude `/local/...`- en `/solestanext/...`-paden worden niet
herkend, geregistreerd of gemigreerd.

## Actuele nulinvoer

De beschrijving van de voormalige algemene foutafhandeling is ingetrokken.
[D-ESP-014](0014-null-fields-expression-contract.md) legt het actuele
veldcontract, de argumentbeperking en de betekenis van `None`/`none` vast.

## Versies en verificatie

Het bestaande huidige formaat en de catalogus blijven gelijk: kandidaat,
manifest, kaart en resource 1.0.0; config-entry 1.9; expressieschema 11;
catalogus 15. Gegenereerde modules worden niet handmatig aangepast.

Dit besluit vervangt de labcompatibiliteitsonderdelen uit D-ESP-007, 008 en 011.
Historische acceptatieverslagen blijven bewijs voor hun toenmalige kandidaat;
zij bewijzen de gewijzigde kandidaat niet opnieuw. Nieuwe controles en grenzen
staan in het [uitvoeringsverslag](../results/compatibility-cleanup-2026-11-13.md).
