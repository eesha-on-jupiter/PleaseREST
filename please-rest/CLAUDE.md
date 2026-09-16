# PleaseREST — Claude Code Plugin
> *Politely turns any REST API into a Grasshopper plugin — so you can take that much needed rest*

## What this plugin is

PleaseREST automates the repeatable process of building a Grasshopper REST API plugin.
Install once. Run `/rest-new-plugin` to start a build for any REST API.
The pipeline handles: API discovery, call extraction, HTTP validation, code scaffolding,
icon generation, tests, packaging, and Food4Rhino publish.

You plan, review, and test. PleaseREST does the rest.

**Active state verb:** `Restling` — used in all progress output.

> **User docs:** [`README.md`](README.md) + the [`docs/`](docs/) folder (overview, pipeline,
> commands, skills/agents, MCPs, troubleshooting). This `CLAUDE.md` is the contributor /
> internal reference; keep both in sync when phases, commands, or skills change.
>
> **Shipped context:** a `CLAUDE.md` at the plugin root is *not* loaded when the plugin is
> installed — Claude Code only ships skills. The consumer-facing orientation (what PleaseREST is,
> which command/skill/agent/MCP to reach for) therefore lives in
> [`skills/pr-overview/SKILL.md`](skills/pr-overview/SKILL.md). Keep it in sync with the
> Skills / Agents / MCPs / Commands sections below.

