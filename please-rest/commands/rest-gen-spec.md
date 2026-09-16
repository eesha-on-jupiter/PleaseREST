---
description: "Regenerate spec/plugin-spec.json from feasibility.json without rerunning API discovery."
---

# /rest-gen-spec

Regenerate `spec/plugin-spec.json` from the existing `spec/feasibility.json`.
Use this when you need to revise the plugin structure without rerunning API discovery.

Load skills: pr-conventions + pr-spec

---

## Steps

1. Read `spec/feasibility.json` — confirm it exists
   If not: "No feasibility.json found. Run /rest-new-plugin first to complete API discovery."

2. Check for `spec/workflows.json`. If missing, run pr-spec's Step 0 (propose a grounded
   candidate workflow list, present it, let the user confirm/edit/add, write workflows.json)
   before continuing — a re-run must not skip workflow gathering just because it isn't a
   first-time build.

3. Read `spec/plugin-spec.json` if it exists — show what will be replaced. Keep its
   `aec_features` block (Gate 3 output) and any components the user hand-edited: the new draft
   must **carry `aec_features` forward unchanged** and present hand-edited components as
   "kept from the existing spec" rather than silently dropping them.

4. Run the pr-spec skill: propose subcategories, components, I/O, builders — derived from
   spec/workflows.json (Dual Style Pattern, consolidated components, no native-GH rebuilds)

5. Run inline validator, including the workflow-coverage and display-name checks

6. Run agent: pr-spec-critic against the drafted spec + workflows.json; fold its simplification
   notes into what's presented next

7. Present proposed spec to user with diff from existing spec (if any), plus the "skip for v1"
   list and pr-spec-critic's simplification notes

8. Wait for approval

9. Write `spec/plugin-spec.json`

10. Update `session.json`: last_completed_step = "plugin-spec.json". **Do not reset
    `completed_phases`.** Set `current_phase = 3` only if `current_phase < 3`; otherwise leave it
    and record `decisions.spec_regenerated_at_phase = [current_phase]`.

11. If the plugin had already passed Phase 5, warn which downstream artifacts are now stale:
    ```
    plugin-spec.json regenerated at Phase [n]. Now stale until re-run:
      • spec/todo.md                      → /rest-gen-todo
      • spec/call-library*.json           → /rest-extract-api, /rest-test-api (only if endpoints changed)
      • built components no longer in the spec, or with changed I/O → rebuild via /rest-build-component
      • icons.json entries for renamed / removed components
    ```

12. Prompt: "Run /rest-gen-todo to regenerate the task list from the updated spec."
