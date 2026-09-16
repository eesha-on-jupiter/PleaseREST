---
description: "Regenerate spec/todo.md from plugin-spec.json after the spec changes."
---

# /rest-gen-todo

Regenerate `spec/todo.md` from the existing `spec/plugin-spec.json`.
Use this after the spec changes — new feature added, component renamed, AEC features selected.

Load skills: pr-conventions + pr-todo

---

## Steps

1. Read `spec/plugin-spec.json` — confirm it exists
   If not: "No plugin-spec.json found. Run /rest-gen-spec first."

2. Scan the project folder (flat layout — `Components/`, `JSON Builders/`, `Components/Presets/`,
   `Utilities/`, `Icons/`, `[PluginName].Tests/` at the plugin root, no `src/`) to find which
   files already exist

3. Generate the phased todo.md — mark existing files [x]

4. Present to user for review

5. Write `spec/todo.md`

6. Update `session.json`: last_completed_step = "todo.md"

7. Prompt: "Shall I start building todo build Phase 1 (Auth)?" — todo.md's build phases are its
   own numbering, distinct from the 15 pipeline phases.
   Only begin coding after explicit approval.
