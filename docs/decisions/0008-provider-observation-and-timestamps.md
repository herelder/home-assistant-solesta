# D-ESP-008 — Provider-onafhankelijke observatie en timestamps

> Actualisering 13 november 2026: [D-ESP-013](0013-production-baseline-compatibility-cleanup.md)
> vervangt de hieronder beschreven labcompatibiliteit en expressie-/bron-ID-migraties.
> Alleen productie 0.2.3 is een oud upgradepad; alle opgeslagen expressies blijven
> letterlijk behouden. De historische onderbouwing hieronder blijft leesbaar.


Datum: 29 oktober 2026; naamcontract definitief aangescherpt op 29 oktober 2026

Status: aanvaard en geïmplementeerd in de 0.2.6-kandidaat (M3);
volledige contractacceptatie volgt in M4

## Aanleiding

`last_report()` en `last_update()` zijn geen MQTT- of ESPHome-eigenschap. Zij
beschrijven wat de Solesta-integratie lokaal heeft waargenomen en moeten daarom
voor alle drie providerprotocollen hetzelfde contract volgen:

- `web_api` levert complete statussnapshots via polling;
- `esphome_native` levert losse statecallbacks;
- `mqtt` levert losse PUBLISH-berichten onder een handmatig gekozen root.

Een broker voegt geen oorspronkelijk publicatietijdstip toe. Ook een Web API-
response of ESPHome-state hoeft geen bruikbare brontimestamp te bevatten. De
integratie stelt deze tijden daarom zelf vast met een injecteerbare UTC-klok.

Dit besluit vervangt voor timestamps:

- het Native-specifieke complete-golf-/barrièrecriterium uit D-ESP-002;
- de regel uit D-ESP-006 dat alleen een volledige geldige meetset
  `last_report` mag verversen.

De overige identiteits-, expressie-, fout-, timeout- en afleidingscontracten
uit die besluiten blijven gelden.

## Besluit: één observatielaag voor alle providers

Er komt één provider-onafhankelijke observatielaag. Per echte
communicatiebron bewaart die laag:

```text
last_report
state[key] = {present, value, changed_at}
```

`value` is een defensieve kopie van de ruwe expression-visible providerwaarde.
De observatielaag kent geen temperatuur, pomp, eenheid, JSON-betekenis,
geldigheidsgrens of Solesta-record. Zij vergelijkt alleen aanwezigheid, type en
waarde.

De vergelijking is typegevoelig en structureel:

- `True` en `1` zijn verschillend;
- mappings worden op keys en waarden vergeleken, niet op invoegvolgorde;
- lijsten en tuples zijn volgordegevoelig en onderling verschillende typen;
- twee NaN-floats gelden voor cachevergelijking als dezelfde ruwe state;
- bytes en tekst zijn verschillende typen.

Zo leidt een ongewijzigde state niet door Python-typecoercion of NaN-gedrag tot
een kunstmatige update. De vergelijking interpreteert de inhoud niet.

Een lokale alias of duplicaat deelt de observatie van zijn echte
communicatiebron. `last_update()` wordt wel per Solesta-systeem berekend,
omdat duplicaten verschillende source-expressies en dus verschillende
gerefereerde keys mogen hebben.

## Rapportregels per provider

Een report is uitsluitend een geaccepteerde statuswaarneming voor één
communicatiebron:

| Provider | Eén report | Statusmodel |
| --- | --- | --- |
| Web API | één succesvol gevalideerde `system_status_flow` | volledige, gezaghebbende snapshot |
| ESPHome Native | één gedecodeerde statecallback van de gekoppelde bron | losse key/value-update |
| MQTT | één PUBLISH onder de geconfigureerde `<root>/#` | losse relatieve-topic/payload-update |

Connect-, discovery-, profiel-, ping- en disconnectverkeer is geen report. Een
MQTT-PUBLISH onder de root is wel een report, ook als de key niet in een
expressie wordt gebruikt. Availability-, LWT-, log-, teller- en
barrièretopics krijgen daarbij geen bijzondere betekenis.

