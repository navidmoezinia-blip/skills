---
name: map-creator
description: >-
  Render geographically accurate maps of real-world places from OpenStreetMap
  data, in any style. Pick a base preset (standard, topographic, physical,
  road_atlas, vintage) and override any layer's colour, width, or dash pattern
  via inline JSON to match any aesthetic. Supports free-form annotations
  (markers and text at real lat/lon), arbitrary bbox or center+radius framing,
  and custom resolution. Do NOT use PIL/matplotlib free-hand or
  `generate_image` for geographic maps — those produce fabricated geography.
---

# Map Creator

Render real-geography maps from OpenStreetMap (OSM) data, styled however the
user wants. The renderer queries the public Overpass API for actual features
(rivers, roads, railways, forests, settlements, admin boundaries), projects
them with Web Mercator, and produces a PNG.

This skill is **generic**: every visual property is overridable, every layer
is optional, and arbitrary annotations can be placed at real coordinates. Six
baseline style presets cover common aesthetics; for any other look, pass
`--style-overrides` JSON to tweak specific properties without writing a new
preset.

## When to use this skill

- "Make me a map of [real place]"
- "Térkép / carte / mapa / 地図 of [place]" (any language)
- Historical battlefield maps, hiking regions, neighbourhood maps, route
  overviews, political maps, election maps, demographic basemaps
- Any output where the geography must match the real world

**Do NOT use** for:
- Abstract diagrams, flow charts, schematic illustrations (use PIL or `generate_image`)
- Fully artistic / fantastical maps (use `generate_image`)
- Live-traffic / routing maps with turn-by-turn (out of scope)

## Routes

| Route       | Trigger                                      | Command |
|-------------|----------------------------------------------|---------|
| **Geocode** | Place name → lat/lon/bbox                    | `python3 scripts/geocode.py "Voronezh"` |
| **Render**  | Bounding box → PNG                           | `python3 scripts/render_map.py --bbox N,S,E,W ...` |
| **Verify**  | Sanity-check the output                      | `python3 scripts/verify_map.py out.png --bbox N,S,E,W --required-labels A,B,C` |

## Standard workflow

### Step 1: Resolve the bounding box

If the user gave specific corner towns, geocode each corner and take the
extremes:

```bash
python3 scripts/geocode.py "Rudkino, Russia"
python3 scripts/geocode.py "Pokrovka, Russia"
# build covering bbox; add ~5% padding on each side
```

For "map of [single place]", use `geocode.py`'s returned `bbox` directly:

```bash
BBOX=$(python3 scripts/geocode.py "Voronezh, Russia" --bbox-only)
```

### Step 2: Render

Minimal:

```bash
python3 scripts/render_map.py --bbox 51.55,50.40,39.85,38.70 --out /home/ubuntu/map.png
```

Full feature set:

```bash
python3 scripts/render_map.py \
  --bbox 51.55,50.40,39.85,38.70 \
  --width-px 3700 --height-px 2760 \
  --layers water,roads,railways,forests,settlements \
  --labels "Уриво-Покровка,Коротояк,Щучье" \
  --style topographic \
  --style-overrides '{"water":{"fill":"#0a4d8a"},"background":"#fff8e1"}' \
  --annotate '[{"lat":51.00,"lon":39.05,"text":"Urivi-hídfő","marker":"#c00"}]' \
  --include scale_bar,compass,graticule,legend,title \
  --title "Don bend, 1942-43" \
  --out /home/ubuntu/don_bend.png
```

## Style system

### Baseline presets (one of these is your `--style`)

| Preset        | Use for |
|---------------|---------|
| `standard`    | General reference (Google-Maps-like neutral palette). Default. |
| `topographic` | Hiking / outdoor / terrain emphasis with earthy palette. |
| `physical`    | Nature emphasis: water and forest pop, roads/cities suppressed. |
| `road_atlas`  | Driving: bold red highways, dense town labels, water secondary. |
| `vintage`     | Aged-paper / sepia aesthetic. Good for historical, decorative, period-feel maps (e.g. WWII era). |

### Any aesthetic via overrides

Every property in a preset can be replaced. Pass `--style-overrides` as inline
JSON; it deep-merges onto the preset (only the keys you set are changed).

