---
description: "Render every background shape in each fill style so the user can see the options and pick one before icons are authored."
argument-hint: "[iconify_id]"
---

# /rest-icon-preview [iconify_id]

Show the icon background options — every shape in `backgrounds/`, rendered in each fill style —
so the user picks a look instead of inheriting whatever the template shipped with.

Run this **before** authoring `icons.json` in Phase 8, or any time you want to change the plugin's
icon style. Read-only unless the user picks something.

---

## Steps

1. Find the config. If `icons.json` exists at the plugin root, read `plugin_prefix`,
   `resources_path` and the current `defaults.background` from it. If it doesn't exist yet
   (typical — this runs before Phase 8 authors it), that's fine: the preview needs no config.

2. Pick the preview glyph. Use `$ARGUMENTS` if the user supplied an Iconify ID (`prefix:name`);
   otherwise default to `mdi:star`. Suggest a glyph from the plugin's own domain when one is
   obvious from `plugin-spec.json` — a preview reads better with a glyph the user recognises.

3. Run MCP: pr-icon-generator →
   `preview_backgrounds(output_dir="Icons/_preview", fg_iconify_id=<glyph>, styles="gradient,solid,none")`
   Add `bg_icon_iconify_id=<glyph>` on a second pass if the user wants to see the watermark layer.
   Pass `fill` / `gradient_from` / `gradient_to` / `gradient_angle` when the user already has brand
   colours in mind — the defaults are a neutral blue, not a house style.

4. Show the returned catalog and point at `Icons/_preview/contact-sheet.png` — one labelled grid of
   every tile. The individual `preview_<slug>_<style>.png` files sit beside it.

5. **Ask the user to choose.** Never pick for them:
   ```
   Icon backgrounds — pick a look:

     Fill style   gradient   two-colour linear gradient behind the glyph
                  solid      one flat colour behind the glyph
                  none       no background at all — the glyph alone, edge to edge

     Shape        any of the [n] slugs in the catalog (ignored if you pick "none")

     Watermark    optional — a faint Iconify silhouette between the shape and the glyph

   Which style, and which shape?
   ```
   Offer colours too, if they haven't said. A plugin usually wants one treatment per subcategory
   with the foreground glyph carrying the meaning.

6. **Warn about the dark-foreground shapes.** If the user picks `trapezoid`, `saddle-shape`,
   `database`, `l-border`, `quarter-circle-right`, `right-triangle` or `half-circle`, say that these
   place the glyph partly outside the artwork by design — a white glyph will disappear where it
   leaves the shape, so the subcategory needs a dark `fg_color`.

7. Write the choice, if `icons.json` exists. Set `defaults.background` (and `defaults.fg_color`
   when they picked a foreground colour) to the chosen style:
   - gradient → `{ "shape": { "type": "<slug>", "gradient": { "from": "#…", "to": "#…", "angle": 135 } } }`
   - solid → `{ "shape": { "type": "<slug>", "fill": "#…" } }`
   - none → `{}`
   Leave every per-subcategory and per-component override alone — this sets the house default only.
   If `icons.json` doesn't exist yet, hand the snippet back and say pr-icons will use it in Phase 8.

8. Say what's next:
   - before Phase 8: "Style recorded. Phase 8 authors icons.json with it."
   - after icons are already rendered: "Run /rest-icons to re-render with the new style."

9. `Icons/_preview/` is scratch — mention that it can be deleted, and that it is covered by the
   generated plugin's `.gitignore` if it was not committed deliberately.
