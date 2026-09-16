# PleaseREST — Claude Plugin Specification

---

## 0. What This Plugin Is

**PleaseREST** is a Claude Code plugin.

You install it once. From that point, any Claude Code session can run `/rest-new-plugin`, point it at a REST API, and PleaseREST handles the full pipeline — from API discovery through to a published `.gha` on Food4Rhino.

The plugin ships as a collection of skills, agents, MCPs, and commands. These are the actual files that live inside the plugin package. They encode the process of building a Grasshopper REST API plugin so that process no longer needs to be done manually.

**What the plugin contains:**
- 11 slash commands — the interface the user types
- 25 skills — the encoded knowledge: C# patterns, GH conventions, file templates, run-findings logging
- 3 agents — reasoning for situations skills can't handle
- 3 MCPs — dedicated Python processes for systematic crawling, HTTP testing, and icon generation
- 1 generated `settings.local.json` — pre-approves all pipeline commands at intake so nothing interrupts mid-run

**What the plugin produces when run:**
- A compiled, tested, icon-complete Grasshopper plugin (`.gha`)
- Published to Food4Rhino and GitHub
- With documentation, CI pipeline, and a `CLAUDE.md` so any future Claude Code session on the generated plugin has full context

**Plugin name:** `PleaseREST`
**Active state verb:** `Restling` — used in all progress output and status messages
**Tagline:** *Politely turns any REST API into a Grasshopper plugin — so you can take that much needed rest*
**Install command:** `/plugin install please-rest`
**Entry point:** `/rest-new-plugin`
**GitHub repo:** `please-rest`
**Author:** Eesha Jain
**Icon prefix for generated plugins:** derived from plugin name (e.g. `AC` for AcmeConnect)

---

## 0.1 Design Philosophy

Building a Grasshopper plugin that wraps a REST API is a repeatable process. Every plugin follows the same shape: map the API, spec the components, validate the calls, scaffold the code, generate icons, test, package, publish. The work is not hard — it is long, manual, and full of the same decisions made over and over.

PleaseREST encodes that process. The goal is not to remove thinking. It is to concentrate thinking where it actually matters: the spec, the AEC feature decisions, and the human test. Everything else runs automatically.

**The measure of success:**
Not "Claude wrote the code." It is "the engineer spent their time planning, reviewing, and testing — not doing mechanical work."

A process that took two weeks should take one day. Most of that day is reviewing output and approving gates — not building.

---

## 0.2 The Restling Verb

`Restling` is the active state verb for PleaseREST. Any time the plugin is doing async work, the output uses this word — not "working" or "processing."

| Context | Output |
|---|---|
| Fetching API docs | `Restling through [Platform] docs...` |
| Extracting call shapes | `Restling through [n] endpoints...` |
| Firing HTTP tests | `Restling with [Platform] API...` |
| Batch component build | `Restling — building [ComponentName]...` |
| Icon generation | `Restling up icons...` |
| Packaging | `Restling complete. 3 targets packaged.` |
| Any failure | `Restling failed — [specific reason]` |

Appears in: all MCP terminal output, skill progress messages, and CI pipeline logs.

---

## 0.3 Session Persistence

PleaseREST is designed to work across multiple coding sessions. A plugin build may span days or weeks — the pipeline should never need to restart from scratch because a session ended.

**How it works:**

Every phase writes to a `session.json` file in the generated plugin's `spec/` folder. This file is the plugin's memory. At the start of any new session, Claude Code reads it before doing anything else. The `/rest-resume-plugin` command is the entry point for returning sessions.

**`session.json` schema:**

```json
{
  "plugin_name": "AcmeConnect",
  "platform": "Miro",
  "docs_url": "https://developers.miro.com/reference",
  "token_env_var": "PLEASE_REST_TOKEN",
  "findings_path": "dogfood/Miro-run-01.md",
  "started": "2026-06-01T09:00:00",
  "last_active": "2026-06-03T14:32:00",
  "current_phase": 10,
  "current_phase_name": "Batch Component Build",
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
  }
}
```

**Write rules:**
- Every skill writes to `session.json` at the end of its phase
- Every MCP writes to `session.json` after completing its run
- Every human gate records which gate was passed and when
- If a session ends mid-phase, `last_completed_step` records the last file written so the next session resumes from that exact point — no work is repeated
- `decisions` is append-only — never overwrite, only add

**Multiple active plugins:**
PleaseREST maintains a global index at `~/.please-rest/sessions.json` listing all active session files across all projects. `/rest-resume-plugin` without arguments reads this index.

```json
{
  "sessions": [
    {
      "plugin_name": "AcmeConnect",
      "path": "/path/to/AcmeConnect/spec/session.json",
      "current_phase": 10,
      "last_active": "2026-06-03T14:32:00"
    },
    {
      "plugin_name": "NotionConnect",
      "path": "/path/to/NotionConnect/spec/session.json",
      "current_phase": 6,
      "last_active": "2026-05-28T10:15:00"
    }
  ]
}
```

---

## 1. Plugin File Structure

This is what lives inside the PleaseREST plugin package. The repo also contains a `tests/` folder at the root (Section 12) — this is development infrastructure for PleaseREST itself, not part of the installed plugin.

> **Layout rule (Claude Code plugin contract):** the manifest is the ONLY file inside
> `.claude-plugin/`. The `commands/`, `skills/`, `agents/`, and `hooks/` directories MUST sit at
> the plugin ROOT — NOT nested under a `.claude/` folder. Nesting them under `.claude/`, or placing
> `plugin.json` at the root, makes the plugin load with 0 skills / 0 MCP servers and no error from
> `/reload-plugins`. Validate the layout with `claude plugin validate ./please-rest` (see §2).

```
please-rest/
│
├── .claude-plugin/
│   └── plugin.json              ← manifest ONLY lives here
│
├── CLAUDE.md
│
├── commands/                    ← at plugin ROOT (auto-discovered)
│   ├── rest-new-plugin.md
│   ├── rest-resume-plugin.md
│   ├── rest-gen-spec.md
│   ├── rest-gen-todo.md
│   ├── rest-extract-api.md
│   ├── rest-test-api.md
│   ├── rest-build-component.md
│   ├── rest-build-all-components.md
│   ├── rest-add-feature.md
│   ├── rest-status.md
│   └── rest-package.md
│
├── skills/                      ← at plugin ROOT (auto-discovered)
│   ├── pr-conventions/SKILL.md
│   ├── pr-component/SKILL.md
│   ├── pr-button/SKILL.md
│   ├── pr-client/SKILL.md
│   ├── pr-builders/SKILL.md
│   ├── pr-bulk-data/SKILL.md
│   ├── pr-assembly/SKILL.md
│   ├── pr-preset/SKILL.md
│   ├── pr-utilities/SKILL.md
│   ├── pr-file-structure/SKILL.md
│   ├── pr-vs-project/SKILL.md
│   ├── pr-icons/SKILL.md
│   ├── pr-spec/SKILL.md
│   ├── pr-todo/SKILL.md
│   ├── pr-unit-tests/SKILL.md
│   ├── pr-build/SKILL.md
│   ├── pr-gh-package/SKILL.md
│   ├── pr-yak-package/SKILL.md
│   ├── pr-ci-template/SKILL.md
│   ├── pr-session/SKILL.md
│   ├── pr-permissions/SKILL.md
│   ├── pr-docs/SKILL.md
│   └── pr-dogfood/SKILL.md
│
├── agents/                      ← at plugin ROOT (auto-discovered)
│   ├── pr-api-scout.md
│   └── pr-aec-advisor.md
│
└── mcps/
    ├── pr-api-extractor/
    │   ├── server.py
    │   └── requirements.txt
    ├── pr-api-tester/
    │   ├── server.py
    │   └── requirements.txt
    └── pr-icon-generator/
        ├── server.py
        ├── icon_config.json
        └── requirements.txt
```

**Skill, command, and agent files are auto-discovered from these root folders** — do NOT list them
in `plugin.json` (see §2). Each skill is `skills/<folder>/SKILL.md`; the **folder name** is what the
skill is invoked by, and the SKILL.md frontmatter needs `name` + `description`. Each agent and command
`.md` should carry YAML frontmatter (`description`) so it loads with metadata.

---

## 2. Plugin Manifest

`.claude-plugin/plugin.json` — declares the plugin's identity and its MCP servers. It does **NOT**
list skills, agents, or commands — those are auto-discovered from the root `skills/`, `agents/`, and
`commands/` folders (§1). Listing them here is a schema error that makes Claude Code reject the whole
manifest (load shows 0 skills / 0 MCP servers, with no error from `/reload-plugins`).

**Manifest schema rules (enforced by `claude plugin validate`):**
- `author` must be an **object** (`{ "name", "email" }`) — a bare string fails validation
- use `displayName`, not `display_name`
- do **not** include `skills`, `agents`, `commands` arrays — auto-discovered, and the validator reads
  their entries as file paths → "Path not found"
- do **not** include a `permissions` block — not a valid manifest field; it is ignored. Pipeline
  permissions live in the generated `settings.local.json` instead (§11)
- `mcpServers` may live inline here OR in a separate `.mcp.json` at the plugin root — use
  `${CLAUDE_PLUGIN_ROOT}` for paths

```json
{
  "name": "please-rest",
  "displayName": "PleaseREST",
  "version": "1.0.0",
  "description": "Politely turns any REST API into a Grasshopper plugin — so you can take that much needed rest. Automates the repeatable parts: API mapping, call validation, codegen, icons, tests, and Food4Rhino publish. You plan, review, and test. PleaseREST does the rest.",
  "author": {
    "name": "Eesha Jain",
    "email": "eesha.jain08@gmail.com"
  },
  "mcpServers": {
    "pr-api-extractor": {
      "command": "python",
      "args": ["${CLAUDE_PLUGIN_ROOT}/mcps/pr-api-extractor/server.py"]
    },
    "pr-api-tester": {
      "command": "python",
      "args": ["${CLAUDE_PLUGIN_ROOT}/mcps/pr-api-tester/server.py"]
    },
    "pr-icon-generator": {
      "command": "python",
      "args": ["${CLAUDE_PLUGIN_ROOT}/mcps/pr-icon-generator/server.py"]
    }
  }
}
```

