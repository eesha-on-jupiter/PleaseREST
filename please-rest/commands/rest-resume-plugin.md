---
description: "Resume a PleaseREST plugin build from the last saved session."
---

# /rest-resume-plugin

Resume a PleaseREST plugin build from where it was left off.
Load skill: pr-session

---

## Lookup order

1. Check current directory for `spec/session.json`
2. If not found: check `~/.please-rest/sessions.json` for all active sessions
3. Handle based on what is found (see below)

---

## Version check

Once a session is loaded — a single session found directly, or one picked from multiple below —
and **before printing its resume summary**, run `pr-session`'s "Version check on resume": compare
that session's `please_rest_version` to the live `plugin.json.version`. If PleaseREST has moved on
since this session was last touched, show the changelog-derived alert (affected completed phases
vs. upcoming phases, per pr-session) **before** the resume prompt below. Accept a phase name (e.g.
"catch up Phase 3") in addition to "yes" / "show todo first" — route to that phase's re-run command
if one exists, or offer a manual walkthrough if not. Stamp `please_rest_version` current once shown.

## One active session

Print summary and ask to continue:

```
PleaseREST — resuming [PluginName]
────────────────────────────────────────
Phase:     [current_phase] of 15 — [current_phase_name]
Last done: [last_completed_step]
Next:      [next_step]

Completed phases:  [list]
Gates passed:      [list]
Gates pending:     [list with descriptions]

Decisions on record:
  AEC features:    [list or "none"]
  Skipped:         [list or "none"]
  Partial calls:   [list or "none"]
  Manual fixes:    [list or "none"]
  Open gate feedback: [gate n — "text", or "none"]
  Degraded/skipped:   [list or "none"]

Restling from where we left off. Continue? (yes / show todo first)
────────────────────────────────────────
```

If user says "show todo first": print current spec/todo.md, then ask again.
If user says "yes": load session, read next_step, continue from exactly that point — honouring the
resume fields in `pr-session` ("How the optional fields change the resume point"): an open
`gate_feedback` / `awaiting_fix` means resume **at the fix**, not at the gate question;
`phase_progress` places you mid-Phase 7 / 11 / 12 / extend round; `degraded["12"]` means Gate 6 is
fully manual; `skipped_phases` are not re-run.

---

## Multiple active sessions

```
PleaseREST — active sessions
────────────────────────────────────────
  1. [PluginName]    Phase [n] — last active [relative time]
  2. [PluginName]    Phase [n] — last active [relative time]

Which would you like to resume?
────────────────────────────────────────
```

User types 1 or 2. Load that session and print its summary (same format as single session above).

---

## No session found

```
No active session found in this directory.
Run /rest-new-plugin to start a new plugin build.
```

---

## After resuming

- Load all context from session.json before doing anything
- Read next_step — continue from exactly that file or operation
- Do not repeat steps already marked [x] in todo.md
- Update last_active timestamp in session.json immediately on resume
