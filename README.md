# hakedis

**Auditable take-off (kırık ölçü) quantity take-off for reinforced-concrete
formwork plans** — reads **DWG / DXF / PDF** drawings directly and produces
element-level quantities without building a 3D model.

Every quantity is kept as an auditable chain of parts: the output is not just a
total, but the *broken-out measurement* that shows exactly where each number
comes from.

```
S01    Column concrete 0.30/0.60       0.513 m3   A=0.1800 m2 x H=2.85 m
P1     Wall concrete t=0.25            2.494 m3   L=3.500 x t=0.25 x H=2.85
         1. leg: (2.63, 1.63) -> (4.50, 1.63) = 1.875 m
         2. leg: (2.63, 1.63) -> (2.63, 3.25) = 1.625 m
K101   Beam concrete 0.25/0.50         0.998 m3   b=0.25 x (h-t)=0.35 x L=11.400
        Gross axis length 12.300 m, support deduction 0.900 m
         1. span: (0.15, 0.00) -> (5.85, 0.00) = 5.700 m
         2. span: (6.15, 0.00) -> (11.85, 0.00) = 5.700 m
```

## Features

| Element | Detection | Quantities computed |
|---|---|---|
| **Column** | Closed section → minimal rotated bounding box (works for skewed columns) | Concrete `A×H`, formwork `perimeter×H` − intersecting beam faces |
| **Shear wall** | Face pairing → **centerline**; corner break-outs for L/T/U walls | Concrete `L×t×H`, formwork `2×L×H` + end forms |
| **Beam** | Closed polygon *or* two parallel lines; **split into net spans at supports** | Concrete `b×(h−t)×L`, formwork soffit + 2 sides |
| **Slab** | Shoelace area from corner coordinates, openings deducted | Concrete `A×t`, table formwork − (beam+column+wall footprint **union**) |
| **Stair** | Closed plan footprint | Concrete `A×k×t`, formwork `A×k` — `k` from riser/tread or explicit |

Optional rules (enabled via config):

- **Reinforcement estimate:** with `donati.aktif`, a `kg` line is added next to
  each concrete line; coefficients are office averages (`kg/m³`).
- **Ribbed (guse) and flat-slab (mantar) floors:** `doseme.tip` applies
  approximation rules to concrete volume; a manual-check warning is emitted.
- **Stair slope factor:** given `merdiven.riht/basamak`, `k = √(1+(riser/tread)²)`.
- **Approximate cost:** multiply measured quantities by ministry/item-rate unit
  prices to produce a bill of quantities and an estimate with KDV.

Two details are handled deliberately:

- **Net span:** beam lengths are measured face-to-face of supports, not axis-to-axis.
- **No double deduction:** slab-formwork deductions for beams, columns, and walls
  use the *union* of their footprints, so intersections are never deducted twice.

## Installation

```bash
git clone <this-repo> && cd hakedis
pip install -e .           # command-line interface
pip install -e ".[web]"    # optional visual UI (web + desktop)
hakedis dogrula            # verify dependencies
```

The visual UI pulls in FastAPI/uvicorn/pywebview; these are only needed for the
`hakedis web` and `hakedis masaustu` commands.

No extra setup is needed for DXF or PDF. Reading **DWG** requires a converter:

```bash
sudo apt install libredwg-tools     # GNU LibreDWG (GPLv3, open source) — recommended
brew install libredwg               # macOS
```

If it is not installed, `hakedis` says so explicitly. Saving the drawing as
`DXF R2013` from your CAD application always works as an alternative.