Voor Web API geldt de teruggegeven mapping als complete snapshot. De
observatielaag vergelijkt de nieuwe mapping met de vorige mapping. Een
overgang aanwezig → ontbrekend of ontbrekend → aanwezig is voor die key een
statewijziging. Een mislukte, afgewezen of ongeldige poll verandert cache noch
timestamps.

Voor Native en MQTT is de cache cumulatief: stilte verwijdert geen key. Een
MQTT-bericht met een lege payload is de basale waarde `""`; de provider leidt
daar geen verwijdering of brokerretentiebetekenis uit af.

Een MQTT-payload wordt voor source-expressies strikt als UTF-8-tekst
gedecodeerd, zonder trimmen, JSON-parsing of numerieke omzetting. Een payload
die geen geldige UTF-8 is, telt wel als ontvangen report maar vervangt geen
expression-visible state; de provider registreert alleen een begrensde,
geredigeerde foutclassificatie.

## `last_report()`

`last_report()` retourneert de aware UTC-`datetime` van het laatste report van
de communicatiebron, of `None` zolang geen report is geaccepteerd.

Daaruit volgen vaste regels:

1. iedere succesvolle Web API-statuspoll verzet `last_report`, ook wanneer de
   complete snapshot gelijk is aan de vorige;
2. iedere Native-statecallback verzet `last_report`, ook bij een identieke of
   ongebruikte state;
3. iedere MQTT-PUBLISH onder de root verzet `last_report`, ook bij een
   identieke, retained of ongebruikte state;
4. een fout, timeout, reconnectpoging of herevaluatie van een oude cache verzet
   `last_report` niet.

## `last_update()`

De compiler levert voor ieder systeem de volledige verzameling gerefereerde
bronkeys, niet alleen de verplichte keys. Keys die uitsluitend binnen
`null(...)` staan, tellen dus eveneens mee.

`last_update()` retourneert de meest recente `changed_at` van de keys die in
enige source-expression van het actuele systeem worden gebruikt. Als nog geen
van die keys is waargenomen, retourneert de functie `None`.

Daaruit volgen vaste regels:

1. de eerste waargenomen waarde van een gebruikte key vestigt de baseline en
   telt als update;
2. een type- of waardewijziging van een gebruikte key verzet `last_update`;
3. een identieke waarde verzet alleen `last_report`;
4. een wijziging van een ongebruikte key verzet alleen `last_report`;
5. een Web API-key die uit een nieuwe complete snapshot verdwijnt, telt als
   wijziging wanneer die key wordt gebruikt;
6. retained MQTT-replay en Native-replay volgen dezelfde vergelijking;
7. bij transient reconnect blijft de cache behouden; een identieke replay
   verzet dan niet `last_update`;
8. na een nieuwe providerlifecycle is de cache leeg en vormen de eerste
   states opnieuw de lokale baseline.

Het toevoegen of verwijderen van een source-expressionkey herschrijft geen
historie. `last_update()` neemt steeds het maximum van de reeds vastgelegde
`changed_at`-waarden van de nu gerefereerde keys.

## Evaluatiecontext

`last_report()` en `last_update()` zijn nul-argumentfuncties in de
evaluatiecontext. Zij zijn geen nagemaakte providerstates en verschijnen niet
in `available_keys` of de ruwe statusmapping.

De coordinator vraagt per refresh één onveranderlijke observatiesnapshot op en
geeft de twee timestamps samen met de ruwe states aan de evaluator. Hierdoor
kan één evaluatie geen mix van twee callbackmomenten zien. Een herevaluatie na
providerfout gebruikt dezelfde ruwe snapshot en dezelfde observatietimestamps;
alleen klokafhankelijke functies zoals `delay_zone()` mogen door de actuele
klok een andere afgeleide waarde geven.

Aanroepen met positionele of keywordargumenten zijn compilefouten. De namen
zonder haakjes blijven gewone bronkeys. Een bestaand bronveld `last_update` en
de nieuwe functie `last_update()` zijn dus expliciet verschillende zaken.

## Gekwalificeerde sourcevelden

Een provider levert intern geen kunstmatig platte veldnaam, maar een
gekwalificeerd bronpad van buiten naar binnen:

```text
("aaaa", "bbbb", "cccc")
```

