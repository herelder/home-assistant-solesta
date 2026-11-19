# D-ESP-018 — MQTT-validatie, exacte roots en credentialwissels

Datum: 17 november 2026.

Status: uitgevoerd in de lokale kandidaat voor reviewpunten S100-05,
S100-06 en S100-07.

## Ontwerp en risico's

Een korte stilte in een MQTT-stream bewijst niet dat alle velden bekend zijn.
Te vroege binding wees geldige gespreide publicaties af. Onbegrensd wachten
zou een formulier echter kunnen laten hangen, en steeds opnieuw binden zou
een bestaande korte naam naar een ander veld kunnen omleiden.

Daarnaast kreeg een externe communicatieroot ten onrechte de trim-/lengteregels
van een lokale kopiealias. Lege credentials namen bij herconfiguratie altijd
het oude wachtwoord over, zelfs bij een verwijderde of gewijzigde gebruikersnaam.

## Besluiten

### Begrensde voorbereiding van de bronveldtabel

- Het generieke providercontract krijgt `async_get_available_keys()` voor
  het voorbereiden van een veldtabel op basis van de vereiste bronnamen.
  De standaarduitvoering retourneert direct de bestaande tabel. Web API en
  Native krijgen geen nieuwe wachttijd of transportspecifieke evaluatorlogica.
- MQTT gebruikt één discoverydeadline van twintig seconden per gestart
  discoveryvenster. De eerdere korte stilte blijft uitsluitend de eerste
  inventarisatie begrenzen. Zolang vereiste namen niet kunnen binden, mogen
  later ontvangen topics de tabel aanvullen. Gewone waarde-/uptimeberichten
  verzetten de deadline niet.
- Zodra de vereiste namen binden, of een definitieve spelling-/ambiguïteitsfout
  bestaat, gaat de tabel naar de bestaande compiler. Op de deadline gebeurt
  dit ook bij ontbrekende velden. De compiler houdt de fouten bij de betrokken
  expressies; transport/authenticatiefouten blijven formuliermeldingen.
- Live systeemvalidatie en validatie van gekoppelde systemen bij een
  verbindingswijziging gebruiken dit contract. De gecompileerde binding blijft
  daarna vast; een nieuw topic leidt niet tot herbinding van de actieve revisie.
  Optionele ontbrekende velden houden het venster niet open.

### Exacte externe identiteit

- Een gekozen communicatiebron wordt letterlijk overgenomen uit discovery.
  Er wordt geen whitespace gestript. De lokale kopiealias houdt zijn bestaande
  getrimde, maximaal 256 tekens lange contract.
- Externe doelen gebruiken de gedeelde opaque provider-ID-validatie, inclusief
  de grens van 65.533 UTF-8-bytes. De bestaande normalisatiefunctie is hiervoor
  intern herbruikbaar gemaakt, zonder verandering van haar betekenis.
- MQTT-rootvalidatie en de controle tegen werkelijk aangeboden bronnen blijven
  gelden. Oversize/lege doelen en foutieve kopieën blijven lokaal geïsoleerd.
  IDs en expressies worden niet gemigreerd of automatisch herschreven.

### Credentialset behouden, vervangen of verwijderen

- Een leeg wachtwoord behoudt het bestaande wachtwoord uitsluitend bij dezelfde
  niet-lege, genormaliseerde gebruikersnaam.
- Twee lege velden vormen een kandidaat voor anonieme toegang. Een andere
  gebruikersnaam vereist een nieuw wachtwoord; het oude gaat niet mee.
- Verbindingsvalidatie en atomaire publicatie blijven ongewijzigd. Een geweigerde
  kandidaat verandert geen opgeslagen verbinding, systeemstempel of expressie.

## Verificatie en grenzen

Regressies toetsen gespreide niet-retained velden, een ander systeem dan de
eerste discoverybron, later zichtbare ambiguïteit, een ontbrekend veld onder
doorgaande andere berichten en vaste binding na validatie. Kopietests bewaren
exacte roots bij aanmaken, activeren, runtimeopbouw, reload en wisselmetadata.
Bytegrenzen, foutieve lokale aliases en alle credentialwissels worden getoetst.

De proeven gebruiken geïsoleerde transport-/opslagfixtures met echte runtime-
en HA-code. Zij stellen geen oorzaak vast voor het historische EMQX-incident
en wijzigen geen live broker of Home Assistant. Configuratieschema's en de
onuitgebrachte integratie-/kaartversie 1.0.0 blijven gelijk.

## Netwerkacceptatie op 18 november 2026

De [aanvullende acceptatie](../results/s100-03-07-network-acceptance-2026-11-18.md)
bevestigt op echte Mosquitto-/EMQX-verbindingen de gespreide discovery,
ontbrekendebrondeadline, exacte roots en credentialsemantiek. HA-flowopslag
was geïsoleerd; de oorspronkelijke live configuraties en accounts zijn niet
gewijzigd. De echte Mosquitto-authenticatieafwijzing bleef atomisch.