**Always validate the manifest before a run** — this catches both layout (§1) and schema errors that
`/reload-plugins` reports silently as zeros:

```
claude plugin validate ./please-rest
```

**Versioning:** `version` here and `please-rest/CHANGELOG.md` are how `/rest-resume-plugin` and
`/rest-add-feature` detect that an in-progress plugin build predates a PleaseREST logic change
(`pr-session`'s "Version check on resume" compares a session's stamped `please_rest_version`
against this field). Any change to a skill, agent, command, or MCP that would change what an
already-completed phase produces must bump this version and add a `CHANGELOG.md` entry naming the
affected phase(s) — a change that doesn't affect phase output doesn't need either.

---

## 3. Commands

The 11 commands are the interface the user types. Each one maps to a skill, an MCP, or a sequence of both.

| Command | Maps to | What it does |
|---|---|---|
| `/rest-new-plugin` | `new-plugin` skill → full pipeline | Intake, discovery, extraction, spec, build |
| `/rest-resume-plugin` | `pr-session` skill | Reads session.json, prints where things are, picks up from last step |
| `/rest-gen-spec` | `pr-spec` skill | Regenerates plugin-spec.json from feasibility.json |
| `/rest-gen-todo` | `pr-todo` skill | Regenerates todo.md from plugin-spec.json |
| `/rest-extract-api` | `pr-api-extractor` MCP | Runs extraction manually — use if docs changed |
| `/rest-test-api` | `pr-api-tester` MCP | Runs HTTP validation manually |
| `/rest-build-component` | `component` / `button` / `builders` / `pr-preset` skill | Scaffolds one component by ID |
| `/rest-build-all-components` | Claude Code iterating todo.md with correct skill per type | Builds all unbuilt components |
| `/rest-add-feature` | `pr-spec` skill → `pr-todo` skill | Feedback loop — updates spec, adds TODO items |
| `/rest-status` | `pr-session` (+ todo.md) | Renders the pipeline progress tree on demand — phases, gates, where you are, what's next; YOUR MOVE if at a gate; component build detail from todo.md in Phase 10+ |
| `/rest-package` | `pr-yak-package` skill | Builds .yak for all 3 targets |

**`/rest-resume-plugin` behaviour in detail:**

Single active session — prints immediately:
```
PleaseREST — resuming AcmeConnect
────────────────────────────────────────
Phase:     10 of 15 — Batch Component Build
Last done: CreateBoardComponent.cs
Next:      DeleteBoardComponent.cs

Completed phases:  1 2 3 4 5 6 7 8 9
Gates passed:      1 2 3 4 5
Gates pending:     6 (Rhino manual test)  7 (cross-platform)

Decisions on record:
  AEC features:    Auth Manager, Batch Processor
  Skipped:         DELETE /boards/{id} — flagged for v2
  Partial calls:   update_item — scaffolded with note
  Manual fixes:    create_connector — wrapper object missing from docs

Restling from where we left off. Continue? (yes / show todo first)
────────────────────────────────────────
```

Multiple active sessions — asks which to resume:
```
PleaseREST — active sessions
────────────────────────────────────────
  1. AcmeConnect      Phase 10 — last active 2 days ago
  2. NotionConnect    Phase 6  — last active 1 week ago

Which would you like to resume?
────────────────────────────────────────
```

No session found — falls through to `/rest-new-plugin` flow:
```
No active session found in this directory.
Run /rest-new-plugin to start a new plugin build.
```

---

## 4. Skills — What Each One Covers

Skills are markdown files that encode a known-correct pattern. Claude Code reads them and follows them. No reasoning — pure template execution.

**Rule for all skills:** `pr-conventions` is always loaded alongside any other skill. It is never loaded alone.

Each skill lives in its own folder: `.claude/skills/[skill-name]/SKILL.md`

---

### `pr-conventions`
The foundation. Loaded with every other skill.
- File naming: `[Name].cs` for components, `[Entity]Builders.cs` for builders, `[Name]Preset.cs` for presets
- Namespace rules: root namespace matches plugin name exactly; only Presets gets a sub-namespace
- Naming table: classes PascalCase, methods PascalCase, params camelCase, locals camelCase
- Resource name prefix: `[XX]_` + PascalCase (e.g. `AC_ItemIcon`)
- Nickname rules: 1–3 chars always
- I/O naming: `Token`/`T`, `Status`/`S`, `Response`/`R`, `[Thing] ID`, `[Thing] JSON`
- I/O chain rule: output name must exactly match the input name of whatever consumes it
- Wiring contract: a link is valid only when name + nickname + data-access all line up; structured
  data travels as Text-carried JSON, never a custom GH type
- Component tiers: unit → aggregator → write (create/update/append/delete) → recursive → preset
- Modularity rule: all write verbs for a resource share one payload contract, so the user wires one
  producer into Create / Update / Append interchangeably without rebuilding
- Comment style: single-line `//` only, sentence case, no period, describe what not how
- JSON rules: always Newtonsoft JObject, never string interpolation, Formatting.None always, null-coalesce all strings

---

### `pr-component`
Pattern for every standard `GH_Component` file.
- File structure: using statements, one-line class comment, constructor with base() call, RegisterInputParams, RegisterOutputParams, SolveInstance, Icon property, ComponentGuid property
- SolveInstance 5-step order: declare variables → DA.GetData calls → guard clauses → logic → DA.SetData calls. Never mix declaration and logic.
- Description always ends with a period
- Input params always supply a default value as the last argument
- Icon and Guid always last in the file, in that order
- No regions inside component files
- One using per line, no global usings

---

### `pr-button`
For any component that creates, updates, or deletes a resource.
- Part 1: `ButtonComponent.cs` base class — copy verbatim into every plugin, only namespace changes
- Part 2: subclass pattern — only override ButtonLabel, RegisterInputParams, RegisterOutputParams, SolveInstance
- `if (!IsTriggered) return;` is always the first line of SolveInstance
- Button colors defined once in ButtonAttributes.Render — never per subclass
- SolveInstance still follows the same 5-step order

---

### `pr-client`
For the single `[PluginName]Client.cs` file in Utilities/.
- Built FROM `call-library-validated.json` (method/URL/headers/body per `endpoint_id`) — never
  hand-written from docs; if the validated file is missing, run Phases 6–7 first (dogfood: MCPs were
  bypassed this way)
- PATCH on net48 uses `new HttpMethod("PATCH")` — `HttpMethod.Patch` does not exist on .NET 4.8
  (dogfood F5); the net48 target needs the `System.Net.Http` reference (handled by `pr-vs-project`, F3)
- This is the only file that touches HttpClient — components never call HttpClient directly
- Region order: Constructor and setup → resource method groups → Private helpers
- Constructor: initialises HttpClient with BaseAddress, sets up token
- `NewRequest()` helper: sets auth header + any additional required headers for this API (e.g. API version headers)
- Every public method returns `Tuple<bool, string, string>` — (success, result, error)
- `Ok()` and `Fail()` are private static helpers — never inline the tuple
- All public methods are async Task — no sync wrappers
- Guard clauses before any HTTP call
- Rate limit delays inside pagination loops only: `await Task.Delay(350)`

---

### `pr-builders`
For static `[Resource]Builders.cs` files that produce JSON.
- No GH_Component inheritance — pure static classes
- Region order: Private helpers → resource groups → Parse helpers
- Private helpers always first
- Category tag comment above every public method: `// item`, `// connector` etc — lowercase, no punctuation
- One builder file per resource family — never mix unrelated resources
- Builder methods called by JSON components only — never by HTTP components
- Private helpers shared across files go in SharedBuilders.cs
- Formatting.None always — never pretty-print in production methods
- Null-coalesce all string params

---

### `pr-icons`
For icon design. Runs **after the spec is final, before component build** — authors `icons.json` (one
entry per component + `defaults`, `subcategories`, `plugin_icon`), lets the **user specify every icon**,
then renders via the pr-icon-generator MCP. Replaces the old scaffold-time `icon_config.json` generation.
- Source website is **Iconify** — every icon is a `prefix:name` ID
- Per icon, all optional and composable: a foreground glyph + a background `shape` (solid or gradient)
  + a background `icon` (a glyph behind, on top of the shape) — use any combination, or omit both for
  no background; foreground tinted to any colour or a gradient (silhouette+tint, so white/light render)
- Style resolves defaults < subcategory < component; gradients supported on bg and fg
- Component icons **24×24**, plugin/ribbon category icon **16×16** (`generate_plugin_icon`)

---

### `pr-bulk-data`
For Grasshopper data-tree handling on bulk/mass data upload. Load with `pr-component` / `pr-builders`
when building unit, aggregator, or bulk-write components.
- Two-axis model: field axis → `list` (schema, one per column), record axis → `tree` (one branch per
  record, `GH_Path(i)`)
- Unit emits values as a `tree`; aggregator zips columns × rows into a `list` of payloads, handling
  **ragged trees** (min + per-record warning, never throw)
- Bulk-write loops the list: rate-limit between calls, batch parallel sub-steps, results are
  index-aligned `list`s the same length as the input
- Index-alignment contract: unit branch `i` → aggregator `list[i]` → write `output[i]`; order and
  count preserved end to end so every result traces back to its source record

---

### `pr-assembly`
For the `[PluginName]Info.cs` file in the root namespace.
- Two classes in one file: `[Plugin]Info : GH_AssemblyInfo` and `[Plugin]CategoryIcon : GH_AssemblyPriority`
- Icon on GH_AssemblyInfo is always null — logo set via GH_AssemblyPriority
- AssemblyVersion always starts at "1.0.0"
- AuthorName / AuthorContact come from `session.json.author` (the user running the build,
  captured at Phase 1 intake) — never a hardcoded person. See `pr-conventions` + `pr-assembly`.
- Both classes in root namespace, no other classes in this file

---

### `pr-preset`
For `GH_ValueList` components that provide API string values.
- Namespace is always `[PluginName].Presets` — never root
- Items is always private static readonly Dictionary
- ListItems.Clear() always called before populating
- Display labels human-readable, values raw API strings
- Align dictionary values so quote characters form a clean column
- No RegisterInputParams, RegisterOutputParams, or SolveInstance

