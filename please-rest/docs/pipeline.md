# The Pipeline — 15 Phases, 7 Gates

`/rest-new-plugin` drives a generated plugin through 15 phases. Seven of those phases end in a
**human gate** — PleaseREST stops, renders the progress tree, and waits for your approval
before continuing. Nothing irreversible happens without a gate.

## Progress tree

Before every gate question (and on resume, and via `/rest-status`), PleaseREST renders a
15-phase / 7-gate tree driven by `session.json`, plus a **YOUR MOVE** block telling you exactly
what to do and how to respond.

```
PleaseREST — AcmeConnect   ·   Restling
═══════════════════════════════════════════════════════════════
  ✓   1  Intake
  ✓   2  API Discovery       ◆ Gate 1 · Approve API           ✓
  ✓   3  Plugin Spec         ◆ Gate 2 · Approve structure     ✓
  ✓   4  AEC Features        ◆ Gate 3 · Select features        ✓
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

## Phases

| # | Phase | What happens | Gate |
|---|---|---|---|
| 1 | **Intake** | Step 0 preflight (MCPs, Python deps, .NET SDK, yak, token, optional Rhino bridge). Plugin name, docs URL, token readiness, optional test workspace / seed IDs. Generates `.claude/settings.local.json` (pre-approvals) and the dogfood findings log. | |
| 2 | **API Discovery** | Fetch docs (falls back to an OpenAPI / Google Discovery / apis.guru spec when the page is a redirect or JS-only; stops before Gate 1 if nothing is readable); map endpoints, auth, resource hierarchy, base URL. Writes `feasibility.json`. | **Gate 1** · Approve API |
| 3 | **Plugin Spec** | Propose target workflows (grounded in the API, confirmed by the user), then propose `plugin-spec.json` — components, subcategories, I/O — derived from them. | **Gate 2** · Approve structure |
| 4 | **AEC Features** | `pr-aec-advisor` cross-references AEC features against the API's data shape. | **Gate 3** · Select features |
| 5 | **Todo List** | Generate `todo.md` build checklist in phase order. | |
| 6 | **API Extraction** | `pr-api-extractor` MCP crawls docs / parses OpenAPI → `call-library.json` (with `auth_in`, `body_required`, `content_type`). *Mandatory.* Stops if 0 entries extract. | |
| 7 | **API Testing** | `pr-api-tester` MCP fires real HTTP calls (disclosed first; uses intake seed IDs) → `call-library-validated.json`. PARTIAL = enrich + retest; one shared error class = harness fix; real FAILED → `pr-api-scout`. Gate 4 auto-clears when nothing failed. | **Gate 4** · Resolve failed calls |
| 8 | **Scaffold** | Flat folder tree; `icons.json` authored; buildable VS project (Rh7 net48 / Rh8 net7.0-windows / net7.0). Build check must be clean. | |
| 9 | **Auth Component** | Build `Client.cs`, `Auth.cs`, `Info.cs`, `ButtonComponent.cs`, utilities — *from validated calls*, honouring each call's `auth_in`. Then build, so Gate 5 has a loadable `.gha`. | **Gate 5** · Test auth in Rhino (verifiable: dev-settings folder → load → press; or "defer to Gate 6") |
| 10 | **Batch Build** | Iterate every `[CODE]` item in `todo.md`'s build phases; one component/builder/preset at a time. `[SHIP]` items wait for Phases 13–15. | |
| 11 | **Icons** | The single render point: component (24×24) + plugin (16×16) icons from `icons.json` via `pr-icon-generator` (`custom: true` icons are skipped). Quick "glance at Icons/" check before continuing. | |
| 12 | **Tests** | **Step A:** xUnit builder-logic tests → build → test until green. **Step B:** build demo `.gh` files (Token blanked before save) + live-test in Rhino (auto-fix loop). No bridge → `demos/README.md` + `degraded["12"]`. | **Gate 6** · Test in Rhino |
| 13 | **Docs** | `pr-docs` generates the portable `docs/` folder for the generated plugin (examples from the spec's workflows if `demos/` is empty). | |
| 14 | **GitHub** | `pr-gh-package` writes README.md (with a "What you can do with it" section), CLAUDE.md, LICENSE, .gitignore inside `<!-- pr:begin/end -->` markers, then **creates the repo and pushes `main`**. Complete on the push, not on the files. | |
| 15 | **Package + Ship** | Validated-calls check, then `.yak` for all 3 targets (net48 / net7.0-windows / net7.0) → `dist/`; both GitHub Actions workflows (`build.yml` on PRs, `publish.yml` on a `v*.*.*` tag → Release with 3 `.yak` + 3 install `.zip`). Complete on those artifacts — Gate 7 is separate. | **Gate 7** · Cross-platform test |

> **Why Docs and GitHub are separate phases (13 and 14):** docs are generated first so the
> Phase-14 README can link into the `docs/` folder. They used to be a single combined step.

## The 7 gates

| Gate | After phase | What you do | How to respond |
|---|---|---|---|
| 1 | API Discovery | Review the endpoint map, auth, hierarchy, base URL. | "yes" or corrections. |
| 2 | Plugin Spec | Review component list, subcategories, I/O. | "yes" or add/remove/rename. |
| 3 | AEC Features | Choose which AEC features to include. | List features, or "none". |
| 4 | API Testing | Decide each remaining failed call. Auto-clears (shown ✓, `auto: true`) when nothing failed. | "fix" / "skip" / "flag for v2". |
| 5 | Auth Component | Point GrasshopperDeveloperSettings at `bin/Debug/net7.0-windows/` (Rh8) or `net48/` (Rh7), restart, drop the auth component, press it. | "works", the error, or "defer to Gate 6". |
| 6 | Tests | Open the pre-built `demos/` files (paste your token into the Token panel); confirm components work live. | "all good" or a bug report. |
| 7 | Package + Ship | Install the `.yak` on Rh7 Win / Rh8 Win / Rh8 Mac. | "passes" or the platform bug. |

## The extend loop (any time after Gate 6 passes — never "too late")

Once Gate 6 has passed for the first time, there is no point in the plugin's life where adding a
component means starting over or being told no. Two entry points, same machinery:

**Still mid-build, before Docs/Packaging** — `/rest-new-plugin` asks after every Gate 6 pass:

```
Gate 6 passed — AcmeConnect's components work live.
Add any new components or workflows before docs + packaging?
  • describe the component(s) / workflow(s) to add
  • or "no" to continue to docs + ship
