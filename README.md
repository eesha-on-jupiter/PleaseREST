# PleaseREST

> *Politely turns any REST API into a Grasshopper plugin — so you can take that much needed rest.*

PleaseREST is a Claude Code plugin that automates the repeatable parts of building a Grasshopper
plugin for a REST API: API discovery, call extraction, live HTTP validation, code scaffolding,
icon generation, tests, docs, packaging, and publishing.

**You plan, review, and test. PleaseREST does the rest.**

Run `/rest-new-plugin`, point it at an API reference, and it drives a **15-phase pipeline with 7
human gates** to a buildable, tested, documented, packaged Grasshopper plugin for Rhino 7 and 8 on
Windows and Mac. Nothing irreversible happens without a gate.

`13 commands · 25 skills · 3 agents · 3 MCP servers · 364 tests`

---

## Install

```
/plugin marketplace add eesha-on-jupiter/PleaseREST
/plugin install please-rest
```

Confirm the MCP servers came up:

```
/mcp
# expect: please-rest → pr-api-extractor, pr-api-tester, pr-icon-generator  (connected)
```

**Local development** — point Claude Code at the plugin folder instead:

```
claude --plugin-dir /path/to/PleaseREST/please-rest
```

### Requirements

| Needed for | What |
|---|---|
| The three MCP servers | **Python ≥ 3.10**, reachable as `python` on PATH, with `mcp[cli] httpx resvg-py pillow pyyaml beautifulsoup4` (`pip install -r please-rest/mcps/<server>/requirements.txt`, each of the three) |
| Building generated plugins | **.NET SDK 8.x** — builds the net48 / net7.0-windows / net7.0 targets plus the net8.0 test project |
| Phase 15 packaging | **`yak`** — ships with Rhino, but is not on PATH; PleaseREST probes the Rhino install |
| Phase 12 live Rhino test (optional) | An external **Grasshopper MCP bridge** (McNeel `Rhino-MCP-Platform`). Without it Phase 12 degrades gracefully and Gate 6 becomes manual |

> The servers are launched as literally `python`. On macOS/Linux that is often only `python3`, and
> on Windows it can resolve to the Microsoft Store stub — either shows up as all three servers
> "not connected". See [troubleshooting](please-rest/docs/troubleshooting.md).

`/rest-new-plugin` checks all of this in a preflight before it asks you anything.

---

## Quick start

```
/rest-new-plugin
```

Intake asks for: **what you want to call the plugin** (any name — there is no required suffix) and
its 2–3 letter icon prefix, **your** author name and contact and GitHub org (they go in the
generated plugin, not in PleaseREST), the **API docs URL**, token readiness, and optionally a
sandbox / seed IDs for the live HTTP tests.

Then it walks the pipeline, stopping at each gate. `/rest-status` shows where you are at any time;
`/rest-resume-plugin` picks a build back up in a later session.

---

## The pipeline — 15 phases, 7 gates

Before every gate question — and on resume, and on `/rest-status` — PleaseREST renders this tree
plus a **YOUR MOVE** block telling you exactly what to do and how to answer.

```
PleaseREST — AcmeConnect   ·   Restling
═══════════════════════════════════════════════════════════════
  ✓   1  Intake
  ✓   2  API Discovery       ◆ Gate 1 · Approve API           ✓
  ✓   3  Plugin Spec         ◆ Gate 2 · Approve structure     ✓
  ✓   4  AEC Features        ◆ Gate 3 · Select features       ✓
  ✓   5  Todo List
  ✓   6  API Extraction
  ✓   7  API Testing         ◆ Gate 4 · Resolve failed calls  ✓
  ✓   8  Scaffold
  ✓   9  Auth Component      ◆ Gate 5 · Test auth in Rhino    ✓
  ► 10  Batch Build
     11  Icons
     12  Tests               ◆ Gate 6 · Test in Rhino
     13  Docs
     14  GitHub
     15  Package + Ship      ◆ Gate 7 · Cross-platform test
═══════════════════════════════════════════════════════════════
```

### Phases