---

### `pr-utilities`
For `PluginUtilities.cs` in Utilities/.
- `GetValues<T>()` — generic helper returning `Enum.GetValues(typeof(T)).Cast<T>()`
- `TabName` — `internal static readonly string` for the plugin's ribbon tab name
- Subcategory name constants — `internal static readonly string Category[XX][Name]`, one per subcategory
- Two-letter sort key controls toolbar order: `AA` = Auth (always first), `ZY` = Presets, `ZZ` = Utilities (always last); intermediate categories use `AB`, `AC`, etc.
- String value carries the numeric prefix the user sees in Rhino: `"1. Auth"`, `"2. Boards"`, etc.
- Use `internal static readonly string` — never `public const string`

---

### `pr-file-structure`
For scaffolding a new generated plugin from scratch — a **flat** layout (no `src/` wrapper), the same
shape as a project from the Grasshopper template.
- Creates the folder tree and non-code files only; the buildable VS project is generated by
  `pr-vs-project` (run together in Phase 8)
- Flat layout: `Components/[Subcategory]/`, `Components/Presets/`, `JSON Builders/`, `Utilities/`,
  `Icons/`, `Properties/` at the root; plus `spec/`, `demos/`, `docs/`, and the `[Plugin].Tests/` project
- **No `assets/` or `dist/`** — packaging creates its own output dirs (`docs/` is kept; filled by
  `pr-docs` in Phase 13)
- Generates `icon_config.json` at the plugin root: derives `plugin_prefix` from plugin name (first
  2–3 uppercase letters), relative paths `Icons` and `Properties/Resources.resx`, a subcategory entry
  per subcategory in plugin-spec.json
- Edge case: plugin name has spaces or special chars — sanitise to PascalCase, warn user
- Edge case: folder already exists — do not overwrite existing .cs files, only create missing folders

---

### `pr-vs-project`
For generating the buildable Visual Studio Grasshopper project and verifying it builds for Rhino 7
and Rhino 8.
- Prefers the official template (`dotnet new install Rhino.Templates` → `dotnet new grasshopper`),
  then renames; falls back to writing the files directly from the template embedded in the skill
- Produces `[Plugin].csproj` (multi-target: Rh7 `net48`, Rh8 Win `net7.0-windows`, Rh8 Mac `net7.0`,
  `.gha` output, `EnableDynamicLoading`), `[Plugin].sln` (main + Tests project), `[Plugin].csproj.user`,
  `Properties/launchSettings.json` (Rhino 7 / Rhino 8 netcore+netfx run profiles), `[Plugin]Info.cs`,
  and `Properties/Resources.resx` + `Resources.Designer.cs`
- Main `.csproj` carries the `Compile Remove` for `[Plugin].Tests\**` so its root-level recursive
  glob does not compile the test project
- **Build check is the gate:** `dotnet build` each target; Rh7 (`net48`) and Rh8 Win
  (`net7.0-windows`) must compile clean, Mac (`net7.0`) compile-checks on Windows via
  `EnableWindowsTargeting`. Does not proceed to component codegen on a project that does not build

---

### `pr-spec`
For producing `plugin-spec.json` from `feasibility.json`.
- Reads feasibility.json and proposes full plugin structure
- Subcategory hard rules: JSON and HTTP always separate; Auth subcategory contains only the auth component; Utilities contains only Client, PluginUtilities, ButtonComponent; Presets contains only GH_ValueList components; every HTTP subcategory with a request body has a corresponding JSON subcategory (resource model: one-to-one; content-type model: many JSON tabs → one HTTP write tab)
- Content-type model: when the API uses a single batchUpdate endpoint with a heterogeneous `requests[]` array, `pr-spec` divides JSON builders by content type (Slides · Shapes · Text · Tables · Media · Style · Compose) instead of by resource — navigable by intent, not by endpoint. HTTP tabs come before JSON tabs; Compose follows the last content-type tab; Geometry tab added only when the API has spatial data
- Component naming rules: class names end in Component, filenames never do; GET = Get/GetAll/Find, write = Create/Update/Delete; JSON component = [Resource]Json; style = [Resource]Style; preset = [Name]Preset
- I/O naming from conventions skill enforced here — traces the full chain before writing
- Records `role` per component, `access` per I/O, a `relations` graph, and `payload_contracts`
- Write model: decides per API how create/update/append share a body; keeps one payload contract per
  resource so write verbs stay interchangeable, flags where the API cannot share a shape
- Spec validator (I/O line-up check) runs inline before presenting: no duplicate GUIDs/nicknames, all
  types map to valid GH params, all endpoints exist in feasibility.json, every consumed input has a
  producer matching on name + nickname + type + access, and every write verb honours its resource's
  shared payload contract
- Writes plugin-spec.json
- Edge cases: endpoint with no clear GH mapping → flag, suggest skip for v1; resource with 30+ fields → propose splitting required/optional; non-standard types → string passthrough with description note

---

### `pr-todo`
For producing `spec/todo.md` from `plugin-spec.json`.
- Phased structure: Phase 1 Auth → Phase 2 Simple Units → Phase 3 Aggregator → Phase 4 Level 2 Aggregator → Phase 5 Custom/AEC → Phase 6 Presets
- Every item tagged: [CODE], [TEST], [ASSET], [MANUAL]
- Marks existing files [x] based on what already exists in the project folder
- Each phase ends with a Verify step
- Only begins coding after explicit user approval

---

### `pr-unit-tests`
For a concern-based xUnit test project — **never one file per component**. Tests target the pure
builder logic that actually runs headless; the file count is fixed regardless of component count.
- `BuilderTests.cs` (primary, always) — `[Theory]` over `builders[]`, cross-checked against
  `call-library-validated.json` body shapes: each `[Resource]Builders` method emits the validated JSON
  shape. Pure functions, no API, no GH.
- `BulkAssemblyTests.cs` — **only when the plugin has `aggregator` components.** Tests the pure
  builder assembly method (`AssembleRecords`): record count == payload count, ragged input uses min +
  warn (no throw), empty values skipped, index alignment preserved. Plain logic — no API, no GH.
- Test project targets **plain net8.0** and **compiles builder sources in** — never a
  `ProjectReference` to the windows-only `.gha`, never a `-windows` target (dogfood F6/F7: the
  windows testhost won't start and the `.gha` can't be referenced)
- **Component call-shape / error-handling tests are deferred** — they need an injectable client +
  headless GH, neither of which the current code shape supports (dogfood F6)
- **Dropped:** input-validation, output-type, and per-component tests. I/O wiring is validated once, statically, by
  the `pr-spec` I/O line-up check at Phase 3 — the test project trusts a passed spec and does not
  re-check it. Output param types are guaranteed by `RegisterOutputParams` (compile-time).
- Lives in a separate `[Plugin].Tests/` project at the repo root (sibling to the flat plugin
  project, added to the `.sln`). The root `.csproj` must `Compile Remove` the test folder so its
  recursive glob does not compile the tests.

---

### `pr-build`
For running `dotnet build` and `dotnet test` and handling failures.
- Sequence: dotnet build → read output → surface compile errors with file + line → fix → rerun
- Then: dotnet test → read output → surface failing tests with test name + assertion → fix → rerun
- On failure: identify the component, apply the relevant skill to fix, rerun
- Does not proceed until all green
- Prints Restling progress messages throughout

---

### `pr-rhino-test`
For Phase 12 Step B — building the demo `.gh` files and live-testing every component in Rhino,
after unit tests are green and **before** HUMAN GATE 6. Driven through an external **Grasshopper MCP
bridge** — the **official McNeel `mcneel/RhinoMCP`** ("Rhino-MCP-Platform" in the Rhino 8/9 Package
Manager). Confirm at runtime that it resolves PleaseREST's custom components against the live GH
registry; community fallback if not (`cordyceps`/`SandMartin`). Not shipped by PleaseREST — the user
wires it in once.
- **Job A — demo files:** derive a small demo set (3–5) from `plugin-spec.json` — connection check,
  one create, one read, one bulk (only if aggregators exist). Place components **by GUID**, wire from
  `call-library-validated.json` sample inputs, save each canvas once to `demos/[name].gh`. These same
  files are what `pr-docs` writes `docs/examples/*.md` from in Phase 13 — built once, used twice.
- **Job B — live smoke test:** load the built `.gha`, place + solve each demo, check it loads /
  instantiates / solves without exception / returns non-empty correct-typed outputs / `Status` ok.
- **Auto-fix loop:** on failure, fix what is fixable (CODE via the relevant build skill + rebuild
  the `.gha`; WIRING by editing the canvas) and retest; **flag the human only when there is no fix**
  (live API outage, platform limit, judgment call). Failures logged via `pr-dogfood` (TOOL vs RUN).
- **Gate:** advance to GATE 6 only when all demos pass (or remaining failures are human-flagged
  no-fix) and `demos/` is populated.
- **Wiring (one-time, official Rhino MCP):** in Rhino 8/9 run `PackageManager`, install
  "Rhino-MCP-Platform", then run `MCPConnect` — it starts a local HTTP/SSE server and prints a
  registration prompt to paste into Claude Code (no fixed-port `claude mcp add`); verify *connected*
  via `/mcp` before testing; auth token read from `PLEASE_REST_TOKEN`.
- **Graceful degradation:** no bridge / custom components unresolvable from the live registry → skip
  automation, print the wiring steps, leave `demos/` for manual creation, fall back to the
  fully-manual Gate 6. Never hard-fails.

---

### `pr-gh-package`
For generating the four files that ship with the generated plugin to GitHub.

**README.md covers:**
- Plugin name, one-sentence description, what API it wraps
- Installation: Food4Rhino link, Yak command
- Quick start: minimum steps to get a connection working
- Component table: one row per component, inputs, outputs, description
- Requirements: Rhino version, Windows/Mac, auth setup
- License

