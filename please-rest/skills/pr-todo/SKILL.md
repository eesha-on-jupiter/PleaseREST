---
name: pr-todo
description: Produce spec/todo.md from plugin-spec.json for Grasshopper REST API plugins
---

# Skill: TODO list

Read `spec/plugin-spec.json` and produce `spec/todo.md` — a phased, tagged task list.
Mark items [x] for files that already exist in the project. Present for user approval.
Do not begin coding until the user explicitly approves.

---

## Build phases (todo.md numbering — distinct from the 15 pipeline phases)

todo.md has its **own** PHASE 1–10 numbering for the build checklist. It is not the pipeline's
Phase 1–15. When either is referred to outside this file, qualify it: "todo build Phase 2" vs
"pipeline Phase 2". Build Phases 1–7 are worked by pipeline Phases 9–12; build Phases 8–10 (tagged
`[SHIP]`) are pipeline Phases 13–15 and run only after Gate 6.

```
PHASE 1 — AUTH
[ ] [PluginName]Client.cs          [CODE] auth headers, base HTTP setup, NewRequest() helper
[ ] [Plugin]Auth.cs                [CODE] Token input → Status + Response output
[ ] [Plugin]Info.cs                [CODE] GH_AssemblyInfo + GH_AssemblyPriority
[ ] ButtonComponent.cs             [CODE] base class — copy verbatim, namespace only
[ ] PluginUtilities.cs             [CODE] TabName + subcategory constants
[ ] Auth icon                      [ASSET] generate_icon → add_to_resources
[ ] Verify: authenticate and get a valid response from the API

PHASE 2 — SIMPLE UNITS
[for each JSON builder + HTTP component pair from plugin-spec.json]
[ ] [Resource]Builders.cs          [CODE] [which methods]
[ ] [Resource]Json.cs              [CODE] [inputs] → [Resource] JSON output
[ ] [HTTPComponent].cs             [CODE] [inputs including JSON] → Status + Response
[ ] [Component] icon               [ASSET] generate_icon → add_to_resources
[ ] Verify: each unit returns valid JSON and pushes successfully to the platform

PHASE 3 — AGGREGATOR
[for each aggregator component from plugin-spec.json]
[ ] [Aggregator].cs                [CODE] wires JSON units to HTTP call
[ ] [Aggregator] icon              [ASSET] generate_icon → add_to_resources
[ ] Verify: full object pushed and visible on platform

PHASE 4 — LEVEL 2 AGGREGATOR
[if platform has higher-order structures — otherwise: SKIPPED]
[ ] [Level2Aggregator].cs          [CODE] aggregates across multiple resources
[ ] Verify: complex object pushed successfully

PHASE 5 — CUSTOM / AEC FEATURES
[for each AEC feature selected in Phase 4 of the pipeline]
[ ] [FeatureComponent].cs          [CODE] [description]
[ ] Verify: feature works end-to-end in Rhino

PHASE 6 — PRESETS
[for each GH_ValueList from plugin-spec.json]
[ ] [Name]Preset.cs                [CODE] [what values it provides]
[ ] Preset icon                    [ASSET] generate_icon → add_to_resources
[ ] Verify: presets compose cleanly with existing components

PHASE 7 — TESTS
[ ] [PluginName].Tests/BuilderTests.cs       [TEST] one test per builder method — expected JSON shape (pure logic, net8.0)
[ ] [PluginName].Tests/BulkAssemblyTests.cs  [TEST] only if the plugin has aggregators — schema/values → assembled payload
[ ] dotnet build                   [CODE] all green
[ ] dotnet test                    [CODE] all green
[for each demo workflow — 3-5 derived from plugin-spec.json: connection, create, read, bulk]
[ ] demos/[name].gh                [MCP]  build canvas once via Grasshopper MCP bridge (place by GUID, wire, save)
[ ] Live MCP smoke test            [MCP]  load .gha, solve each demo, auto-fix on failure, flag human only if no fix
[ ] Verify: all demos pass and demos/ is populated (or degrade gracefully to manual)

PHASE 8 — DOCS                     (pipeline Phase 13 — after Gate 6)
[ ] docs/index.md                  [SHIP] plugin overview + install
[ ] docs/quickstart.md             [SHIP]
[ ] docs/authentication.md         [SHIP]
[ ] docs/components/[sub]/[name].md [SHIP] one per component
[ ] docs/examples/[demo].md        [SHIP] one per demo workflow
[ ] docs/changelog.md              [SHIP] starts at 1.0.0

PHASE 9 — GITHUB                   (pipeline Phase 14)
[ ] README.md                      [SHIP] may link to docs/
[ ] CLAUDE.md                      [SHIP]
[ ] LICENSE                        [SHIP]
[ ] .gitignore                     [SHIP]

PHASE 10 — PACKAGE                 (pipeline Phase 15)
[ ] dotnet build -c Release × 3    [SHIP] net48 / net7.0-windows / net7.0
[ ] yak build × 3                  [SHIP]
[ ] .github/workflows/publish.yml  [SHIP]
[ ] Verify: .yak files in dist/

[HUMAN GATE 6] Rhino manual test — demos pre-built & pre-checked; open demos/ and confirm live in GH
[HUMAN GATE 7] Cross-platform test — install .yak on Rh7 Win / Rh8 Win / Rh8 Mac
```

---

## Tags

- `[CODE]`   — source file to write or edit (build Phases 1–7; what `/rest-build-all-components` iterates)
- `[TEST]`   — test file to write (builder tests only — never one per component)
- `[ASSET]`  — icon to generate (no code file). Rendered in pipeline Phase 11 (or as
               `/rest-build-all-components` finishes each group); a component marked `"custom": true`
               in icons.json is marked [x] by hand and never rendered
- `[SHIP]`   — docs / GitHub / package step (build Phases 8–10 = pipeline Phases 13–15). Never run
               by `/rest-build-all-components` — only after Gate 6
- `[MCP]`    — driven through the Grasshopper MCP bridge (build/solve a `.gh` canvas live in Rhino)
- `[MANUAL]` — requires human action

---

## Mark existing files [x]

Before writing todo.md, scan the project folder. The layout is **flat** (pr-file-structure):
project files sit at the plugin root, there is no `src/`.
- If `Components/[Subcategory]/[file].cs`, `Components/Presets/[file].cs`, `JSON Builders/[file].cs`
  or `Utilities/[file].cs` exists → mark that item [x]
- If `Icons/[prefix]_[Component].png` exists → mark the ASSET item [x]
- If `[PluginName].Tests/BuilderTests.cs` (or `BulkAssemblyTests.cs`) exists → mark that TEST item [x]
- If `docs/…`, `README.md`, `dist/*.yak` etc. exist → mark the matching `[SHIP]` item [x]
Scanning the wrong path marks nothing done, and `/rest-build-all-components` then rebuilds — and
overwrites — every existing file.

---

## Rules

- Follow phase order exactly — never reorder to accommodate convenience
- Every phase ends with a Verify step
- Human gates are printed as standalone lines, not checkboxes
- Only begin coding after the user explicitly types approval
