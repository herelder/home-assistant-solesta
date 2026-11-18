# M7 — gezamenlijke releasevoorbereiding Solesta 1.0.0

> Historisch testbewijs voor de kandidaat van 5 november 2026. De opschoning
> van 13 november heeft het migratiecontract gewijzigd: opgeslagen expressies
> worden nu zonder uitzondering letterlijk behouden. De oude proef bewijst
> deze gewijzigde kandidaat niet opnieuw. Zie het
> [nieuwe wijzigings- en testverslag](compatibility-cleanup-2026-11-13.md).


Datum: 5 november 2026

Status: lokale releasevoorbereiding uitgevoerd voor kandidaat **1.0.0**;
publieke release nog niet vrijgegeven. HACS/CodeQL op de uiteindelijke
GitHub-ref blijven open. De lokale macOS-interpreter heeft een afzonderlijk
afsluitprobleem, hieronder expliciet begrensd.

Scope: Web API, ESPHome Native en MQTT samen. Deze fase omvat gebruikersuitleg,
publicatie/privacycontrole, versienummering, releasevalidatie en een actuele
productie-upgradeproef op een herstelkopie. Productieplaatsing en publieke
release vallen onder een afzonderlijk besluit.

## Gebruikersdocumentatie

- De [configuratiehandleiding](../installation.md) beschrijft de GUI-flow voor
  alle drie providers, bronkeuze, activering, herconfiguratie en providerwissels.
- De [source-expressionhandleiding](../source-expressions.md) behandelt
  bronvelden, entiteitsafhankelijkheden, conversies, naamkwalificatie,
  optionaliteit, timestamps, alerts, instellingen en validatie.
- De [energieformules en vergelijking met Solesta](../energy-calculations.md)
  zijn inhoudelijk behouden; de verwijzingen vanuit de handleidingen zijn
  uitgebreid.
- README, entiteiten, dashboard, duplicaten, probleemoplossing, privacyuitleg,
  changelog en [release notes](../release-notes.md) zijn op dezelfde kandidaat
  afgestemd. De uitleg is tegen de actuele formulieren en broncode nagegaan.
- Twintig voorbeelden zijn daadwerkelijk met de compiler/evaluator uitgevoerd;
  alle lokale Markdown-verwijzingen, ook in de onderliggende plannen en
  verslagen, zijn gecontroleerd.

## Versies en compatibiliteit

Manifest en kaart gebruiken 1.0.0. Het functionele broncontract verandert in
deze fase niet: config-entryschema 1.9, expressieschema 11 en catalogusrevisie
15 blijven van kracht. De release notes leggen de bestaande, specifiek
vastgestelde compatibiliteitsmigraties uit.

| Onderdeel | Kandidaat |
| --- | --- |
| Integratie, kaart en resourcecache | 1.0.0 |
| Config-entryschema | 1.9 |
| Expressieschema | 11 |
| Catalogus | revisie 15; 21 entiteitsdefinities |
| Providerpreset | revisie 3, ongewijzigd |
| Reproduceerbare labbuild | `03eb4fead7af` |

In M7 zijn geen bronmapping, rekenformule of providerimplementatie gewijzigd.
De functionele bron is die van de geaccepteerde 0.2.6-kandidaat. Manifest en
kaart zijn naar 1.0.0 gebracht, versieasserties zijn afgestemd en de HA-testjob
installeert nu expliciet de al vereiste `aiomqtt==2.5.1`. Die afhankelijkheid
ontbrak in de workflow voor de afzonderlijke HA-contracttests.

## Lokale releasecontroles

De controles zijn op een schone kandidaatkopie uitgevoerd, zonder privédata,
virtuele omgevingen of gegenereerde testbestanden in de publicatieboom.

