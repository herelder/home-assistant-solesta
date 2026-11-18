# Fysieke acceptatie ESPHome Native-provider vanuit Solesta Lab

Datum: 22 oktober 2026

Solesta Lab-build: `1fc1c02ed6b2`

Resultaat: mDNS-selectie en rechtstreekse native-API-verbinding geslaagd

## Reikwijdte en veiligheidsgrens

Deze controle omvat de twee afsluitende onderdelen van fase 3:

1. de mDNS-keuzelijst met handmatige hostinvoer als terugvalroute;
2. een rechtstreekse verbinding vanuit het gegenereerde Solesta Lab-pakket met
   de fysieke NanoC6.

Er is niets in Home Assistant geïnstalleerd of gewijzigd. De bestaande
productie-integratie `solesta` bleef versie `0.2.3`. De Home Assistant-share en
de Nano-configuratie zijn alleen gelezen om de bestaande API-encryptiesleutel
voor de proef te gebruiken; de sleutel is niet gelogd of in dit rapport
opgenomen. De providerwissel en controle van entity unique ID's en historie
zijn nadrukkelijk niet uitgevoerd.

## mDNS-keuzelijst

De configuratiestroom gebruikt de gedeelde zeroconf-instantie van Home
Assistant en zoekt kort naar `_esphomelib._tcp.local.`. Gevonden nodes worden
als een keuzelijst aangeboden. Iedere keuze vult alleen host en poort voor; de
velden blijven bewerkbaar. De vaste optie **Handmatig invoeren** blijft altijd
beschikbaar, ook als mDNS niets vindt of niet bruikbaar is.

De fysieke netwerkproef vond precies één ESPHome-node met de verwachte
zichtbare naam, lokale `.local`-hostnaam en native-API-poort `6053`. mDNS-data
wordt uitsluitend als onbetrouwbare bedieningshulp behandeld. De versleutelde
native API en het door de node gemelde MAC-adres blijven de validatiegrens.

## Rechtstreekse Solesta Lab-verbinding

De providercode is geladen uit het gegenereerde pakket
`work/solesta_lab/custom_components/solesta_lab`, niet uit een testdubbel. De
proef heeft daarna:

- met de bestaande Noise-PSK een versleutelde native-API-verbinding geopend;
- apparaatprofiel, entiteitscatalogus en state-abonnement opgehaald;
- één bronidentiteit in de vorm `<geschoond-mac>/uart1` vastgesteld;
- de vereiste bronwaarden `temperature_1_raw` tot en met
  `temperature_4_raw`, `pump_raw`, `data_valid` en de afgeleide `last_update`
  ontvangen;
- de verbinding gesloten en opnieuw geopend met het bij de eerste verbinding
  vastgestelde MAC-adres als verplichte identiteit;
- bevestigd dat `flow_raw`, `frame_sequence` en de ruwe data-agewaarde niet in
  het publieke Solesta-broncontract verschijnen.

Beide verbindingen slaagden. `data_valid` was tijdens de eindcontrole waar.
Het apparaat rapporteerde ESPHome `2026.9.1`.

## Bevinding en correctie

De eerste fysieke proef maakte zichtbaar dat ESPHome het YAML-id
`data_age_seconds` in deze firmware via de native API aanbiedt als object-id
`data_age`, afgeleid van de zichtbare naam **Data age**. Daardoor ontbrak de
synthetische `last_update` aanvankelijk.

De provider accepteert nu beide object-id-varianten als private technische
bron voor `last_update`. Geen van beide data-agevelden wordt publiek gemaakt.
Een regressietest dekt specifiek de op de fysieke Nano waargenomen variant.

## Nog niet uitgevoerd

Fase 3 is met deze fysieke validatie afgerond. Solesta Lab is nog niet in Home
Assistant geïnstalleerd. Eerst volgt in fase 4 de parallelle acceptatie van de
Web API- en ESPHome Native-provider gedurende een representatief meetvenster.

De volledige providerwissel Web API → ESPHome Native → Web API volgt pas in
fase 5, nadat beide providers afzonderlijk zijn geaccepteerd. Daarbij worden
de blijvende entity unique ID's en Recorderhistorie expliciet gecontroleerd.