| # | Phase | What happens | Gate |
|---|---|---|---|
| 1 | **Intake** | Preflight (MCPs, Python deps, .NET SDK, yak, token, optional bridge). Name, prefix, author, org, docs URL, seed IDs. Writes the pre-approvals file and the findings log. | |
| 2 | **API Discovery** | Fetch the reference — falling back to an OpenAPI / Google Discovery / apis.guru spec when the page is a redirect or JS-only. Map endpoints, auth, hierarchy, base URL. | **1** · Approve API |
| 3 | **Plugin Spec** | Propose target *workflows* first, grounded in the API; then derive components, subcategories and I/O from the confirmed list. | **2** · Approve structure |
| 4 | **AEC Features** | `pr-aec-advisor` cross-references an AEC feature library against the API's real data shape. | **3** · Select features |
| 5 | **Todo List** | Generate the `todo.md` build checklist in phase order. | |
| 6 | **API Extraction** | `pr-api-extractor` parses the spec or crawls the docs → `call-library.json`. | |
| 7 | **API Testing** | `pr-api-tester` fires **real HTTP calls** (disclosed first) → `call-library-validated.json`. Failures route to `pr-api-scout`. | **4** · Resolve failed calls *(auto-clears if nothing failed)* |
| 8 | **Scaffold** | Flat folder tree, `icons.json`, and a buildable multi-target VS project. Build must be clean. | |
| 9 | **Auth Component** | Client, auth, assembly info, button base, utilities — **from validated calls**, honouring each call's real auth placement. | **5** · Test auth in Rhino |
| 10 | **Batch Build** | Every component, builder and preset, one at a time, in todo order. | |
| 11 | **Icons** | Component (24×24), ribbon (16×16) and README/listing (1024×1024) icons from `icons.json`. | |
| 12 | **Tests** | xUnit builder tests to green, then demo `.gh` files built and live-tested in Rhino with an auto-fix loop. | **6** · Test in Rhino |
| 13 | **Docs** | The portable `docs/` folder for the generated plugin. | |
| 14 | **GitHub** | README, CLAUDE.md, LICENSE, .gitignore — then **creates the repo and pushes `main`**. | |
| 15 | **Package + Ship** | `.yak` for all three targets → `dist/`, plus both GitHub Actions workflows. | **7** · Cross-platform test |

### Gates

| Gate | After | What you do | How you answer |
|---|---|---|---|
| 1 | API Discovery | Review the endpoint map, auth, hierarchy, base URL. | "yes", or corrections |
| 2 | Plugin Spec | Review the component list, subcategories, I/O. | "yes", or add / remove / rename |
| 3 | AEC Features | Choose which AEC features to include. | list them, or "none" |
| 4 | API Testing | Decide each remaining failed call. | "fix" / "skip" / "flag for v2" |
| 5 | Auth Component | Load the `.gha` in Rhino, drop the auth component, press it. | "works", the error, or "defer to Gate 6" |
| 6 | Tests | Open the pre-built `demos/`, confirm components work live. | "all good", or a bug report |
| 7 | Package + Ship | Install the `.yak` on Rh7 Win, Rh8 Win, Rh8 Mac. | "passes", or the platform bug |

### The extend loop

Once Gate 6 has passed, there is no point in a plugin's life where adding a component means
starting over. `/rest-add-feature <description>` re-enters at Phase 3 for that component alone —
mid-build, sitting in docs, or years after shipping — and catches up docs, README and packaging
for it. Full detail: [docs/pipeline.md](please-rest/docs/pipeline.md).

---

## Commands

| Command | What it does |
|---|---|
| `/rest-new-plugin` | Start a new build — the full 15-phase pipeline |
| `/rest-resume-plugin` | Resume a build from its last session, with a version-drift check |
| `/rest-status` | Render the progress tree on demand (read-only, safe any time) |
| `/rest-gen-spec` | Regenerate `plugin-spec.json` from `feasibility.json` |
| `/rest-gen-todo` | Regenerate `todo.md` from `plugin-spec.json` |
| `/rest-extract-api` | Re-run API extraction manually |
| `/rest-test-api` | Re-run HTTP validation manually |
| `/rest-build-component <id>` | Scaffold one component by ID |
| `/rest-build-all-components` | Build every unbuilt component in phase order |
| `/rest-add-feature <description>` | Add a component or workflow at any time, even post-ship |
| `/rest-icon-preview [glyph]` | Render every background shape in each fill style, then pick one |
| `/rest-icons [component]` | Re-render icons from `icons.json` and embed them |
| `/rest-package` | Validated-calls check, `.yak` for all 3 targets, both CI workflows |

Full reference: [docs/commands.md](please-rest/docs/commands.md).

---

## Skills