| Controle | Resultaat |
| --- | --- |
| Canonieke generatorcheck | `thetruth.py` en `provider_defaults.py` actueel |
| Deterministische labbuildcheck | geslaagd |
| Python-suite | 300 tests geslaagd |
| Dashboardkaart | 33 tests geslaagd |
| HA 2026.9.0 / native client 46.2.0 / aiomqtt 2.5.1 | 24 contracttests geslaagd |
| HA 2026.10.4 / native client 46.6.0 / aiomqtt 2.5.1 | 24 contracttests geslaagd |
| Ruff 0.16.7, zoals vastgelegd voor CI | geslaagd |
| Officiële Hassfest uit HA Core 2026.10.4 | 1 integratie; 0 ongeldig |
| Gedocumenteerde expressievoorbeelden | 20 geslaagd |
| Lokale documentatielinks, recursief | geen ontbrekende bestanden |
| Formulevergelijking met Solesta | inhoudelijk behouden |
| Diffcontrole | geen witruimtefouten |

De HA-contractsuite is daarnaast met een apart gehouden Python 3.14.10
uitgevoerd: opnieuw 24 geslaagd. Dit is geen wijziging van HA of de
Python-installatie in productie.

## Actuele productie-upgrade op een native herstelkopie

Home Assistant maakte op 5 november 2026 om 12:21:50 UTC via de Companion-app
een native handmatige back-up met instellingen, historie en apps. De lokaal
gedownloade export is 314.726.400 bytes. SHA-256:
`643a61e789a6fce7fd29bf81d1552c7909fde8bab789bda8834d07db37d29450`.
Alleen het Home Assistant-deel is voor de proef uitgepakt; bewijs, opslag,
database en credentials blijven in de genegeerde privéwerkmap.

Uit die consistente kopie zijn uitsluitend de productie-`solesta`-entry,
bijbehorende registers, dashboardopslag en Recorderkopie in een aparte
HA 2026.10.4-configuratie opgenomen. HTTP luisterde op `127.0.0.1`; de
bestaande Web API is voor de normale meetophaling gebruikt. De native en
MQTT-labentries uit de back-up zijn niet in deze proef gestart. Er is geen
actieve Recorderdatabase via SMB geopend of gekopieerd.

| Meetpunt | 0.2.3-nulmeting | 1.0.0 eerste start | 1.0.0 tweede start | 0.2.3 terugrolkopie |
| --- | --- | --- | --- | --- |
| HA config entry | geladen | geladen | geladen | geladen |
| Config-entryschema | 1.1 | 1.9 | 1.9 | 1.1 |
| Expressieschema | 4 | 11 | 11 | 4 |
| Bestaande registry-entiteiten | 21 | 21 | 21 | 21 |
| Solesta-apparaten | 1 | 1 | 1 | 1 |
| Actieve systemen / succesvolle coordinator | 1 / ja | 1 / ja | 1 / ja | 1 / ja |
| Entiteiten met bruikbare actuele state | 18 | 18 | 18 | 18 |

Alle bestaande registry-ID's, entity-ID's, unique ID's, hub- en systeem-UID's,
config-/subentrykoppelingen, apparaatkoppelingen en `disabled_by`-waarden
bleven behouden. Er zijn geen vervangende entiteiten of dubbele apparaten
aangemaakt. De tweede start behield de volledige Solesta-config-entry,
entiteitsrecords en apparaatrecords ongewijzigd.

Van de 21 oorspronkelijke expressies veranderde uitsluitend `last_report`,
van exact `last_update` naar `last_report()`, conform het vastgestelde
compatibiliteitscontract. Er zijn geen expressies toegevoegd of naar nieuwe
fabrieksformules teruggezet. De bestaande bronmapping en Web API-koppeling
bleven behouden.

De 19 entiteiten met opgeslagen historie behielden exact **99.279**
oorspronkelijke state-rijen, inclusief hun eerste en laatste timestamp. De
vergelijking was begrensd op het hoogste state-ID uit de back-up, zodat nieuwe
testmetingen niet als ontbrekende of extra oude historie tellen. De
Recorder-integriteitscontrole gaf `ok`. De bestaande kaartresource werd in
plaats bijgewerkt naar `/solesta/solesta-status-card.js?v=1.0.0`.

De terugrolproef startte de oorspronkelijke 0.2.3-code met de oorspronkelijke
configuratie en Recorderkopie uit dezelfde native back-up. Dit bewijst het
backup-pad; alleen oude Python-bestanden over een gemigreerde opslag zetten
is geen geteste downgrade.

### Begrenzing van de macOS-proef

