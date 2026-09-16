---
name: pr-session
description: Read, write, and resume session.json state across coding sessions for Grasshopper REST API plugins
---

# Skill: Session

Manages `spec/session.json` — the plugin build's persistent memory — and the global
`~/.please-rest/sessions.json` index across all active plugin builds.

---

## session.json schema

```json
{
  "plugin_name": "AcmeConnect",
  "platform": "Acme",
  "docs_url": "https://developers.acme.example/reference",
  "token_env_var": "PLEASE_REST_TOKEN",
  "findings_path": "dogfood/AcmeConnect-run-01.md",
  "started": "2026-06-01T09:00:00",
  "last_active": "2026-06-03T14:32:00",
  "please_rest_version": "1.0.0",
  "current_phase": 10,
  "current_phase_name": "Batch Build",
  "completed_phases": [1, 2, 3, 4, 5, 6, 7, 8, 9],
  "gates_passed": [1, 2, 3, 4, 5],
  "gates_pending": [6, 7],
  "last_completed_step": "CreateBoardComponent.cs",
  "next_step": "DeleteBoardComponent.cs",
  "decisions": {
    "aec_features_selected": ["Auth Manager", "Batch Processor"],
    "skipped_endpoints": ["DELETE /boards/{id} — destructive, flagged for v2"],
    "partial_calls": ["update_item — response shape uncertain, scaffolded with note"],
    "manual_fixes": ["create_connector — wrapper object missing from docs, fixed manually"]
  },
  "flags": {
    "token_ready": true,
    "openapi_spec_used": false,
    "auth_gate_passed": true,
    "first_component_approved": true
  },

  "preflight": { "mcp": "ok", "python_deps": "ok", "dotnet": "ok — 8.0.404", "yak": "missing — Phase 15 will stop", "token": "ok", "bridge": "missing — Gate 6 manual" },
  "author": { "name": "A. Builder", "contact": "abuilder@example.com" },
  "github_org": "acme-tools",
  "github": {
    "repo": "acme-tools/AcmeConnect",
    "url": "https://github.com/acme-tools/AcmeConnect",
    "visibility": "public",
    "pushed_at": "2026-09-14T11:20:00",
    "workflows": ["build.yml", "publish.yml"],
    "released_tags": ["v1.0.0"]
  },
  "published": {
    "yak_pushed": true,
    "food4rhino_url": "https://www.food4rhino.com/en/app/acmeconnect",
    "backfilled": true
  },
  "gate_feedback": { "6": "CreateRecord returns 400 — 'fields' wrapper missing" },
  "awaiting_fix": true,
  "skipped_phases": [],
  "degraded": { "12": "no bridge — manual Gate 6" },
  "phase_progress": {
    "7":  { "tested_ids": ["auth_check", "list_boards"] },
    "11": { "rendered": ["AC_FindRecord", "AC_CreateRecord"] },
    "12": { "step": "B", "attempt": 2 },
    "extend": { "round": 1, "step": 5 }
  }
}
```

**Optional fields — all default to absent/empty; a session without them is valid and resumes
exactly as before:**

