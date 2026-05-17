---
name: figma-mockup
description: "Use when the user wants to generate Figma-compatible SVG mockup files. Creates landing pages, mobile apps, dashboards, and UI component libraries with AI-generated content — realistic brand names, copy, pricing, testimonials, logos, and illustrations. Supports high-fidelity and wireframe modes with multiple themes. No placeholders or lorem ipsum."
---

# Figma Mockup v4.0 — Layout Engine Rewrite

Generate Figma-compatible SVG mockup files with **AI-generated content** — complete with realistic brand names, copy, pricing, testimonials, logos, and illustrations. **No placeholders. No lorem ipsum. Every section is filled with contextually relevant content.**

## What's New in v4.0

| Feature | v3 | v4.0 |
|---------|-----|------|
| Layout System | Hardcoded positions | **Layout engine** with 8px grid, spacing constants, collision detection |
| Typography | Inconsistent sizing | **Professional type scale** (Hero→Tiny) with proper line heights |
| Text Centering | `y + h/2 + 5` magic numbers | **Mathematical baseline calculation** via `LayoutCalc.text_baseline_y()` |
| Text Overflow | Text overflows containers | **Auto-truncation** with ellipsis and **word-wrap** utilities |
| Mobile Layout | Manual position math | **`MobileLayout` class** with pre-calculated section positions |
| Overlap Prevention | Elements could overlap | **Bounding box system** with `LayoutValidator` |
| SVG Structure | Flat elements | **Semantic `<g>` groups** with IDs for Figma layer organization |
| Component Library | Inconsistent sizing | **Standardized dimensions** (buttons: 44px, icons: 24px, list items: 72px) |
| Tab Bar | Basic | **iOS-accurate** tab bar (83px with home indicator) |
| Status Bar | Approximate | **Exact iOS dimensions** (44px safe area) |
| Button Text | Off-center | **Pixel-perfect centering** with icon+text layout calculation |
| Badge Width | Character count heuristic | **Font-metric based** width calculation |

### Architecture (New in v4.0)
- **`layout_engine.py`** — Grid system, spacing constants, typography scale, collision detection, bounding box utilities
- **`generate_mockup.py`** — SVG generation with layout engine integration
- **`svg_icons.py`** — 45+ SVG icon library
- **`content_generator.py`** — AI content generation via Abacus.AI LLM
- **`logo_generator.py`** — Programmatic SVG logo generation
- **`image_generator.py`** — Themed SVG illustration generation

## Capabilities

| Mockup Type | Description | Default Size |
|-------------|-------------|--------------|
| `landing_page` | Full marketing page: hero, features, pricing, testimonials, CTA, footer | 1440 × 3200 |
| `mobile_app` | iPhone-sized screen: status bar, cards, list items, tab bar | 390 × 844 |
| `dashboard` | Analytics dashboard: sidebar, KPI cards, charts, data table | 1440 × 1024 |
| `ui_components` | Component library: buttons, inputs, cards, badges, avatars, toggles | 1200 × 2200 |

### Fidelity Modes

| Mode | Description |
|------|-------------|
| `high` | **(default)** Polished, production-ready with shadows, gradients, realistic colors |
| `wireframe` | Structural focus: grayscale, simple strokes, minimal styling |

### Themes (high-fidelity mode only)

| Theme | Style |
|-------|-------|
| `light` | Clean white with indigo primary (default) |
| `dark` | Dark background with soft purple primary |
| `brand_blue` | Blue-tinted, trust-oriented brand palette |

### AI Content Generation

The generator uses **Abacus.AI LLM APIs** to create contextually relevant content:

- **Brand Identity**: Unique brand name, tagline, and company description
- **Hero Section**: Compelling headlines, subheadlines, and CTA text
- **Features**: 3 features with titles, descriptions, and appropriate icons
- **Testimonials**: 3 realistic testimonials with names, roles, and companies
- **Pricing**: 3 tiers with industry-appropriate prices
- **Stats/Metrics**: Realistic numbers specific to the industry
- **How It Works**: Step-by-step process descriptions
- **Footer**: Industry-specific navigation, links, and legal text
- **Logo**: SVG monogram generated from the brand name

