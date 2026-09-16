# Commands Reference

PleaseREST ships 13 slash commands, all prefixed `rest-`. They drive the pipeline, re-run
individual phases, and manage state.

## Pipeline entry & resume

### `/rest-new-plugin`
Start a new build. Checks for an existing `spec/session.json` first (never overwrites without
confirmation), runs a **preflight** (MCP servers connected, Python deps, .NET SDK, yak, token,
optional Rhino bridge — results saved to `session.json.preflight`), then runs the full **15-phase**
pipeline from intake, pausing at each of the 7 gates. This is the main entry point.

### `/rest-resume-plugin`
Resume from the last session. Reads `spec/session.json` (or the global sessions index if not in
a plugin directory), renders the progress tree, and continues from `next_step`. Handles
single-session, multiple-session, and no-session cases. First checks whether PleaseREST has moved
on since this session was last touched — see [versioning](index.md#design-principles) — and shows
what changed (with a re-run option) before the resume prompt if so.

### `/rest-status`
Render the pipeline progress tree on demand at any time — completed/current/upcoming phases,
passed/current gates, a `Now:`/`Next:` footer, and (mid-build) a per-subcategory component
completion count from `todo.md`. Also flags (read-only, one line) if a newer PleaseREST version
is available. Read-only; touches no state.

## Spec & planning

### `/rest-gen-spec`
Regenerate `spec/plugin-spec.json` from `feasibility.json` (re-runs Phase 3's Step 0 workflow
proposal if `workflows.json` doesn't exist yet, then the spec proposal, `pr-spec-critic`'s
simplification pass, and the inline validator). Use after editing the feasibility map. Carries the
existing `aec_features` (Gate 3) forward, never resets `completed_phases`, and — when run after
Phase 5 — lists which downstream artifacts (todo, call libraries, built components) are now stale.

### `/rest-gen-todo`
Regenerate `spec/todo.md` from `plugin-spec.json` (Phase 5). Use after the component list
changes.

## API extraction & testing

### `/rest-extract-api`
Re-run API extraction manually (Phase 6) — the `pr-api-extractor` MCP, writing
`call-library.json`. Use to refresh after docs/spec changes. The previous file is kept as
`call-library.prev.json`, a diff is shown, and hand enrichments recorded in
`decisions.manual_fixes` are re-applied or listed — a re-extract never silently erases Gate-4 work.

### `/rest-test-api`
Re-run HTTP validation manually (Phase 7) — the `pr-api-tester` MCP, writing
`call-library-validated.json` (previous kept as `.prev.json`). Reads the token from
`PLEASE_REST_TOKEN`; passes `decisions.seed_ids` from intake. Routes results: an all-same-error
run is treated as one harness problem, PARTIAL entries are "enrich `example_request` then retest",
only real FAILED entries go to `pr-api-scout` and then Gate 4.

## Component building

### `/rest-build-component <id>`
Scaffold a single component by its ID from `plugin-spec.json`. Loads the right type skill
(`pr-component` / `pr-button` / `pr-builders` / `pr-preset`) for that component. Writes to the
flat layout (`Components/…`, `JSON Builders/`, `Components/Presets/`) and refuses to build from a
non-VALIDATED call unless the user decided so at Gate 4.

### `/rest-build-all-components`
Build every unbuilt `[CODE]` item in `todo.md`'s build phases in order, rendering each group's
`[ASSET]` icons as it goes. Stops before the `[SHIP]` items (docs / GitHub / package — those are
Phases 13–15, after Gate 6). Equivalent to running Phase 10 to completion.

## Icons

### `/rest-icon-preview [iconify_id]`
Render every background shape in `backgrounds/` in each fill style — **gradient**, **solid**,
**none** — into `Icons/_preview/`, as individual PNGs plus one labelled `contact-sheet.png`, then
ask which to use. Optionally previews the watermark layer too. Writes the chosen style into
`icons.json`'s `defaults.background` if that file exists yet; otherwise hands back the snippet for
Phase 8. Run it before icons are authored, or any time you want to change the plugin's look. The
optional argument is the Iconify glyph to preview with (default `mdi:star`).

### `/rest-icons [component_name]`
Re-run icon rendering manually (Phase 11) — `generate_icon` + `add_to_resources` for every
component in `icons.json`, then `generate_plugin_icon` for the 16×16 ribbon icon. With a component
name, renders just that one. Skips `"custom": true` components (a hand-made PNG is never
overwritten, but is still embedded), tracks `phase_progress["11"].rendered` so a mid-render resume
picks up where it stopped, and ends with the same quick "glance at Icons/" review Phase 11 uses.
Does not re-author `icons.json`. The resx embed is Windows-only.

## Extending & packaging

### `/rest-add-feature <description>`
Add a new feature or component to an existing build, at any point in its life — mid-build,
sitting in Docs/GitHub/Package, or already shipped; there's no "too late" state. First runs the
same version check as `/rest-resume-plugin`. Re-enters the pipeline at **Phase 3** (spec update
only, workflow-proposal + `pr-spec-critic` included) and runs Phases 6–12 for the new components
only (incrementally — new endpoints are merged into the call library and retested alone; on a
plugin that hasn't reached Phase 9 yet it stops after amending the spec and todo) — including the **icon approval gate** and a live **Gate 6** re-test — then catches up any
of Phases 13–15 the plugin had already finished (incremental docs, always-fresh README/CLAUDE.md,
a `dist/*.yak` rebuild) so a shipped plugin never ends up with an undocumented, unpackaged
component. This is the same loop `/rest-new-plugin` offers after Gate 6; existing components are
never rebuilt.

### `/rest-package`
Build `.yak` packages for all three Rhino targets (Rh7 Win, Rh8 Win, Rh8 Mac) into `dist/`, and
generate both CI workflows — `.github/workflows/build.yml` and `publish.yml` (Phase 15). Refuses to package a component
whose call is not VALIDATED unless you say "ship anyway" (recorded in
`decisions.ship_unvalidated`). Post-ship rounds bump the csproj `<Version>` first.

---

## At a glance

| Command | Phase(s) | Writes |
|---|---|---|
| `/rest-new-plugin` | 1–15 | everything |
| `/rest-resume-plugin` | — | continues from `session.json` |
| `/rest-status` | — | nothing (read-only) |
| `/rest-gen-spec` | 3 | `plugin-spec.json` |
| `/rest-gen-todo` | 5 | `todo.md` |
| `/rest-extract-api` | 6 | `call-library.json` |
| `/rest-test-api` | 7 | `call-library-validated.json` |
| `/rest-build-component <id>` | 10 | one component file |
| `/rest-build-all-components` | 10 | all component files + icons |
| `/rest-icon-preview [glyph]` | 8 (or any time) | `Icons/_preview/*`, `icons.json` `defaults.background` |
| `/rest-icons [component]` | 11 | `Icons/*.png`, `Resources.resx` |
| `/rest-add-feature <desc>` | 3, 6–12 (+13–15 catch-up if needed) | new components only |
| `/rest-package` | 15 | `dist/*.yak`, CI workflow |
