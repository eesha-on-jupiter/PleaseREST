# Skills & Agents

PleaseREST is built from 25 skills (all prefixed `pr-`) and 3 agents. Skills are loaded by the
commands at the right phase — you don't invoke most of them directly. They encode the
conventions, file patterns, and rules that keep every generated plugin consistent.

## Always loaded

- **`pr-conventions`** — base naming, namespaces, comments, and JSON rules. Loaded alongside
  any other skill.
- **`pr-overview`** — what PleaseREST is and which command / skill / agent / MCP handles what. This
  is the orientation that ships with the plugin (a root `CLAUDE.md` is not loaded for installed
  plugins). Load it when unsure which piece to reach for.

## Code generation (file-type skills)

Loaded when the file being written matches:

| Skill | Covers |
|---|---|
| `pr-file-structure` | Flat folder scaffold for a new plugin (no `src/`, no `assets/dist`) |
| `pr-vs-project` | The buildable VS Grasshopper project — Rh7 (net48), Rh8 (net7.0-windows / net7.0) — + build check |
| `pr-component` | Any `GH_Component` file |
| `pr-button` | Create/update/delete components (extend `ButtonComponent`) |
| `pr-builders` | `[Resource]Builders.cs` — pure JSON builder classes |
| `pr-bulk-data` | Grasshopper data-tree handling for bulk/mass upload |
| `pr-client` | `[PluginName]Client.cs` — built from validated calls, never the docs |
| `pr-assembly` | `[PluginName]Info.cs` (assembly + category icon wiring) |
| `pr-preset` | `GH_ValueList` preset components |
| `pr-utilities` | `PluginUtilities.cs` — `TabName`, category constants, `GetValues<T>()` |
| `pr-icons` | Previews the background options and gets an explicit style pick, then authors `icons.json` post-spec (user specifies every icon) and renders three sizes via the icon MCP — 24×24 components, the 16×16 ribbon icon, and the 1024×1024 README / Food4Rhino logo |

## Spec & planning

- **`pr-spec`** — Step 0: propose a grounded target-workflow list from `feasibility.json` before
  drafting anything; then produce `plugin-spec.json` derived from the confirmed `workflows.json`
  (uniform + parametric-tree component pairs, consolidated components for common chains, no
  components that just rebuild native GH capability).
- **`pr-todo`** — produce `spec/todo.md` from `plugin-spec.json`. Its build Phases 1–10 are its own
  numbering (distinct from the 15 pipeline phases); docs / GitHub / package items are tagged `[SHIP]`
  and belong to pipeline Phases 13–15.

## Testing

- **`pr-unit-tests`** — xUnit test scaffold (net8.0, pure builder logic).
- **`pr-build`** — `dotnet build` + `dotnet test` loop with failure surfacing.
- **`pr-rhino-test`** — Phase 12 Step B: build the demo `.gh` files and live-test every
  component in Rhino through an external Grasshopper MCP bridge, with an auto-fix loop, before
  Gate 6. Degrades gracefully to manual when no bridge is wired.

## Ship layer

- **`pr-docs`** — generate the portable `docs/` folder for the generated plugin (Phase 13).
- **`pr-gh-package`** — generate README.md, CLAUDE.md, LICENSE, .gitignore, then create the GitHub repo and push `main` (Phase 14).
- **`pr-yak-package`** — build `.yak` for all 3 targets (Rh7 Win, Rh8 Win, Rh8 Mac), plus the
  post-Gate-7 publishing checklist (tag → Release, `yak push`, Food4Rhino listing) and the backfill
  that replaces the README / `docs/index.md` pre-release placeholders with real links and dates.
- **`pr-ci-template`** — generate `.github/workflows/build.yml` (PR build + test) and `publish.yml` (tag → Release with 3 `.yak` + 3 install `.zip`).

## Orchestration & infrastructure

- **`pr-session`** — read/write/resume `session.json` + the global sessions index; owns the
  15-phase / 7-gate progress tree and the resume-time version check (alerts when a build predates
  a PleaseREST change, per `CHANGELOG.md`).
- **`pr-permissions`** — generate the generated plugin's `.claude/settings.local.json` at Phase 1
  intake, pre-approving every command the pipeline needs (git, dotnet, yak, nuget, python,
  powershell, all tools of the three MCP servers, and the bridge status check).
- **`pr-dogfood`** — maintain a running findings log per run, appending findings, errors, and
  phase results automatically; tags each as a tool defect vs. a target-API issue.

---

## Agents

Agents run autonomously at specific points and return structured results.

### `pr-aec-advisor`
Runs after the plugin spec is confirmed (Phase 4). Cross-references an AEC feature library
against the API's actual data shape and outputs structured feature recommendations for Gate 3.

### `pr-spec-critic`
Runs on the *drafted* (not yet confirmed) plugin spec, right before Gate 2 — the simplification
counterpart to `pr-aec-advisor`. Flags components that don't trace to any workflow, missed merges
or consolidations, and Dual Style Pattern tree variants nobody's workflow needs, as "Simplification
notes" the user reviews alongside the structure.

### `pr-api-scout`
Runs after `pr-api-tester` (Phase 7) on **FAILED or PARTIAL** call-library entries. Reads the
tester's `error_body`, re-checks the docs page (or the OpenAPI operation when there is no docs
page), patches `call-library.json`, and retests. Skips harness-class failures (every entry failing
the same way) and "enrich then retest" PARTIALs. Escalates to the human (Gate 4) after one pass if
entries still fail.