```

**Already in Docs/GitHub/Package, or fully shipped** — just run `/rest-add-feature <description>`
directly. Same loop, plus a catch-up step so a shipped plugin never ends up with a component that
docs and packaging don't know about.

If you name new items, **only those items** run the full build loop (existing components are
never rebuilt):

1. Spec addition → todo update.
2. Extract + test the new endpoints (skipped if a pure workflow reuses validated endpoints).
3. Build the new component/preset files.
4. Render their icons — then an **Icons gate**: *"Are these icons OK? (yes / describe changes)"*.
   You must approve the new icons before it moves on.
5. Unit tests + live Rhino re-test, then a **re-run of Gate 6** for the new items.
6. **Catch-up** (`/rest-add-feature` only, and only for phases already completed): incrementally
   update `docs/` (Phase 13) if docs were already generated, always regenerate the GitHub
   README/CLAUDE.md (Phase 14), and rebuild `dist/*.yak` (Phase 15) if the plugin was already
   packaged — so the new component is documented and shippable, not just built.

From `/rest-new-plugin`, it asks again after each round, looping until you answer "no" — only
then does it continue to Phase 13. This loop adds no new fixed phases; each round is recorded
under `session.json` → `decisions.extend_rounds`.

## Sessions & resume

Every phase, gate, MCP run, and file write updates `spec/session.json` (and the global
`~/.please-rest/sessions.json` index). To pick up where you left off:

```
/rest-resume-plugin
```

PleaseREST renders the progress tree from the saved state and continues. If `session.json` is
lost mid-build, it reconstructs `completed_phases` from `todo.md` `[x]` items and re-derives
token readiness from the actual environment.

A gate answered with a bug report is remembered (`gate_feedback`, `awaiting_fix`), so a session
closed mid-fix resumes at the fix rather than re-asking the gate. Mid-phase position is kept for
Phase 7 (tested IDs), 11 (rendered icons), 12 (step / attempt) and extend rounds; skipped or
degraded phases are recorded and never silently re-run.

## Graceful degradation

The Phase 12 **live** Rhino test depends on an external Grasshopper MCP bridge. If no bridge is
wired in (or it can't resolve custom components), PleaseREST skips the automation, prints the
one-time wiring steps, writes `demos/README.md` describing each canvas for manual creation,
records `degraded["12"]` in `session.json`, and falls back to a fully-manual Gate 6. It never
hard-fails on the missing bridge. See [troubleshooting](troubleshooting.md#grasshopper-mcp-bridge).

## What Phase 7 does to your account

The HTTP validation fires **real** calls with your token: one POST / PUT / PATCH per write endpoint
creates a real record; DELETEs are never fired. The pipeline says so before it runs and uses the
"Test workspace / seed IDs" you gave at intake, so test records land in a sandbox rather than
production. Tokens are read from `PLEASE_REST_TOKEN`, never written to `call-library-validated.json`,
`session.json` or the demo `.gh` files.