**CLAUDE.md (plugin-specific) covers:**
- Platform name, base URL, auth method, API version, extra required headers
- Platform-specific context (coordinate system, canvas model, data model quirks)
- API resource hierarchy as mapped in feasibility.json
- Plugin structure: subcategory overview, full component list with inputs/outputs
- JSON builders: which file covers which resources, which components use each builder
- Key design rules specific to this plugin
- How to add a new component: which files to touch, which skills to load, which builder to extend
- Known limitations and skipped endpoints with reason
- Skills to load for each file type
- Current build state synced from session.json: phase, last completed step, next step
- Todo list: current todo.md embedded — updated by pr-session every phase and gate
- See Section 4.1 for the full CLAUDE.md header block format

**LICENSE:** MIT by default
**.gitignore:** bin/, obj/, .vs/, *.user, dist/, *.DS_Store

---

### `pr-yak-package`
For packaging the generated plugin as `.yak` files.
- Runs `dotnet build -c Release` for each target
- Runs `yak build` in the output directory
- Validates manifest: name, version, author, description, icon, keywords, requires (Rhino version)
- Outputs three .yak files to `/dist/`: [plugin]-win-rh7.yak, [plugin]-win-rh8.yak, [plugin]-mac-rh8.yak

---

### `pr-ci-template`
For generating `.github/workflows/publish.yml`.
- Trigger: push of a version tag (`v*.*.*`)
- Steps: checkout → dotnet restore → dotnet build → dotnet test → yak build all targets → upload to Food4Rhino or attach to GitHub release
- Includes version bump action from tag
- Prints Restling status at each step

---

### `pr-session`
For reading, writing, and resuming session state across multiple coding sessions. Also owns the
**progress tree** rendered at every human gate and on resume (15 phases / 7 gates, driven by
`session.json` — see §8).

**On `/rest-resume-plugin`:**
- Checks current directory for `spec/session.json`
- If not found: checks `~/.please-rest/sessions.json` for all active sessions
- If one session: prints summary and asks to continue
- If multiple sessions: lists them with phase + last active date, asks which to resume
- If none: prompts user to run `/rest-new-plugin`
- After resume: loads the correct `session.json`, reads `next_step`, and continues from exactly that point

**On every phase completion:**
- Updates `current_phase` and `current_phase_name`
- Appends completed phase to `completed_phases`
- Updates `last_active` timestamp
- Records `last_completed_step` and `next_step`
- Appends any new decisions to the `decisions` block
- Updates the global `~/.please-rest/sessions.json` index
- Triggers `pr-gh-package` to regenerate CLAUDE.md with current build state and todo list

**Write timing:**
- Skills: write at end of phase
- MCPs: write after tool run completes
- Human gates: write immediately when gate is passed, recording gate number and timestamp
- Mid-phase interruption: write `last_completed_step` after every individual file written — not just at phase end

**Edge cases:**
- `session.json` is corrupted or missing mid-build: reconstruct from `todo.md` completion state and existing files in the project folder, warn user
- User runs `/rest-new-plugin` in a directory that already has a `session.json`: warn that an active session exists, ask whether to resume or start fresh
- Two sessions have the same plugin name: disambiguate by path in the sessions index

---


## 4.1 Generated Plugin CLAUDE.md — Header Block

Every CLAUDE.md produced by `pr-gh-package` for a generated plugin opens with this header block. This tells any new Claude Code session exactly what tools are available and where the build is — before reading anything else. It is regenerated by `pr-session` at the end of every phase and every human gate so it is always current.

```markdown
# [PluginName] — Grasshopper Plugin for [Platform] REST API
> Built with PleaseREST

## PleaseREST Context
This plugin was built using the PleaseREST pipeline.
Load the skills below before writing any code.

## Skills
Always load with every file:
- pr-conventions

Load when the file type matches:
- pr-component          — any GH_Component file
- pr-button             — any create / update / delete component
- pr-builders           — any [Resource]Builders.cs file
- pr-client             — [PluginName]Client.cs
- pr-assembly           — [PluginName]Info.cs
- pr-preset             — any GH_ValueList component
- pr-utilities          — PluginUtilities.cs

## Agents
- pr-api-scout             — call if an API endpoint is failing and docs need re-checking
- pr-aec-advisor           — call if adding a new AEC feature
- pr-spec-critic           — call via /rest-add-feature to check new components for unnecessary complexity

## MCPs
- pr-api-extractor         — re-run if API docs changed: /rest-extract-api
- pr-api-tester            — re-run to validate calls: /rest-test-api
- pr-icon-generator              — generate icons for new components

## Commands
- /rest-new-plugin                  start a new plugin build
- /rest-resume-plugin               resume this build from last session
- /rest-gen-spec               regenerate plugin-spec.json
- /rest-gen-todo                 regenerate todo.md
- /rest-extract-api                 re-run API extraction
- /rest-test-api                    re-run API testing
- /rest-build-component <id>        scaffold one component
- /rest-build-all-components        build all unbuilt components
- /rest-add-feature <desc>          add a new feature
- /rest-status                      show current build state
- /rest-package                     package for all targets

## Current Build State
Phase:     [current_phase] of 15 — [current_phase_name]
Last done: [last_completed_step]
Next:      [next_step]
Updated:   [last_active]

## Todo List
> Full phased task list — updated every session
[current todo.md embedded here]
```

---


---

### `pr-permissions`
For generating `settings.local.json` at the start of every new plugin build.
- Runs during Phase 1 intake — before anything else
- Generates the full permissions file for this specific pipeline
- Shows a readable summary of what is being pre-approved before the user confirms
- Pre-approves: dotnet build/test/restore/pack, yak build/push, python, pip, git add/commit/push/tag, powershell, mkdir/cp/mv/rm/echo/cat, all 4 MCP tools
- If a custom AEC feature adds a new command: appends it to settings.local.json and asks user to re-approve before continuing
- Never auto-approves destructive commands without explicit user review
- Writes file to the root of the generated plugin folder — not inside PleaseREST

---


---

### `pr-docs`
For generating the `docs/` folder of clean markdown documentation for the generated plugin.
- Runs in Phase 13 (Docs); `pr-gh-package` runs separately in Phase 14 (GitHub)
- Source: `plugin-spec.json` + `call-library-validated.json`
- Format: plain markdown, no frontmatter, no platform assumptions — drop into Notion, GitBook, Mintlify, Obsidian, Docusaurus or anything else
- One file per component — never combines multiple components in one page
- One index file per subcategory — lists all components in that group with one-line descriptions

**Per component page covers:**
- Display name and one-sentence description
- Inputs table: name, type, required, default, description
- Outputs table: name, type, description
- API endpoint it calls: method, URL template
- Example response shape (from call-library-validated.json)
- Usage notes from spec (edge cases, format requirements)
- Link to related components (e.g. JSON builder that feeds into this HTTP component)

**Other pages:**
- `index.md` — plugin name, what API it wraps, what version, install instructions, component count by subcategory
- `quickstart.md` — minimum steps: get token, drop auth component, verify connection, first create operation
- `authentication.md` — how to get a token for this specific API, where to plug it into GH, what the status output means
- `examples/` — one page per demo workflow, written from the demo .gh files built in Phase 12 (Step B, `pr-rhino-test`)
- `changelog.md` — starts at 1.0.0, one entry per release

**Edge cases:**
- Component has a PARTIAL validated call: note it on the component page with a warning that response shape may vary
- Component was skipped (MISSING endpoint): generate a stub page noting it is planned for a future version
- Subcategory has only one component: still gets its own folder, no collapsing

---

### `pr-dogfood`
Maintains a running **findings log** for the current pipeline run so breakages are captured as they
happen, not from memory. Triggered by `pr-session` at every phase boundary, and directly on any
failure or human gate.
- Writes to the path in `session.json` → `findings_path` (default `dogfood/[plugin]-run-01.md`;
  during PleaseREST self-dogfooding, point it at the PleaseREST repo's `dogfood/` file)
- Append-only; numbers findings sequentially and never renumbers
- Each finding tagged **TOOL** (a PleaseREST defect — the dogfood signal that drives plugin fixes)
  or **RUN** (an issue with the current target API/build)
- Trigger points: end of every phase; the moment any command exits non-zero or an MCP returns
  FAILED / AMBIGUOUS / MISSING / PARTIAL; a build/test error; `claude plugin validate` errors;
  every human gate; any time the user says output is wrong
- **Scope limits (must be stated, not hidden):** cannot catch load-time failures that stop skills
  from loading at all (the F1/F2 class — covered by the Phase-0 `claude plugin validate` check), and
  cannot catch subtle wrongness in output that compiles but is semantically wrong (covered by human
  gate review). It is a complete record of *observed failures*, not of correctness.

## 5. Agents — What Each One Does

Agents only run when a situation requires reasoning that a skill cannot handle.

---

### `pr-api-scout`
**When:** After `pr-api-tester` MCP returns FAILED entries.
**What it does:**
- Reads the FAILED entries and their full error responses from call-library-validated.json
- Re-fetches the specific docs pages for those endpoints only
- Reasons about what was extracted incorrectly: wrong field name, missing wrapper object, wrong URL pattern, undocumented required header
- Patches call-library.json for those entries only
- Triggers pr-api-tester to rerun on patched entries only (uses `retest_entries` tool)
- If still failing after one pass: escalates to human with a clear explanation of what was tried and what the remaining ambiguity is
- Does not touch VALIDATED entries

---

### `pr-aec-advisor`
**When:** After plugin-spec.json is confirmed, before todo.md is generated.
**What it does:**
- Reads plugin-spec.json — specifically resource types, field names, data shapes, hierarchy
- Cross-references against the AEC Feature Library (Section 6)
- Produces specific recommendations with rationale tied to this API's actual structure
- Only recommends a feature if the API has the fields to support it naturally
- Does not produce a generic list — every recommendation references a specific field or resource from this API

**Output format:**
```
FEATURE: In-GH Documentation Writer
RATIONALE: This API has a rich-text content field on [Resource].
           The same pattern from NotionConnect maps directly here.
ADDS: DocumentPlugin component, LogSession component
EFFORT: Low
RECOMMEND: Yes

FEATURE: BIM Data Bridge
RATIONALE: API resources have no geometry or property-map fields.
RECOMMEND: No — not a natural fit
```

Human selects which features to include. Selected features are appended to plugin-spec.json before todo.md is generated.

---

### `pr-spec-critic`
**When:** Right after `pr-spec` drafts `plugin-spec.json` + `spec/workflows.json` in Phase 3 — before Gate 2, not after (that's `pr-aec-advisor`'s job on the *confirmed* spec).
**What it does:**
- Reads the drafted spec against `spec/workflows.json` for unnecessary complexity: components that
  don't trace to any workflow, components that should have merged into one parametric component,
  chains of primitives a workflow always uses together that should get a consolidated component,
  Dual Style Pattern tree variants nobody's workflow actually needs, and pure-indirection wrappers
  with no real parametric capability
- Every finding is grounded in a specific workflow (or the stated absence of one) — never a generic
  "this seems complex" note
- Findings are suggestions only — folded into what's shown at Gate 2 as "Simplification notes"; the
  user accepts, rejects, or amends each one before the spec is written
- Never re-litigates the subcategory model or the modularity/payload-contract rules — those are
  `pr-spec`'s job; this agent only looks at component count and granularity against the workflow list
- No findings is a complete answer — does not pad with speculative simplifications

---

## 6. MCPs — Full Specs

MCPs are dedicated Python processes running outside Claude's context window.

> **pr-api-extractor and pr-api-tester are mandatory, not optional.** Phases 6–7 must run and produce
> `call-library.json` + `call-library-validated.json` before Phase 8/9. The client (`pr-client`) and
> JSON builders (`pr-builders`) are built **from** the validated output — never hand-written from the
> docs. A dogfood run silently bypassed both MCPs (hand-wrote the client), leaving the call shapes
> unvalidated; the Phase 9 precondition and the `pr-client` rule now prevent that.

---

### `pr-icon-generator` ✅ built

**What it does:** Renders layered icons from Iconify glyphs — a background layer (none / solid /
gradient / an Iconify glyph) plus a foreground glyph tinted to any colour (incl. white or a gradient,
via a silhouette+tint pipeline so light glyphs no longer vanish). Renders at 4× then downscales with
LANCZOS. Injects PNGs into Resources.resx + Resources.Designer.cs. All driven by the plugin's
`icons.json`, which the **`pr-icons`** skill authors after the spec is final and the user specifies.

**Tools:**
- `generate_icon(component_name, config_path?, subcategory?, iconify_id?)` — renders one component
  icon (default **24×24**) using the component's entry in `icons.json` (style resolves
  defaults < subcategory < component); `subcategory`/`iconify_id` are optional overrides / legacy.
