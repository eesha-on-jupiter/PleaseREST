---
description: "Build every unbuilt component from spec/todo.md in phase order, applying the correct skill per component type."
---

# /rest-build-all-components

Build all unbuilt components from spec/todo.md in phase order.
Applies the correct skill per component type. Marks [x] in todo.md as each completes.

---

## Steps

1. Read `spec/todo.md` — find all `[ ]` items tagged `[CODE]` in the **build phases** (todo
   build Phases 1–7). Items tagged `[SHIP]` (todo build Phases 8–10: docs, GitHub, package) are
   **out of scope** for this command — they run in pipeline Phases 13–15, after Gate 6. Stop
   before the first `[SHIP]` item.

2. Confirm with user: "Ready to build [n] components. Starting from [first unbuilt item]. Continue?"

3. For each unchecked [CODE] item, in phase order:

   a. Determine type:
      - `.cs` file in `Utilities/` ending in `Client.cs` → pr-conventions + pr-client
      - `.cs` file in `Utilities/` = `ButtonComponent.cs` → pr-conventions + pr-button
      - `.cs` file in `Utilities/` = `PluginUtilities.cs` → pr-conventions + pr-utilities
      - `.cs` file in `JSON Builders/` → pr-conventions + pr-builders
      - `.cs` file in `Components/Presets/` → pr-conventions + pr-preset
      - `.cs` file where component type = "button" in plugin-spec.json → pr-conventions + pr-button
      - All other `.cs` files in `Components/` → pr-conventions + pr-component

   b. Look up the component's call shape in `spec/call-library-validated.json` — the entry must
      be `VALIDATED` (same rule as `/rest-build-component` step 3; never fall back to the
      unvalidated `call-library.json`)

   c. Write the file

   d. Mark `[x]` in todo.md immediately

   e. Write `last_completed_step` and `next_step` to session.json immediately after each file

   f. Print: `Restling — building [FileName]... ✓`

4. After each build-phase group completes: render that group's `[ASSET]` icon items via MCP
   pr-icon-generator (`generate_icon` → `add_to_resources`, `config_path` = the plugin's
   `icons.json`) and mark them `[x]`. Pipeline Phase 11 then only renders whatever is still
   unrendered (and the 16×16 plugin icon) — it is a catch-up, not a second full render.

5. After all [CODE] items are built: run `dotnet build`
   - If errors: fix and rerun (see pr-build)

6. Print:
   ```
   Restling complete. [n] components built.
   Run /rest-status to see the full completion state.
   ```

---

## Rules

- Never skip ahead — follow phase order in todo.md exactly
- Never build a component before its builder file (builder files come first in todo build Phase 2 —
  todo.md's own numbering, not pipeline Phase 2)
- Only `[CODE]` and `[ASSET]` items — never `[SHIP]` items (those belong to pipeline Phases 13–15)
- If session.json has a `last_completed_step`: start from `next_step`, not from the beginning
- If a component file already exists (marked [x]): skip it without overwriting
