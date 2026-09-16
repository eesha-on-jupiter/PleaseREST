---
name: pr-dogfood
description: Maintain a running findings log for the current pipeline run — append findings, errors, and phase results to the dogfood file automatically at every phase, failure, and human gate
---

# Skill: Dogfood / run findings logger

Keeps a human-readable findings log current throughout a pipeline run, so breakages are captured
**as they happen** instead of relying on the engineer to remember them. This skill is what makes
"Claude keeps the dogfood file updated" real: `pr-session` invokes it at every phase boundary, and
it is also triggered directly the moment anything fails.

This skill only ever **appends** — it never rewrites or renumbers existing findings.

---

## Where it writes

- The findings file path is `findings_path` in `spec/session.json` (set at Phase 1 intake).
- Default: `dogfood/[plugin]-run-01.md` in the generated plugin workspace.
- During PleaseREST self-dogfooding, set `findings_path` to the PleaseREST repo's dogfood file
  (e.g. `.../PleaseREST/dogfood/[platform]-run-01.md`) so tool bugs land in the tool's repo.
- If the file does not exist, create it with the header + phase-log blocks below, then append.

---

## When to write (trigger points)

1. **End of every phase** — append/update the Phase log (tick the phase, note next). Runs right
   after `pr-session` writes `session.json`.
2. **The moment anything fails** — append a finding immediately when:
   - a Bash / `dotnet` / `yak` / `python` command exits non-zero
   - `pr-api-extractor` returns `AMBIGUOUS` or `MISSING`, or `pr-api-tester` returns `FAILED` / `PARTIAL`
   - a build or test error appears in `pr-build`
   - `claude plugin validate` reports any error
3. **At every human gate** — record the gate number, what was reviewed, and any issue the human raised.
4. **Whenever the user says output is wrong** — log it as a finding straight away.
5. **Whenever a generated artifact is edited by hand to make it work** — the strongest TOOL signal
   there is. If a csproj, a workflow, a manifest, a README or a `.gitignore` that PleaseREST wrote
   had to be changed for the plugin to build, package, release or install, that is a defect in the
   skill that wrote it. Log it *even though the build is now green* — especially then, because
   nothing else will ever surface it.
6. **Phases 13, 14 and 15, every time.** The ship phases are the ones that get done in a hurry, by
   hand, across sessions — and they are the least covered by any automated check. Tick each one and
   append a finding for anything that had to be fixed to get through it. In one dogfood run these
   three phases produced **zero** findings while three real tool defects were being fixed by hand in
   the workflow and the csproj; that is the failure mode this trigger exists to stop.
7. **A red CI run** — a failing GitHub Actions job is a non-zero exit like any other, even though it
   happened on a runner rather than locally. Paste the failing step and its error.

---

## Finding format (append one block per finding)

```
### F[n] — short title
- **Category:** TOOL (a PleaseREST defect) | RUN (an issue with THIS target API or build)
- **Phase:** [n] — [name]
- **What:** what happened, concretely (paste the actual error / status)
- **Impact:** what it breaks or blocks
- **Fix:** which skill / MCP / spec file to change and how (TOOL); or how it was worked around (RUN)
- **Status:** open | fixed
```

- Number findings sequentially across the whole run; **never renumber** existing ones.
- **TOOL** findings are PleaseREST bugs — these are the dogfood signal that drives plugin fixes.
  **RUN** findings are about the current API/build and stay with this run.
- Every finding must point at a **real, reproduced symptom** — never speculation. If unsure whether
  something is a defect, note it as an observation under Phase log, not as a finding.
- When a TOOL finding is fixed, set Status to `fixed` and add a `Fix (spec):` line if the spec changed.

---

## Header block (write once, when creating the file)

```markdown
# Dogfood Run — [PluginName]

> Target API: [Platform] · Started [date] · Driver: Claude (--plugin-dir launch)
> Goal: build a working Grasshopper plugin for [Platform]; capture every place PleaseREST breaks.
> findings_path: [this file]

## Findings

_None yet._

## Phase log
- [ ] Phase 1 — Intake
- [ ] Phase 2 — API Discovery
- [ ] GATE 1 — approve API
- [ ] Phase 3 — Plugin Spec
- [ ] GATE 2 — approve structure
- [ ] Phase 4 — AEC Features
- [ ] GATE 3 — select features
- [ ] Phase 5 — Todo List
- [ ] Phase 6 — API Extraction
- [ ] Phase 7 — API Testing
- [ ] GATE 4 — resolve failed calls
- [ ] Phase 8 — Scaffold
- [ ] Phase 9 — Auth Component
- [ ] GATE 5 — test auth in Rhino
- [ ] Phase 10 — Batch Build
- [ ] Phase 11 — Icons
- [ ] Phase 12 — Tests
- [ ] GATE 6 — test in Rhino
- [ ] Phase 13 — Docs
- [ ] Phase 14 — GitHub
- [ ] Phase 15 — Package + Ship
- [ ] GATE 7 — cross-platform test
- [ ] Published — tag / yak push / Food4Rhino / backfill
```

Write the list out in full — it is the run's own checklist, and a log that says
`- [ ] ... (all 15 phases + 7 gates)` never gets ticked. If an existing log still carries the old
14-phase numbering (`Phase 13 — Docs + GitHub`, `Phase 14 — Package + Ship`), correct those two
lines to the current 15-phase names on the next write; that is renumbering the *phase log*, which
is a checklist, not renumbering findings, which is forbidden.

---

## What this skill CANNOT catch (state this to the user, do not pretend otherwise)

- **Load-time failures** that stop the plugin or its skills from loading at all (bad manifest, wrong
  layout — the F1/F2 class). If skills do not load, this skill does not run. Those are caught by
  `claude plugin validate` and the Phase 1 Step 0 preflight in `/rest-new-plugin`, not here.
- **Subtle wrongness** in generated output that compiles/passes but is semantically wrong. This skill
  logs failures and what it is told; it is **not** a substitute for human review at the gates.

- **Anything done in a different session with this skill not loaded.** The log is only as complete
  as the sessions that wrote it; a phase finished in a bare `claude` session leaves no trace. On
  resume, if `session.json` shows phases the log never ticked, say so and backfill the phase log
  from what is on disk (`pr-session`'s phase-completion audit) rather than leaving it silently wrong.

Be honest about this scope when reporting status — never imply the dogfood file is a complete record
of correctness. It is a complete record of *observed failures*, which is not the same thing.