De minimale lokale HA-omgeving mist enkele voor deze Solesta-proef niet
gebruikte kerncomponentafhankelijkheden, waaronder camera/conversation en de
Supervisor-client. Die geven setupmeldingen; Solesta, frontendresource en
Recorder zijn afzonderlijk gecontroleerd. Dit is geen volledige HA OS-test.

Na de geslaagde HA-stop trad in meerdere lokale processen een native
Python-`SIGSEGV` op tijdens modulefinalisatie (`dictkeys_decref`,
`gc_collect_main`, `finalize_modules`). Dit gebeurde zowel met de kandidaat
als met de oorspronkelijke 0.2.3-terugrolkopie, en ook met een apart
gedownloade Python 3.14.10 naast de bestaande 3.14.6. De precieze veroorzakende
runtime/extension is niet vastgesteld. Er is geen productcode aangepast om
de interpreterfout te maskeren.

De geladen entry, succesvolle metingen, bewaarde identiteit/historie en
idempotente migratie zijn vóór die modulefinalisatie vastgelegd. De verse
Recorder-run had na HA-stop een eindtijd en `closed_incorrect=0`.
Deze resultaten gelden; een foutloze procesafsluiting van de lokale
macOS-testomgeving is **niet** bewezen. Behoud deze beperking bij het
releasebesluit en voer de uiteindelijke kandidaat-smokecontrole op de
doelomgeving uit vóór productiegebruik.

## R08/R09 en publiceerbaar bewijs

R08 is inhoudelijk afgehandeld met de gezamenlijke installatie-, expressie-,
upgrade- en privacyhandleidingen. R09 is afgehandeld voor de kandidaatboom:
11 verslagen/plannen/besluiten hebben publicatiekopieën met consistente
pseudoniemen voor installatie-, apparaat-, systeem-, register- en
netwerkidentificatoren. Het verband tussen herhaalde identificatoren blijft
zichtbaar; meetwaarden, tijden en uitkomsten zijn behouden. De oorspronkelijke
bewijsstukken en de omzettingstabel zijn privé bewaard.

De controle van kandidaattekst vond geen oorspronkelijke identificatoren uit
die tabel of credentialpatroonhits. Dit is een gerichte controle, geen
garantie dat iedere denkbare gevoelige waarde door een patroon herkenbaar is.
De firmwaretemplate gebruikt secretverwijzingen voor API-key en Wi-Fi.

De openbare remote bevatte bij controle geen `codex/esphome-provider`-branch.
Publiek `main` stond op `bccaee942ec20fe906f7ea3dd4a9978f1abba0b6`; de vier
bereikbare publieke commits bevatten geen van de gecontroleerde oorspronkelijke
installatie-identificatoren. De lokale projectgeschiedenis bevat die
oorspronkelijke stukken nog wel en mag daarom **niet** worden gepusht of
samengevoegd voor publicatie.

Er is een schone kandidaatkopie zonder `.git` of privéwerkdata voorbereid.
De [publicatieroute](../maintainer-security.md#publish-the-100-candidate-without-private-project-history)
is een nieuwe branch vanaf de gecontroleerde publieke basis, met uitsluitend
de geïnspecteerde kandidaatbestanden als nieuwe wijziging. Er is geen publieke
geschiedenis herschreven en er is niets gepusht.

## Nog vóór publieke release

1. Beoordeel de genoemde macOS-testbeperking en voer een kandidaat-smokecheck
   op de beoogde HA-doelomgeving uit onder afzonderlijke installatieopdracht.
2. Maak de schone releasebranch volgens de beschreven publicatieroute;
   controleer opnieuw als publieke `main` inmiddels is veranderd.
3. Laat HACS, Hassfest, tests en CodeQL op de uiteindelijke GitHub-ref lopen.
   De [officiële HACS Action](https://hacs.dev/docs/publish/action/) controleert
   een GitHub-ref; hij is voor deze ongepubliceerde lokale kandidaat niet
   uitgevoerd. Lokale Hassfest en structuurchecks vervangen die actie niet.
4. Neem het afzonderlijke besluit over publiceren en live productie-upgrade.

Productie blijft `solesta` 0.2.3; Solesta Lab blijft 0.2.6. Er is in M7 geen
integratie op de live HA-installatie vervangen en geen live HA-herstart gedaan.
