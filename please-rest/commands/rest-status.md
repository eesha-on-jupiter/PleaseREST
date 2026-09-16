---
description: "Show the pipeline progress tree for the active build. Read-only, safe to run at any time."
---

# /rest-status

Show where the active plugin build is — the full pipeline progress tree, on demand, at any time.
Read-only; safe to run whenever.

---

## Steps

1. Read `spec/session.json`.
   If not found: "No active session in this directory. Run /rest-new-plugin to start, or
   /rest-resume-plugin to pick up another build."

2. Load skill: `pr-session`. Render the **progress tree** exactly as it appears at a gate — the
   15-phase / 7-gate tree with inline gate labels, driven by `session.json`
   (`completed_phases`, `current_phase`, `gates_passed`, `gates_pending`):
   - `✓` completed phase · `►` current phase (mid-build) · blank upcoming
   - `◆ Gate n · <label>` with `✓` passed / `◀ YOU ARE HERE` current / nothing upcoming
   - `Now:` / `Next:` footer

3. **If the build is currently sitting at a gate** (a pending gate is awaiting the user), also print
   that gate's **YOUR MOVE** block so they see exactly what to do. If mid-phase (not at a gate),
   replace it with a one-line `In progress:` note — current phase, last step done, next step.

4. **Version check (read-only, no stamping — that only happens on resume/add-feature).** If
   `session.json.please_rest_version` differs from the live `plugin.json.version`, append one line:
   `PleaseREST: v[stamped] → v[current] available — run /rest-resume-plugin for details.` Omit this
   line entirely when the versions match or the field is missing on an old session (no need to
   alarm on a plain status check — the resume flow is where the real alert and choice live).

4a. **Phase-completion audit.** Run `pr-session`'s "Phase-completion audit" — check the on-disk
   artifacts for phases 11–15 against `completed_phases` and print the mismatch block if any phase's
   artifacts are all present but the phase isn't recorded (or vice versa). This is a read-only
   command, so **offer** the reconciliation rather than writing it: end the block with
   "Run /rest-resume-plugin to reconcile." Nothing else in `/rest-status` writes, and neither does
   this.

5. **Build detail** (only meaningful from Phase 10 onward) — read `spec/todo.md` and append a compact
   per-phase completion count so the user can see batch-build progress inside Phase 10:

```
Build detail (todo.md):
  Auth                 [n/n] ✓
  Simple Units         [n/n] (n remaining)
  Aggregator           [n/n]
  Level 2              SKIPPED
  Custom / AEC         [n/n]
  Presets              [not started]
  Overall: [n] of [total] component tasks complete
```

6. **Ship state** (only from Phase 14 onward) — append a short block so "is it actually out there?"
   is answerable at a glance, read from `session.json.github`, `session.json.published` and `dist/`:

```
Ship state:
  GitHub:   github.com/[org]/[PluginName] — pushed [date] · workflows build.yml, publish.yml
  Released: v1.0.0 (6 assets: 3 .yak + 3 .zip)      ← or "no tag pushed yet"
  Yak:      pushed / not pushed
  F4R:      [listing url] / not listed
  Docs:     links backfilled / still says "(pending first release)"
  dist/:    3 .yak, 3 .zip
```

   `github` absent → `GitHub: not pushed`. Never infer the repo from `github_org` alone: the org is
   a naming input, the `github` block is evidence of an actual push. The last three lines come from
   `published`; if `published.backfilled` isn't set while a tag or a listing exists, say so — a live
   plugin whose README still reads "(pending first release)" is the most common stale-ship state.

7. No writes — this command is read-only (does not touch `session.json` or the index).

---

## Example output (mid-batch-build, between gates)

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
Now:   ► Phase 10 — Batch Build (in progress)
Next:  Phase 11 — Icons   →   Phase 12 → Gate 6 · Test in Rhino
───────────────────────────────────────────────────────────────
In progress:  last done CreateRecord.cs · next UpdateRecord.cs

Build detail (todo.md):
  Auth                 [3/3] ✓
  Simple Units         [8/8] ✓
  Aggregator           [2/5] (3 remaining)
  Presets              [not started]
  Overall: 13 of 21 component tasks complete
```