De bron van zo'n pad is transportspecifiek maar uitsluitend structureel:

- geneste JSON-mappings leveren één segment per objectkey;
- een relatief MQTT-topic wordt op `/` gesplitst, met behoud van lege levels;
- een Native-object-ID is vooralsnog een pad met één segment.

JSON-lijsten worden niet verder doorlopen en blijven één ondoorzichtige
bronwaarde. De MQTT-root is routeconfiguratie en hoort niet bij het bronpad.

Web API verplaatst geneste velden, zoals de huidige waarden onder `metrics`,
niet langer naar het hoofdniveau. De kwalificatielaag maakt zo'n kopie
overbodig en houdt de oorspronkelijke structuur beschikbaar.

### Canonieke expressienaam

De canonieke expressienaam bevat de gecodeerde padsegmenten in omgekeerde
volgorde, gescheiden door `__`:

```text
aaaa/bbbb/cccc  ->  cccc__bbbb__aaaa
metrics/temp_collector  ->  temp_collector__metrics
```

Hierdoor staat het inhoudelijke blad vooraan en kan de gebruiker alleen zoveel
buitenste context toevoegen als voor ondubbelzinnigheid nodig is.

Ieder afzonderlijk segment wordt botsingsvrij en reversibel naar een geldig
identifiersegment gecodeerd. De codering is definitief als volgt:

1. Een leeg segment wordt `_0E`.
2. ASCII-letters blijven ongewijzigd.
3. ASCII-cijfers blijven ongewijzigd, behalve een cijfer aan het begin van
   een segment; dat wordt als byte-escape geschreven.
4. Een gewone interne underscore blijft alleen leesbaar wanneer zij niet naast
   een andere underscore staat en het volgende bronbyte zelf ongewijzigd kan
   blijven: een ASCII-letter of een cijfer 1–9. In alle andere gevallen wordt
   de underscore ge-escaped.
5. Iedere andere underscore en ieder ander UTF-8-byte wordt `_0HH`, waarbij
   `HH` twee uppercase hexadecimale cijfers zijn. Een underscore wordt dus
   `_05F` en `-` wordt `_02D`.

Daarmee kan brontekst niet op een `_0HH`-escape lijken en kan een behouden
underscore niet samen met de escape van het volgende teken alsnog `__`
vormen. De regels garanderen dat een gecodeerd segment zelf nooit `__` bevat
en dat segmentgrenzen eenduidig blijven. Voorbeelden:

```text
sensor/boiler-1/state  ->  state__boiler_02D1__sensor
a//c                   ->  c___0E__a
temp__raw              ->  temp_05F_05Fraw
```

Decodering weigert niet-canonieke escapes en ongeldige UTF-8. Hoofdletters en
kleine letters blijven onderscheiden, zoals bij MQTT-topics en JSON-keys.

### Kortste unieke kwalificatie

Een naam in een source-expression wordt op hele segmenten vergeleken met de
canonieke namen in de sourceveldnamentabel. Kandidaat `K` past bij naam `N`
wanneer:

```text
K == N
of
K begint met N + "__"
```

Er moet precies één kandidaat bestaan. Een exacte naam krijgt geen voorrang
op een tweede langere kandidaat.

Voor de paden:

```text
aaaa/bbbb/cccc  ->  cccc__bbbb__aaaa
aaaa/dddd/cccc  ->  cccc__dddd__aaaa
```

is `cccc` dus ambigu en ongeldig, terwijl `cccc__bbbb` het eerste veld uniek
selecteert. `temp` matcht nooit `temperature__metrics`, omdat matching alleen
op segmentgrenzen gebeurt.

Voor het zeldzame geval dat ook een volledig pad het begin van een langer pad
is, bestaat het gereserveerde absolute anker `_0R__`. Dit anker is geen
bronsegment en kan door de segmentencoder niet uit externe data ontstaan:

```text
_0R__cccc                    # exact top-level veld cccc
_0R__cccc__bbbb__aaaa        # exact dit volledige geneste pad
```

De absolute vorm moet exact één volledig canoniek pad na het anker bevatten.
Zij is ook de enige manier om een nog niet waargenomen, uitsluitend optionele
bronkey vooraf expliciet te declareren. Een onbekende verplichte key blijft een
validatiefout.