25 skills, all prefixed `pr-`. Commands load them at the right phase — you rarely invoke one
directly. They encode the conventions and file patterns that keep every generated plugin
consistent.

**Always loaded**

| Skill | Covers |
|---|---|
| `pr-conventions` | Plugin naming and icon prefix rules, namespaces, file naming, wiring contract, comment and JSON style |
| `pr-overview` | The shipped orientation — what PleaseREST is and which piece handles what |

**Code generation** — loaded when the file being written matches

| Skill | Covers |
|---|---|
| `pr-file-structure` | The flat folder scaffold (no `src/`) |
| `pr-vs-project` | The buildable VS project — Rh7 `net48`, Rh8 Win `net7.0-windows`, Rh8 Mac `net7.0` — plus the Release-output rules yak depends on |
| `pr-component` | Any `GH_Component` |
| `pr-button` | Create / update / delete components (`ButtonComponent`) |
| `pr-builders` | `[Resource]Builders.cs` — pure JSON builders |
| `pr-bulk-data` | Grasshopper data-tree handling for bulk writes |
| `pr-client` | `[PluginName]Client.cs` — built from validated calls, never from the docs |
| `pr-assembly` | `[PluginName]Info.cs` — assembly info and category icon wiring |
| `pr-preset` | `GH_ValueList` preset components |
| `pr-utilities` | `PluginUtilities.cs` — tab name, category constants, enum helpers |
| `pr-icons` | Shows the background options, gets an explicit pick, authors `icons.json`, renders all three sizes |

**Spec and planning**

| Skill | Covers |
|---|---|
| `pr-spec` | Target workflows first, then `plugin-spec.json` derived from them |
| `pr-todo` | `todo.md` from the spec, in build order |

**Testing**

| Skill | Covers |
|---|---|
| `pr-unit-tests` | xUnit builder-logic tests (net8.0) — never one file per component |
| `pr-build` | The `dotnet build` + `dotnet test` loop, with failures surfaced |
| `pr-rhino-test` | Phase 12 Step B — demo `.gh` files and live component testing through the bridge |

**Ship layer**

| Skill | Covers |
|---|---|
| `pr-docs` | The generated plugin's portable `docs/` folder |
| `pr-gh-package` | README, CLAUDE.md, LICENSE, .gitignore — then repo creation and push |
| `pr-yak-package` | `.yak` for all three targets, the publishing checklist, and the post-release backfill |
| `pr-ci-template` | `build.yml` (PR) and `publish.yml` (tag → Release) |

**Orchestration**

| Skill | Covers |
|---|---|
| `pr-session` | `session.json`, the sessions index, the progress tree, the phase-completion audit, the version check |
| `pr-permissions` | The generated plugin's `.claude/settings.local.json` pre-approvals |
| `pr-dogfood` | The running findings log — tags each finding as a tool defect or a target-API issue |

Detail: [docs/skills-and-agents.md](please-rest/docs/skills-and-agents.md).

---

## Agents

| Agent | Runs | Does |
|---|---|---|
| `pr-spec-critic` | On the drafted spec, before Gate 2 | Flags components that trace to no workflow, missed consolidations, and tree variants nobody needs — as simplification notes you see alongside the structure |
| `pr-aec-advisor` | After the spec is confirmed, Phase 4 | Cross-references an AEC feature library against the API's real data shape and recommends features for Gate 3 |
| `pr-api-scout` | After HTTP validation, Phase 7 | Reads each failure's response body, re-checks the docs or spec operation, patches the call library, retests. Skips harness-class failures; escalates to Gate 4 after one pass |

---

## MCP servers

Three servers ship with the plugin and load from `plugin.json`.

### `pr-api-extractor` — turns a reference into a call library

| Tool | |
|---|---|
| `extract_from_openapi(spec_url, component_list, output_path?)` | Auto-detects **OpenAPI 3**, **Swagger 2.0** and **Google API Discovery**; fills `base_url`, `auth_in`, `body_required`, `content_type`; resolves `$ref`s and server variables |
| `extract_from_docs(docs_url, endpoint_path, method, component_name, endpoint_id, output_path?)` | Parses one endpoint from prose docs (Readme.io, GitBook, Stoplight, Redoc, raw HTML) |
| `write_call_library(entries, output_path)` | Write a library from prepared entries |

Status tags: `EXTRACTED` · `PARTIAL` · `AMBIGUOUS` · `MISSING`.

