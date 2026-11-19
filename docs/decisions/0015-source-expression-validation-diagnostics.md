# D-ESP-015 — Foutlocaties bij bronexpressievalidatie

Datum: 15 november 2026

Status: geïmplementeerd in de kandidaatbron en op 15 november geplaatst en
gecontroleerd in Solesta Lab 0.2.8. De vier labsystemen zijn geherconfigureerd
en actief; zie het [installatieverslag](../results/solesta-lab-0.2.8-installation-2026-11-15.md).

## Besluit

De configuratieflow meldt fouten bij het bronexpressieveld waarin zij ontstaan.
Dit geldt voor reguliere systemen en kopieën bij alle drie providers. Alleen
fouten die niet aan een expressie zijn toe te schrijven, zoals verbinding,
authenticatie of een ongeldige provider-veldtabel, blijven algemene meldingen.

De compiler bewaart de betrokken entiteitssleutels bij een fout. Onafhankelijke
fouten worden samen gerapporteerd; bij een kringverwijzing worden uitsluitend
de echte kringleden gemarkeerd, niet hun afhankelijke afnemers. De validatie
vervangt geen andere expressies door fabriekswaarden om een fout te lokaliseren.

Bronbinding onderscheidt ontbrekende, dubbelzinnige en onjuist geschreven
veldnamen met getypeerde fouten. De flow vertaalt deze en syntax-, functie- en
evaluatiefouten naar vaste Nederlandse en Engelse meldingen. Ruwe bronwaarden
en exceptionteksten komen niet in formuliermeldingen terecht.

Een ontbrekende waarde in een ontvangen snapshot wordt door de evaluator aan
de betrokken expressies gekoppeld. Fouten in een afhankelijkheid blijven als
zodanig herkenbaar; de oorspronkelijke fout blijft bij het oorspronkelijke
veld staan.

## Grenzen

Er verandert niets aan opgeslagen bronexpressies, provideridentiteiten,
evaluatiesemantiek of configuratieschema's. Er is geen migratie. Het eerdere
besluit blijft gelden: nieuwe systemen en kopieën kunnen uitgeschakeld worden
opgeslagen voordat live bronvalidatie slaagt; activeren vereist wel een
geslaagde validatie. Syntax en interne afhankelijkheden worden ook bij het
aanmaken gecontroleerd.
