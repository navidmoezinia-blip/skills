---
name: icon-generator
description: "Use when the user wants to generate icons of any type and style. Creates high-quality app icons, favicons, UI icons, logos, game icons, social media icons, and custom designs using AI image generation (Abacus.AI) with professional post-processing. Outputs in PNG (with transparency, multiple sizes), SVG, and ICO formats, with batch generation and full icon-set workflows."
---

# Icon Generator Skill

---

## Capabilities

### Icon Types
| Type | Description |
|---|---|
| **App / Application** | Mobile and desktop app icons (iOS, Android, macOS, Windows) |
| **Favicon** | Website favicons in standard sizes with ICO bundling |
| **UI / Interface** | Buttons, navigation, settings, toggles, status indicators |
| **Social Media** | Profile pictures, channel icons, platform-specific assets |
| **Logo-style** | Brand marks, monograms, wordmarks rendered as icons |
| **Game** | Game app icons, in-game item icons, achievement badges |
| **System** | OS-level icons for files, folders, drives, notifications |
| **Custom** | Anything described in natural language |

### Styles
| Style | Prompt Keyword |
|---|---|
| Flat design | `flat` |
| 3D / Gradient | `3d` |
| Line / Outline | `line` |
| Minimalist | `minimalist` |
| Material Design | `material` |
| iOS style | `ios` |
| Glassmorphism | `glass` |
| Neumorphism | `neumorph` |
| Skeuomorphic | `skeuomorphic` |
| Custom | Any free-text style description |

### Output Formats
- **PNG** — with transparency, any size from 16×16 to 1024×1024
- **SVG** — vector traced from the generated raster
- **ICO** — multi-resolution favicon bundle (16, 32, 48, 64, 128, 256)
- **Icon Sets** — generate a coherent family of icons in one batch

---

## Usage

### Quick Start — Single Icon

```python
# In DeepAgent, run:
exec(open("<icon_generator_skill_path>/scripts/generate_icon.py").read())

result = generate_icon(
    description="A rocket launching from a phone screen",
    style="flat",
    sizes=[128, 256, 512],
    formats=["png", "svg"],
    output_dir="/home/ubuntu/<my_icons>"
)
print(result)  # dict with paths to generated files
```

### Batch Generation — Multiple Icons

```python
exec(open("<icon_generator_skill_path>/scripts/batch_generate.py").read())

icons = [
    {"description": "Home button", "style": "line"},
    {"description": "Settings gear", "style": "line"},
    {"description": "User profile avatar", "style": "line"},
    {"description": "Search magnifying glass", "style": "line"},
    {"description": "Notification bell", "style": "line"},
]

results = batch_generate(
    icon_specs=icons,
    sizes=[64, 128, 256],
    formats=["png"],
    output_dir="/home/ubuntu/ui_icon_set"
)
```

### Format Conversion

```python
exec(open("<icon_generator_skill_path>/scripts/convert_formats.py").read())

# PNG → ICO (multi-size favicon)
create_ico("/home/ubuntu/logo.png", "/home/ubuntu/favicon.ico")

# PNG → SVG (vector trace)
png_to_svg("/home/ubuntu/logo.png", "/home/ubuntu/logo.svg")

# Resize a PNG to multiple sizes
resize_to_sizes("/home/ubuntu/logo.png", [16, 32, 64, 128, 256, 512], "/home/ubuntu/output/")
```

---

## Parameters Reference

### `generate_icon()`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `description` | str | *required* | Natural-language description of the icon |
| `style` | str | `"flat"` | Style keyword or free-text style description |
| `icon_type` | str | `"app"` | One of: `app`, `favicon`, `ui`, `social`, `logo`, `game`, `system`, `custom` |
| `sizes` | list[int] | `[256, 512]` | Pixel sizes to export (square) |
| `formats` | list[str] | `["png"]` | Output formats: `png`, `svg`, `ico` |
| `output_dir` | str | `"/home/ubuntu/generated_icons"` | Where to save files |
| `background` | str | `"transparent"` | `"transparent"`, `"white"`, `"black"`, or hex color |
| `color_scheme` | list[str] | `None` | Optional list of hex colors to influence palette |
| `padding` | float | `0.1` | Fractional padding around the icon (0.0–0.5) |
| `name_prefix` | str | `"icon"` | Filename prefix for generated files |
| `optimize` | bool | `True` | Apply PNG compression / SVG optimization |
| `remove_bg` | bool | `True` | Auto-remove background for transparency |

### `batch_generate()`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `icon_specs` | list[dict] | *required* | List of dicts, each with at least `description` (plus optional overrides for any `generate_icon` param) |
| `sizes` | list[int] | `[256, 512]` | Default sizes (overridable per icon) |
| `formats` | list[str] | `["png"]` | Default formats |
| `output_dir` | str | `"/home/ubuntu/generated_icons"` | Output directory |
| `consistent_style` | str | `None` | Force a single style across all icons |

### Conversion Functions

