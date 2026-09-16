---
description: "Scaffold one component by ID from plugin-spec.json, selecting the correct skill for its type."
argument-hint: "<component_id>"
---

# /rest-build-component <component_id>

Scaffold one component by ID. Looks up the component in plugin-spec.json,
selects the correct skill, and writes the file.

---

## Steps

1. Read `spec/plugin-spec.json` — find the component matching `component_id`
   (match on `class_name`, `file_name`, or `endpoint_id` — whichever the user supplied)
   If not found: list available component IDs and ask the user to pick one.

2. Determine component type:
   - `type: "button"` → load pr-conventions + pr-button
   - `type: "preset"` → load pr-conventions + pr-preset
   - Subcategory name contains "JSON" → load pr-conventions + pr-builders
   - Everything else → load pr-conventions + pr-component

3. Read the matched call shape from `spec/call-library-validated.json`
   (use the entry matching `endpoint_id`). Honour its `auth_in` (header / header:<Name> /
   query:<param>) and `body_required` when writing the call.
   If the entry is missing, or its `test_result.tag` is not `VALIDATED`: STOP. Do not fall back
   to the unvalidated `call-library.json` — run `/rest-test-api` (PARTIAL: enrich
   `example_request` then `retest_entries`) or have the user decide at Gate 4 (skip / flag for v2).
   The only exception is an entry the user already recorded under
   `session.json.decisions.skipped_endpoints` or `ship_unvalidated` — build it with a `// TODO:
   unvalidated call` note and say so.

4. Write the component file to the correct path (flat layout — project files at the plugin
   root, no `src/`; see pr-file-structure):
   - Component: `Components/[Subcategory]/[FileName].cs`
   - Builder: `JSON Builders/[FileName].cs`
   - Preset: `Components/Presets/[FileName].cs`
   If the file already exists and is marked `[x]` in todo.md, do not overwrite it — tell the user
   and stop (a rebuild of a hand-edited file is their call).

5. Generate a new GUID for `ComponentGuid` — do not reuse any existing GUID in the project

6. Mark the item [x] in `spec/todo.md`

7. Update `session.json`: last_completed_step = that file, next_step = next todo item

8. Prompt: "Run generate_icon for [ComponentName] when ready, or continue with the next component."