### Industry-Aware Content

The generator detects the industry from your description and generates appropriate content:

| Industry | Example Pricing | Example Stats | Example Features |
|----------|----------------|---------------|------------------|
| Coffee/Café | $3.50 - $29/mo | 5,000+ cups, 4.9★ rating | Single-Origin Beans, Expert Baristas |
| SaaS/Tech | $9 - $99/mo | 10K+ users, 99.9% uptime | Lightning Fast, Secure by Default |
| E-commerce | Free - $24.99/mo | 50K+ products, 1M+ customers | Fast Shipping, Easy Returns |
| Finance | $4.99 - $49.99/mo | $2.5B+ managed, 150K+ users | Real-Time Tracking, Smart Insights |
| Healthcare | $19 - $199/mo | 200K+ patients, 500+ doctors | 24/7 Telehealth, Smart Scheduling |

## Usage

### Quick Start

```bash
python3 scripts/generate_mockup.py \
  --type landing_page \
  --description "Coffee Shop in Seattle" \
  --output /home/ubuntu/output/coffee.svg
```

### Full Argument Reference

```
python3 scripts/generate_mockup.py \
  --type <TYPE>            # Required: landing_page | mobile_app | dashboard | ui_components
  --description <TEXT>     # Required: description for AI content generation
  --output <PATH>          # Required: output SVG file path
  --fidelity <MODE>        # Optional: high (default) | wireframe
  --theme <THEME>          # Optional: light (default) | dark | brand_blue
  --width <INT>            # Optional: override canvas width
  --height <INT>           # Optional: override canvas height
  --seed <INT>             # Optional: random seed for reproducible output
  --no-ai                  # Optional: skip LLM API, use industry-specific defaults
```

### Examples

**Coffee shop landing page (AI-generated content):**
```bash
python3 scripts/generate_mockup.py \
  --type landing_page \
  --description "Coffee Shop in Seattle" \
  --output coffee.svg
```
*Output: Brand "Rainy Day Roasters", tagline "Coffee Worth Braving the Rain", menu items, realistic prices ($3.50-$5.25), Seattle-specific footer links*

**SaaS dashboard (dark theme):**
```bash
python3 scripts/generate_mockup.py \
  --type dashboard \
  --theme dark \
  --description "E-commerce sales analytics for fashion retailer" \
  --output dashboard.svg
```
*Output: Brand "StyleMetrics", KPIs like "Total Revenue $48,290", "Conversion 3.24%", fashion-specific table data*

**Mobile fitness app:**
```bash
python3 scripts/generate_mockup.py \
  --type mobile_app \
  --theme brand_blue \
  --description "Fitness tracking and workout planner" \
  --output fitness.svg
```
*Output: App name "FitPath", fitness-specific activities, workout-related quick actions*

**Reproducible output with seed:**
```bash
python3 scripts/generate_mockup.py \
  --type landing_page \
  --description "AI-powered project management tool" \
  --seed 42 \
  --output saas.svg
```
*Same seed + description = identical output every time*

**Fast generation without AI (uses industry defaults):**
```bash
python3 scripts/generate_mockup.py \
  --type landing_page \
  --description "Coffee Shop in Seattle" \
  --no-ai \
  --output coffee_fast.svg
```
*Instant generation using pre-built industry-specific content*

**Wireframe mode:**
```bash
python3 scripts/generate_mockup.py \
  --type landing_page \
  --fidelity wireframe \
  --description "Developer tools platform" \
  --output wireframe.svg
```

## Performance Notes

| Mode | Generation Time | Notes |
|------|----------------|-------|
| `--no-ai` | < 1 second | Uses built-in industry defaults |
| AI-powered (cached) | < 1 second | Reuses previously generated content |
| AI-powered (first run) | 5-15 seconds | LLM API call for content generation |