```bash
# Neon dark — derived from `standard`
python3 scripts/render_map.py --bbox ... --style standard \
  --style-overrides '{
    "background": "#0a0a14",
    "water": {"fill": "#00ffd0", "edge": "#00b89a"},
    "forests": {"fill": "#1a5a3a", "alpha": 0.8},
    "roads": {"edge": "#ff6a00"},
    "settlements": {"marker": "#ffd700", "label_color": "#ffffff"},
    "graticule": {"edge": "#2a2a3a", "alpha": 0.3},
    "title": {"color": "#ffffff"}
  }' --out /home/ubuntu/neon.png

# Corporate brand colours
python3 scripts/render_map.py --bbox ... --style standard \
  --style-overrides '{"water":{"fill":"#1f497d"},"roads":{"edge":"#c0504d"},"forests":{"fill":"#9bbb59"}}' \
  --out /home/ubuntu/branded.png

# Reusable: save the overrides to a file and pass --style-file
python3 scripts/render_map.py --bbox ... --style-file /home/ubuntu/my_palette.json --out ...
```

### Schema of a style dict

```json
{
  "background":  "#f7f5ee",
  "water":       { "fill": "#7eb8db", "edge": "#3a82a8", "width_km": 0.05, "alpha": 0.95 },
  "forests":     { "fill": "#aacb8f", "alpha": 0.55 },
  "roads":       { "edge": "#d28a3c", "width_km": 0.05 },
  "railways":    { "edge": "#444444", "width_km": 0.04, "dash": [6, 4] },
  "settlements": { "marker": "#c0392b", "edge": "#5a1a14", "label_color": "#1a1a1a" },
  "graticule":   { "edge": "#bdbdbd", "alpha": 0.35 },
  "annotations": { "marker": "#c0392b", "text_color": "#1a1a1a", "text_size": 14 },
  "title":       { "color": "#1a1a1a", "size": 26 }
}
```

Every section is optional in an override file — only what you set is replaced.

## Annotations (place arbitrary markers/text at lat/lon)

Use `--annotate` with a JSON array. Each entry needs `lat` + `lon`; the rest is
optional and falls back to the style's `annotations` section.

```bash
python3 scripts/render_map.py --bbox ... \
  --annotate '[
    {"lat": 51.00, "lon": 39.05, "text": "Urivi-hídfő"},
    {"lat": 50.93, "lon": 39.16, "text": "Korotojaki-hídfő", "marker": "#c00", "text_size": 18, "weight": "bold"},
    {"lat": 50.52, "lon": 39.38, "text": "Scsucsjei-hídfő"}
  ]' --out /home/ubuntu/battlefield.png
```

Per-annotation overrides: `marker` (hex colour, or `null` for text-only),
`size` (marker px), `edge`, `edge_width`, `text_color`, `text_size`,
`weight` (`bold`/`normal`), `dx`/`dy` (text offset in mercator units),
`ha`/`va` (matplotlib text alignment).

For reusable annotation sets, use `--annotate-file path/to.json`.

## Zoom and layer selection — IMPORTANT

OSM contains way more features than fit at any given zoom. The single most
common failure mode of this skill is requesting too many layers / too low a
label tier for the bbox span, producing an unreadable wall of overlapping
labels and lines. **Pick the layer set based on bbox span**, not by always
asking for "everything".

Compute the **larger of** `(north − south)` and `(east − west)` in degrees.
Then use the row that matches:

| Span (max side) | Scale            | Layers                                              | Label tier | Settlement strategy |
|----------------:|------------------|-----------------------------------------------------|-----------:|---------------------|
| **> 10°**       | continent / country | `water` ONLY                                     | n/a        | **Skip the `settlements` layer.** Hand-pick 5–15 important cities and pass them via `--annotate` with their real lat/lon. |
| **2°–10°**      | country / large region | `water,settlements`                            | 1 (cities) | Use `--labels` to bold the important ones. Optionally `--annotate` for non-OSM points (battles, POIs). |
| **0.3°–2°**     | small region / metro | `water,roads,railways,forests,settlements` (default) | 2–3   | Standard map; `--labels` for emphasis. |
| **< 0.3°**      | single city / neighbourhood | `water,roads,railways,settlements` (skip forests — usually noise at this zoom) | 4–5 | Include hamlets/suburbs. |

Rules of thumb that fall out of the table:

- **At country zoom, the `settlements` layer is your enemy.** Even at
  `--label-tier 1` (cities only), large countries return 500–2000 OSM-tagged
  cities. Use `--annotate` with hand-picked coordinates instead.
- **Roads and railways at country zoom** are a black smear that hides
  everything else. Skip both layers if the bbox is > 5° on its longest side.
