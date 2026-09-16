---
name: pr-icons
description: Author icons.json after the spec is final, let the user specify every icon, then render via the pr-icon-generator MCP
---

# Skill: Icons

Owns the plugin's icon design. Runs **after `plugin-spec.json` is final** (Phase 3 approved) and
**before component code is built** — once the component list is fixed but before we make the
components, so every icon can be specified up front. This replaces the old behaviour where
`pr-file-structure` silently generated a flat config at scaffold time.

The icon source website is **Iconify** (`iconify.design`) — every icon is referenced by its Iconify
ID, `prefix:name` (e.g. `mdi:magnify`, `ph:plus-bold`, `lucide:table`).

---

## Step 1 — show the background options and let the user pick (mandatory)

**Never choose a background for the user, and never let the template's choose itself.** Before
writing a single line of `icons.json`:

```
preview_backgrounds(output_dir="Icons/_preview", fg_iconify_id="<a glyph from this plugin's domain>",
                    styles="gradient,solid,none")
```

That renders every shape in `backgrounds/` in each fill style through the real render path, writes
`Icons/_preview/contact-sheet.png` (one labelled grid) plus a PNG per tile, and returns a catalog
with paste-ready snippets. Show it, then ask for a **fill style** and a **shape** (and optionally a
watermark and colours). `/rest-icon-preview` is this step as a standalone command.

The template's blue gradient rounded-square is a **placeholder, not a house style** — it exists so
the file is valid, not so it ships. A plugin whose icons all sit on a blue gradient blob nobody
asked for is the failure this step prevents.

## Step 2 — scaffold `icons.json` from the spec

Start from `mcps/pr-icon-generator/icons.template.json` — copy it to the plugin root as `icons.json`
and delete every `_`-prefixed documentation key. Write the **user's chosen style** into `defaults`
(and `plugin_icon`), replacing the template's placeholder background. Then read `plugin-spec.json`
and fill in the rest: one entry per component, grouped by subcategory, with a `plugin_icon` block.
Leave each `fg_iconify_id` filled with a **suggested** Iconify ID following the glyph rules below —
the user edits these.

## Step 3 — let the user specify

Present `icons.json` and ask the user to confirm or change icons. The background is built from
**independent optional layers** — the user picks any combination:
- the **foreground** Iconify glyph (`fg_iconify_id`) — itself optional
- a background **`shape`** (filled solid or with a gradient) — optional
- a background **`icon`** (an Iconify glyph behind the foreground) — optional
- **no background** — just omit both `shape` and `icon`
- colours / gradients for the shape, the bg icon, and the foreground
Wait for approval before rendering. The user may say "I'll pick the background icons" — let them fill
the `icon.iconify_id` per subcategory.

### The four background treatments

Exactly what the renderer supports — quote these verbatim when offering the choice:

```json
// gradient — two-colour linear gradient behind the glyph
"background": { "shape": { "type": "<slug>", "gradient": { "from": "#2D6CDF", "to": "#1B3A8B", "angle": 135 } } }

// solid — one flat colour behind the glyph
"background": { "shape": { "type": "<slug>", "fill": "#2D6CDF" } }

// none / transparent — no background at all; the glyph alone, filling the canvas
"background": {}

// watermark — optional extra layer, on top of any shape, under the foreground glyph
"background": { "shape": { "type": "<slug>", "fill": "#2D6CDF" },
                "icon":  { "iconify_id": "prefix:name", "color": "#FFFFFF", "opacity": 0.45 } }
```

`<slug>` is any shape from `preview_backgrounds` / `list_background_shapes()` — the SVG filenames in
`backgrounds/`, not a fixed list in code. Drop an SVG in and it works immediately.

## Step 4 — render

For each component: `generate_icon(component_name, config_path=icons.json)` then
`add_to_resources(component_name, config_path)`. Then once, as a **separate final step** for the
whole-plugin icon: `generate_plugin_icon(config_path)` + `add_to_resources("[PluginName]Logo", config_path)`.

- Component icons render at **24×24** px → resource `[XX]_[ComponentName]`, referenced in component
  code as `Properties.Resources.[XX]_[ComponentName]`.
