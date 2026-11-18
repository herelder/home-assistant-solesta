# D-ESP-007 — Provider-onafhankelijke expressies en optionele evaluatie

> Actualisering 13 november 2026: [D-ESP-013](0013-production-baseline-compatibility-cleanup.md)
> vervangt de hieronder beschreven labcompatibiliteit en expressie-/bron-ID-migraties.
> Alleen productie 0.2.3 is een oud upgradepad; alle opgeslagen expressies blijven
> letterlijk behouden. De historische onderbouwing hieronder blijft leesbaar.


Datum: 27 oktober 2026

Status: aanvaard door de gebruiker; geïmplementeerd in kandidaat 0.2.5

## Aanleiding en risico's

De [review van de releasekandidaat](../results/solesta-hacs-release-candidate-review-2026-10-26.md)
toonde onder meer dat ontbrekende pompgegevens onafhankelijke alarmregels
konden blokkeren, dat een schemaupgrade bestaande expressies kon vervangen en
dat een verouderde duplicaatkoppeling de hele provider kon tegenhouden.
De herstelkeuzes zijn door de gebruiker vastgesteld. Dit besluit vervangt de
providerafhankelijke standaardexpressies en de expressieherschrijving uit de
eerdere implementatie van D-ESP-006.

De belangrijkste regressierisico's zijn stil verlies van een bestaande
configuratie, het verbergen van echte meetfouten en het onbedoeld wijzigen van
een identiteit. Daarom blijven bestaande expressieteksten en lokale
identiteiten behouden, blijven oorspronkelijke evaluatiefouten zichtbaar en
wordt alleen expliciet optionele foutpropagatie onderbroken.

## Eén canonieke fabrieksexpressie

De systeemlaag en entiteitsopbouw kennen geen providertype. Alleen
`EntityDescriptions.xlsx` bepaalt de fabrieksexpressies. Hardcoded
ESPHome-standaarden zijn verwijderd. Nieuwe ESPHome-systemen vereisen daarom
handmatig ingestelde bronexpressies wanneer hun bronvelden afwijken van de
catalogus. Een providerwissel mag uitsluitend de `source_system_id` invullen;
de gebruiker beoordeelt en wijzigt de expressies.

Een upgrade verandert **geen enkele bestaande source-expression**. Dit geldt
ook voor teksten die overeenkomen met een vroegere fabrieksexpressie.
Migratie voegt alleen nieuwe ontbrekende entiteitssleutels uit de catalogus
toe en actualiseert schema- en afhankelijkheidsmetadata. Bestaande waarden,
inclusief spaties, blijven behouden. De nieuwe standaardalertketen wordt dus
ook niet automatisch in bestaande systemen geplaatst.

## Actuele invoerfunctie

De vroegere uitleg van een algemene evaluatiefoutbeschermer is ingetrokken.
Het actuele `null()`-contract staat in
[D-ESP-014](0014-null-fields-expression-contract.md). Alleen afzonderlijke
velden of veldvrije expressies/constanten zijn argumenten. De catalogus gebruikt
`perc_pump_pwm > 0` voor de pompstatus en vier velden in `null(...)` voor alerts.
`None` en `none` zijn in bronexpressies gewone veldnamen.

## Systeemisolatie en duplicaten

Een foutieve of verouderde duplicaatkoppeling verhindert niet dat andere
correct geconfigureerde actieve systemen starten. Ongeldige duplicaten worden
afzonderlijk overgeslagen. Een echte ontdekte bron heeft bij een aliasbotsing
voorrang. Ook een al ongeldige systeemexpressie blokkeert de schemaupgrade van
geldige zustersystemen niet.

Herconfiguratie biedt uitsluitend echte bronnen van de huidige provider aan.
Een oud bron-ID wordt niet als kunstmatige keuze toegevoegd. Een uitgeschakeld
systeem mag zijn ongewijzigde oude koppeling bewaren. Activeren of een andere
bron kiezen vereist een actuele, live gevalideerde bron.

Bij een duplicaat is de communicatiebron opnieuw te kiezen; de lokale alias,
`system_uid`, entiteiten en opgeslagen expressies blijven behouden. Alleen het
kiezen en valideren van een andere bron verandert de koppeling. De drieledige
mergecontrole omvat ook deze communicatiebron.

## Overige herstelcontracten

- `drop()` is interne catalogusconfiguratie. Een gebruiker krijgt bij gebruik
  in een ander veld een expliciete formulierfout. Eerder opgeslagen onjuist
  gebruik blijft zichtbaar en kan worden gecorrigeerd. Interne archiefvelden
  blijven verborgen en behouden hun opgeslagen expressie.
