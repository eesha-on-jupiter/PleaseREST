---
description: "Re-render icons from icons.json and embed them into Resources.resx, without rerunning the full pipeline."
argument-hint: "[component_name]"
---

# /rest-icons [component_name]

Re-run icon rendering manually (Phase 11) — the `pr-icon-generator` MCP, writing `Icons/*.png` and
embedding each into `Resources.resx`. Use after editing `icons.json`, after `/rest-icon-preview`
changed the style, or to redo a single icon.

This renders what `icons.json` already says. It does **not** re-author `icons.json` — that's
`pr-icons` in Phase 8, or `/rest-icon-preview` for the background style.

---

## Steps

1. Confirm `icons.json` exists at the plugin root.
   If not: "No icons.json found. It's authored in Phase 8 — run /rest-icon-preview to pick a style,
   then /rest-resume-plugin." Stop.

2. Read `icons.json` for `plugin_name`, `plugin_prefix`, `resources_path`, `resx_path`, and the
   component list. Note this path — every MCP call takes it as `config_path`.

3. Decide the scope:
   - `$ARGUMENTS` given → that one component only (match on the `name` in `icons.json`; if no match,
     list the available names and stop).
   - no argument → every component in `icons.json`, plus the 16×16 plugin icon **and** the
     1024×1024 large logo.

4. **Skip `"custom": true` components.** The generator returns a skip message and never overwrites a
   hand-made `Icons/[XX]_[Name].png` — don't treat that as a failure. They still need step 6.
   If the user named a `custom` component explicitly, say it is hand-made and only embed it.

5. Render, per component:
   `generate_icon(component_name, config_path)` → then `add_to_resources(component_name, config_path)`
   Print Restling progress as each one lands. `add_to_resources` shells out to PowerShell and is
   **Windows-only** — on macOS it returns a clear error and the PNGs are still written, so the resx
   embed has to happen on a Windows machine.

6. Render the two plugin-level icons last, as separate steps, when no component argument was given:
   - `generate_plugin_icon(config_path)` → `add_to_resources("[PluginName]Logo", config_path)`
     The 16×16 ribbon/category icon at resource `[XX]_[PluginName]Logo` — the exact name
     `pr-assembly` wires via `AddCategoryIcon`. Keep the two in lockstep.
   - `generate_plugin_icon(config_path, size=1024, out_name="[XX]_Plugin_Icon.png")`
     The large logo, written to the plugin root for the README header and the Food4Rhino listing.
     **No `add_to_resources`** — it is a repo asset, not an embedded resource.

7. Track progress as you go: append each rendered resource name to
   `session.json.phase_progress["11"].rendered`, so a resume mid-render picks up at the next one.
   Clear `phase_progress["11"]` when a full (no-argument) run finishes and mark Phase 11 complete
   if it wasn't already.

8. Print the summary:
   ```
   Restling complete.
     Rendered:  [n]
     Skipped:   [n] (custom — hand-made PNG kept)
     Embedded:  [n]
     Failed:    [n]
   ```
   List any failure with its message. A bad `fg_iconify_id` is the usual cause — fix it in
   `icons.json` and rerun for that one component.

9. **Quick review (not a numbered gate).** List the rendered files in `Icons/` and ask:
   "Icons rendered — glance at Icons/ and say 'ok', or name any to redo."
   Re-render named ones from an edited `icons.json`.

10. If the plugin is already built, remind the user that a changed icon needs a rebuild to show up
    in Grasshopper: `dotnet build`, then reload Rhino.
