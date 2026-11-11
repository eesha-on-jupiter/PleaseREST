---
description: "Start a new Grasshopper REST API plugin build through the full 15-phase PleaseREST pipeline."
---

# /rest-new-plugin

Start a new Grasshopper REST API plugin build using the PleaseREST pipeline.
Check for an existing session before starting — never overwrite without confirmation.

---

## Before starting

Check if `spec/session.json` exists in the current directory.
If it does: "An active session exists for [PluginName] at phase [n]. Resume with /rest-resume-plugin, or type 'fresh' to start over."
Stop unless the user confirms fresh start.

---

## At every gate — show the progress tree

Before asking ANY `[HUMAN GATE]` question below, first render the **progress tree** from `pr-session`
(the 15-phase / 7-gate tree driven by `session.json`), showing completed phases, the current phase,
the gate the user is at (`◀ YOU ARE HERE`), the `Now:` / `Next:` footer, and the **YOUR MOVE** block
that states exactly what the user must do at this gate and how to respond. The user should see the
full pipeline picture and their required action at every gate, not just the question.

---

## PHASE 1 — INTAKE

**Step 0 — Preflight** *(part of Phase 1, not a new phase — every dogfood run so far failed at
setup, so check the environment before asking a single question)*:

| Check | How | If it fails |
|---|---|---|
| PleaseREST loaded | `/mcp` shows `please-rest → pr-api-extractor, pr-api-tester, pr-icon-generator (connected)` | run `claude plugin validate <plugin-dir>`; see docs/troubleshooting.md |
| MCP Python deps | `python -c "import mcp, httpx, resvg_py, PIL, yaml, bs4"` (Python ≥ 3.10) | `pip install -r <plugin>/mcps/pr-api-extractor/requirements.txt` (and the other two). If `python` itself is **not found** (macOS/Linux have only `python3`; Windows may hit the Store stub), that — not the deps — is why row 1 failed: see docs/troubleshooting.md, then restart Claude Code |
| .NET SDK | `dotnet --version` → SDK 8.x or newer (8.x recommended; 10.x verified — it builds net48 + net7.0 targets too) | install .NET SDK 8 + the net48 targeting pack |
| yak | probe `C:\Program Files\Rhino 9\System\Yak.exe` (then Rhino 8, Rhino 7) / `/Applications/Rhino 9.app/Contents/Resources/bin/yak` (then `Rhino 8.app`) — full list in pr-yak-package | only blocks Phase 15 — note it, continue |
| Token | `PLEASE_REST_TOKEN` set and non-empty | needed from Phase 7 — note it, continue |
| Rhino bridge | optional — `claude mcp list` shows a Grasshopper MCP | only affects Phase 12 Step B — Gate 6 degrades to manual |

Write the results to `session.json.preflight` (`{check: "ok" | "missing — <note>"}`) so resume can
see what was known. Hard stops: the first two rows. Everything else is a warning carried forward.

Ask the user:
```
PleaseREST — new plugin setup
────────────────────────────────────────
Plugin name:    (whatever you want to call it — Slate, TulipGH, AcmeConnect…)
Icon prefix:    (2–3 letters, used on every icon resource — proposed once you name it)
Docs URL:       (API reference URL or OpenAPI spec URL)
Author name:    [git config user.name]        ← yours; goes in the plugin, not PleaseREST's
Author contact: [git config user.email]
GitHub org/user:                              (for repo + docs links; blank = ask at Phase 14)
Token ready?    (yes / no — we'll need it for Phase 7)
Test workspace / seed IDs (optional):
                (a sandbox workspace, board, project… ID that Phase 7 may create
                 test records in — e.g. board_id=abc123. Phase 7 fires real POST /
                 PUT / PATCH calls, one per endpoint; DELETEs are never fired.)
────────────────────────────────────────
```