### `pr-api-tester` — validates every call against the live API

| Tool | |
|---|---|
| `test_endpoint(entry, token?, seed_ids?, base_url?)` | One endpoint |
| `run_all_tests(call_library_path, output_path, token?, skip_destructive?, base_url?, seed_ids?)` | The whole library; DELETEs skipped by default |
| `retest_entries(entry_ids, ...)` | Specific entries — used by `pr-api-scout` and for mid-run 401 recovery |

Reads the token from `PLEASE_REST_TOKEN`; it is never passed as an argument and never written to
any output file.

### `pr-icon-generator` — renders the plugin's icons

| Tool | |
|---|---|
| `preview_backgrounds(output_dir, ...)` | Render every background shape in every fill style to a contact sheet, so the options can be **seen** before anything is chosen |
| `list_background_shapes()` | The shapes currently available |
| `generate_icon(component_name, config_path, subcategory?, iconify_id?)` | One 24×24 component icon |
| `generate_plugin_icon(config_path, size?, out_name?)` | The 16×16 ribbon icon; `size` / `out_name` render the 1024×1024 README and listing logo |
| `add_to_resources(component_name, config_path)` | Embed a PNG into `Resources.resx` + `Resources.Designer.cs` (Windows only) |

Foreground glyphs come from [Iconify](https://iconify.design). Background shapes are SVG files in
`backgrounds/` — drop one in and it is available immediately, no code change.

**External:** the Grasshopper MCP bridge used in Phase 12 is *not* shipped here — it needs a live
Rhino session and you wire it yourself. See [docs/mcps.md](please-rest/docs/mcps.md).

---

## What you get out of it

For each plugin PleaseREST builds:

- A buildable **Visual Studio project** targeting Rhino 7 (`net48`), Rhino 8 Windows
  (`net7.0-windows`) and Rhino 8 Mac (`net7.0`)
- **Components** wired to a shared client, built only from calls that were validated live
- **xUnit builder tests** that run without Rhino
- **Icons** at all three sizes, embedded as resources
- A portable **`docs/` folder** — one page per component, quickstart, authentication, workflows,
  examples, changelog
- **README, CLAUDE.md, LICENSE, .gitignore**, with generated regions fenced so your edits survive
  regeneration
- **3 `.yak` packages** plus **3 install `.zip` bundles**
- **Two GitHub Actions workflows** — build + test on PRs, and tag → Release with all six assets

Authorship is yours: the plugin name, icon prefix, author name and contact, and GitHub org come
from intake and flow into `GH_AssemblyInfo`, `manifest.yml`, the README byline and the LICENSE.

---

## Repo layout

```
PleaseREST/
├── .claude-plugin/marketplace.json   the marketplace manifest — what /plugin marketplace add reads
├── please-rest/                      the plugin itself
│   ├── .claude-plugin/plugin.json    plugin manifest (name, version, MCP servers)
│   ├── commands/                     13 slash commands
│   ├── skills/                       25 skills
│   ├── agents/                       3 agents
│   ├── mcps/                         3 MCP servers (Python)
│   ├── docs/                         user documentation
│   ├── README.md                     the plugin's own readme
│   ├── CLAUDE.md                     contributor notes
│   └── CHANGELOG.md                  what changed, and the pre-1.0.0 upgrade guide
├── tests/                            364 tests across the three MCP servers
└── PleaseREST-spec.md                the full design spec
```

**Tests**

```
cd tests
pip install -r requirements.txt
pytest
```

---

## Documentation

| | |
|---|---|
| [Overview & concepts](please-rest/docs/index.md) | What PleaseREST is and how the pieces fit |
| [The pipeline](please-rest/docs/pipeline.md) | All 15 phases, all 7 gates, the extend loop |
| [Commands](please-rest/docs/commands.md) | Every command in detail |
| [Skills & agents](please-rest/docs/skills-and-agents.md) | What each of the 25 skills and 3 agents does |
| [MCP servers](please-rest/docs/mcps.md) | Every tool, every argument |
| [Troubleshooting](please-rest/docs/troubleshooting.md) | The failures that actually happen, and their fixes |
| [Changelog](please-rest/CHANGELOG.md) | Release history, and upgrading a pre-1.0.0 build |

---

## License

MIT — Copyright (c) 2026 Eesha Jain. See [LICENSE](LICENSE).