> **Versioning:** `.claude-plugin/plugin.json`'s `version` and [`CHANGELOG.md`](CHANGELOG.md) are
> how `/rest-resume-plugin` and `/rest-add-feature` detect that an in-progress plugin build predates
> a logic change (see `pr-session`'s "Version check on resume"). **Any change to a skill, agent,
> command, or MCP that would change what an already-completed phase produces must bump the version
> and add a `CHANGELOG.md` entry tagged with the affected phase(s).** A change that doesn't affect
> phase output (typo fixes, doc wording) doesn't need either. Skipping this makes the whole
> mechanism silently stale.

---

## Skills — what each covers

Always load alongside any other skill:
- `pr-conventions`     — naming, namespaces, comments, JSON rules

Load when the file type matches:
- `pr-component`       — any `GH_Component` file
- `pr-button`          — any create / update / delete component (extends `ButtonComponent`)
- `pr-builders`        — any `[Resource]Builders.cs` file
- `pr-bulk-data`       — GH data-tree handling for bulk/mass upload (unit/aggregator/bulk-write)
- `pr-client`          — `[PluginName]Client.cs`
- `pr-assembly`        — `[PluginName]Info.cs`
- `pr-preset`          — any `GH_ValueList` component
- `pr-utilities`       — `PluginUtilities.cs` — `TabName`, `Category[XX]` constants, `GetValues<T>()`
- `pr-file-structure`  — flat folder scaffold for a new generated plugin (no src/, no assets/docs/dist)
- `pr-vs-project`      — buildable VS Grasshopper project (Rh7 net48 / Rh8 net7.0-windows / Mac net7.0) + build check
- `pr-icons`           — shows the background options (`preview_backgrounds`) and gets an explicit style pick, then authors icons.json post-spec, user specifies every icon, renders via pr-icon-generator (24×24 components, 16×16 ribbon icon, 1024×1024 README / Food4Rhino logo)
- `pr-spec`            — proposing target workflows (Step 0, grounded in the API), then producing `plugin-spec.json` from `feasibility.json` + the confirmed workflow list
- `pr-todo`            — producing `spec/todo.md` from `plugin-spec.json`
- `pr-unit-tests`      — pure builder-logic xUnit tests (`BuilderTests.cs` + optional `BulkAssemblyTests.cs`, net8.0) — never one file per component
- `pr-build`           — `dotnet build` + `dotnet test` loop with failure surfacing
- `pr-rhino-test`      — Phase 12 Step B: builds the demo `.gh` files + live-tests components in Rhino via an external Grasshopper MCP bridge, auto-fix loop, before Gate 6
- `pr-gh-package`      — `README.md`, `CLAUDE.md`, `LICENSE`, `.gitignore`, then `gh repo create` + push (Phase 14)
- `pr-yak-package`     — `.yak` build for all 3 targets (Rh7 Win, Rh8 Win, Rh8 Mac) + the post-Gate-7 publish checklist (tag / `yak push` / Food4Rhino) and the README + docs placeholder backfill
- `pr-ci-template`     — `.github/workflows/build.yml` (PR) + `publish.yml` (tag → 3 `.yak` + 3 `.zip` Release)
- `pr-session`         — `session.json` read/write/resume + global sessions index + the phase-completion audit that reconciles recorded phases against artifacts on disk (optional fields: `preflight`, `github`, `published`, `gate_feedback`/`awaiting_fix`, `skipped_phases`, `degraded`, `phase_progress`, …)
- `pr-permissions`     — `.claude/settings.local.json` generated inside the generated plugin at Phase 1 intake (a root-level file is ignored by Claude Code)
- `pr-docs`            — `docs/` folder of portable markdown, incl. up to two cross-cutting concept pages (Phase 13)
- `pr-dogfood`         — running findings log per run (appends findings / phase results / gate notes to `findings_path`)
- `pr-overview`        — the shipped orientation: what PleaseREST is and which command / skill / agent / MCP handles what (mirrors this file's inventory)

> **Two "Phase N" numberings:** the pipeline's Phases 1–15 and `todo.md`'s own build Phases 1–10
> (`pr-todo`). Qualify as "todo build Phase 2" vs "pipeline Phase 2" wherever it could be read either
> way. todo items tagged `[SHIP]` are pipeline Phases 13–15 and are never run by
> `/rest-build-all-components`.

---

## Agents

- `pr-api-scout`   — runs after `pr-api-tester`; for FAILED or PARTIAL entries reads `test_result.error_body`, re-fetches the docs page (or re-reads the spec operation), patches `call-library.json`, retests; escalates after one pass if still failing. Skips harness-class failures (every entry failing the same way) and "enrich then retest" PARTIALs
- `pr-aec-advisor` — runs after plugin-spec is confirmed; cross-references AEC feature library against the API's actual data shape; outputs structured recommendations
- `pr-spec-critic` — runs on the drafted (not yet confirmed) plugin-spec, before Gate 2; flags unnecessary complexity against workflows.json — merge/consolidation candidates, unneeded tree variants, empty indirection

---

## MCPs

- **`pr-api-extractor`** — crawls API docs or parses an OpenAPI spec / Google API Discovery doc; writes `call-library.json`
  - `extract_from_openapi(spec_url, component_list, output_path?)` — auto-detects OpenAPI 3 (`paths`),
    Swagger 2.0 (`swagger: "2.0"`) and Google API Discovery (`resources→methods`, for
    Slides/Sheets/Docs/Drive/Gmail/Calendar — `base_url` = `rootUrl` + `servicePath`); fills each
    entry's `base_url`, `auth_in` (from `securitySchemes` / `security`: `"header"` = Authorization:
    Bearer · `"header:<Name>"` = raw token in that header · `"query:<param>"`), `body_required`
    (required top-level body fields) and `content_type`; reads OpenAPI 3 `examples` and schema-level
    `example` / `default`; substitutes `servers[].variables` defaults; a non-dict spec or an external
    `$ref` returns a clear error / PARTIAL instead of raising. Progress goes to stderr (stdout is the
    MCP stream).
  - `extract_from_docs(docs_url, endpoint_path, method, component_name, endpoint_id, output_path?)`
  - `write_call_library(entries, output_path)`
  - Status tags: EXTRACTED · PARTIAL (write endpoint with no resolvable body — enrich before testing) ·
    AMBIGUOUS (oneOf/anyOf) · MISSING
  - Tested: Petstore OpenAPI spec — EXTRACTED/MISSING tags correct, path + query params resolved

- **`pr-api-tester`** — fires real HTTP calls; writes `call-library-validated.json`
  - `test_endpoint(entry, token?, seed_ids?, base_url?)` — `token` falls back to `PLEASE_REST_TOKEN`
  - `run_all_tests(call_library_path, output_path, token?, skip_destructive?, base_url?, seed_ids?)`
  - `retest_entries(entry_ids, call_library_path, output_path, token?, base_url?, seed_ids?)`
  - Joins a `base_url` to relative `url_template`s (entry `base_url` field wins over the arg); token
    placement follows the entry's `auth_in` (`header` → `Authorization: Bearer` · `header:<Name>` →
    raw token in that header · `query:<param>`)
  - Auth: reads `PLEASE_REST_TOKEN` env var; never pass the token as an argument (it would land in the
    transcript). The token is never written to any output file.
  - **PARTIAL entries are not fired.** Write endpoints with no `example_request` are listed as
    "skipped — PARTIAL (enrich example_request, then retest_entries)" and written with
    `test_result.tag: "PARTIAL"`, `error: "not tested — no request body example"`. 3xx → PARTIAL
    "redirect — check base_url". 429 honours `Retry-After`; timeouts retry on their own counter.
  - Responses are parsed **in full** for tagging and seed harvesting; only the stored `response_body`
    is truncated to 2000 chars. Seed IDs are harvested from every 2xx as both `boardId` and `board_id`;
    `build_url` accepts either form and URL-encodes values; `{+name}` placeholders are flagged unfilled.
  - Each `test_result` = `{ tag, status_code, latency_ms, validated, error, error_body }` — `error_body`
    is the first 500 chars of a failing response, for `pr-api-scout`.
  - Tested: httpbin — VALIDATED on 200, FAILED on 401/404, POST body sent correctly