- The plugin / ribbon category icon renders at **16×16** px → resource **`[XX]_[PluginName]Logo`**
  (`[XX]` = `plugin_prefix`, e.g. AcmeConnect → `AC_AcmeConnectLogo`). This is the exact name
  `pr-assembly` wires via `AddCategoryIcon` (as `Properties.Resources.[XX]_[PluginName]Logo`) — pass
  `"[PluginName]Logo"` to `add_to_resources` (it prepends the prefix), and keep the two in lockstep.
  `pr-vs-project` seeds a placeholder under this same key at scaffold; this step overwrites it.
- The **large logo** renders at **1024×1024** px to the plugin root as `[XX]_Plugin_Icon.png`:
  `generate_plugin_icon(config_path, size=1024, out_name="[XX]_Plugin_Icon.png")`. Same `plugin_icon`
  block, same artwork, rendered big. **Do not** `add_to_resources` it — it is a repo asset, not an
  embedded resource, and embedding a 1024 px PNG bloats the `.gha` for nothing.

### Three sizes, three jobs — render all three

| Size | Where it goes | Used by |
|---|---|---|
| 24×24 | `Icons/[XX]_[Component].png` → `Resources.resx` | every component's `Icon` property |
| 16×16 | `Icons/[XX]_[PluginName]Logo.png` → `Resources.resx` | the Grasshopper ribbon tab (`AddCategoryIcon`, `pr-assembly`) |
| 1024×1024 | `[XX]_Plugin_Icon.png` at the **plugin root** (never in `Icons/`, never in the resx) | the README header image (`pr-gh-package`) and the Food4Rhino listing image (`pr-yak-package`) |

The big one is the one that gets forgotten, and it is the only one a *user* ever sees before they
install anything — both dogfooded plugins needed it hand-made at ship time. Render it in Step 4
with the other two. A hand-authored `.svg` beside it is optional and always the user's own work;
the MCP renders PNG only.

---

## icons.json schema

```json
{
  "plugin_name": "[PluginName]",          // exactly as the author named it — no assumed suffix
  "plugin_prefix": "[XX]",                // from intake (pr-conventions "Plugin name"); never re-derive it here
  "resources_path": "Icons",
  "resx_path": "Properties/Resources.resx",

  "defaults": {
    "size": 24,
    "fg_color": "#FFFFFF",
    "background": {
      "shape": {                                         // OPTIONAL — omit for no shape
        "type": "rounded-square",                        // see Shapes below; list_background_shapes()
        "gradient": { "from": "#2D6CDF", "to": "#1B3A8B", "angle": 135 }
        // or solid instead of gradient:  "fill": "#444444"
      }
      // "icon": { ... }  also OPTIONAL — see subcategory example
    }
  },

  "plugin_icon": {
    "size": 16,
    "fg_iconify_id": "[prefix:name]",
    "fg_color": "#FFFFFF",
    "background": { "shape": { "type": "rounded-square",
                              "gradient": { "from": "#2D6CDF", "to": "#1B3A8B", "angle": 135 } } }
  },

  "subcategories": {
    "[Subcategory]": {
      "background": {
        "shape": { "type": "rounded-square", "gradient": { "from": "#2D6CDF", "to": "#1B3A8B", "angle": 135 } },
        "icon":  { "iconify_id": "[prefix:name]", "color": "#FFFFFF", "opacity": 0.45 }  // bg glyph (solid silhouette, blended)
      },
      "fg_color": "#FFFFFF"
    }
  },

  "components": [
    { "name": "FindBoard", "subcategory": "[Subcategory]",
      "fg_iconify_id": "mdi:magnify" },

    { "name": "GlyphOnly", "subcategory": "[Subcategory]",
      "fg_iconify_id": "mdi:eye",
      "background": {} },                                 // no background — glyph alone

    { "name": "ShapeOnly", "subcategory": "[Subcategory]",
      "fg_iconify_id": "mdi:plus",
      "background": { "shape": { "type": "circle", "fill": "#2D6CDF" } },
      "fg": { "from": "#FFFFFF", "to": "#BBD0FF", "angle": 90 } },  // optional fg gradient

    { "name": "HandDrawn", "subcategory": "[Subcategory]",
      "custom": true }                                     // hand-made Icons/[XX]_HandDrawn.png — generator skips it
  ]
}
```

