# Logo and visual identity

## Community identity

The house-and-sun mark is original artwork for this independent community
integration. It combines solar heat, water circulation and the home in one
compact symbol. It is not a Solesta corporate logo and must not be presented as
evidence of certification, endorsement or a **Works with Home Assistant**
partnership.

Use **Solesta for Home Assistant** as the repository and documentation name.
Use **Solesta** as the concise integration and dashboard-card name. When the
project is shown outside Home Assistant, keep the description **independent
community integration** nearby.

## Image files

The high-resolution dashboard artwork in
`custom_components/solesta/frontend/solesta-community-logo.png` is the source
for all published variants. The same square artwork is deliberately used for
both the icon and the logo:

| File | Size | Purpose |
| --- | ---: | --- |
| `brand/icon.png` | 256 × 256 px | Standard integration icon |
| `brand/icon@2x.png` | 512 × 512 px | High-density integration icon |
| `brand/logo.png` | 256 × 256 px | Standard integration logo |
| `brand/logo@2x.png` | 512 × 512 px | High-density integration logo |

All files are transparent PNGs. The README uses `logo.png`; Home Assistant can
select the appropriate local brand asset; and the bundled dashboard card uses
the high-resolution source artwork. This keeps the appearance consistent
without loading artwork from an external server.

## Colour palette

The dashboard uses a restrained supporting palette derived from the mark:

| Role | Colour |
| --- | --- |
| Deep solar teal | `#002F3C` |
| Supporting teal | `#0C4757` |
| Solar orange | `#F18522` |
| Water blue | `#3B82F6` |
| Healthy/online green | `#42C98B` |
| Alert red | `#E83630` |
| Main text | `#13242B` |

Use orange for heat and emphasis, blue for cold water, green only for a healthy
or active state, and red only for an actual warning or error. The dashboard
uses Home Assistant's local/system fonts and does not download a web font.

## Usage rules

- Preserve the original proportions and transparent background.
- Do not recolour, rotate, crop through or place text over the mark.
- Keep enough empty space around it that the sun rays and house outline remain
  clearly separated from surrounding text or controls.
- Do not combine it with the Home Assistant logo or an official Solesta logo in
  a way that could imply endorsement.
- Use only the files in the integration's `brand` directory for release assets;
  derive future sizes from the high-resolution community artwork.