### Sourceveldnamentabel en binding

De configuration flow bouwt per systeem een sourceveldnamentabel uit:

- de Web API-schema-/presetpaden en de gevalideerde statussnapshot;
- de Native-entitydiscovery;
- de onder de handmatig gekozen MQTT-root waargenomen relatieve topics;
- expliciet absoluut gedeclareerde, uitsluitend optionele paden.

De compiler resolveert iedere korte naam precies eenmaal tegen die tabel en
bewaart het volledige gekwalificeerde bronpad in de compiled metadata. De
volledige en verplichte referenced-keysets bestaan dus uit exacte paden, niet
uit de door de gebruiker gekozen afkortingen. `last_update()` gebruikt die
exacte volledige set.

De tabel en bindings zijn bevroren voor de actuele configuratierevisie. Een
later nieuw ontvangen topic wordt wel basaal gecachet en telt voor
`last_report()`, maar kan een bestaande expressie niet stilzwijgend anders
laten binden. Bij herconfiguratie wordt de tabel opnieuw opgebouwd; een dan
ontstane ambiguïteit moet de gebruiker met extra kwalificatie oplossen.

De bestaande apostrofsuffix voor het expliciet kiezen van een bronveld boven
een gelijknamige entiteitsafhankelijkheid blijft na deze naamresolutie gelden.

## Compatibiliteit en versies

- Bestaande externe bronkeys met de naam `last_update` blijven gewone
  providerwaarden. De exacte oude fabrieksexpressie `last_report = last_update`
  wordt eenmalig gemigreerd naar `last_report()` omdat de Native-provider geen
  synthetisch bronveld meer mag maken. Andere expressies met `last_update`
  blijven bytegelijk bewaard.
- Framebarrières, `data_valid`, data-age en vergelijkbare publishermetadata
  mogen als gewone bronkeys blijven bestaan, maar mogen de gedeelde
  observatiecache of timestampfuncties niet sturen.
- De fabrieksexpressie voor de entiteit `last_report` wordt voor nieuw
  aangemaakte systemen `last_report()`. De canonieke bron blijft
  `EntityDescriptions.xlsx`.
- Het expressieschema wordt bij implementatie verhoogd van 7 naar 8 vanwege
  de contextfuncties, gekwalificeerde bronpaden en volledige
  referenced-keymetadata.
- Door de gewijzigde fabrieksexpressie wordt de catalogusrevisie bij
  implementatie verhoogd van 10 naar 11.
- De migratie naar die versies voegt alleen ontbrekende cataloguskeys toe en
  verandert geen bestaande expressietekst, conform D-ESP-007.
- De latere historische variadische aanscherping verhoogt in
  kandidaat 0.2.6 het expressieschema verder naar 9 en de gegroepeerde
  alertfabriek verhoogt de catalogusrevisie naar 12. Ook daarbij blijven
  bestaande expressieteksten ongewijzigd.
- Het verwijderen van de vier alertdrempelentiteiten verhoogt daarna het
  expressieschema naar 10 en de catalogusrevisie naar 13. Alleen voor deze
  verwijdering inlineert de migratie de opgeslagen drempelwaarden in de
  resterende expressies en ruimt zij de oude registerentiteiten op.
- Het volledig verwijderen van Native-specifieke broninterpretatie verhoogt
  het expressieschema naar 11 en het config-entryschema naar 1.8. De enige
  expressiewijziging is de hierboven beschreven exacte oude
  `last_report = last_update`-fabrieksexpressie.

## Implementatiegrens

De observatielaag hoort onder het abstracte providercontract, niet in
entiteitsplatformen, kaart, archiefcode of een MQTT-specifieke evaluatorbranch.
Pushadapters gebruiken een eventoperatie; Web API gebruikt een complete-
snapshotoperatie. Beide leveren hetzelfde onveranderlijke resultaatcontract
aan `SystemCoordinator`.

M3 heeft dit besluit in de canonieke bron geïmplementeerd. De implementatie
wijzigt geen live configuratie; de volledige regressie- en contractmatrix
wordt in M4 uitgevoerd.