**The plugin name is the author's choice — there is no house pattern.** `Connect` is not a
suffix PleaseREST expects or appends; don't suggest `[Platform]Connect` as if it were the
convention. Take the name given, check it against the constraints in `pr-conventions` ("Plugin
name"), and if it can't be a C# namespace (spaces, hyphens, leading digit) say which place breaks
and offer the nearest valid form rather than rewriting it silently. Then **propose the 2–3 letter
`plugin_prefix`** from that name (`pr-conventions`' derivation rules) and get a yes in the same
breath — it lands in every icon resource key and is expensive to change after Phase 11.

**Author name / contact** are the *user's own*, and they end up in four shipped places — the
`GH_AssemblyInfo` Grasshopper shows in its loaded-libraries list, `manifest.yml`'s `authors`, the
README byline, and the LICENSE copyright. Pre-fill both from `git config user.name` /
`git config user.email` and ask the user to confirm or correct them; if git has neither, ask
outright. **Never** generate a plugin under a hardcoded name — PleaseREST's own author is not the
author of what it builds.

Write `spec/intake.json`:
```json
{
  "plugin_name": "[PluginName]",
  "plugin_prefix": "[XX]",
  "docs_url": "[url]",
  "author": { "name": "[AuthorName]", "contact": "[AuthorContact]" },
  "github_org": "[org]",
  "token_ready": true,
  "seed_ids": { "board_id": "abc123" }
}
```
Mirror `author` and `github_org` into `session.json` (top level) and `seed_ids` into
`session.json.decisions.seed_ids` — Phase 7 passes it to `run_all_tests`.

Load skill: pr-permissions
Generate `.claude/settings.local.json` inside the generated plugin folder (Claude Code reads
project settings from `.claude/`, never from a root-level file), show the pre-approval summary, and
wait for the user to confirm before any further phase runs.

Load skill: pr-dogfood
Set `findings_path` in `session.json` to `dogfood/[PluginName]-run-01.md` (bump to `-run-02`, `-run-03`,
… if a findings file for this plugin already exists — never overwrite a prior run). Create that file
with its header + phase-log blocks now, so every later phase / failure / gate appends to it.

Update `session.json`: phase 1 complete (now includes `plugin_name`, `findings_path`).

---

## PHASE 2 — API DISCOVERY

Load skill: pr-conventions (always) + pr-spec (for context on what to look for)

Fetch the docs URL. **If the fetch fails, redirects to a marketing page, or the page is JS-rendered
with no endpoint content** (dogfood: Google's reference pages), do not guess: try, in order, an
OpenAPI / Swagger URL linked from the page, the platform's Google Discovery doc
(`https://<service>.googleapis.com/$discovery/rest?version=v1`), and apis.guru
(`https://api.apis.guru/v2/specs/<vendor>/…`). If none yields endpoints, stop **before Gate 1**
with: "Couldn't read the API reference at [url] — give me a reference or spec URL." Never present
an empty overview at Gate 1.

Map:
- All REST endpoints (method + path)
- Auth method and token format
- Resource hierarchy (what owns what, what ID is needed for each call)
- API version and base URL
- Any extra required headers (e.g. X-Api-Version)
- Whether an OpenAPI spec is available

Write `spec/feasibility.json`.

Present the API overview in this format:
```
Platform:        [name]
Base URL:        [url]
Auth method:     [Bearer token / OAuth / API key]
API version:     [version]
Extra headers:   [any required]

API hierarchy:
  [Resource]
    └── [Child resource]
          └── [Grandchild resource]

OpenAPI spec:    [yes — url / no]
Endpoints found: [n]
```

**[HUMAN GATE 1]** "Does this look correct? Any corrections before I continue?"
Wait for approval or corrections. Apply corrections to feasibility.json.
Update session.json: gate 1 passed.

> **Every gate:** if the user's answer is a correction / bug report rather than approval, write it
> to `session.json.gate_feedback["<n>"]` and set `awaiting_fix: true` *before* starting the fix, and
> clear both when the gate passes — so a session closed mid-fix resumes at the fix, not at the
> question (see pr-session).

---

## PHASE 3 — PLUGIN SPEC

Load skill: pr-spec

**Step 0 — workflows.** Draft a grounded candidate workflow list from feasibility.json (per
pr-spec's Step 0 — concretely how this platform's data inside Grasshopper beats its native UI,
plus the cross-platform tabular benchmark). Present it as "here's how this plugin could make your
work easier." Let the user confirm, edit, add, or remove. Write spec/workflows.json.

Read feasibility.json + spec/workflows.json. Produce and present plugin-spec.json proposal,
derived from the confirmed workflows (Dual Style Pattern, consolidated components where a
workflow's common case chains several primitives, no components that just rebuild native GH
capability).
Run inline validator, including the workflow-coverage and display-name checks. Do not write until
user approves.

Run agent: pr-spec-critic against the drafted spec + workflows.json. Fold any "Simplification
notes" into what's presented next.

**[HUMAN GATE 2]** "Does this structure work? Anything to add or remove?" Also show the
"Proposed to skip for v1 (not used by any stated workflow)" list and pr-spec-critic's
simplification notes alongside the structure.
Apply changes. Write spec/plugin-spec.json.
Update session.json: phase 3 complete, gate 2 passed.

---

## PHASE 4 — AEC FEATURES

Run agent: pr-aec-advisor
Present feature recommendations.

**[HUMAN GATE 3]** User selects features. Append to plugin-spec.json under "aec_features".
Update session.json: gate 3 passed, aec_features_selected recorded.

---

## PHASE 5 — TODO LIST

Load skill: pr-todo
Generate spec/todo.md from plugin-spec.json.
Update session.json: phase 5 complete.

Present: "Shall I start building? (Next: Phases 6–8 — extract + validate the API, then scaffold —
before todo build Phase 1, Auth.)" — todo.md's build phases are its own numbering, distinct from
the 15 pipeline phases.
Wait for explicit approval before any code is written. Record it as
`decisions.build_approved: true`.

---

## PHASE 6 — API EXTRACTION  *(MANDATORY — do not skip)*

Run MCP: pr-api-extractor
- If OpenAPI spec available: use extract_from_openapi
- Otherwise: use extract_from_docs for each endpoint in component_list

Print Restling progress. Write spec/call-library.json. Each entry carries `auth_in`
(`header` | `header:<Name>` | `query:<param>`, filled from the spec's security schemes),
`body_required` and `content_type` — check `auth_in` agrees with Phase 2's auth finding.
**If 0 entries are EXTRACTED**, stop: the source is wrong (see Phase 2's fallbacks) — do not enter
Phase 7 with nothing to test. PARTIAL entries (write endpoint, no resolvable body) are expected for
JS-rendered docs: enrich `example_request` now, record each in `decisions.manual_fixes`.
Update session.json: phase 6 complete.

> **Hard rule:** Phases 6–7 are not optional and must not be replaced by reading the docs and
> hand-writing the client. The client and components are built FROM `call-library-validated.json`
> (see Phase 9 precondition). If you find yourself about to write an HTTP call without a validated
> entry for it, stop — run the pr-api-extractor / pr-api-tester MCPs first. (A past run silently skipped
> these and hand-wrote the client; that is the failure this rule prevents.)

---

## PHASE 7 — API TESTING

**Disclosure first:** "Phase 7 fires real HTTP calls with your token — one POST / PUT / PATCH per
write endpoint creates a real record; DELETEs are skipped. Using seed IDs: [decisions.seed_ids or
'none — IDs will be harvested from list/create responses']." Continue on acknowledgement.

Run MCP: pr-api-tester → `run_all_tests(call_library_path, output_path, skip_destructive=True,
seed_ids=decisions.seed_ids)` — never pass the token as an argument (it reads `PLEASE_REST_TOKEN`).
Print Restling progress. Write spec/call-library-validated.json.
Track progress in `session.json.phase_progress["7"].tested_ids` as entries complete.

Route the results:
- **All FAILED with the same error class** (every "missing http:// protocol", every 401, every
  "Missing seed ID") → one harness / token / base_url problem, not N API defects. Fix it once
  (`base_url`, token, `seed_ids`) and rerun. Do **not** send every entry to pr-api-scout.
- **401 mid-run** → the tester halts and writes what it has. Refresh the token, then
  `retest_entries(untested_ids, ..., seed_ids)` for the rest — do not rerun the whole library.
- **PARTIAL** ("not tested — no request body example" / "redirect — check base_url") → not an API
  failure: enrich `example_request` (or fix `base_url`) in call-library.json, `retest_entries`,
  record in `decisions.manual_fixes`.
- **FAILED** (a real non-2xx from a well-formed call) → run agent pr-api-scout (reads
  `test_result.error_body`), patch and retest.

If still FAILED after pr-api-scout:
**[HUMAN GATE 4]** Present each remaining FAILED entry. User decides: fix / skip / flag for v2.
Record decisions in session.json (`decisions.skipped_endpoints`) — a skipped endpoint's component
is then built with a `// TODO: unvalidated call` note, never silently from the unvalidated library.
**If zero entries are FAILED or PARTIAL**, Gate 4 auto-clears: write it to `gates_passed` with
`auto: true` (pr-session) so the tree shows ✓, and say "Gate 4 auto-cleared — nothing to resolve."
Update session.json: phase 7 complete, gate 4 passed.

---

## PHASE 8 — SCAFFOLD

Load skill: pr-file-structure
Create the flat folder tree (no src/, no assets/dist); leave Icons/ empty.
Load skill: pr-icons
**First** run `preview_backgrounds` (or tell the user to run `/rest-icon-preview`) and have them
pick a fill style + shape from the contact sheet — never inherit the template's placeholder
background. Then author icons.json from the final spec and have the user specify every icon
(fg glyph + background: none/solid/gradient/icon; `"custom": true` for a hand-made icon the
generator must leave alone).
Icons **render in Phase 11** (the single render point); Phases 9–10 only write code. (Exception:
`/rest-build-all-components` may render a group's `[ASSET]` items as it goes — Phase 11 then
renders only what is still unrendered, plus the 16×16 plugin icon.)
Load skill: pr-vs-project
Generate the VS project from the GH template (.csproj/.sln/.csproj.user/launchSettings/Info.cs/
Resources). Rename namespaces, GUIDs, assembly info.
BUILD CHECK: dotnet build for Rhino 7 (net48) + Rhino 8 (net7.0-windows / net7.0) — must be clean
before any component code.
Update session.json: phase 8 complete.

---

## PHASE 9 — AUTH COMPONENT

**Precondition:** `spec/call-library-validated.json` must exist (Phases 6–7 ran). If it is missing,
do NOT hand-write the client — go back and run Phases 6–7 first. Build `[Plugin]Client.cs` FROM the
validated entries (method, URL, headers, body per `endpoint_id`), never from the docs directly.

Load skills: pr-conventions + pr-client + pr-component + pr-assembly
Build: [Plugin]Client.cs, [Plugin]Auth.cs, [Plugin]Info.cs, ButtonComponent.cs, PluginUtilities.cs
— the client honours each entry's `auth_in` (Bearer header / named header / query param).
Write last_completed_step after each file.
Then `dotnet build` (all three targets) — Gate 5 needs a loadable `.gha`.

**[HUMAN GATE 5]** Make it verifiable, not a formality:
```
Gate 5 — test the auth component in Rhino
  1. GrasshopperDeveloperSettings → add the folder  bin/Debug/net7.0-windows/  (Rhino 8 Win;
     Rhino must be on .NET Core 8 — see pr-rhino-test's runtime preflight) or  bin/Debug/net48/  (Rhino 7).
     Rhino 9 uses the Rhino 8 builds:  net7.0-windows/  on Windows,  net7.0/  on Mac (also Rhino 8 Mac).
  2. Restart Rhino, open Grasshopper, drop [Plugin]Auth, paste your token, press the button.
  3. Reply "works" (Status = 200 / OK) or paste the exact Status / error text.
```
If the user cannot load Rhino right now, they may say "defer to Gate 6": record
`decisions.gate5_deferred: true`, leave Gate 5 in `gates_pending`, and re-ask it together with
Gate 6 (the Auth demo is part of the pre-built demos). Never mark Gate 5 passed on "build is clean"
alone.
Wait for "works" or specific error report. Fix if needed (`gate_feedback["5"]` while fixing).
Update session.json: gate 5 passed.

---

## PHASE 10 — BATCH BUILD

Load skill: pr-conventions + (pr-component or pr-button or pr-builders or pr-preset per type)
Iterate every [CODE] item in spec/todo.md's **build phases** (todo build Phases 1–7) in order.
`[SHIP]` items (todo build Phases 8–10: docs / GitHub / package) are pipeline Phases 13–15 — never
run them here. Every HTTP component is built from a `VALIDATED` entry (or a Gate-4 `skipped_endpoints`
decision, with a TODO note) — never from the unvalidated library.
For each file:
  - Write the file
  - Write last_completed_step = this file
  - Write next_step = next [CODE] item
  - Mark [x] in todo.md
Icons are not rendered here — Phase 11 renders everything from icons.json in one pass.
Update session.json: phase 10 complete.

---

## PHASE 11 — ICONS

Load skill: pr-icons. Render from icons.json via the pr-icon-generator MCP:
- each component (24×24): generate_icon → add_to_resources
- plugin/ribbon icon (16×16): generate_plugin_icon → add_to_resources
Always pass config_path = the plugin's icons.json. Skip components marked `"custom": true` (the
generator does this itself) and anything already rendered by `/rest-build-all-components`.
Track `session.json.phase_progress["11"].rendered` as each icon lands, so a resume mid-render
picks up at the next one.
**Quick review (not a numbered gate):** list the rendered files in `Icons/` and ask "Icons rendered
— glance at Icons/ and say 'ok', or name any to redo." Re-render named ones from an edited
icons.json; then continue.
Update session.json: phase 11 complete.

---

## PHASE 12 — TESTS

**Step A — Unit tests.**
Load skill: pr-unit-tests
Scaffold the concern-based test project (net8.0, builder sources compiled in — NOT a reference to the
windows-only .gha): BuilderTests (primary, pure logic) + BulkAssemblyTests when the plugin has
aggregators. No per-component tests.
Load skill: pr-build
Run dotnet build → dotnet test → fix → rerun until all green.

**Step B — Example files + live MCP test.**
Load skill: pr-rhino-test (via a Grasshopper MCP bridge — see the skill for one-time wiring).
- Verify the bridge is up (status check). If not configured, degrade gracefully: skip automation,
  print the wiring steps, write `demos/README.md` specifying each demo canvas for manual build
  (pr-rhino-test's fallback), record `session.json.degraded["12"] = "no bridge — manual Gate 6"`,
  and fall back to a fully-manual Gate 6.
- Build the demo .gh files into demos/ — each canvas ONCE (placed by GUID from plugin-spec.json,
  wired from call-library-validated.json sample inputs). These are reused by pr-docs in Phase 13.
- Live-test each demo: load the .gha, solve, check loads/instantiates/solves/non-empty correct outputs.
- AUTO-FIX LOOP: on failure, fix (code via the relevant build skill + rebuild the .gha, or canvas)
  and retest. Flag the human ONLY when there is no fix (live API outage, judgment call). Log via pr-dogfood.
- Track `session.json.phase_progress["12"]` = `{ step: "A" | "B", attempt: n }` so a resume lands
  in the right step of the auto-fix loop.
- **Tokens never persist in demos:** before saving any `.gh`, blank the Token input (or set it to
  `<PASTE_TOKEN>`) — `demos/` is committed and shipped by pr-docs.
- Proceed only when all demos pass (or remaining failures are human-flagged no-fix) and demos/ is populated.
Update session.json: phase 12 complete.

**[HUMAN GATE 6]** "Open the pre-built demos/ files (paste your token into the Token panel first),
and confirm the components work live in Grasshopper." If Phase 12 was degraded (no bridge), say so:
"No bridge was wired, so demos/ holds a README describing each canvas — build them from it, then
confirm." If Gate 5 was deferred, the Auth demo covers it — pass both together.
Demos are pre-built and pre-checked, so the user does very little. Present any human-flagged no-fix items.
Wait for "all good" or bug report. On a bug report write `gate_feedback["6"]` + `awaiting_fix: true`,
fix, rerun Step B, clear both when it passes.
Update session.json: gate 6 passed.

---

## AFTER GATE 6 — EXTEND LOOP  *(optional, repeats until the user declines)*

Every time Gate 6 passes — and before Phase 13 — ask whether the build should grow:

```
Gate 6 passed — [PluginName]'s components work live.
Add any new components or workflows before docs + packaging?
  • describe the component(s) / workflow(s) to add
  • or "no" to continue to docs + ship
```

**If "no"** → continue to Phase 13.

**If the user names new components/workflows** → run the FULL build loop for *those items only*
(same machinery as `/rest-add-feature`; existing components are never rebuilt). For each round:

1. Load skill: pr-spec — propose the additions to plugin-spec.json (new component(s) / builder
   methods / subcategory, or a new workflow = demo canvas / `GH_ValueList` preset). Validate inline,
   present, and wait for approval. **Append only** — never rewrite existing components.
2. Load skill: pr-todo — add todo.md items for the new items only; leave existing items untouched.
3. Run MCP: pr-api-extractor for the new endpoints only — extract to a temporary path
   (`spec/call-library.new.json`) and merge only the new `endpoint_id`s into call-library.json, so
   existing entries and their Gate-4 hand fixes are never rewritten.
   *(Skip if the new item is a pure workflow that only reuses already-validated endpoints.)*
4. Run MCP: pr-api-tester → `retest_entries(new_ids, ..., seed_ids=decisions.seed_ids)` for the
   new entries only (already-validated endpoints are not re-fired). Route as in Phase 7: PARTIAL →
   enrich + retest; FAILED → agent pr-api-scout; if still FAILED, run **[HUMAN GATE 4]** scoped to
   the new entries (fix / skip / flag for v2).
5. Load pr-conventions + the correct type skill (pr-component / pr-button / pr-builders / pr-preset).
   Build the new component / preset files.
6. **Icons.** Load pr-icons, add the new components' entries to icons.json (user specifies each icon),
   then render via pr-icon-generator — `generate_icon` → `add_to_resources` for each new 24×24
   component (and `generate_plugin_icon` if the plugin icon changed).

   **[HUMAN GATE — ICONS]** Show the newly rendered icons and ask:
   "Are these icons OK? (yes / describe changes)". On changes, edit icons.json and re-render.
   **Do not move on until the user approves the new icons.**

7. Load pr-unit-tests — add builder test cases for the new builder methods to `BuilderTests.cs`
   (never one test file per component). Load pr-build — dotnet build → dotnet test until green.
8. Load pr-rhino-test — build/refresh the demo .gh files for the new items and live-test them
   (same auto-fix loop as Phase 12 Step B).
9. Re-run **[HUMAN GATE 6]** for the new items only: "Confirm the new components work live in
   Grasshopper." Fix and rerun Step 8 on a bug report.
10. Update session.json — append the round to `decisions.extend_rounds`
    (the items added + that Gate 6 / icon gate passed), `last_completed_step`, `next_step`; clear
    `phase_progress.extend` (kept as `{ round, step }` while a round is running so a resume lands in
    the right step); regenerate CLAUDE.md via pr-gh-package (inside its `<!-- pr:begin -->` /
    `<!-- pr:end -->` markers only).

After this round's Gate 6 passes, **return to the top of this loop and ask again** — keep looping
until the user answers "no". Only then continue to Phase 13.

---

## PHASE 13 — DOCS

Load skill: pr-docs
Generate the docs/ folder — one md per component, subcategory indexes, quickstart,
authentication, examples, changelog. If `demos/` holds no `.gh` files (Phase 12 degraded), the
examples pages are written from `plugin-spec.json`'s workflows instead and say so.
Update session.json: phase 13 complete.

---

## PHASE 14 — GITHUB

Load skill: pr-gh-package

**A. Write the four files.** README.md, CLAUDE.md, LICENSE, .gitignore (the README can reference
the docs/ folder written in Phase 13). Generated sections sit inside `<!-- pr:begin -->` /
`<!-- pr:end -->` markers; on any re-run only those sections are regenerated, so user edits outside
them survive. The README's **"What you can do with it"** section comes from the confirmed target
workflows — it is part of the template, not an optional extra.

**B. Check what the .gitignore is about to let through.** `dogfood/`, `.claude/` and
`settings.local.json` must be ignored *before* the first commit (the two `git` checks in
`pr-gh-package`). This is the last moment it's free.

**C. Create the repo and push.** Ask public/private, then `git init -b main` → `git add .` → review
`git status --short` → commit → `gh repo create [org]/[PluginName] --source=. --remote=origin
--push`. No `gh`? Hand the user the browser + `git remote add` path; don't improvise auth.

Update session.json: write the `github` block (repo, url, visibility, pushed_at) and mark phase 14
complete. **The phase is complete on the push, not on the files** — README.md on disk with no
remote is a half-finished Phase 14.

---

## PHASE 15 — PACKAGE + SHIP

Run `/rest-package`'s validated-calls check first (no component ships on a non-VALIDATED call
without an explicit "ship anyway" recorded in `decisions.ship_unvalidated`).
Load skill: pr-yak-package
Build .yak for all 3 targets (net48 → rh7, net7.0-windows → rh8 win, net7.0 → rh8 mac) → dist/
Load skill: pr-ci-template
Generate both workflows — `.github/workflows/build.yml` (PR → build + test) and `publish.yml`
(tag → Release with 3 `.yak` **and** 3 Libraries-folder `.zip` files). Commit and push them.

Update session.json: **phase 15 complete** — three packages plus both workflows is the whole
deliverable. Gate 7 is a separate human test of what was just built and stays pending.

**[HUMAN GATE 7]** "Install .yak on Rh7 Win, Rh8 Win, Rh8 Mac. Does it pass?"
Wait for "passes" or platform bug. Fix and repackage (`gate_feedback["7"]` while fixing).
Update session.json: gate 7 passed; set the plugin's entry in `~/.please-rest/sessions.json` to
`status: complete`.

**Only then**, publish — three separate channels, none of which is a side effect of another
(`pr-yak-package` "Publishing" has the full checklist):
1. `git tag v<csproj Version> && git push origin v<version>` → `publish.yml` builds the six Release
   assets. Confirm the run went green, then append the tag to `github.released_tags`.
2. `yak login` + `yak push` for **all three** packages → `published.yak_pushed`.
3. Food4Rhino listing — the three install **zips**, the 1024 px `[XX]_Plugin_Icon.png`, the csproj
   description, links to the repo/Release/docs → `published.food4rhino_url`.

**Then the backfill.** README's `(pending first release)` lines and `docs/index.md`'s
`(pre-release)` / Food4Rhino / Released placeholders are now stale — replace them with the real
links and dates and push (`pr-yak-package` "After publishing"), then set `published.backfilled`.
Skipping this is how a live plugin keeps telling its users it hasn't shipped.

Print:
```
Restling complete.
[PluginName] is packaged and pushed — github.com/[org]/[PluginName].
3 .yak packages in dist/; tag v<version> to have CI publish the Release (3 .yak + 3 .zip).
Then: yak push (3 packages), the Food4Rhino listing (the 3 zips + the 1024px logo), and the
README / docs/index.md backfill. PleaseREST does not publish for you.
```