- **`pr-icon-generator`** — renders layered icons (optional bg shape + optional bg icon + optional fg
  glyph, any colour or gradient via silhouette+tint); injects into `Resources.resx` + `Designer.cs`.
  Driven by `icons.json` (authored by `pr-icons` post-spec). Background icons (`bg.icon`) are always
  rendered as **solid silhouettes** (outline icons' interior holes filled in via `make_solid`);
  `color` defaults to `#FFFFFF`, `opacity` to `0.45`.
  - `generate_icon(component_name, config_path, subcategory?, iconify_id?)` — 24×24 component icon.
    A component with `"custom": true` in `icons.json` is skipped (hand-made `Icons/[XX]_[Name].png` kept).
  - `generate_plugin_icon(config_path, size?, out_name?)` — 16×16 plugin/ribbon category icon by
    default; `size=1024, out_name="[XX]_Plugin_Icon.png"` renders the large README / Food4Rhino logo
    to the plugin root instead (`out_name` resolves under the icons.json folder and may not escape
    it; the big logo is never embedded in the resx)
  - `list_background_shapes()` — the shape names currently in `backgrounds/`
  - `preview_backgrounds(output_dir, fg_iconify_id?, styles?, shapes?, size?, fill?, gradient_from?,
    gradient_to?, gradient_angle?, fg_color?, bg_icon_iconify_id?)` — renders every shape × style
    through the real render path into `output_dir`: `preview_<slug>_<style>.png` per tile plus a
    labelled `contact-sheet.png`, returning a catalog with paste-ready snippets. `styles` ⊆
    `gradient,solid,none` (`none` = no background, emitted once as `preview_none.png`); `shapes`
    narrows to named slugs; `bg_icon_iconify_id` adds the watermark layer. Needs no `icons.json` —
    colours come in as arguments. This is what makes the options **visible**; `/rest-icon-preview`
    wraps it, and `pr-icons` must run it before authoring.
  - `add_to_resources(component_name, config_path)` — **Windows-only** (PowerShell `ResXResourceWriter`);
    Designer.cs de-dupe matches the `Bitmap <Name>` property itself, not the VS comment pattern.
  - Style resolution `defaults < subcategories[sub] < components[i]`: an explicit `"background": {}`
    (or `"icon": {}` inside it) clears the inherited layer — only an *omitted* key inherits; a
    component-level solid `fg_color` beats an inherited `fg` gradient. Iconify fetches are cached per
    process; a malformed id (`mdiplus`) gets an "expected 'prefix:name'" error.
  - `config_path` is **required** on every tool — it names the plugin's `icons.json`. There is no
    default config: `icons.template.json` beside `server.py` is a template pr-icons copies, and
    omitting `config_path` raises rather than silently rendering another plugin's icons. The old
    flat `bg_shape`/`bg_color`/`icon_color` schema has been removed.
  - **Background shapes are SVG files in `mcps/pr-icon-generator/backgrounds/`, not code.** There are
    no built-in shapes: `shape.type` is the filename slug (`bg-icon_Arrow-Square.svg` → `arrow-square`),
    and dropping a new SVG in makes it available with no code change. Files must be square-viewBox
    vector with unfilled geometry (they're rasterised to a silhouette and tinted); raster `<image>`
    elements and empty files are rejected with a clear error.
  - **Glyph placement is authored in the artwork, not computed.** Each background SVG also carries a
    `#ed1c24` rect marking where the foreground glyph goes — drawn in Illustrator beside the shape.
    `split_glyph_box()` strips it before rasterising (so it never renders) and `glyph_box()` reads it
    as the placement. Boxes may be non-square; a square glyph fits the shorter side, centred.
    Resolution is by *fill colour*, not Illustrator's `cls-N` class name, which is unstable across
    re-exports. Override per icon with the `glyph` block in `icons.json`.
  - Some shapes (`trapezoid`, `saddle-shape`, `database`, `l-border`, `quarter-circle-right`,
    `right-triangle`, `half-circle`) deliberately place the glyph box **partly outside** the artwork —
    the shape reads as a base or accent under the glyph. These need a **dark** foreground; a white
    glyph would disappear off the shape.
  - Foreground glyphs still come from Iconify (`prefix:name`).
  - **The glyph fills ~95-100% of its target area — the authored glyph box, or the full canvas
    when there's no background.** `trim_alpha()` crops the glyph to its own ink before placing,
    because Iconify glyphs pad their viewBox (`mdi:plus` only draws in ~58% of it, `mdi:magnify`
    ~75%) — without trimming, that padding scales along with `fit` and leaves the icon visibly
    smaller than the box/canvas it was placed to fill. Trimming is unconditional (both with and
    without a background) so `fit` always describes what's actually drawn.
  - No drop-shadow support — icons render as background layer + foreground glyph only.

- **Grasshopper MCP bridge** (EXTERNAL — not shipped here) — used by `pr-rhino-test` in Phase 12 to
  build the demo `.gh` files and live-test components in Rhino. **Official: McNeel `mcneel/RhinoMCP`**
  ("Rhino-MCP-Platform" in the Rhino 8/9 Package Manager). Install via the `PackageManager` command
  (search "Rhino-MCP-Platform"), then run `MCPConnect` in Rhino — it starts a local HTTP/SSE server
  and prints a registration prompt you paste into Claude Code (no fixed-port `claude mcp add`). Not in
  `plugin.json` because it needs a live Rhino session and is user-wired. **Caveat:** confirm at runtime
  that it places/resolves PleaseREST's *custom* components against the live registry before relying on
  it; community fallback if not: `cordyceps` (or `SandMartin`). See `pr-rhino-test/SKILL.md`.

---

## Commands

```
/rest-new-plugin                  start a new plugin build (full 15-phase pipeline)
/rest-resume-plugin               resume from last session
/rest-gen-spec                    regenerate plugin-spec.json from feasibility.json
/rest-gen-todo                    regenerate todo.md from plugin-spec.json
/rest-extract-api                 re-run API extraction manually
/rest-test-api                    re-run HTTP validation manually
/rest-build-component <id>        scaffold one component by ID
/rest-build-all-components        build all unbuilt components in phase order
/rest-add-feature <description>   add a component/feature any time — even post-ship (re-enters at Phase 3, catches up Docs/GitHub/Package)
/rest-icon-preview [glyph]        render every background shape in each fill style — pick one before icons are authored
/rest-icons [component]           re-render icons from icons.json + embed into Resources.resx (manual Phase 11)
/rest-status                      show the pipeline progress tree on demand (where you are + what's next)
/rest-package                     build .yak for all 3 targets + both CI workflows
```

---

## Tests

Tests live **outside** the `please-rest/` plugin folder, at the repo root:

```
tests/
├── requirements.txt              pytest, pytest-asyncio, mcp[cli], httpx, resvg-py, pillow, pyyaml, beautifulsoup4
├── conftest.py                   shared path constants (REPO_ROOT, MCP_ROOT, etc.)
│
├── pr-icon-generator/
│   ├── conftest.py               loads server.py under unique key, pins it as `server` per test
│   ├── test_config.py                    — load_config: config_path required, re-read on every call, missing file;
│   │                                        icons.template.json valid/modern/no-legacy/shapes-exist
│   ├── test_rendering.py       190 tests  — hex_to_rgb, shape discovery/slugs, size_svg_root,
│   │                                        load_shape_mask (every shipped SVG + raster/empty
│   │                                        rejection), glyph_box parsing + box↔fit/anchor,
│   │                                        gradient, fill_from_alpha, scale_alpha, make_solid (4),
│   │                                        resolve_placement, build_background + bg.icon
│   │                                        opacity (2), _render
│   ├── test_generate_icon.py    11 tests  — generate_icon (config, override, no-glyph, missing
│   │                                        config_path, HTTP error), generate_plugin_icon
│   │                                        (Logo, 16px), add_to_resources
│   └── test_style_and_resources.py 15 tests — resolve_style (`background: {}`, `icon: {}`, fg_color
│                                            precedence), `custom: true` skip, Iconify id parsing,
│                                            Designer.cs de-dupe / safe insertion
│
├── pr-api-extractor/
│   ├── conftest.py               loads server.py under unique key, pins it as `server` per test
│   ├── test_refs.py             14 tests  — resolve_refs (circular, nested, list), simplify_schema
│   ├── test_schema.py           10 tests  — extract_params, blank_entry defaults
│   ├── test_extract_openapi.py   9 tests  — inline Petstore spec, YAML input, MISSING, pagination note
│   └── test_spec_formats.py     22 tests  — securitySchemes → auth_in, Discovery servicePath,
│                                            Swagger 2.0, plural `examples`, servers[] variables,
│                                            non-dict spec, external $ref → PARTIAL, body_required
│
└── pr-api-tester/
    ├── conftest.py               loads server.py under unique key, pins it as `server` per test
    ├── test_url_builder.py       7 tests  — build_url: single/multi params, missing, unfilled
    ├── test_tag_result.py       15 tests  — 200/201/204/401/403/404/500, schema key matching
    ├── test_write_validated.py   6 tests  — merge, order preservation, untested entries retained
    ├── test_test_endpoint.py     8 tests  — 200/404/401/429 backoff, timeout, missing param, POST body
    └── test_run_all_tests.py    21 tests  — run_all_tests / retest_entries via MockTransport: PARTIAL
                                             skip, seed_ids param, seed harvesting from full body
                                             (truncation), camel/snake seed keys, auth_in header:<Name>,
                                             error_body, 3xx → PARTIAL, output order
```

Per-file test counts above are indicative — later dev rounds added tests for `resolve_style`, `custom`
skip, truncation vs harvesting, seed-key forms, `auth_in` placement, `run_all_tests` /
`retest_entries` (MockTransport), `securitySchemes` → `auth_in`, Discovery `servicePath`, Swagger
2.0, plural `examples`, non-dict specs and Designer.cs de-dupe, plus three for
`generate_plugin_icon`'s `size` / `out_name` (the 1024 px logo, the path-escape refusal, a bad size).
`pytest -q` is the source of truth.

**Run all tests:**
```
cd tests
pip install -r requirements.txt      # pytest, pytest-asyncio, mcp[cli], httpx, resvg-py, pillow, pyyaml, beautifulsoup4
pytest
```

**Run one MCP's tests:**
```
pytest pr-api-extractor/
pytest pr-api-tester/
pytest pr-icon-generator/
```

---

## Working on PleaseREST itself

### File structure

```
PleaseREST/                                  repo root (the plugin lives in please-rest/)
├── .claude-plugin/
│   └── marketplace.json                     marketplace manifest — what `/plugin marketplace add`
│                                            reads; lists please-rest with source ./please-rest
├── LICENSE                                  MIT — PleaseREST's own licence
├── .gitignore                               keeps .claude/, dogfood/, __pycache__, .pytest_cache/
│                                            and the working files out of the repo
├── PleaseREST-spec.md                       full specification
├── todo.md                                  build progress for PleaseREST itself
├── .claude/                                 NOT COMMITTED — machine-local: settings.local.json
│                                            (pre-approved permissions) + launch.json. This is the
│                                            only place Claude Code reads project-local settings
│                                            from, and none of it is read once the plugin is installed
├── dogfood/                                 NOT COMMITTED — dogfood run logs (internal)
├── tests/                                   MCP test suite (see Tests above); committed, not shipped
│                                            to plugin users — it lives outside please-rest/
│
└── please-rest/                             the shipped plugin
    ├── .claude-plugin/
    │   └── plugin.json                      plugin manifest (name, mcpServers)
    ├── .claude/                             NOT COMMITTED — plugin-dev settings only
    ├── CLAUDE.md                            this file (contributor notes)
    ├── README.md                            user-facing entry point → docs/
    │
    ├── docs/                                user-facing documentation
    │   ├── index.md                         overview & concepts
    │   ├── pipeline.md                       15 phases / 7 gates / extend loop
    │   ├── commands.md                       command reference
    │   ├── skills-and-agents.md              skills + agents reference
    │   ├── mcps.md                           MCP servers + tools
    │   └── troubleshooting.md                common issues + fixes
    │
    ├── commands/                            13 command files (all rest-*)
    │   ├── rest-new-plugin.md
    │   ├── rest-resume-plugin.md
    │   ├── rest-gen-spec.md
    │   ├── rest-gen-todo.md
    │   ├── rest-extract-api.md
    │   ├── rest-test-api.md
    │   ├── rest-build-component.md
    │   ├── rest-build-all-components.md
    │   ├── rest-add-feature.md
    │   ├── rest-status.md
    │   ├── rest-icon-preview.md
    │   ├── rest-icons.md
    │   └── rest-package.md
    │
    ├── skills/                              25 shipped skill folders (all pr-*)
    │   ├── pr-overview/                     shipped orientation (mirrors this file)
    │   ├── pr-conventions/
    │   ├── pr-component/
    │   ├── pr-button/
    │   ├── pr-client/
    │   ├── pr-builders/
    │   ├── pr-bulk-data/
    │   ├── pr-assembly/
    │   ├── pr-preset/
    │   ├── pr-utilities/
    │   ├── pr-file-structure/
    │   ├── pr-vs-project/
    │   ├── pr-icons/
    │   ├── pr-spec/
    │   ├── pr-todo/
    │   ├── pr-unit-tests/
    │   ├── pr-build/
    │   ├── pr-rhino-test/
    │   ├── pr-gh-package/
    │   ├── pr-yak-package/
    │   ├── pr-ci-template/
    │   ├── pr-session/
    │   ├── pr-permissions/
    │   ├── pr-dogfood/
    │   └── pr-docs/
    │
    ├── agents/                              3 agents (all pr-*)
    │   ├── pr-api-scout.md
    │   ├── pr-aec-advisor.md
    │   └── pr-spec-critic.md
    │
    └── mcps/                                3 MCP servers (all pr-*)
        ├── pr-api-extractor/
        │   ├── server.py
        │   └── requirements.txt
        ├── pr-api-tester/
        │   ├── server.py
        │   └── requirements.txt
        └── pr-icon-generator/
            ├── server.py
            ├── backgrounds/                shape SVGs (bg-icon_*.svg) — artwork + glyph box
            ├── icons.template.json         starting point pr-icons copies (never rendered)
            └── requirements.txt
```

### Build state

All rounds complete as of 2026-06-11. Tests written as of 2026-06-11.

```
Round 1 — Fix pr-icon-generator MCP           ✅ complete
Round 2 — pr-api-extractor + pr-api-tester ✅ complete — tested against Petstore + httpbin
Round 3 — Missing skills             ✅ complete
Round 4 — Ship layer skills          ✅ complete
Round 5 — Agents                     ✅ complete
Round 6 — Plugin packaging           ✅ complete
Round 7 — MCP test suite             ✅ complete — 364 tests across 3 MCPs in tests/
Round 8 — Permissions + docs         ✅ complete — pr-permissions + pr-docs skills, settings.local.json cleaned
```

### Icon-engine parity with the sibling product

`mcps/pr-icon-generator/` is kept at **feature parity** with the equivalent server in the separate
standalone icon product (its `sect-icon-generator` / `sect-icons`). `server.py`,
`icons.template.json` and `backgrounds/` are functionally identical and differ only in the server's
own name — its docstring header and the `FastMCP(...)` argument. Rendering behaviour, the schema and
the four background treatments must stay the same in both; the entry points deliberately differ
(PleaseREST drives icons through the pipeline plus `/rest-icon-preview` and `/rest-icons`).

**Changing icon rendering?** Apply it in both repos, diff the two `server.py` files to confirm only
the name lines differ, and run both test suites. This note lives here, not in `pr-icons`: skills
ship to users, and cross-repo maintenance instructions are contributor business.

### Adding a new skill

1. Create `skills/pr-[name]/SKILL.md` at the plugin root (frontmatter `name:` must equal the folder
   name). Skills are **auto-discovered** — do **not** add a `skills` array to `plugin.json`: that is a
   schema error that loads the plugin with zero skills and no error message (dogfood Airtable F2).
2. Add a line for it in the Skills section of this file **and** in `skills/pr-overview/SKILL.md`.
3. Update the skill count in the file tree above, `README.md` and `docs/skills-and-agents.md`.
4. Run `claude plugin validate ./please-rest`.

### Adding a new command

1. Create `commands/[command-name].md` at the plugin root (frontmatter `description:`). Commands are
   auto-discovered — no `commands` array in `plugin.json`.
2. Add a line for it in the Commands section of this file, in `README.md`, `docs/commands.md` and
   `skills/pr-overview/SKILL.md`.
3. Run `claude plugin validate ./please-rest`.

### Adding an agent

Same pattern: `agents/pr-[name].md`, auto-discovered, no manifest array; list it here, in
`docs/skills-and-agents.md` and in `pr-overview`.