| Field | Written when | Meaning / default |
|---|---|---|
| `preflight` | Phase 1 Step 0 | Environment check results (`"ok"` or `"missing — <note>"`). Absent = never checked. |
| `author` | Phase 1 intake, pre-filled from `git config user.name` / `user.email` and confirmed | `{ name, contact }` — **the user building the plugin**. Substituted for `[AuthorName]` / `[AuthorContact]` in `GH_AssemblyInfo` (`pr-assembly`), `manifest.yml` `authors` (`pr-yak-package`), the README byline and the LICENSE copyright (`pr-gh-package`). Absent on a pre-1.0.0 session = ask once and write it; never fall back to a hardcoded person. |
| `github_org` | Phase 1 (if the user gives one) or first `pr-docs` / `pr-gh-package` run | GitHub org/user for generated links. Absent = ask. |
| `github` | Phase 14, **after** the repo is created and `main` is pushed (`pr-gh-package` "Publish to GitHub") | `{ repo, url, visibility, pushed_at, workflows, released_tags }`. Absent = the plugin has never been pushed, whatever else is on disk. `released_tags` grows one entry per tag push that fires `publish.yml`. |
| `published` | After Gate 7, as each distribution channel actually goes live (`pr-yak-package` "Publishing") | `{ yak_pushed, food4rhino_url, backfilled }`. Absent = nothing has been distributed beyond the repo. `backfilled` records that the README / `docs/index.md` placeholders were replaced with the real links and dates. |
| `gate_feedback` | A gate is answered with a correction / bug report instead of approval | `{ "<gate n>": "the user's words" }`. Removed for that gate when it passes. |
| `awaiting_fix` | Set `true` together with `gate_feedback`; cleared to `false` when the gate passes | Resume goes to the fix, not the gate question. Default `false`. |
| `skipped_phases` | A phase is deliberately not run (`[{ "phase": 12, "reason": "…" }]`) | Resume never re-runs a listed phase. Default `[]`. |
| `degraded` | A phase ran in fallback mode (`{ "12": "no bridge — manual Gate 6" }`) | Tells Gate 6 / pr-docs how the phase actually ran. Default `{}`. |
| `phase_progress` | Mid-phase, for the phases that have internal position: `"7".tested_ids`, `"11".rendered`, `"12".{step,attempt}`, `"extend".{round,step}` | Cleared for a phase when that phase completes. Default `{}`. |
| `decisions.seed_ids` | Phase 1 intake ("Test workspace / seed IDs") | Passed to `run_all_tests` / `retest_entries` as `seed_ids`. |
| `decisions.ship_unvalidated` | `/rest-package` "ship anyway" | Components allowed to ship on non-VALIDATED calls, on record. |
| `decisions.spec_regenerated_at_phase` | `/rest-gen-spec` after Phase 3 | Marks downstream artifacts as stale. |
| `decisions.gate5_deferred` | Gate 5 "defer to Gate 6" | Gate 5 is re-asked with Gate 6. |
| `gates_passed` entries may be objects | Gate 4 auto-clear | `4` or `{ "gate": 4, "auto": true }` — render both as ✓; `auto` means no human decided (nothing to decide). |

`please_rest_version` — the PleaseREST version this session was last confirmed against (from
`please-rest/.claude-plugin/plugin.json`). Stamped on every write; compared against the live
plugin version on resume — see "Version check on resume" below. A missing stamp, or any `2.x`
stamp from the pre-release period, means the session predates 1.0.0 and is always treated as
behind — never silently skipped, and never read as "newer" by version order.

---

## Global sessions index

`~/.please-rest/sessions.json` — lists all active session files.

```json
{
  "sessions": [
    {
      "plugin_name": "AcmeConnect",
      "path": "/path/to/AcmeConnect/spec/session.json",
      "current_phase": 10,
      "last_active": "2026-06-03T14:32:00",
      "status": "active"
    }
  ]
}
```

`status` is `"active"` until Gate 7 passes, then `"complete"` (written by `/rest-package` /
Phase 15). `/rest-resume-plugin` lists `active` sessions only, unless asked for completed ones;
`/rest-add-feature` on a `complete` session flips it back to `active` for the round. A missing
`status` (index written before 1.0.0) means `active`. On Windows, `~` is the user profile folder
(`%USERPROFILE%\.please-rest\sessions.json`).

---

## On /rest-resume-plugin

1. Check current directory for `spec/session.json`
2. If not found: check `~/.please-rest/sessions.json`
2a. Once a session is identified (here, or after the user picks one under "Multiple sessions"
    below), run **"Version check on resume"** (below) before printing its summary.
3. **One session** — print summary and ask to continue:

```
PleaseREST — resuming [PluginName]
────────────────────────────────────────
Phase:     [n] of 15 — [phase_name]
Last done: [last_completed_step]
Next:      [next_step]

Completed phases:  [list]
Gates passed:      [list]
Gates pending:     [list with descriptions]

Decisions on record:
  AEC features:    [list]
  Skipped:         [list]
  Partial calls:   [list]
  Manual fixes:    [list]
  Open gate feedback: [gate n — "text", or "none"]
  Degraded/skipped:   [list or "none"]

Restling from where we left off. Continue? (yes / show todo first)
────────────────────────────────────────
```

3a. **How the optional fields change the resume point** (checked in this order, first match wins):
   - `awaiting_fix: true` → resume **at the fix** for `gate_feedback[n]`: re-show the feedback,
     load the relevant build skill, fix, rerun that phase's check (Step B for Gate 6), then re-ask
     the gate. Never re-ask the gate question first as if the report had not happened.
   - `phase_progress["7"]` present and Phase 7 not complete → `retest_entries` for the IDs not in
     `tested_ids` (with `decisions.seed_ids`), not `run_all_tests` from scratch.
   - `phase_progress["11"]` → render only icons not in `rendered`.
   - `phase_progress["12"]` → re-enter Step A or B at `attempt` (the auto-fix cap still applies).
   - `phase_progress["extend"]` → resume the extend round at `step` (steps are numbered in
     `/rest-new-plugin`'s extend loop / `/rest-add-feature`).
   - `degraded["12"]` → Gate 6 is fully manual (demos/README.md, not pre-checked .gh files); say so.
   - a phase in `skipped_phases` is shown as `–` in the tree and never re-run without being asked.
   - `decisions.gate5_deferred` → Gate 5 is still pending; ask it together with Gate 6.
   - otherwise → `next_step`, as before.

4. **Multiple sessions** — ask which to resume:

```
PleaseREST — active sessions
────────────────────────────────────────
  1. [PluginName]    Phase [n] — last active [relative time]
  2. [PluginName]    Phase [n] — last active [relative time]

Which would you like to resume?
────────────────────────────────────────
```

5. **No session** — fall through to /rest-new-plugin:

```
No active session found in this directory.
Run /rest-new-plugin to start a new plugin build.
```

---

## Progress tree (render at EVERY gate)

At every human gate — and on resume — render this tree first, so the user always sees where they are,
what's being worked on, the gate they're at, and what's coming. Drive it from `session.json`
(`completed_phases`, `current_phase`, `gates_passed`, `gates_pending`).

```
PleaseREST — [PluginName]   ·   Restling
═══════════════════════════════════════════════════════════════
  ✓   1  Intake
  ✓   2  API Discovery       ◆ Gate 1 · Approve API           ✓
  ✓   3  Plugin Spec         ◆ Gate 2 · Approve structure     ◀ YOU ARE HERE
      4  AEC Features        ◆ Gate 3 · Select features
      5  Todo List
      6  API Extraction
      7  API Testing         ◆ Gate 4 · Resolve failed calls
      8  Scaffold
      9  Auth Component      ◆ Gate 5 · Test auth in Rhino
     10  Batch Build
     11  Icons
     12  Tests               ◆ Gate 6 · Test in Rhino
     13  Docs
     14  GitHub
     15  Package + Ship      ◆ Gate 7 · Cross-platform test
═══════════════════════════════════════════════════════════════
Now:   ◆ Gate 2 · Approve structure
Next:  Phase 4 — AEC Features   →   Gate 3 · Select features
───────────────────────────────────────────────────────────────
YOUR MOVE — Gate 2: Approve the plugin structure
  • Review the component list, subcategories, and I/O wiring above.
  • Reply "yes" to continue, or tell me what to add / remove / rename.
```

Each gate carries its **short label inline** (`◆ Gate 1 · Approve API`), not just the number — so the
whole pipeline reads at a glance. Always also print the **YOUR MOVE** block under the tree at a gate —
the user must know exactly what to do and how to respond. Use the labels and per-gate text below.

**What the user does at each gate (the YOUR MOVE block):**

| Gate | YOUR MOVE — what to do | How to respond |
|---|---|---|
| 1 | Review the API overview — endpoints, auth, hierarchy, base URL. | "yes" to continue, or correct anything wrong. |
| 2 | Review the component list, subcategories, and I/O wiring. | "yes", or say what to add / remove / rename. |
| 3 | Choose which AEC features to include (or describe a custom one). | List the features to add, or "none". |
| 4 | Review the calls that failed validation; decide each one. | Per entry: "fix", "skip", or "flag for v2". |
| 5 | Point GrasshopperDeveloperSettings at `bin/Debug/net7.0-windows/` (Rh8, .NET Core 8) or `bin/Debug/net48/` (Rh7), restart Rhino, drop the auth component, press the button. | "works", or paste the exact Status / error; or "defer to Gate 6". |
| 6 | Open the pre-built `demos/` files (paste your token into the Token panel first) and confirm each works live. If Phase 12 was degraded, build them from `demos/README.md`. | "all good", or report the component + bug. |
| 7 | Install the .yak on Rhino 7 Win, Rhino 8 Win, and Rhino 8 Mac. | "passes", or name the platform + the bug. |

**Phase glyph (left column):** `✓` = in `completed_phases`; `►` = `current_phase` and not yet
complete (used mid-phase / on resume); blank = upcoming.

**Gate marker (right of the phase that precedes it):** always `◆ Gate n · <label>` (labels below),
then a status flag — `✓` if in `gates_passed`, `◀ YOU ARE HERE` if it's the gate awaiting the user,
nothing if upcoming.

**Gate labels** (used inline in the tree and in the `Now:` / `Next:` footer):

| Gate | Label |
|---|---|
| 1 | Approve API |
| 2 | Approve structure |
| 3 | Select features |
| 4 | Resolve failed calls |
| 5 | Test auth in Rhino |
| 6 | Test in Rhino |
| 7 | Cross-platform test |

**Phase → gate map:** Gate 1 after 2, Gate 2 after 3, Gate 3 after 4, Gate 4 after 7, Gate 5 after 9,
Gate 6 after 12, Gate 7 after 15. The fixed 15 phase names are the labels above — never renumber.
(Phases 13 Docs and 14 GitHub are separate steps — `pr-docs` writes `docs/`, then `pr-gh-package`
writes README/CLAUDE.md/LICENSE/.gitignore; Package + Ship is Phase 15.)

**Extend loop (any time after Gate 6 first passes — not just before Phase 13).** Once Gate 6 passes,
`/rest-new-plugin` asks whether to add new components/workflows before Phase 13; if yes, those items
run the full build loop on their own — including an **Icons** gate ("Are these icons OK?") and a
re-run of **Gate 6** for the new items — then the question repeats until the user declines. The same
loop runs on demand via `/rest-add-feature`, at *any* point in the plugin's life — mid-build, sitting
in Docs/GitHub/Package, or already shipped. There is no state where a new component means "start
over" or "too late": naming one always re-enters at Phase 3 for that component alone.
This loop does **not** add new fixed phases: keep `current_phase` at 12 while it runs (unless the
plugin has already advanced past 12, in which case `current_phase` doesn't move backward — only the
new component's own build state is tracked mid-round), record each pass under `decisions.extend_rounds`
(items added + icon/Gate-6 approvals), and re-mark Gate 6 as `◀ YOU ARE HERE` in the tree while a round
is awaiting its live re-test or icon approval.
If invoked from `/rest-new-plugin` before Phase 13 has run, only advance to Phase 13 when the user
answers "no" to adding more. If invoked via `/rest-add-feature` after Phase 13/14/15 already
completed, catch those phases up for the new component instead of leaving them stale: incrementally
extend `docs/` if Phase 13 already ran, always regenerate README/CLAUDE.md (Phase 14), and rebuild
`dist/*.yak` via `/rest-package` if Phase 15 already ran (rebuild only — never auto-tag or push).

**Footer:** `Now:` is the current gate (or current phase mid-build) with its one-line ask; `Next:` is
the next phase and the gate it leads to (omit the gate if none follows before the end).

The 7 gate one-liners (for the `Now:`/`Next:` footer):
1 API overview · 2 plugin structure · 3 AEC features · 4 resolve failed calls · 5 auth in Rhino ·
6 pre-built demos in Rhino · 7 cross-platform test.

**Gate 4 auto-clear:** when Phase 7 ends with zero FAILED and zero PARTIAL entries there is nothing
for the human to decide. Write Gate 4 to `gates_passed` as `{ "gate": 4, "auto": true }`, remove it
from `gates_pending`, render it `✓` and say "Gate 4 auto-cleared". Never leave it pending forever,
and never write a bare `4` as if a human had decided.

**Gate rejection:** any gate answered with a correction or bug report writes
`gate_feedback["<n>"]` = the user's words and `awaiting_fix: true` *before* the fix starts. The
tree keeps `◀ YOU ARE HERE` on that gate with a `(fixing: …)` suffix. Both are cleared when the
gate passes.

On resume, render this tree in place of (or above) the text summary so returning users get the same
picture.

---

## Write timing

| Event | What to write |
|---|---|
| Phase complete | `current_phase`, `current_phase_name`, append to `completed_phases`, `last_active`, `last_completed_step`, `next_step` |
| Human gate passed | `gates_passed` append, `gates_pending` remove, timestamp note in decisions |
| MCP run complete | `last_active`, `last_completed_step`, `next_step` |
| File written mid-phase | `last_completed_step` = that file name, `next_step` = next file in todo.md |
| Decision made | Append to relevant `decisions` key — never overwrite |
| Gate answered with a correction / bug | `gate_feedback["<n>"]`, `awaiting_fix: true` (cleared when the gate passes) |
| Phase skipped or ran in fallback mode | append to `skipped_phases` / set `degraded["<n>"]` |
| Mid-phase position (7 / 11 / 12 / extend round) | `phase_progress["<n>"]` (removed when the phase completes) |
| Phase 14 — repo created + `main` pushed | `github` block, append `14` to `completed_phases` |
| Phase 15 — 3 `.yak` in `dist/` + both workflows written | append `15` to `completed_phases` (Gate 7 is separate and stays in `gates_pending`) |
| Gate 7 passed | `gates_passed` append, `gates_pending` remove, index entry `status: "complete"` |
| Tag pushed / `yak push` / Food4Rhino listed | `github.released_tags` append · `published.yak_pushed` · `published.food4rhino_url` — one at a time, as each actually happens |
| README + `docs/index.md` placeholders replaced with real links/dates | `published.backfilled: true` |

**`current_phase` is not a substitute for `completed_phases`.** Advancing `current_phase` to 15
without appending 14 says "phase 14 never happened", and that is exactly what `/rest-status` will
render — a ✓-less row under a plugin that is already on GitHub. Every phase writes **both**. The
two ship phases are the ones that get missed, because they're also the two most often run by hand
outside `/rest-new-plugin`'s linear pass:

- **Phase 14 completes on the push,** not on writing README.md. Files on disk with no `github`
  block is a half-done phase.
- **Phase 15 completes on the artifacts** — three `.yak` files and `build.yml` + `publish.yml` —
  *not* on Gate 7. Gate 7 is a human cross-platform test of what Phase 15 produced; leaving 15 out
  of `completed_phases` until the gate passes makes the packaging look un-run for as long as the
  user takes to get to a Mac.

---

## Phase-completion audit (run on resume and on /rest-status)

Session state drifts from the filesystem — a phase run by hand, a session file restored from an
older copy, a step done in a different Claude Code session. Before rendering the tree, check the
artifacts of the phases that leave obvious traces, and reconcile:

| Phase | Artifact on disk | Also required |
|---|---|---|
| 11 Icons | `Icons/*.png` + entries in `Properties/Resources.resx` | |
| 12 Tests | `[PluginName].Tests/` with at least one test file | |
| 13 Docs | `docs/index.md` + `docs/components/` | |
| 14 GitHub | `README.md`, `LICENSE`, `.gitignore`, `CLAUDE.md` | `git remote -v` names a remote **and** `session.json.github` is present |
| 15 Package | 3 × `dist/*.yak` + `.github/workflows/publish.yml` + `build.yml` | |

For any phase whose artifacts are all present but which is **not** in `completed_phases`, print one
line per phase and offer to reconcile — never silently rewrite the session, and never silently
believe the session over the disk:

```
Recorded state doesn't match what's on disk:
  Phase 14 (GitHub) — README.md, LICENSE, .gitignore present; remote is
                      github.com/acme-tools/AcmeConnect — but 14 isn't in completed_phases
  Phase 15 (Package) — dist/ has 3 .yak and publish.yml exists — but 15 isn't in completed_phases

Mark these complete? (yes / no — leave as-is)
```

On "yes": append the phases, backfill `github` from `git remote get-url origin` if it's missing,
and leave `gates_pending` alone — a gate is a human decision and is never inferred from a file.

The reverse mismatch matters too: a phase **in** `completed_phases` whose artifacts are gone (a
deleted `dist/`, a `docs/` never written) gets the same one-liner the other way round, and an offer
to re-run it.

Every `session.json` write also stamps `please_rest_version` to the plugin's current version (read
from `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`) — this keeps a plugin built start-to-finish
in one sitting automatically current with no extra step; the resume-time check below is what
catches a session that was set aside and picked up again after PleaseREST itself changed.

After every write to `session.json`: update `~/.please-rest/sessions.json` index entry.
After every phase complete **from Phase 14 onward** (there is no generated CLAUDE.md to
regenerate before pr-gh-package has run at Phase 14): trigger `pr-gh-package` to regenerate the
generated plugin's CLAUDE.md inside its `<!-- pr:begin -->` / `<!-- pr:end -->` markers.
After every phase complete, and immediately on any failure or human gate: trigger `pr-dogfood`
to append the phase result / finding to the file at `findings_path`. This is what keeps the
dogfood log current without the engineer having to remember — see the `pr-dogfood` skill for
trigger points and the finding format.

---

## Version check on resume

Runs at the start of `/rest-resume-plugin` and `/rest-add-feature` — both re-enter an existing
session read from disk, so both need to know whether PleaseREST itself has moved on since.

1. Compare `session.json.please_rest_version` to the live `plugin.json.version`
   (`${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`).

   **A `2.x` stamp means pre-1.0.0, and is always behind — never ahead.** PleaseREST's public
   history starts at 1.0.0; the `2.x` numbers come from the unreleased development period and were
   renumbered at first release. A plain semver comparison would read `2.6.0 > 1.0.0` and wave the
   session through with no alert, which is exactly backwards: those are the oldest sessions that
   exist. Treat any stamp whose major version is **2 or higher** as pre-1.0.0.

   A **missing** stamp means the same thing — a session written before the field existed. Never
   skip the check on a missing stamp: it is the session most likely to be behind.

   In both cases go to step 3 with the "Upgrading a plugin started before 1.0.0" section of
   `CHANGELOG.md` as the change list.
2. If equal: proceed normally, no alert.
3. If the stamped (or assumed-baseline) version is older: read `${CLAUDE_PLUGIN_ROOT}/CHANGELOG.md`, collect
   every entry strictly between the stamped version and the current version, and split by
   cross-referencing each entry's tagged phase(s) against `session.json.completed_phases`:
   - **Affects a completed phase** — that phase's own output predates the changed logic.
   - **Affects an upcoming phase** — informational only; it applies automatically once that phase
     runs, no action needed now.
4. Present both buckets before the usual resume prompt:
   ```
   ⚠ This plugin was built during PleaseREST's pre-release period (stamped v2.6.0) —
     now on v1.0.0. See "Upgrading a plugin started before 1.0.0".

   Affects phases you've already completed:
     • Phase 3 (Plugin Spec): pr-spec now derives components from stated workflows instead of a
       1:1 API mapping. Your plugin-spec.json predates this — re-run via /rest-gen-spec to rebuild
       it against the new logic, or continue as-is.

   Affects phases not reached yet (no action needed — applies automatically when you get there):
     • Phase 11 (Icons): icon rendering bugfixes.

   Continue as-is, or catch up a phase now?
   ```
   For a flagged phase with a dedicated re-run command (3 `/rest-gen-spec`, 5 `/rest-gen-todo`,
   6 `/rest-extract-api`, 7 `/rest-test-api`, 10 `/rest-build-component` /
   `/rest-build-all-components`, 15 `/rest-package`), name that command. For one without (1, 2, 4
   — re-run agent `pr-aec-advisor` by hand and re-select at Gate 3 —, 8, 9, 11, 12, 13, 14),
   describe the change and offer to walk through the catch-up manually — there's no dedicated
   command for those phases, and inventing one per phase is out of scope here.

   **Catch-ups for any pre-1.0.0 build** — the full list is `CHANGELOG.md`'s "Upgrading a plugin
   started before 1.0.0" section; read it from there rather than from memory, and present only the
   items that apply to this plugin's `completed_phases`. The ones that block a correct release:
   re-run `/rest-package` (the Rh8 Windows `.yak` was the Mac build, CI used `src/` paths, and both
   workflows are regenerated); add the Release `PropertyGroup` from `pr-vs-project` to the csproj;
   and set `session.json.author`, then fix the hardcoded author in `[PluginName]Info.cs`,
   `manifest.yml`, the README byline and the LICENSE. Also run the phase-completion audit above — a
   pre-1.0.0 build that reached GitHub or `dist/` almost certainly has Phases 14/15 missing from
   `completed_phases` and no `github` block.
5. Stamp `please_rest_version` to the current version once the alert has been shown, **regardless
   of the user's choice** — this means "you've been informed," not a nag that repeats on every
   future resume for the same already-surfaced gap. Actually catching up a phase (running
   `/rest-gen-spec` etc.) is a separate act that changes the real files; declining it doesn't undo
   having been told.

---

## Edge cases

- `session.json` corrupted or missing mid-build:
  - Reconstruct `completed_phases` from todo.md `[x]` items
  - Reconstruct `last_completed_step` from the newest `.cs` file under `Components/`,
    `JSON Builders/` or `Utilities/` at the plugin root (flat layout — there is no `src/`)
  - Optional fields (`gate_feedback`, `phase_progress`, `degraded`, …) cannot be reconstructed —
    leave them absent and tell the user any in-flight gate fix must be re-stated
  - Warn user that session was reconstructed
- `flags.token_ready` is **never** carried forward unverified — always re-derive it from an actual
  environment check of `token_env_var` (the var is set and non-empty) on resume and on any
  reconstruction. A persisted `true` can outlive the token (a reconstructed or copied session asserts
  readiness it never confirmed), which silently unblocks the Phase 7 / Gate 5 auth verify against a
  token that isn't there. If the var is unset, set `token_ready: false` and tell the user to set it
  before the auth verify. (dogfood F4)
- `/rest-new-plugin` run in a directory with existing `session.json`:
  - Warn: "An active session exists for [PluginName] at phase [n]. Resume or start fresh?"
  - Do not overwrite until user confirms
- Two sessions with the same plugin name:
  - Disambiguate by full path in the sessions index
  - Display path in the sessions list when names clash