- **Forests at country zoom** can be 10k+ polygons and routinely time out
  Overpass. Skip them above ~3° span. They're useful at region/city zoom.
- **If the user asks for "all features"**, push back: explain that picking
  layers per zoom is what makes a map readable, then propose the row from
  the table.

When in doubt, render once with the recipe above, check the result, and only
add layers back in if the map looks empty.

## Layers

All optional. Default set: `water,roads,railways,forests,settlements`.

| Layer         | OSM tags                                        | Notes |
|---------------|-------------------------------------------------|-------|
| `water`       | `waterway=river/stream/canal`, `natural=water/wetland` | Rivers as lines, lakes/wetlands as polygons. |
| `roads`       | `highway=motorway..residential`                 | Add `--layer-spec` to include service/track/path. |
| `railways`    | `railway=rail/light_rail/narrow_gauge`          | Dashed by default. |
| `forests`     | `landuse=forest`, `natural=wood`                | Polygons. |
| `settlements` | `place=city..hamlet/suburb`                     | Density via `--label-tier 1..5`. |

To add a layer the skill doesn't ship (e.g. admin boundaries, buildings,
POIs), edit `LAYER_QUERIES` in `scripts/overpass_query.py` with the OSM
tag filter, then add a corresponding `draw_<layer>` function in
`scripts/render_map.py`.

## Common patterns

### Map of a single place (auto-bbox)

```bash
BBOX=$(python3 scripts/geocode.py "Kraków, Poland" --bbox-only)
python3 scripts/render_map.py --bbox "$BBOX" --style standard --out /home/ubuntu/krakow.png
```

### Historical battlefield (vintage style + annotations)

```bash
python3 scripts/render_map.py --bbox 51.55,50.40,39.85,38.70 \
  --style vintage \
  --annotate '[
    {"lat":51.00,"lon":39.05,"text":"Urivi-hídfő","marker":"#7a2a2a","text_size":18,"weight":"bold"},
    {"lat":50.93,"lon":39.16,"text":"Korotojaki-hídfő","marker":"#7a2a2a","text_size":18,"weight":"bold"},
    {"lat":50.52,"lon":39.38,"text":"Scsucsjei-hídfő","marker":"#7a2a2a","text_size":18,"weight":"bold"}
  ]' --title "Don bend, 1942-43" --out /home/ubuntu/don.png
```

### Brand-coloured city map

```bash
python3 scripts/render_map.py --bbox ... --style standard \
  --style-overrides '{
    "background":"#ffffff",
    "water":{"fill":"#1f497d"},
    "forests":{"fill":"#9bbb59"},
    "roads":{"edge":"#c0504d"}
  }' --out /home/ubuntu/branded.png
```

## Step 3: Verify

```bash
python3 scripts/verify_map.py /home/ubuntu/map.png \
  --bbox 51.55,50.40,39.85,38.70 \
  --required-labels "Воронеж" \
  --min-feature-count water=5,settlements=10
```

Checks the output exists with expected dimensions, that Overpass returned
enough features per layer, and that each required label was actually
plottable. If verification fails, do not present the map — expand the bbox,
relax labels, or report the problem.

## Honest limitations to communicate

OSM data is **modern**. River course, contours, and most settlement positions
are stable for centuries, so they're accurate for historical periods too. But
the **railway / road network for a specific year** is not authoritative —
features built or destroyed since are not filtered out. If the user needs
strict period-accurate infrastructure:

> "Base geography (rivers, contours, town positions) is OSM-sourced and
> accurate. Railway and road alignments reflect the modern network — some
> 1940s lines may have been removed, and some current alignments didn't exist
> yet. For strict period accuracy, a Soviet Genshtab 1:100k overlay would be
> needed (not in v1)."

## Guidelines

- Never invent coordinates. If geocode can't find a place, tell the user and
  ask — do not guess from memory.
- Always declare the data source ("Rendered from OpenStreetMap, retrieved
  <date>") in the user-facing response. Maps are easy to mistake for
  cartographic authority; honest provenance matters.
- For very large bboxes (>500 km on a side), expect Overpass timeouts. Render
  in tiles and stitch, or accept reduced feature density.
- Keep the output file under `/home/ubuntu/` so it appears as a deliverable.
- When the user asks for a specific aesthetic ("neon", "watercolor",
  "blueprint"), reach for `--style-overrides` rather than asking them to
  describe colours individually — guess sensible values and iterate.