Content is automatically cached after first generation. Same description + type + seed combination will use cached content on subsequent runs.

## Input / Output Specification

### Input

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--type` | string | ✅ | `landing_page`, `mobile_app`, `dashboard`, `ui_components` |
| `--description` | string | ✅ | Description for AI content generation |
| `--output` | string | ✅ | Output SVG file path |
| `--fidelity` | string | ❌ | `high` (default) or `wireframe` |
| `--theme` | string | ❌ | `light` (default), `dark`, `brand_blue` |
| `--width` | int | ❌ | Override canvas width |
| `--height` | int | ❌ | Override canvas height |
| `--seed` | int | ❌ | Random seed for reproducible output |
| `--no-ai` | flag | ❌ | Skip AI, use industry defaults (fast) |

### Output

- **Format:** SVG (valid XML, Figma-compatible)
- **Content:** All text, logos, illustrations, and avatars are generated — no placeholders
- **Figma Import:** File → Import → select the `.svg` file
- **Compatibility:** Figma, Sketch, Adobe XD, Inkscape, any SVG viewer/browser
- **Structure:** Grouped elements with semantic comments for easy layer navigation
- **Icons:** 50+ real SVG path icons, fully editable in Figma

## File Structure

```
figma-mockup/
├── SKILL.md                          # This file
├── scripts/
│   ├── generate_mockup.py            # Main generator (v3.0 — AI-powered)
│   ├── content_generator.py          # AI content generation module
│   ├── logo_generator.py             # SVG logo generator
│   ├── image_generator.py            # SVG illustration generator
│   └── svg_icons.py                  # SVG icon library (50+ icons)
├── references/
│   └── theme_reference.json          # Theme and mockup type metadata
└── templates/
    └── batch_generate.sh             # Batch generation script
```

## Module Reference

### content_generator.py
- `generate_content(description, mockup_type, seed)` → Dict with all content sections
- Uses Abacus.AI `evaluate_prompt` API for LLM-powered generation
- Automatic industry detection from description
- Built-in fallbacks for 10+ industries
- Content caching in `.content_cache/` directory

### logo_generator.py
- `generate_logo(brand_name, color, size, style)` → Standalone SVG string
- `generate_logo_inline(brand_name, color, x, y, size)` → Inline SVG for embedding
- Styles: `monogram`, `geometric`, `badge`, `minimal`, `circle_monogram`, `auto`

### image_generator.py
- `generate_hero_image(x, y, w, h, theme, description, industry)` → SVG illustration
- `generate_feature_image(x, y, w, h, theme, icon, index)` → Feature illustration
- `generate_profile_avatar(cx, cy, r, theme, name, index)` → Initial-based avatar
- 5 illustration styles: `dashboard_preview`, `abstract_shapes`, `wave_pattern`, `isometric_grid`, `floating_elements`

## Requirements

- **Python 3.7+** (standard library only for core generation)
- **Abacus.AI SDK** (for AI content generation — pre-configured, no setup needed)
- **Optional:** Use `--no-ai` flag to skip AI and use built-in defaults (zero dependencies)

## Tips for Agents

1. **Provide a descriptive `--description`** — more detail = better AI-generated content. "Coffee Shop in Seattle's Capitol Hill" generates better content than just "Coffee Shop".
2. **Use `--seed`** for reproducible outputs when consistency matters across multiple runs.
3. **Use `--no-ai`** for instant generation when speed is critical or API is unavailable.
4. **Industry detection is automatic** — the description triggers appropriate content templates.
5. **Content is cached** — re-running the same description is instant.
6. **All mockup content is editable in Figma** — text, colors, layouts can be adjusted after import.
7. **Type aliases supported**: `landing` → `landing_page`, `mobile` → `mobile_app`, `components` → `ui_components`.
