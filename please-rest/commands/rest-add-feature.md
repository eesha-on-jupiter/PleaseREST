---
description: "Add a feature or component to an existing plugin build, at any point after Gate 6 — even a shipped plugin; re-enters the pipeline at Phase 3, spec update only."
argument-hint: "<description>"
---

# /rest-add-feature <description>

Add a new feature or component to an existing plugin build — whether the plugin is mid-build,
sitting in Docs/GitHub/Package (Phases 13-15), or already shipped. There is no "too late" state:
naming a new component always re-enters the pipeline at Phase 3 for that component alone.

Re-enters the pipeline at Phase 3 (spec update only).
Runs Phases 6–12 for the new component(s) only, including the icon approval gate and a live
Rhino re-test at Gate 6. This is the same loop `/rest-new-plugin` offers after Gate 6 — the
difference is this command also catches the plugin back up on any of Phases 13-15 it had
already finished (step 14 below), since a shipped plugin with an undocumented, unpackaged
component isn't actually done.

---

## Step 0 — version check

Before reading anything else, run `pr-session`'s "Version check on resume" against
`spec/session.json` (this command re-enters an existing session exactly like `/rest-resume-plugin`
does, so it carries the same check). If PleaseREST has moved on since this session was last
touched, show the changelog-derived alert (affected completed phases vs. upcoming, per
`pr-session`) before proceeding to Step 1. Stamp `please_rest_version` current once shown.

## Steps

1. Read `spec/session.json` and `spec/plugin-spec.json`
   If not found: "No active session. Run /rest-new-plugin first."

   **Guard — plugin not scaffolded yet.** If `session.json.current_phase < 9` (no VS project, no
   client), there is nothing to build the feature *into*. Run steps 2–6 only (amend
   `plugin-spec.json` + `todo.md`, with pr-spec-critic), then stop with: "Added to the spec and
   todo — the main pipeline will extract, test and build it when it reaches Phases 6–10. Resume
   with /rest-resume-plugin." Do not run steps 7–15.

2. Understand the feature from the user's description.
   Ask clarifying questions if needed:
   - Which API endpoints does this use?
   - Is this a new subcategory or extends an existing one?
   - Any custom I/O requirements?

3. Load skill: pr-spec
   Propose additions to plugin-spec.json:
   - New component(s) with I/O
   - New builder methods (if needed)
   - New subcategory (if needed)
   Validate the additions inline.

3a. Run agent: pr-spec-critic against the amended spec + `workflows.json` (same as Phase 3) —
   fold its simplification notes into what's presented next.

4. Present the proposed additions. Wait for approval.

5. Append the new components to plugin-spec.json — do not rewrite existing components.
   Record in session.json decisions: `"aec_features_selected"` (if AEC feature) or create a new decisions key.

6. Load skill: pr-todo
   Add new items to spec/todo.md for the new components only. Mark all existing items unchanged.

7. Run MCP: pr-api-extractor for the new endpoints only. `extract_from_openapi` writes a whole
   file, so extract to a **temporary path** (e.g. `spec/call-library.new.json`) and merge only the
   new `endpoint_id`s into `spec/call-library.json` — existing entries (and their Gate-4 hand fixes)
   are never rewritten.

8. Run MCP: pr-api-tester → `retest_entries(new_ids, "spec/call-library.json",
   "spec/call-library-validated.json", seed_ids=decisions.seed_ids)` — the new IDs only, so
   already-validated endpoints are not re-fired (and no duplicate test records are created).

9. Route exactly as `/rest-test-api` step 5: PARTIAL → enrich + retest; FAILED → agent
   pr-api-scout → Gate 4 (scoped to the new entries) if still failing.

10. Load pr-conventions + correct type skill. Build the new component files.

11. Load skill: pr-icons. Add the new components' entries to icons.json (user specifies each icon),
    then run MCP pr-icon-generator (`generate_icon` → `add_to_resources`) for the new components.

11a. **[HUMAN GATE — ICONS]** Show the newly rendered icons and ask:
    "Are these icons OK? (yes / describe changes)". On changes, edit icons.json and re-render.
    Do not move on until the user approves the new icons.

12. Load skill: pr-unit-tests. Add builder test cases for the new builder methods to
    `BuilderTests.cs` (and `BulkAssemblyTests.cs` if an aggregator was added) — never one test
    file per component.
    Load skill: pr-build. Run dotnet build → dotnet test until green.

13. Load skill: pr-rhino-test. Build/refresh the demo .gh files for the new components and live-test
    them (auto-fix loop, as in Phase 12 Step B).
    **[HUMAN GATE 6]** "Confirm the new components work live in Grasshopper." Fix and rerun on a bug report.

14. Check `session.json.completed_phases` for phases the plugin already finished, and catch each
    one up on the new component(s) — don't leave a shipped plugin with an undocumented, unpackaged
    component just because those phases ran before this one existed:
    - **13 (Docs) already done:** Load skill: pr-docs, in incremental mode — add the new
      component's page(s) under `docs/components/[subcategory]/`, update that subcategory's
      `index.md` and `workflows.md`, and append one `changelog.md` entry for this addition. Do not
      regenerate pages for untouched components.
    - **14 (GitHub) already done:** always re-run pr-gh-package regardless (next line) — no
      separate check needed, README/CLAUDE.md regeneration is cheap and safe to always do. That
      includes the README's "What you can do with it" bullets: a new component that adds a real
      capability adds a bullet. Committing and pushing the regenerated files is the user's call —
      offer it, don't push on your own.
    - **15 (Package + Ship) already done:** this is a post-ship round, so **bump the version
      first** — patch-increment `<Version>` in the `.csproj` (the single version source: manifest
      and AssemblyVersion follow it) and add a matching entry to `docs/changelog.md` naming the
      new component(s). Then run `/rest-package` to rebuild the `.yak` for all 3 targets so
      `dist/` reflects the new component. This only touches local build output — it does not tag
      or push — so do it without asking. Tell the user afterward that a `v<new version>` tag +
      push is needed to actually ship the update.

15. Update session.json: decisions (append to `decisions.extend_rounds`), `phase_progress.extend`
    (`round`, `step` — cleared when the round completes), last_completed_step, next_step.
    Regenerate CLAUDE.md via pr-gh-package (inside its `<!-- pr:begin -->` / `<!-- pr:end -->`
    markers only).