| Function | Description |
|---|---|
| `create_ico(png_path, ico_path, sizes)` | Bundle a PNG into a multi-size ICO |
| `png_to_svg(png_path, svg_path, colors, simplify)` | Trace a PNG into an SVG |
| `resize_to_sizes(png_path, sizes, output_dir)` | Export a single PNG to multiple square sizes |
| `optimize_png(png_path, output_path)` | Lossless PNG compression |
| `extract_palette(image_path, n_colors)` | Extract dominant colors from an image |
| `remove_background(image_path, output_path)` | Remove background, return RGBA PNG |

---

## Best Practices

1. **Be specific in descriptions** — "A blue gradient shield with a white checkmark in the center" produces better results than "security icon".
2. **Choose style early** — Mixing styles in a set looks inconsistent. Use `consistent_style` in batch mode.
3. **Generate large, export small** — Always generate at 512 or 1024 and downscale. Upscaling loses quality.
4. **Use transparent backgrounds** for maximum flexibility (default behavior).
5. **For favicons**, always export ICO with embedded 16, 32, and 48 px sizes.
6. **For app stores**, generate 1024×1024 PNG without transparency (iOS requires opaque).
7. **Color schemes** — Pass a `color_scheme` list to keep icons on-brand.
8. **SVG output** is auto-traced from the raster — for pixel-perfect vectors, manually refine the SVG.

---

## Common Use Cases & Examples

### 1. iOS App Icon
```python
generate_icon(
    description="A minimalist purple owl face on a soft gradient background",
    style="ios",
    icon_type="app",
    sizes=[1024],
    formats=["png"],
    background="#1a1a2e",
    padding=0.0,
    remove_bg=False,
    name_prefix="ios_app_icon"
)
```

### 2. Website Favicon Set
```python
generate_icon(
    description="The letter 'A' in a rounded square with a teal to cyan gradient",
    style="flat",
    icon_type="favicon",
    sizes=[16, 32, 48, 64, 128, 256],
    formats=["png", "ico"],
    name_prefix="favicon"
)
```

### 3. UI Navigation Icon Set
```python
batch_generate(
    icon_specs=[
        {"description": "Home house icon", "name_prefix": "nav_home"},
        {"description": "Magnifying glass search icon", "name_prefix": "nav_search"},
        {"description": "Heart favorite icon", "name_prefix": "nav_favorites"},
        {"description": "Shopping cart icon", "name_prefix": "nav_cart"},
        {"description": "User profile silhouette icon", "name_prefix": "nav_profile"},
    ],
    consistent_style="line",
    sizes=[24, 48, 96],
    formats=["png", "svg"],
    color_scheme=["#333333"],
)
```

### 4. Game Achievement Badges
```python
batch_generate(
    icon_specs=[
        {"description": "Gold trophy with sparkles", "name_prefix": "badge_gold"},
        {"description": "Silver shield with a star", "name_prefix": "badge_silver"},
        {"description": "Bronze medal with laurel wreath", "name_prefix": "badge_bronze"},
    ],
    consistent_style="3d",
    sizes=[128, 256],
    formats=["png"],
)
```

### 5. Social Media Profile Picture
```python
generate_icon(
    description="Abstract geometric fox head in orange and white",
    style="minimalist",
    icon_type="social",
    sizes=[400, 800],
    formats=["png"],
    background="transparent",
    name_prefix="social_avatar"
)
```

### 6. System File-Type Icons
```python
batch_generate(
    icon_specs=[
        {"description": "Document page icon with 'PDF' text", "name_prefix": "filetype_pdf"},
        {"description": "Spreadsheet grid icon with green accent", "name_prefix": "filetype_xlsx"},
        {"description": "Image landscape photo icon", "name_prefix": "filetype_img"},
        {"description": "Code file icon with angle brackets", "name_prefix": "filetype_code"},
    ],
    consistent_style="flat",
    sizes=[32, 64, 128, 256],
    formats=["png", "ico"],
)
```

---

## File Structure

```
icon_generator_skill/
├── SKILL.md                          # This file
├── scripts/
│   ├── generate_icon.py              # Single icon generation
│   ├── batch_generate.py             # Batch / icon-set generation
│   ├── convert_formats.py            # Format conversion utilities
│   └── icon_utils.py                 # Shared helpers (prompts, processing)
├── templates/
│   ├── style_prompts.json            # Curated prompt fragments per style
│   └── icon_presets.json             # Ready-made preset configurations
└── references/
    └── platform_specs.json           # Size/format specs for iOS, Android, web, etc.
```

---

## Dependencies

The scripts will auto-install any missing packages. Core dependencies:

- `Pillow` — image processing, resizing, ICO creation
- `rembg` — AI background removal
- `svgtrace` / custom tracer — PNG to SVG conversion
- `abacusai` — AI image generation via Abacus.AI SDK

---

## Notes

- AI image generation produces raster images. SVG output is an auto-traced approximation.
- Background removal works best on icons with clear foreground subjects.
- For production use, review and refine generated icons — AI output is a strong starting point.
- All scripts are designed to be `exec()`-ed in DeepAgent or run standalone via `python3`.