All dependencies are open source and free:
[ezdxf](https://ezdxf.mozman.at/) (MIT), [shapely](https://shapely.readthedocs.io/) (BSD),
[pdfplumber](https://github.com/jsvine/pdfplumber) (MIT), openpyxl (MIT), numpy (BSD),
[GNU LibreDWG](https://www.gnu.org/software/libredwg/) (GPLv3, invoked as an external process).

## Usage

```bash
# 1. Generate a sample plan to try it out
hakedis ornek deneme.dxf
hakedis metraj deneme.dxf

# 2. Inspect layers of your own drawing
hakedis katmanlar plan.dwg

# 3. Generate an office config and enter your layer names
hakedis config-yaz --cikti ofis.yml

# 4. Run the take-off
hakedis metraj plan.dwg --config ofis.yml \
    --kat "3. Normal Kat" --kat-yuksekligi 3.20 --doseme-kalinligi 0.15

# 5. Multi-storey / multi-sheet work
hakedis toplu gir.dxf kat1.dxf kat2.dxf \
    --kat-adlari "Giris Kat" "1. Normal Kat" "2. Normal Kat"
hakedis toplu plan.pdf --paftalar "1:Giris,2:1.Kat,3:2.Kat" --config ofis.yml
```

### Approximate cost from a previous run

```bash
hakedis metraj plan.dwg --json sonuc.json          # dump the take-off to JSON
hakedis maliyet sonuc.json --config ofis.yml       # apply unit prices
```

Set `maliyet.aktif: true` in the config to embed the cost table in the take-off
console output and the Excel workbook automatically.

## Visual UI (web + desktop)

Both faces share the same single-page interface; both start a local server
(`127.0.0.1`). Your drawing never leaves your machine and no internet
connection is required:

```bash
hakedis web                 # opens in the default browser
hakedis masaustu            # native desktop window (webview)
```

Tabs:

- **Metraj (Take-off):** drag-and-drop a file; choose floor name/height,
  reinforcement, slab type, stair slope. Summary cards, the broken-out
  measurement table, the **control sheet** (SVG), and warnings are shown on one
  screen; Excel/JSON/SVG download.
- **Eşleştir (Mapping):** scan the file for PDF colors or DXF/DWG layers, then
  assign an element type to each. This replaces the "renk_esleme bos" warnings
  and gives each candidate a suggested mapping (including a smart "ignore"
  suggestion for hatching/measurement layers).
- **Toplu Metraj (Bulk):** add floor files one by one; produces a floor-summary
  table and a shared take-off table.
- **PDF İncele (Inspect):** color/line-thickness dump of a PDF sheet plus a
  ready-to-use `renk_esleme` YAML template.
- **Maliyet (Cost):** edit poz unit prices, KDV, and currency; compute an
  estimate from the last take-off, and toggle whether the cost is embedded in
  take-off results and Excel.
- **Ayarlar (Settings):** quick form or advanced YAML editor — same
  configuration as `config-yaz`, managed from the UI.

On macOS the desktop window uses `pywebview` (WKWebView), WebView2 on Windows,
WebKitGTK on Linux; if `pywebview` is not installed, `hakedis masaustu`
automatically falls back to the browser.

## Outputs

- `plan.metraj.xlsx` — Summary / Take-off Table / **Broken-out Measurements** /
  Elements / Warnings / Maliyet (when enabled)
- `plan.metraj.kontrol.svg` — **control sheet**
- `--json` for machine-readable output (for handing off to other systems)
- `plan.toplu.xlsx` for bulk runs — Floor Summary / Take-off Table / Broken-out /
  Elements / Warnings

### Control sheet

The biggest risk in automated take-off is a mis-detected element entering the
table unnoticed. The SVG control sheet shows **how the system understood the
drawing**: every element is painted by type, labeled with its name and section,
and wall/beam centerlines are drawn over it with their break-out points.

Before delivering, verify three things:

1. Every column/wall/beam is painted — any that were skipped?
2. The colors are right — was a column counted as a wall?
3. Do the dashed centerlines pass through the middle of each element?

Low-confidence elements are marked `!` next to their name, auto-named ones `*`;
both also land in the Warnings sheet.

## Configuration

Generated with `hakedis config-yaz`. The things you will typically edit:

```yaml
birim: cm                      # DXF $INSUNITS is used if present

kat:
  kat_yuksekligi: 3.00
  doseme_kalinligi: 0.15

katmanlar:                     # YOUR layer names (regex)
  kolon:  ['^KOLON', '^S-KOL']
  perde:  ['^PERDE']
  kiris:  ['^KIRIS', '^KİRİŞ']
  doseme: ['^DOSEME', '^DÖŞEME']
  yoksay: ['^AKS', '^ÖLÇÜ', '^DONATI']

metraj:                        # toggle to match office practice
  kiris_betonu_doseme_dusumu: true
  doseme_kalibindan_mesnet_dus: true

doseme:                        # special slab types (approximate rules)
  tip: normal                  # normal | guseli | mantar
  guseli_hacim_katsayisi: 1.35
  mantar_kolon_ustu_artisi: 0.05
  mantar_kolon_baslik_alani: 1.00

merdiven:                      # slope factor: k = √(1+(riser/tread)²)
  riht: 0.175
  basamak: 0.28
  kalinlik: 0.14

donati:                        # APPROXIMATE reinforcement (kg per m³ concrete)
  aktif: false
  katsayilar:
    kolon: 110
    perde: 90
    kiris: 120
    doseme: 95
    merdiven: 70

pozlar:                        # your unit-price bill item numbers
  kolon_beton: "16.058/1-K"
  demir: "18.001"

maliyet:                       # approximate cost (unit prices x quantities)
  aktif: false
  para_birimi: "TL"
  kdv_oran: 20
  poz_fiyatlari:               # poz -> unit price (ILLUSTRATIVE — update these)
    "16.058/1-K": 4200
    "21.011/K": 480
    "18.001": 55
```

Label reading understands `K101 25/50`, `S01 30x60`, `P1 25`, `TD=15`,
`K-12 (30/70)`; sections written in metres such as `0.25/0.50` are
distinguished as well. If your format differs, add a regex under
`etiket.desenler`.

## Take-off from PDF

PDFs have no layers, so two things are supplied externally:

```bash
hakedis pdf-incele plan.pdf        # see the sheet's colors and page size
```

Map the reported colors in `ofis.yml`:

```yaml
pdf:
  renk_esleme:
    "#ff0000": kolon
    "#0000ff": kiris
    "#808080": doseme
```

You may give the sheet scale, but **two-point calibration is more reliable**
(the sheet may not be printed to scale). Measure a known axis distance in PDF
points and pass:

```bash
hakedis metraj plan.pdf --config ofis.yml --kalibre 340.5:6.00
```

Only **vector** PDFs can be read. For scanned (raster) sheets there is no line
data; rather than silently producing wrong results, the system raises an
explicit error.

### Sta4CAD / design-suite output

Sta4CAD formwork plans are drawn with filled (hatched) elements: concrete fills
are red, rib hatching green, boundaries blue, and dimensions black. The hatch
is emitted as thousands of tiny segments rather than closed polygons, which
would otherwise flood heuristic detection with noise. When a dense short-line
pattern is detected, the fill colors are mapped to "ignore" by default and the
slab-only result is reported with an explicit note (this behavior is
configurable under `pdf.sta4cad_*`). For exact column/wall/beam quantities from
such plans, use the matching tab or the DWG source.

## Limitations

Honestly stated so you can trust the output:

- **No rebar detailing.** The system does not read rebar drawings.
  `donati.aktif` produces a coefficient-based *estimate* (kg per m³ concrete) —
  a pre-sizing figure, not a control sheet.
- **Stairs** are computed from the plan footprint; the slope factor from
  riser/tread is applied to the whole footprint (landings included), so the
  result is approximate and flagged with low confidence.
- **Ribbed (guse) and flat (mantar) slabs** use coefficient-based approximate
  rules; the actual rib/guse geometry is not read and manual review is required.
- **Curved elements** have no special handling and come out approximate.
- One sheet is processed per run. For multi-storey work use the `toplu` command
  (multiple files or a multi-page PDF), naming each floor with
  `--kat-adlari` / `--paftalar` and producing a shared Excel and JSON output.
- **Costs are illustrative.** Unit prices are examples; always enter current
  ministry / provincial unit prices before relying on an estimate.

The output is **a take-off to be checked, not a checked take-off.** Do not
submit it before reviewing the control sheet and the Warnings sheet.

## Tests

```bash
pip install -e ".[test]"
pytest -q          # 128 tests: geometry, labels, end-to-end DXF/PDF, web API
```

Expected values in the end-to-end tests are hand-computed so that the take-off
formulas cannot silently change.

## License

MIT. (LibreDWG is invoked as an external process and remains under its own
GPLv3 license.)