**`"custom": true`** — the icon is hand-made. Drop `Icons/[XX]_[Name].png` (24×24) in yourself;
`generate_icon` returns a skip message and never overwrites it, `add_to_resources` still embeds
it. Mark its `[ASSET]` todo item `[x]` by hand. Use this for any icon a Phase 11 batch re-render
must leave alone.

**Resolution order:** `defaults` < `subcategories[sub]` < `components[i]`. Anything omitted inherits;
set `"background": {}` on a component to override down to no background (an explicit empty block
clears the inherited layers; only an *omitted* key inherits). Inside `background`, `"icon": {}` drops
an inherited bg icon while keeping your own `shape`. A component-level solid `fg_color` overrides an
inherited `fg` gradient.

**Background = optional layers (mix freely):**
- `shape` — a background SVG from `backgrounds/`; `fill` for solid **or** `gradient` for a linear
  gradient. Omit for no shape.
  - `align` — optional `{ fit, anchor }` (same shape as the foreground `glyph` override, below) to size
    and position the shape within the canvas. Default fits the whole canvas, centred (today's behaviour).
- `icon` — an Iconify glyph (`iconify_id`) drawn behind the foreground as a **solid silhouette** (interior
  holes of outline icons are filled in automatically). Sits on top of `shape` if both are present
  (**foreground glyph on a background icon on a shape**). Omit for no bg icon.
  - `color` — fill colour (default `"#FFFFFF"`). Use a light colour; the icon blends with the shape below via `opacity`.
  - `opacity` — `0..1`, blends the icon over the shape behind it (default `0.45`). Increase toward 1.0 for a more prominent bg icon; decrease toward 0 for a faint watermark.
  - `gradient` — use `{ "from": hex, "to": hex, "angle": deg }` instead of `color` for a gradient fill.
  - `align` — optional `{ fit, anchor }`, same as `shape.align` above, to size/position the bg icon
    independently (e.g. push it into a corner instead of centring it behind the foreground).
- both omitted (or `background: {}`) → **no background**, foreground glyph alone.

**Foreground:** a hex (`fg_color`) or a gradient (`fg`) — and the glyph itself is optional. Glyphs are
silhouette-tinted, so white / light / gradient foregrounds all render correctly.

**Shapes** — values for `shape.type`. Every shape is an SVG in the pr-icon-generator MCP's
`backgrounds/` folder; **call `preview_backgrounds()` to see them rendered, or
`list_background_shapes()` for the names alone** rather than trusting this list. The slug is the
filename minus the `bg-icon_` prefix, lowercased
(`bg-icon_Arrow-Square.svg` → `arrow-square`). As shipped (30):

`1-arch`, `3-arches`, `arrow-square`, `block`, `bookmark`, `bubble`, `canvas`, `chevron`, `circle`,
`cloud`, `copy`, `cut-square`, `database`, `diamond`, `document`, `ellipse`, `file`, `flower`,
`half-circle`, `hexagon`, `l-border`, `octagon`, `pentagon`, `quarter-circle-right`,
`right-triangle`, `rounded-rectangle`, `rounded-square`, `saddle-shape`, `square`, `trapezoid`.

**Glyph placement is drawn, not computed.** Each background SVG carries a `#ed1c24` rect marking
where the foreground glyph goes, authored in Illustrator next to the shape. The renderer strips that
rect before drawing (it never appears in output) and uses it as the glyph area. So placement is a
design decision living in the artwork — there is nothing to tune in `icons.json` for it, and adding a
shape means drawing its box, not writing config.

- Boxes may be **non-square** (Document's is wider than tall). A square glyph fits the shorter side,
  centred in the box.
- **Background icon, no shape** (just `background.icon`) → the bg icon fills the canvas and the
  foreground glyph sits at 85%, centred.
- **No background at all** (`background: {}` or omitted) → the glyph **fills the canvas edge to
  edge**: it is trimmed to its own ink first, then scaled until its longer side reaches 24px, with
  aspect preserved (a wide glyph spans the full width and is centred vertically). Iconify glyphs
  carry padding inside their viewBox — `mdi:plus` draws in only ~58% of it — so without the trim a
  glyph-only icon would render noticeably small.

**Some shapes need a dark foreground.** `trapezoid`, `saddle-shape`, `database`, `l-border`,
`quarter-circle-right`, `right-triangle` and `half-circle` place the glyph box *partly outside* the
artwork on purpose — the shape reads as a base or accent beneath the glyph rather than a container.
A white glyph on these disappears where it leaves the shape. Pick a dark `fg_color` for any
subcategory using them, or choose a container shape (`square`, `circle`, `hexagon`, `octagon`,
`rounded-square`, `bubble`, `flower`, `diamond`, …) if you want white-on-colour.

If a box reads badly for one particular icon, override it with the `glyph` block below.

Override the foreground per component / subcategory / defaults with an optional `glyph` block:
```json
"glyph": { "fit": 0.7, "anchor": [0.5, 0.5] }
```
`fit` = glyph's longest side as a fraction of the canvas; `anchor` = `[ax, ay]` in 0..1 (0.5,0.5 =
centred, higher = toward right/bottom). Everything stays optional.

**Every layer is independently alignable** — foreground glyph, background shape, and background icon
each take their own `{ fit, anchor }` block, so you can decide exactly where each one sits:
```json
"background": {
  "shape": { "type": "circle", "fill": "#2D6CDF", "align": { "fit": 0.9, "anchor": [0.5, 0.5] } },
  "icon":  { "iconify_id": "mdi:star", "align": { "fit": 0.6, "anchor": [0.8, 0.2] } }
},
"glyph": { "fit": 0.7, "anchor": [0.3, 0.6] }
```
- `background.shape.align` — sizes/positions the shape (default: fills the canvas, centred)
- `background.icon.align` — sizes/positions the background icon independently of the shape
  (default: fills the canvas, centred)
- top-level `glyph` — sizes/positions the foreground (default: shape-aware, see above)

All three default to the pre-alignment full-bleed/shape-aware behaviour, so `align` is only needed
when you want to depart from it (e.g. a small badge shape in a corner with the bg icon offset behind it).

---

## Glyph selection rules (suggested defaults)
- GET / read → outline glyph (e.g. `mdi:magnify`, `ph:eye`)
- POST / create → filled glyph with a plus (e.g. `mdi:plus-circle`)
- PATCH / update → a pencil / refresh (e.g. `mdi:pencil`)
- DELETE → a minus / trash (e.g. `mdi:trash-can`)
- JSON builder / aggregator → structural glyph (e.g. `lucide:table`, `ph:brackets-curly`)
- Preset (GH_ValueList) → list / menu glyph
- Auth → lock / key glyph
- Utilities → wrench / tool glyph

## Design quality bar
- One consistent background treatment per subcategory; foreground glyph communicates function at 24px
- Pick a per-plugin palette referencing the API platform's identity, adapted for a dense technical GH
  context (high contrast, modern). Gradients should be subtle (two close hues), not garish
- When unsure, **show the preview and ask** — do not fall back to a gradient blob. A useful prompt is
  "gradient reads as branded, solid reads as flat and modern, none reads as a plain toolbar glyph"
- There is no drop-shadow layer — depth comes from the background shape/gradient choice, not a shadow

## Rules
- **A background is never chosen for the user.** Run `preview_backgrounds` and get an explicit
  fill-style + shape decision before `icons.json` is written. The template's gradient
  rounded-square is a placeholder to keep the file valid — treating it as a default is the bug
  this rule exists to prevent
- Runs after the spec is final, before component build — never at scaffold time
- `icons.json` lives at the plugin root; the pr-icon-generator MCP is always called with its path as `config_path`
- Component icons 24×24, plugin/category icon 16×16, large logo 1024×1024 at the plugin root
- Every icon is user-approved before rendering; after the Phase 11 batch render, the rendered
  `Icons/` files are shown for a quick glance ("ok" / name any to redo) before the pipeline moves on
- `"custom": true` icons are never rendered or overwritten