- `generate_plugin_icon(config_path?)` — renders the **16×16** plugin/ribbon category icon from the
  `plugin_icon` block; saved as `<prefix>_<PluginName>Logo.png` (wired by `pr-assembly`).
- `add_to_resources(component_name, config_path?)` — injects a generated PNG into Resources.resx +
  Designer.cs (idempotent). Use the component name or `<PluginName>Logo`.

**`config_path`:** path to the plugin's `icons.json`. Relative paths inside it resolve from the config
file's own directory. Cached per resolved path. Omit to fall back to `icon_config.json` next to
`server.py` (the legacy flat config still renders via the solid fallback).

**Background = optional, composable layers** (mix freely): an optional `shape` (filled solid or with a
gradient) and an optional `icon` (an Iconify glyph behind the foreground, on top of the shape if both
are present — always rendered as a **solid silhouette**, interior holes of outline icons filled in;
`color` defaults `#FFFFFF`, `opacity` defaults `0.45` so lightness is controlled independently of
colour). Omit both → no background, glyph alone. Foreground is also optional and accepts a hex or
a gradient. **Every layer aligns independently** — shape, bg icon, and foreground glyph each take
their own optional `align`/`glyph`-style `{ fit, anchor }`, defaulting to the shape-aware placement
described below when omitted.

**Glyph placement is shape-aware:** container shapes (square/circle/etc.) hold the glyph inside at
~80% centred; accent shapes (`star`, `triangle`, `triangle_down`) place it larger and offset to a
side so it overflows the silhouette; a background icon with no shape holds the glyph at 85% centred
over it; no background at all → 100% centred (glyph alone fills the canvas). Overridable per icon
via an optional `glyph: { fit, anchor }`.

**`icons.json`** is authored by `pr-icons` (full schema there), one entry per component plus
`defaults`, `subcategories`, and a `plugin_icon` block. Component icons are 24×24, the plugin icon is
16×16.

**Background shapes (16):** `circle`, `square`, `rounded_square` (default), `squircle`, `pill`,
`diamond`, `triangle`, `triangle_down`, `hexagon`, `rounded_hexagon`, `octagon`, `star`,
`parallelogram`, `parallelogram_left`, `trapezoid`, `trapezoid_down`

**Icon design quality standard:**
The goal is icons that look better than what any engineer or designer would make manually.
- Iconify glyph must communicate the component's function unambiguously at 24px
- Background shape is consistent within a category type across the plugin
- Color palette is chosen per-plugin — not inherited, not default
- Palette feels considered and modern — reference the API platform's visual identity, then adapt it for a technical GH plugin context (dense, precise, high contrast)
- When in doubt: high contrast + clean shape + bold glyph wins

**Icon glyph selection rules:**
- GET operations: outline icons — suggests reading, not writing
- POST/CREATE: filled icons with a plus or add indicator
- DELETE: filled icons with a minus or remove indicator
- JSON builder components: geometric/structural icons — suggests data shape
- Preset components: list or menu icons — suggests selection
- Auth component: lock or key icon
- Utilities: tool or wrench icon

---

### `pr-api-extractor` ✅ built

**What it does:** Crawls API docs or parses an OpenAPI spec or a Google API Discovery doc, extracts the full request shape for every endpoint in plugin-spec.json, writes call-library.json.

**Language:** Python — httpx, BeautifulSoup4, PyYAML

**Tools:**

`extract_from_openapi(spec_url, component_list, output_path?)`
- Fetches raw JSON or YAML from spec_url (URL or local file path)
- **Auto-detects format:** OpenAPI (`paths` key) vs Google API Discovery (`discoveryVersion` / `resources→methods` — used by Slides, Sheets, Docs, Drive, Gmail, Calendar)
- Resolves all `$ref` pointers before extracting — circular refs detected via immutable visited-set pattern
- Merges path-level and operation-level parameters; detects pagination keys (cursor, page, offset, etc.)
- For each path/method in component_list, extracts full call shape; fills `base_url` and `auth_in` on each entry
- Handles YAML: parses with PyYAML, processes as dict

`extract_from_docs(docs_url, endpoint_path, method, component_name, endpoint_id, output_path?)`
- Fetches one specific endpoint's docs page
- Parses with BeautifulSoup — targets: parameter tables, JSON code blocks
- Handles common docs platforms: Readme.io, GitBook, Stoplight, Redoc, raw HTML
- Marks MISSING if page returns 404 or is JavaScript-only (< 200 chars visible text)
- Returns one call-library.json entry; appends to existing file if output_path provided

`write_call_library(entries, output_path)`
- Writes call-library.json
- Prints extraction summary: extracted / ambiguous / missing counts

**Output format per entry:**
```json
{
  "endpoint_id": "get_board",
  "component": "GetBoardComponent",
  "method": "GET",
  "url_template": "/v2/boards/{board_id}",
  "path_params": [{ "name": "board_id", "type": "string", "required": true }],
  "query_params": [],
  "headers": { "Authorization": "Bearer {token}" },
  "body_schema": null,
  "response_schema": { "id": "string", "name": "string" },
  "example_request": {},
  "example_response": {},
  "notes": "",
  "status": "EXTRACTED"
}
```

**Status values:** EXTRACTED / AMBIGUOUS / MISSING

**Edge cases:**
- YAML spec: parse with PyYAML
- Spec uses $ref pointers: resolve all before processing
- oneOf / anyOf in body schema: extract all variants, mark AMBIGUOUS
- Response schema undocumented: leave null, do not invent
- Docs require JavaScript to render: mark MISSING, do not attempt headless browser
- Docs page 404: mark MISSING, continue
- Paginated endpoint: add pagination key to entry
- Conflicting examples: extract both, mark AMBIGUOUS

---

### `pr-api-tester` ✅ built

**What it does:** Fires real HTTP calls against every entry in call-library.json, records pass/fail, writes call-library-validated.json.

**Language:** Python — httpx async

**Tools:**