- Een provider-ID wordt na asynchrone verbindingsvalidatie opnieuw gecontroleerd
  en zonder tussenliggende `await` geclaimd en opgeslagen. Mislukt opslaan,
  dan wordt de claim vrijgegeven; bestaande afbreekafhandeling blijft gelden.
- ESPHome-`missing_state`, NaN en oneindige metingen worden geen echte nul of
  verse meetset. Een onbekende waarde wist ook een eerder geldige cachewaarde.
  Alleen echte complete metingen of geldige bronouderdom verversen de tijd;
  een los geldig-signaal doet dat niet.
- Recordscheiding gebruikt RS (`U+001E`) wanneer aanwezig, anders uitsluitend
  CRLF, CR of LF. Unicode-tekens zoals `U+2028` in JSON-tekstvelden worden niet
  als recordscheiding behandeld. Python en dashboard volgen hetzelfde contract.
- `aioesphomeapi>=46.2.0` laat de door Home Assistant gekozen versie toe. De
  minimumcombinatie HA 2026.9.0/client 46.2.0 en HA 2026.10.4/client 46.6.0
  krijgen afzonderlijke tests met de echte bibliotheken.

## Versies en acceptatie

Manifest, kaart en resourceversie zijn 0.2.5. Het config-entryschema is 1.4,
het expressieschema 7 en de catalogusrevisie 10; providerpresetrevisie 3 en
archiefformaten veranderen niet. Generatie gebeurt uitsluitend via de
canonieke werkmap en generator.

De historische aanscherping van 30 oktober 2026 maakt de toenmalige hulp variadisch en groepeert
de vijf optionele alertinputs. Daardoor wordt het config-entryschema 1.6, het
expressieschema 9 en de catalogusrevisie 12 in kandidaat 0.2.6. Opgeslagen
expressies worden ook bij deze migratie niet herschreven; de evaluator blijft
de vroegere negenargumentenvorm van `solar_thermal_alerts()` accepteren.

De daaropvolgende vereenvoudiging schrapt de vier alertdrempelentiteiten en
plaatst hun waarden als constanten in `alerts_system`. Dit verhoogt het
config-entryschema naar 1.7, het expressieschema naar 10 en de catalogusrevisie
naar 13. Deze migratie vormt de expliciete uitzondering op bytegelijk behoud:
zij voegt de opgeslagen drempelwaarden in de resterende expressies in en
verwijdert uitsluitend de vier vervallen entiteitssleutels en hun oude
vermeldingen in het Home Assistant-entiteitenregister.

De fabrieksexpressies refereren daarna niet langer aan de ongebruikte
Solesta-bronnen `alerts` en `temp4`: de vijfde optionele alertinput en
`temp_reserved` zijn aanvankelijk `None`. De catalogusrevisie stijgt hierdoor
naar 14. Het config-entryschema en expressieschema veranderen niet, en reeds
opgeslagen source-expressies worden niet herschreven.

Op 1 november 2026 is de nullwaarde expliciet gemaakt met de nieuwe
nulargumentfunctie `null()`. `temp_reserved` gebruikt voortaan `null()` en de
fabrieksexpressie voor `alerts_system` geeft uitsluitend de vier werkelijk
gebruikte optionele waarden door. De evaluator blijft zowel de eerdere
vijfwaardige groepsvorm als de negenargumentenvorm ondersteunen voor bestaande
configuraties. De catalogusrevisie stijgt naar 15; config-entryschema en
expressieschema blijven gelijk en opgeslagen expressies worden niet
automatisch herschreven.

De daaropvolgende verwijdering van de laatste Native-specifieke
broninterpretatie verhoogt het config-entryschema naar 1.8 en het
expressieschema naar 11. Alleen de exacte oude fabrieksexpressie
`last_report = last_update` wordt daarbij `last_report()`; andere aangepaste
expressies blijven ongewijzigd.

Het [herstelverslag](../results/solesta-review-fixes-2026-10-27.md) bevat de
uitgevoerde controles. Dit besluit is geen opdracht voor installatie,
herstart of publicatie. De eerder uitgevoerde herstelkopieacceptatie van
0.2.4 bewijst niet de live werking van deze nieuwe kandidaat. Gebruikersuitleg,
publicatiecontrole van acceptatierapporten en definitieve releasenummering
blijven afzonderlijk werk in fase 6.
