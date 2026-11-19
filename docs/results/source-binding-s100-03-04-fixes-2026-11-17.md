# Bronbinding — herstel S100-03 en S100-04

Datum: 17 november 2026.

Basis: branch `codex/esphome-provider`, commit
`a4214fd871675b5f176db542d8946eed56935e42`, met het eerder lokaal uitgevoerde
[NanoC6-herstel](nanoc6-s100-01-02-fixes-2026-11-17.md).
De wijzigingen zijn lokaal en niet geïnstalleerd of gepubliceerd.

## Herstel

Volgens [D-ESP-017](../decisions/0017-duplicate-and-own-source-binding.md):

| Bevinding | Uitvoering |
| --- | --- |
| S100-03 | Runtimeopbouw controleert eerst de duplicaatkoppeling en compileert daarna tegen de veldtabel van het communicatiedoel. Dit is dezelfde bron die live validatie en hubherconfiguratie gebruiken. De lokale alias blijft behouden voor de systeemidentiteit en providerstatusroute. |
| S100-04 | Een eigen entiteitsnaam in de eigen expressie blijft een bronverwijzing, maar gebruikt nu dezelfde canonieke bronresolver als andere bronverwijzingen. Unieke korte paden binden; ambigue paden worden afgewezen, ook binnen `null(...)`. |

De runtimewijziging beperkt zich tot `configuration.py` en `compile.py`.
Providers, entiteitsplatformen, kaart en archivering krijgen geen nieuwe
providerspecifieke logica. Er is geen opslagmigratie of expressieherschrijving.
Schema's en kandidaatversie 1.0.0 blijven gelijk; de eerdere firmwarecorrectie
blijft 0.1.1. De gebruikershandleiding verduidelijkt de eigenveldregel.

## Regressiebewijs

De nieuwe tests zijn eerst tegen de ongewijzigde runtime uitgevoerd. De
kopiebinding faalde in alle vijftien onderzochte combinaties; de
eigenveldproeven toonden verkeerde binding, ontbrekende ambiguïteitsafwijzing
en te late ontbrekendebroncontrole. Dezelfde tests slagen na de twee kleine
runtimecorrecties.

De HA-regressie toetst vijf naam-/providercombinaties bij eerste setup, een
nieuw providerlifecycle en herkoppeling: Native met gewone/absolute namen en
MQTT met korte/volledige/absolute namen. Voor iedere combinatie worden
werkelijke live validatie, runtimecompilatie, statusophaling en evaluatie
vergeleken. Zij controleert het juiste doel en de veldtabel, de gewijzigde
meting na herkoppeling, behoud van alias/UID/subentry en ongewijzigde opslag.
Native gebruikt aparte hoofd-/subdevicecatalogi; MQTT aparte bronroots.

Vier nieuwe compilerregressies toetsen unieke geneste eigenvelden tegenover
de expliciete apostrofvorm, ambiguïteit met en zonder nullable invoer,
ontbrekende vereiste/nullable eigenbronnen en hoofdlettergevoelige `None`/`none`.
Andere entiteitsnamen blijven afhankelijkheden; eigen bronnen worden geen
cirkelverwijzingen. Bestaande tests behouden cyclus- en alertfoutpropagatie.

## Controles

Uitgevoerd op een schone kopie van de niet-genegeerde bronbestanden, met logs
buiten de kandidaatboom:

| Controle | Resultaat |
| --- | --- |
| `tools/build.py --check` | Beide runtimecatalogi reproduceerbaar |
| `tools/build_lab.py --check` | Deterministisch; build-ID `3c03d995f620` |
| Ruff | Geslaagd |
| Volledige Python-suite | **308 tests geslaagd** |
| HA 2026.9.0-contractsuite | **33 tests geslaagd**, zelfstandige Python 3.14.10 |
| HA 2026.10.4-contractsuite | **33 tests geslaagd**, dezelfde zelfstandige Python |
| Dashboard | **33 bestaande assertions geslaagd** via de eerder vastgelegde Node REPL-callbackharness; geen native `node --test`-claim |
| Diffcontrole | Geen witruimtefouten |

De volledige suites omvatten de 0.2.3-metadata-upgrade met letterlijk behoud
van opgeslagen expressies, de Web API-route, providerwissels en isolatie van
ongeldige/uitgeschakelde kopieën. De gegenereerde bestanden en hun werkboeken
zijn ongewijzigd.

Tijdelijk bewijs staat in `/private/tmp/solesta-source-binding-fixes-20261117/`
en de voor/na-uitvoer `s100-03-*.log` en `s100-04-*.log` onder `/private/tmp/`.
De regressies staan blijvend in `tests/ha_release_contracts.py` en
`tests/test_review_regressions.py`.

## Begrenzing

De proeven gebruiken echte HA-klassen en provider-/compiler-/evaluatorcode,
met gesimuleerde verbindingen en opslag. Herladen en herkoppelen zijn lokaal
beproefd via nieuwe providerinstances en runtimeopbouw, niet via een echte
HA-herstart. Er is geen live configuratie, apparaat of Recorder benaderd.

De oorspronkelijke review blijft bewijs voor zijn oorspronkelijke kandidaat.
Deze opdracht herstelt alleen S100-03 en S100-04. De overige open bevindingen
en de bestaande releaseacceptatiepunten blijven afzonderlijk staan. De schone
releasecheckout is niet bijgewerkt; er is niets gecommit of gepubliceerd.

## Aanvullende netwerkacceptatie op 18 november

De geïnstalleerde Lab-code is daarna met echte Native- en MQTT-verbindingen
beproefd, met geïsoleerde HA-configuratieopslag. S100-03 en S100-04 slagen;
de oorspronkelijke live configuraties zijn ongewijzigd gebleven. Zie het
[acceptatieverslag S100-03 t/m S100-07](s100-03-07-network-acceptance-2026-11-18.md)
voor de varianten en de grens tussen echte verbindingen, discoveryfixtures
en een volledige HA-herstart.