`test_endpoint(entry, token, seed_ids?, base_url?)`
- Fires one HTTP request using the entry's call shape
- Joins `base_url` to any relative `url_template` (entry's own `base_url` field wins over the arg)
- seed_ids: dict of resource IDs for endpoints requiring a pre-existing record (e.g. `{"board_id": "abc123"}`)
- Returns: `{status_code, response_body, latency_ms, validated, tag, error}`
- tag values: VALIDATED / PARTIAL / FAILED

`run_all_tests(call_library_path, output_path, token?, skip_destructive?, base_url?)`
- Iterates all EXTRACTED entries; builds seed_ids incrementally from POST response IDs
- Halts entire run on 401 — writes partial results, prompts token refresh
- Writes call-library-validated.json via `_write_validated()` which merges tested results over originals preserving order

`retest_entries(entry_ids, call_library_path, output_path, token?, base_url?)`
- Reruns tests for specific entry IDs only
- Used by pr-api-scout after patching failed entries; merges results into existing validated file

**Per-entry result tags:** VALIDATED / PARTIAL (shape mismatch or rate limit exhausted) / FAILED

**Auth:** token from `PLEASE_REST_TOKEN` env var, or passed as argument. Token placement defaults to `Authorization: Bearer`; set `auth_in: "query:<param>"` per entry for APIs that require the token as a query parameter (e.g. `"auth_in": "query:access_token"`). Returns clear error if neither token nor env var is set — never silently proceeds without auth.

**Safe test defaults:**
- GET: use example IDs from extraction, or ask user for a real ID
- POST: use minimal valid payload, create at most one test record
- DELETE: skipped by default (skip_destructive=True)
- PATCH: uses record created by POST test if available

**Edge cases:**
- 429 rate limit: exponential backoff, max 3 retries, then mark PARTIAL not FAILED
- 401 auth failure: pause entire run, report to user, do not mark all FAILED
- Timeout: retry once after 5s, then mark FAILED
- POST creates a record: store returned ID for subsequent GET/PATCH/DELETE tests
- Empty 200 response: mark PARTIAL, note in entry
- Token expired mid-test: pause, ask user to refresh, resume from last position

---

## 7. Pipeline — The Process the Plugin Runs

This is what happens when a user runs `/rest-new-plugin`. Every phase, every primitive, every gate.

```
/rest-new-plugin
  │
  ▼
PHASE 1 — INTAKE (skills: new-plugin + pr-permissions + pr-dogfood)
  Ask: plugin name, docs URL, token ready?
  Write: spec/intake.json; generate settings.local.json
  Set session.json findings_path = dogfood/[PluginName]-run-01.md and create that findings file
    (new file per plugin; -run-02/-03 if one already exists)
  │
  ▼
PHASE 2 — API DISCOVERY (Claude Code + new-plugin skill)
  Fetch docs URL, map all endpoints, auth method, hierarchy
  Write: spec/feasibility.json
  │
  ▼ [HUMAN GATE 1] Confirm API overview
  │
  ▼
PHASE 3 — PLUGIN SPEC (skill: spec)
  Propose subcategories, component list, I/O, builders
  Validate inline
  Write: spec/plugin-spec.json
  │
  ▼ [HUMAN GATE 2] Confirm plugin structure
  │
  ▼
PHASE 4 — AEC FEATURES (agent: pr-aec-advisor)
  Read plugin-spec.json, cross-reference AEC feature library
  Recommend specific features with rationale
  │
  ▼ [HUMAN GATE 3] Select AEC features
  │
  ▼
PHASE 5 — TODO LIST (skill: todo)
  Generate phased task list from final spec
  Write: spec/todo.md
  │
  ▼
PHASE 6 — API EXTRACTION (MCP: pr-api-extractor)   ← MANDATORY, do not skip
  Detect: OpenAPI spec or docs-only
  Extract full call shape per endpoint
  Write: spec/call-library.json
  Print: extraction summary
  (Never replace 6–7 by hand-writing the client from docs — client/components are built FROM
   call-library-validated.json. A past run silently skipped these; the rule below prevents it.)
  │
  ▼
PHASE 7 — API TESTING (MCP: pr-api-tester)
  Fire real HTTP calls for all EXTRACTED entries
  Write: spec/call-library-validated.json
    │
    ├── FAILED entries → agent: pr-api-scout
    │     Re-fetch docs for failed endpoints
    │     Patch call-library.json
    │     Rerun pr-api-tester for patched entries only
    │
    └── Still FAILED → [HUMAN GATE 4] Manual resolution
  │
  ▼
PHASE 8 — SCAFFOLD (skills: filestructure + vsproject + icons authoring)
  filestructure: create flat folder tree (no src/, no assets/dist); leave Icons/ empty
  vsproject: generate .csproj/.sln/.user/launchSettings/Info.cs/Resources from GH template
             rename namespaces, GUIDs, assembly info
             BUILD CHECK — dotnet build for Rhino 7 (net48) + Rhino 8 (net7.0-windows/net7.0)
  icons (pr-icons): author icons.json from the final spec, USER SPECIFIES every icon
             (fg glyph + background: none/solid/gradient/icon) — rendered later in Phase 11
  │
  ▼
PHASE 9 — AUTH COMPONENT (skills: client + component + assembly)
  Precondition: spec/call-library-validated.json MUST exist (Phases 6–7 ran). If missing, go back —
    do not hand-write the client from docs.
  Build: [Plugin]Client.cs, [Plugin]AuthComponent.cs, [Plugin]Info.cs
  Build the client FROM call-library-validated.json (method/URL/headers/body per endpoint_id)
  │
  ▼ [HUMAN GATE 5] Test auth component in Rhino
  │
  ▼
PHASE 10 — BATCH BUILD (Claude Code + correct skill per type)
  Iterate every [CODE] item in todo.md
  Apply: component / button / builders / preset skill per type
  Always load conventions alongside type skill
  Follow phase order — never skip ahead
  Mark each item [x] in todo.md
  │
  ▼
PHASE 11 — ICONS (skill: pr-icons → MCP: pr-icon-generator, from icons.json)
  Each component (24×24): generate_icon → add_to_resources
  Plugin/ribbon icon (16×16): generate_plugin_icon → add_to_resources
  Runs after each phase group or in batch after Phase 10
  │
  ▼
PHASE 12 — TESTS (skills: test-scaffolder → build-runner → pr-rhino-test)
  Step A — Unit tests:
    Scaffold concern-based xUnit project (CallShapeTests + ErrorHandlingTests, data-driven)
      + BulkAssemblyTests when the plugin has aggregator components (tree→list upload logic)
    dotnet build → dotnet test → fix failures → rerun until all green
  Step B — Example files + live MCP test (pr-rhino-test, via a Grasshopper MCP bridge):
    Build the demo .gh files into demos/ — each canvas built ONCE (reused as the test fixture
      AND as the example file pr-docs writes from in Phase 13)
    Load the built .gha, place each component by GUID, wire inputs, solve, read outputs
    Auto-check: loads / instantiates / solves w/o exception / non-empty correct-typed outputs
    AUTO-FIX LOOP: on failure, fix (code via build skill + rebuild, or canvas) → retest;
      flag the human ONLY when there is no fix (live API outage, judgment call)
    Proceed only when all demos pass and demos/ is populated
    Degrades gracefully to fully-manual when no bridge is configured
  │
  ▼ [HUMAN GATE 6] Rhino manual test — demos pre-built & pre-checked; user opens & confirms
  │
  ▼ EXTEND LOOP (after every Gate 6 pass — repeats until user declines)
  │   Ask: "Add new components or workflows before docs + packaging?"
  │   If yes → run the full build loop for those items only (spec → extract → test →
  │     build → icons → unit tests → live re-test):
  │       • [HUMAN GATE — ICONS] show rendered icons, "Are these icons OK?" — wait for approval
  │       • [HUMAN GATE 6] re-confirm the new items live in Grasshopper
  │     then ask again. If no → continue to Phase 13.   (same loop as /rest-add-feature)
  │
  ▼
PHASE 13 — DOCS (skill: pr-docs)
  Generate: docs/ folder — clean markdown, one file per component
    ├── docs/index.md               plugin overview, what API it wraps, install
    ├── docs/quickstart.md          minimum steps to get a connection working
    ├── docs/authentication.md      how to get a token, where to plug it in
    ├── docs/components/
    │   └── [subcategory]/
    │       └── [component].md      inputs table, outputs table, endpoint, example response, notes
    ├── docs/examples/              one .md per demo workflow
    └── docs/changelog.md           version history — starts at 1.0.0
  Source: plugin-spec.json + call-library-validated.json
  Format: plain markdown, no frontmatter, no platform assumptions
  User can drop docs/ into Notion, GitBook, Mintlify, Obsidian, Docusaurus — anything
  │
  ▼
PHASE 14 — GITHUB (skill: pr-gh-package)
  Generate: README.md, CLAUDE.md, LICENSE, .gitignore  (README may link to the docs/ folder)
  │
  ▼
PHASE 15 — PACKAGE + SHIP (skills: yak-packager + ci-template)
  Build .yak for all 3 targets → /dist/
  Generate GitHub Actions CI workflow
  │
  ▼ [HUMAN GATE 7] Cross-platform manual test
  │
  ▼
DONE — plugin live on Food4Rhino and GitHub

  ↑
  └── FEEDBACK LOOP: /rest-add-feature  (same loop the post-Gate-6 EXTEND step runs)
        Re-enters at Phase 3 (spec update only)
        Runs Phases 6–12 for new components only — incl. icon approval gate + live Gate 6 re-test
```

---

## 8. Human Gates

| # | After phase | What human does | Signal to continue |
|---|---|---|---|
| 1 | API discovery | Reviews endpoint map, corrects if needed | Approval or correction |
| 2 | Plugin spec | Reviews component list, subcategories, I/O | Approval or change request |
| 3 | AEC features | Selects features, optionally describes custom | Feature selection |
| 4 | API testing | Reviews remaining FAILED entries, decides per entry | Fix / skip / flag for later |
| 5 | Auth component | Tests in Rhino, checks connection status output | "Works" or specific error |
| 6 | Rhino manual test | Opens the pre-built, pre-checked demo `.gh` files and confirms outputs live in GH | "All good" or bug report |
| 7 | Cross-platform | Installs .yak on Rh7 Win / Rh8 Win / Rh8 Mac | "Passes" or platform bug |

**Extend loop gates (repeatable, after every Gate 6 pass).** When the user opts to add new
components/workflows after Gate 6, each round adds two recurring checkpoints before continuing:
an **Icons** gate ("Are these icons OK?" — approve or describe changes) and a **re-run of Gate 6**
for the new items. These are not numbered fixed gates; they repeat per added item-set until the
user declines further additions. Same loop as `/rest-add-feature`.

**Progress tree at every gate:** before each gate question, the pipeline renders a 15-phase /
7-gate progress tree (owned by `pr-session`, driven by `session.json`) showing completed phases (`✓`),
the current phase (`►`), the gate the user is at (`◆ Gate n ◀ YOU ARE HERE`), passed gates (`✓`),
upcoming phases/gates, a `Now:` / `Next:` footer, **and a YOUR MOVE block stating exactly what the
user must do at this gate and how to respond** (the "What human does" / "Signal to continue" columns
above, per gate). The user always sees where they are, what's being worked on, the current gate, what
to do, and what's coming. Also rendered on `/rest-resume-plugin`.

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

---

## 9. AEC Feature Library

The pr-aec-advisor agent uses this as a reference. It only recommends a feature if the API has the fields to support it.

| Feature | Needs in API | What it adds |
|---|---|---|
| In-GH Documentation Writer | Rich-text or document content fields | Components writing session logs or usage notes back into the platform |
| BIM Data Bridge | Property/attribute dictionaries on resources | Components mapping API fields to/from standard BIM fields |
| Geometry Serializer | API accepts or returns coordinate or geometry data | Components converting Rhino geometry to/from the API's spatial format |
| Batch Processor | List operations or pagination | Wraps single-item components in list-processing with progress output |
| Auth Manager | Any token-based auth | Persistent token storage — user sets once, all components inherit |
| Version Watcher | Modified/updated timestamp on resources | Polls for changes, triggers GH solution refresh |
| Error Reporter | Structured error responses | Collects errors across a session, outputs a readable report |

---

## 10. Generated Plugin Workspace Structure

What PleaseREST produces when it runs. This is not the plugin itself — it is the output.

Flat layout — same shape as a project from the Grasshopper template (no `src/` wrapper).

```
[GeneratedPluginName]/
├── spec/
│   ├── intake.json
│   ├── feasibility.json
│   ├── plugin-spec.json
│   ├── call-library.json
│   ├── call-library-validated.json
│   ├── todo.md
│   └── session.json                  ← written and updated throughout the pipeline
├── Components/
│   ├── [Subcategory]/[ComponentName].cs
│   └── Presets/[Name]Preset.cs
├── JSON Builders/[Resource]Builders.cs
├── Utilities/
│   ├── [PluginName]Client.cs
│   ├── PluginUtilities.cs
│   └── ButtonComponent.cs
├── Icons/
├── Properties/
│   ├── Resources.resx
│   ├── Resources.Designer.cs
│   └── launchSettings.json
├── [PluginName]Info.cs
├── [PluginName].csproj                ← multi-target Rh7/Rh8 Win/Rh8 Mac
├── [PluginName].csproj.user
├── [PluginName].sln
├── icon_config.json
├── demos/
├── dogfood/
│   └── [PluginName]-run-01.md          ← findings log (pr-dogfood), created at Phase 1 intake
├── docs/
│   ├── index.md
│   ├── quickstart.md
│   ├── authentication.md
│   ├── components/
│   ├── examples/
│   └── changelog.md
├── [PluginName].Tests/                ← plain net8.0; compiles builder sources in (no .gha ref)
│   ├── [PluginName].Tests.csproj
│   ├── BuilderTests.cs
│   └── BulkAssemblyTests.cs           ← only if the plugin has aggregator components
├── .github/workflows/publish.yml
├── README.md
├── LICENSE
├── CLAUDE.md
└── .gitignore
```

---

## 11. Permissions — `settings.local.json`

PleaseREST generates a `settings.local.json` file during Phase 1 intake — before anything else runs. This file pre-approves every command the pipeline needs so Claude Code never stops mid-run to ask for permission.

---

### When it's generated

Phase 1, immediately after intake questions are answered. Written to the root of the generated plugin folder. Claude Code picks it up automatically.

The user sees:

```
PleaseREST — generating settings.local.json
────────────────────────────────────────
Pre-approving all pipeline commands for this build.

dotnet new (Grasshopper template) / build / test / restore / pack
yak build / push
powershell (icon injection into Resources.resx)
git add / commit / push / tag
python (MCP servers)
All 3 MCP tools (pr-api-extractor, pr-api-tester, pr-icon-generator)

Review the full list in settings.local.json before continuing.
Confirm to start pipeline? (yes / review first)
────────────────────────────────────────
```

One approval at intake. Nothing interrupts after that.

---

### Generated `settings.local.json`

```json
{
  "permissions": {
    "allow": [

      "Bash(dotnet new:*)",
      "Bash(dotnet restore:*)",
      "Bash(dotnet build:*)",
      "Bash(dotnet test:*)",
      "Bash(dotnet run:*)",
      "Bash(dotnet pack:*)",
      "Bash(dotnet publish:*)",
      "Bash(dotnet clean:*)",
      "Bash(dotnet format:*)",
      "Bash(dotnet add:*)",
      "Bash(dotnet remove:*)",
      "Bash(dotnet list:*)",
      "Bash(dotnet sln:*)",
      "Bash(dotnet nuget:*)",
      "Bash(dotnet tool:*)",
      "Bash(dotnet msbuild:*)",
      "Bash(dotnet vstest:*)",
      "Bash(dotnet --info)",
      "Bash(dotnet --version)",

      "Bash(msbuild:*)",
      "Bash(nuget:*)",

      "Bash(yak:*)",

      "Bash(git:*)",
      "Bash(gh:*)",

      "Bash(python *)",
      "Bash(pip:*)",

      "Bash(powershell -NonInteractive -Command:*)",
      "Bash(powershell -Command:*)",

      "Bash(claude mcp list)",

      "Bash(mkdir:*)",
      "Bash(cp:*)",
      "Bash(mv:*)",
      "Bash(rm:*)",
      "Bash(echo:*)",
      "Bash(cat:*)",
      "Bash(ls:*)",

      "mcp__plugin_please-rest_pr-api-extractor__*",
      "mcp__plugin_please-rest_pr-api-tester__*",
      "mcp__plugin_please-rest_pr-icon-generator__generate_icon",
      "mcp__plugin_please-rest_pr-icon-generator__add_to_resources"
    ]
  }
}
```

---

### Rules

- Generated once per plugin at intake — not copied from a template, generated fresh so it only includes what this specific pipeline needs
- User reviews it before approving — it is shown in full before the pipeline starts
- It lives in the generated plugin folder, not in the PleaseREST plugin folder
- If the user adds a custom AEC feature that needs a new command, the `pr-session` skill appends it to `settings.local.json` and asks the user to re-approve before continuing
- Never auto-approve destructive commands without explicit user review — DELETE endpoints in the pr-api-tester are skipped by default for the same reason

---

## 12. Build Order

Shortest path to a working test on a real plugin.

```
Round 1 — Fix what exists                              ✅ complete
  pr-icon-generator: config_path param, dynamic prefix, path resolution

Round 2 — The two new MCPs (highest risk, test early)  ✅ complete
  pr-api-extractor MCP
  pr-api-tester MCP
  → Tested against Petstore OpenAPI spec + httpbin

Round 3 — Missing skills                               ✅ complete
  filestructure skill (includes icon_config.json generation)
  spec skill
  utilities skill

Round 4 — Ship layer skills                            ✅ complete
  test-scaffolder
  build-runner
  gh-package
  yak-packager
  ci-template
  session skill (+ global sessions index at ~/.please-rest/)

Round 5 — Agents                                       ✅ complete
  pr-api-scout agent
  pr-aec-advisor agent

Round 6 — Plugin packaging                             ✅ complete
  plugin.json manifest
  CLAUDE.md for the PleaseREST plugin itself

Round 7 — MCP test suite                               ✅ complete
  tests/ folder at repo root (outside please-rest/)
  144 pytest tests across all 3 MCPs (see Section 13)

Round 8 — Permissions + docs                           ✅ complete
  pr-permissions skill
  settings.local.json generator wired into Phase 1 intake
  pr-docs skill (docs/ folder generator, Phase 13)
```

---

---

## 13. MCP Test Suite

Tests for the three MCPs live in `tests/` at the repo root — not inside the `please-rest/` plugin folder. They are development infrastructure for PleaseREST, not part of the installed plugin.

**Location:** `[repo-root]/tests/`
**Framework:** pytest + pytest-asyncio
**Install:** `pip install -r tests/requirements.txt`
**Run:** `cd tests && pytest`

### Structure

```
tests/
├── requirements.txt              pytest, pytest-asyncio
├── conftest.py                   shared path constants (REPO_ROOT, MCP_ROOT, etc.)
│
├── pr-icon-generator/
│   ├── conftest.py               sys.path injection for server.py
│   ├── test_config.py            load_config: default path, explicit path, per-path caching,
│   │                             missing file error, subcategory key validation
│   ├── test_rendering.py         hex_to_rgb, shape_mask (12 shapes, 2× parametrized), gradient,
│   │                             fill_from_alpha, scale_alpha, make_solid (4 tests),
│   │                             resolve_placement (4), build_background + bg.icon opacity (2), _render
│   └── test_generate_icon.py     iconify_id format validation, unknown subcategory,
│                                 mocked SVG fetch (save/prefix/HTTP error),
│                                 add_to_resources error cases
│
├── pr-api-extractor/
│   ├── conftest.py               sys.path injection for server.py
│   ├── test_refs.py              resolve_refs: flat passthrough, local $ref, nested $ref,
│   │                             circular ref protection, list of refs, missing ref, primitives
│   │                             simplify_schema: None, empty, flat properties, oneOf, anyOf, array, $ref in property
│   ├── test_schema.py            extract_params: empty, path param, query param, mixed, $ref param
│   │                             blank_entry: required keys, EXTRACTED status, uppercase method, auth header
│   └── test_extract_openapi.py   inline Petstore spec (no network): EXTRACTED, query params, path params,
│                                 response schema resolved, MISSING path, MISSING method,
│                                 output file written, YAML spec, pagination note
│
└── pr-api-tester/
    ├── conftest.py               sys.path injection for server.py
    ├── test_url_builder.py       build_url: no params, single param, multiple params,
    │                             missing seed ID, extra seed IDs, integer ID, unfilled placeholder
    ├── test_tag_result.py        200/201/204 → VALIDATED, 401/403/404/500 → FAILED,
    │                             empty body → PARTIAL, schema key matching, extra keys, invalid JSON
    ├── test_write_validated.py   creates file, tested entry replaces original, untested entry retained,
    │                             order follows original, creates parent dirs, all-FAILED case
    └── test_test_endpoint.py     mocked httpx: 200 VALIDATED, 404 FAILED, 401 FAILED,
                                  429 backoff → PARTIAL, timeout → FAILED, missing path param,
                                  token substituted in headers, POST sends example body

```

### Design rules for test files

- Each MCP subfolder has its own `conftest.py` — all three MCPs ship a file named `server.py`, so each conftest loads its own under a unique `sys.modules` key (`server_icon_gen`, etc.) and re-pins it as `server` before every test. This keeps the three suites isolated in a single `pytest` run; no `__init__.py` needed
- No live network calls in any test — httpx is mocked via `unittest.mock.patch`
- `pr-icon-generator` tests that need a config write a minimal one to `tmp_path` — they do not depend on any single plugin's `icon_config.json`
- `pr-api-extractor` tests use inline spec dicts written to temp files — no external URLs
- `pr-icon-generator`'s `load_config()` re-reads `icons.json` from disk on every call (no caching), so edits made mid-session — including a "redo all/some icons" pass — are always picked up

---

*PleaseREST — v1.0.0*
*13 commands · 25 skills · 3 agents · 3 MCPs (+ 1 external Grasshopper MCP bridge) · 364 MCP tests*
*This number is `plugin.json`'s `version` exactly — there is no separate "Spec vX.Y" tag. New
entries go in `please-rest/CHANGELOG.md`, which `pr-session`'s resume-time version check reads.
The dated notes below are the pre-release development history: they were never published, their
numbering was retired at 1.0.0, and they are kept only as a record of why things are the way they
are.*
*Removed: ntfy notifier MCP, pr-notify skill, /rest-notify-setup — desktop app + Dispatch handles notifications natively*
*v1.7 — fixed plugin packaging to match Claude Code's plugin contract (found during AirtableConnect dogfood run, F1+F2): manifest moved to `.claude-plugin/plugin.json`; `commands/`, `skills/`, `agents/` moved to plugin root (out of `.claude/`); manifest schema corrected — `author` as object, `displayName` not `display_name`, removed the auto-discovered `skills`/`agents`/`commands` arrays and the invalid `permissions` block. Added `claude plugin validate` as the Phase-0 load check (§1, §2).*
*v1.8 — added the `pr-dogfood` skill: a run-findings logger wired into `pr-session` that appends to `session.json`→`findings_path` at every phase, failure, and gate. Tags findings TOOL (PleaseREST defect) vs RUN (target-API issue). Honestly scoped: it logs observed failures, not load-time failures (use `claude plugin validate`) or subtle output wrongness (use gate review).*
*v2.0 — progress tree: `pr-session` now renders a 14-phase / 7-gate progress tree (inline gate labels + a YOUR MOVE block telling the user what to do) at every human gate and on resume — completed/current/upcoming phases, passed/current/upcoming gates, Now/Next footer (§8); wired into `rest-new-plugin` before every gate; `/rest-status` renders the same tree on demand at any time. Icon overhaul: new `pr-icons` skill authors `icons.json` AFTER the spec is final and the user specifies every icon (moved out of scaffold-time `pr-file-structure`). pr-icon-generator MCP rewritten — layered rendering from independent OPTIONAL pieces (a bg shape solid/gradient, a bg Iconify glyph, a fg glyph — any combination or none), gradients on bg and fg, any foreground colour via silhouette+tint (white/light glyphs now render), 4× LANCZOS downscale. Sizes split: component icons 24×24, plugin/ribbon category icon 16×16 via new `generate_plugin_icon`. Source website is Iconify. (pr-icon-generator tests need updating to the new signatures/modes.)*
*v2.5 — removed the drop-shadow feature from pr-icon-generator entirely. It resolved independently of `background` (defaults/subcategory/component), so a `shadow` block set at the `defaults` level applied even to icons configured with no background — `make_solid`'s blur+rethreshold dilated the glyph into a solid, offset, semi-opaque blob that read as an unwanted background shape behind "icon only, no bg" renders. Removed `shadow` resolution from `resolve_style`, the shadow branch from `_render`, the `SHADOW_OFFSET`/`SHADOW_OPACITY`/`SHADOW_BLUR` constants, and the unused `offset` param from `place_glyph`. No `icons.json` in this repo used a `shadow` block, so no config migration was needed.*
*v2.1 — Phase 12 gained Step B (`pr-rhino-test`): builds the demo `.gh` files and live-tests every component in Rhino through an external Grasshopper MCP bridge, with an auto-fix loop (fix code/canvas + rebuild → retest; flag the human only when there is no fix). The demo canvases are built ONCE and reused as both the Gate-6 test fixture and the example files `pr-docs` writes from — fixing the old phantom "demo .gh files generated in Phase 5" reference (nothing built them; now built in Phase 12 Step B). GATE 6 stays a human gate but is now pre-built + pre-checked, so the user just opens `demos/` and confirms. Degrades gracefully to the fully-manual gate when no bridge is wired in. New skill `pr-rhino-test` (24 skills). (§7 pipeline, §8 gates, `pr-docs`, `pr-todo`, `rest-new-plugin`.)*
*v1.9 — flat plugin layout (matches the GH template, no `src/`; presets under `Components/`); added `pr-vs-project` (official GH template, ticks Rhino 7 net48 / Rhino 8 net7.0-windows+net7.0, build-check gate); added `pr-bulk-data` (data-tree bulk upload, assembly logic in a pure builder method); reworked component relations + modularity (one payload contract per resource → all write verbs interchangeable; `pr-spec` validates name+nickname+type+access). AirtableConnect dogfood fixes: F3 net48 `System.Net.Http` reference restored in `pr-vs-project`; F5 `new HttpMethod("PATCH")` on net48 in `pr-client`; F6/F7 tests re-pivoted to pure builder logic on plain net8.0 (builder sources compiled in, no `.gha` reference, no per-component tests); MCPs made mandatory (Phase 9 precondition + `pr-client` rule: client built FROM `call-library-validated.json`, never hand-written) after the run silently skipped pr-api-extractor/pr-api-tester.*
*v2.4 — dogfood fixes encoded; icon rendering improvements. (1) GoogleSlidesConnect dogfood: F1 content-type model now prescriptive in `pr-spec` (fixed tab layout table, naming rules, write path — no plugin name referenced); `pr-utilities` gains a "Content-type model" section with ordering rules and a concrete code example. (2) F2 (Google API Discovery adapter in `pr-api-extractor`) and F3 (`base_url` join + `auth_in` query support + seed chaining in `pr-api-tester`) already encoded in MCP code and CLAUDE.md — spec Section 6 descriptions updated to match. (3) F5 plugin icon resource name corrected: `<PluginName>Logo` (not `PluginIcon`) in `generate_plugin_icon`, `pr-assembly`, and `pr-icons` — spec description fixed. (4) F4 and F6 (preserialized resources csproj fix; `Properties.Resources.[XX]_` prefix) already fully encoded in skills — no spec change needed. (5) `pr-icon-generator` rendering: `make_solid()` helper fills interior holes of outline icons to produce solid silhouettes; background icons (`bg.icon`) now default to white (`#FFFFFF`) at 45% opacity; drop shadows also use the solid silhouette. Eight new tests (make_solid behaviour + bg.icon opacity); blur test assertion strengthened to unique-alpha-levels metric (robust to make_solid pre-binarisation). Total tests 156. Spec Section 6 background layer description updated.*
*v2.3 — icon `shadow` gains options (still optional/opt-in). The drop shadow keeps its previous behaviour — off unless a `shadow` block is set, defaulting to opacity 0.65, offset [0.07,0.07], colour = foreground — and adds two options: a `blur` field (gaussian blur radius in final px, default 0 = hard-edged) for a soft drop shadow, and an explicit `color` (any hex, e.g. `#000000`, or `"fg"` to keep the foreground colour). Added a gaussian-blur pass (Pillow `ImageFilter`); new `SHADOW_BLUR` constant. Tests extended (148 total pass: hex/`fg` colour, optional blur softening, opt-in resolution). Updated `pr-icons`, CLAUDE.md, `docs/mcps.md`.*
*v2.2 — three changes. (1) MCP permissions/loading fix: the plugin's MCP servers are plugin-scoped (`mcp__plugin_please-rest_<server>__*`), so `pr-permissions` no longer emits the bare `mcp__<server>__*` names or an `enabledMcpServers`/`enabledMcpjsonServers` list — those made Claude Code report `pr-icon-generator`/`pr-api-*` as "not loaded" (phantom `.mcp.json` servers) while the real plugin servers stayed loaded. (2) Post-Gate-6 EXTEND LOOP: after every Gate 6 pass, `rest-new-plugin` asks whether to add new components/workflows; if yes, those items run the full build loop on their own — including an Icons approval gate ("Are these icons OK?") and a re-run of Gate 6 — then it asks again until the user declines. Same loop `/rest-add-feature` runs on demand. No new fixed phases; tracked under `decisions.extend_rounds`. (3) Docs and GitHub split into separate phases: pipeline is now **15 phases / 7 gates** — Phase 13 DOCS (`pr-docs`, `docs/` folder), Phase 14 GITHUB (`pr-gh-package`, README/CLAUDE.md/LICENSE/.gitignore, may link the docs), Phase 15 PACKAGE + SHIP; Gate 7 now after 15. Updated across `rest-new-plugin`/`rest-add-feature`/`rest-status`/`rest-resume-plugin`, `pr-session` (tree + map), `pr-todo` (todo template split: DOCS / GITHUB / PACKAGE), `pr-docs`, `pr-gh-package`, `pr-dogfood`, CLAUDE.md.*
*v2.6.0 — workflow-driven plugin specs + real version tracking, both new (25 skills, 3 agents). (1)
`pr-spec` gains Step 0: propose a grounded candidate workflow list from the API before drafting any
component (never a blank prompt), then derive the spec from it — the Dual Style Pattern (a uniform
list component + a parametric tree component wherever something varies per-item, e.g. per cell/
shape/text-run), consolidating a chain a workflow always uses together into one component, and a
rule against rebuilding capability native GH already has (Gradient, Remap Numbers). New agent
`pr-spec-critic` reviews the draft for exactly this kind of missed simplification before Gate 2. (2)
`pr-icon-generator`: the foreground glyph is now trimmed to its own ink unconditionally, not only
when there's no background — previously a backgrounded icon kept Iconify's viewBox padding and
rendered visibly smaller than its target area; and `load_config()` re-reads `icons.json` from disk
on every call instead of caching it by path, so a "redo these icons" pass always sees the latest
edits. (3) **Versioning, from scratch:** `plugin.json`'s `version` had never been bumped past this
doc's own "v1.0" tag despite the real history below — this entry is the last one written here.
Going forward, `plugin.json.version` IS this number, tracked in `please-rest/CHANGELOG.md`, and
`session.json.please_rest_version` mirrors it so `/rest-resume-plugin` / `/rest-add-feature` can
alert when a build predates a change (`pr-session`'s "Version check on resume").*
