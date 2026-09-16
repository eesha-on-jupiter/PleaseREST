---
name: pr-spec
description: Propose target workflows, then produce plugin-spec.json from feasibility.json and the confirmed workflow list for Grasshopper REST API plugins
---

# Skill: Plugin spec

Read `spec/feasibility.json`, run Step 0 to propose and confirm target workflows, then produce
`spec/plugin-spec.json` — the full proposed structure of the generated plugin, derived from those
workflows rather than a raw 1:1 endpoint mapping. Validate inline before writing. Present to the
user for approval before writing.

---

## Step 0 — Propose, then confirm, target workflows

Run this **before** drafting any component. This is a **PleaseREST-proposes-first** step, not a
blank "what do you want" prompt — mirroring the discipline `pr-aec-advisor` already applies
("never produce a generic list... every item is tied to this API's actual data").

Every plugin PleaseREST has actually built independently rediscovered the same lesson mid-build:
mapping API endpoints 1:1 to components produces a plugin nobody wants to use (from a spreadsheet
plugin's build log: the user rejected the 1:1 mapping — "too many components... formatting one grid
needed 3 separate item-only components" — and asked for components designed around real parametric
Grasshopper workflows instead). Step 0 makes that the starting point instead of something
discovered the hard way partway through.

1. Read `feasibility.json`'s resources/fields and draft a written list of candidate workflows:
   concretely, how having this 3rd-party platform's data available *inside Grasshopper* could be
   genuinely more useful than using the platform's own native UI — because Grasshopper brings
   parametric/tree-based power the platform's own UI can't (e.g. "vary font size across every text
   run in a deck based on a computed value" — trivial as a tree operation, painful to do by hand
   one shape at a time). Each candidate names: the workflow, which specific API fields/resources
   it uses, and *why doing it in Grasshopper beats doing it natively* — no generic filler entries.
2. Always include the **cross-platform tabular benchmark** as one candidate: *"take a simple
   tree/list of tabular data (rows × columns, as if from an Excel sheet) and turn it into content
   in [platform]"* — every document/spreadsheet/deck plugin built with this pipeline has ended up
   reinventing it by hand under a different name (a cell-grid writer, a tree-to-table builder, a
   slides-from-layout builder), so propose it up front. Include it as a real candidate grounded in
   the platform's actual content model, or state why it doesn't fit and drop it — never a generic
   placeholder.
3. **Present this list to the plugin creator as "here's how this plugin could make your work
   easier"** and let them confirm, edit, add, or remove — they're reacting to a grounded draft,
   not filling a blank page.
4. Write `spec/workflows.json`:
   ```json
   {
     "workflows": [
       {
         "name": "Heatmap cell coloring",
         "user_goal": "Color a range of cells based on a computed value per cell",
         "data_shape": "tree of records -> parallel tree of computed style values",
         "varies_per_item": true,
         "benchmark": "tabular-to-platform"
       }
     ]
   }
   ```
   `varies_per_item: true` is the signal the Dual Style Pattern (below) uses to decide whether a
   resource needs the tree/parametric component, not just the uniform one. `benchmark:
   "tabular-to-platform"` tags a workflow as satisfying the cross-platform benchmark, which
   `pr-aec-advisor` checks for once components are drafted.

No new human gate here — the workflow list is confirmed conversationally, then feeds straight
into the structure proposal shown at the existing Gate 2 (which now approves the workflow list and
the derived structure together).

---

## Input: feasibility.json shape

```json
{
  "platform": "Acme",
  "base_url": "https://api.acme.example",
  "auth_method": "Bearer token",
  "api_version": "v2",
  "extra_headers": {},
  "resources": [
    {
      "name": "Board",
      "endpoints": [
        { "id": "get_board",    "method": "GET",    "path": "/v2/boards/{board_id}" },
        { "id": "create_board", "method": "POST",   "path": "/v2/boards" },
        { "id": "delete_board", "method": "DELETE", "path": "/v2/boards/{board_id}" }
      ]
    }
  ]
}
```

---

## Subcategory hard rules

1. JSON components and HTTP components are always in separate subcategories
2. Auth subcategory contains only the auth/connect component
3. Utilities subcategory contains only: `[Plugin]Client.cs`, `PluginUtilities.cs`, `ButtonComponent.cs`
4. Presets subcategory contains only GH_ValueList components
5. Every HTTP subcategory that sends a request body has a corresponding JSON subcategory — resource model: one-to-one pairing. Content-type model: many JSON content-type tabs feed one HTTP write tab; the separation rule still holds but the pairing is many-to-one

---

## Dividing subcategories — resource model vs content-type model

The **default** is one subcategory per REST resource (one per entry in `feasibility.resources`).

**Exception — batch-style / single-write-endpoint APIs.** When the API funnels every write through
**one endpoint that takes a heterogeneous `requests[]` array** (batchUpdate pattern — Google Slides,
Google Docs, Google Sheets all use this shape), the resource model collapses every JSON builder into
one giant tab that's hard to navigate. Detect this shape and instead divide the JSON builders by
**content type** — the object types the user is composing, not the REST resource being called. The tab
name tells the user what they're building, not how the API sends it: "I want to add a shape" → **Shapes**.

**Detection:** `feasibility.resources` has effectively one write endpoint whose body is an array of
varied request objects (a `requests[]` / `batchUpdate` shape).

**Tab layout for content-type model — fixed ordering:**

| Position | Tab | Type | Contents |
|---|---|---|---|
| 1 | Auth | http | Auth component only — always first |
| 2–n | HTTP resource tabs | http | Read endpoints grouped by accessed resource; the single write send (e.g. BatchUpdate) in one tab with its reads |
| n+1–m | Content-type tabs | json | JSON builders divided by object type — outermost container type first, innermost detail last |
| m+1 | Compose | json | Aggregator (RequestsAggregator) + any deck/template assembly AEC components |
| optional | Geometry | util | Spatial/unit bridge — only when the API has geometric or coordinate data; this tab type is an AEC differentiator not found in generic content tools |
| last–1 | Presets | preset | GH_ValueList components |
| last | Utilities | util | Client, PluginUtilities, ButtonComponent |

**Naming rules for this model:**
- Content-type tab names carry **no "JSON" suffix** — the content type name is self-explanatory ("Slides", "Shapes", "Text", not "Slides JSON")
- HTTP tab names describe the resource being accessed ("Presentation", "Pages") — not "Requests" or "Sends"
- Compose is the assembly point; the BatchUpdate HTTP component lives in its HTTP tab, not in Compose
- AEC features fold into natural content-type homes (table helper → Tables, color helper → Style, template helper → Compose, geometry bridge → Geometry) — no separate AEC tab

**Write path:** every content-type JSON tab → Compose (aggregator) → HTTP write tab (BatchUpdate)

(dogfood F1)

---

## Component naming rules

| Type | Class name | File name |
|---|---|---|
| Standard GH_Component | `[Name]Component` | `[Name].cs` |
| GET list | `GetAll[Resource]Component` | `GetAll[Resource].cs` |
| GET single | `Get[Resource]Component` | `Get[Resource].cs` |
| GET search | `Find[Resource]Component` | `Find[Resource].cs` |¹
| POST | `Create[Resource]Component` | `Create[Resource].cs` |
| PUT/PATCH | `Update[Resource]Component` | `Update[Resource].cs` |
| DELETE | `Delete[Resource]Component` | `Delete[Resource].cs` |
| JSON builder component | `[Resource]JsonComponent` | `[Resource]Json.cs` |
| Style component | `[Resource]StyleComponent` | `[Resource]Style.cs` |
| Preset | `[Name]PresetComponent` | `[Name]Preset.cs` |

¹ **If the target API has no list/search endpoint** (get/create/update by ID only — e.g. Google Docs),
a `Find[Resource]` by name must call a **sibling API** (e.g. Drive `files?q=name contains '…'`), which
needs the **correct read scope declared up front** — `drive.readonly`, **not** `drive.file` (app-created
files only). `pr-aec-advisor` flags this at Phase 4; make sure the declared scope set (and `pr-permissions`)
carries it. (dogfood F8)

**Display names are workflow language, not API language.** The table above governs `class_name` /
`file_name` — those stay exactly as shown, technical and stable. The spec's canvas-facing `name` /
`nickname` fields are a separate concern: they must come from the confirmed workflow's own
wording, never a bare `Verb + Resource` copy of the endpoint (e.g. "Apply Changes" not "Batch
Update", "Rows or Columns" not "Dimension" — both real renames a user made by hand, after the fact,
on a plugin this pipeline had already generated). Renaming only the display layer is safe — class names, file names, GUIDs, and I/O
are untouched by it. The inline validator (below) flags any component whose `name` is an
unmodified `Verb+Resource` string with no pass taken against workflow language.

---

## I/O naming

Apply conventions skill rules. Trace the full chain before writing:

- `Token` / `T` — always first input on every component
- `[Thing] ID` — for all ID inputs and outputs (e.g. `Board ID`, `Item ID`)
- `[Thing] JSON` — for all serialised JSON inputs and outputs
- `Status` / `S` — success/failure string output on all HTTP components
- `Response` / `R` — raw API response JSON output on all HTTP components
- Output name of a JSON component must exactly match the input name of the component that consumes it

---

## Write model & modularity

A generated plugin must be usable **modularly** — the user wires one payload-producing chain into
any write operation (create / update / append / delete) without rebuilding it. Design the spec so
this holds.

**Tiers (set `role` on every component):**
- `unit` — one field/piece of payload JSON from user inputs; outputs schema JSON (item) and/or value
  JSON (tree)
- `aggregator` — gathers many unit outputs (list + tree) into a record payload (list)
- `write` — sends a payload: create / update / append / delete
- `recursive` — output feeds the same-nickname input of another instance (nesting)
- `preset` — fixed API string values

**Modularity rules:**
1. For each resource, define **one payload contract** — a single `{name, nickname, access}` — and
   record it in `payload_contracts`. Every write verb for that resource takes that exact input.
2. Write components differ only by verb + endpoint, plus an extra `[Thing] ID` input when the verb
   targets an existing record (update / append / delete). The payload input is identical across them.
3. Never give two write verbs incompatible payload shapes. One resource → one contract → many verbs.
4. The payload producer is decoupled from the consumer — it does not reference any specific verb.

**Per-API decision (this is where the platform matters):** APIs differ in how create vs update vs
append work — shared body, distinct shapes, or upsert. Inspect `feasibility.json` per resource:
- If create and update accept the same body → one shared contract feeds both (preferred)
- If a verb needs extra/fewer fields → keep the same contract and let the write component include the
  ID or trim server-managed fields; do **not** fork the contract
- If the API genuinely cannot share a shape → split the contract, set both in `payload_contracts`,
  and **flag it** so the user knows that chain is not interchangeable

---

## Dual Style Pattern — uniform vs. parametric-per-item

Generalizes a pattern that has been hand-built after the fact on more than one generated plugin:
per-trait style components (a background-colour style, a font-size style) alongside one bulk grid
writer that takes the same traits as trees.

**When it applies:** a resource is a naturally repeating child collection (cells in a range,
shapes on a slide, runs of text, rows in a table) AND a workflow marks `varies_per_item: true` for
it, or the tabular benchmark applies to it.

**Always build the pair, not just one:**
- **Uniform component** (`[Property]StyleComponent`, per the naming table above) — one property,
  all inputs `access: list`, broadcasts/last-value-repeats across a targeted range. Confirmed
  shape: range-address inputs (e.g. `Start Row`/`End Row`/`Start Column`/`End Column`, all `list`)
  + one property input (`list`) → one `Request JSON` output (`list`). One component per property —
  good for "set everything to X."
- **Parametric/tree component** (`Write[Resource]GridComponent` or `[Resource]ByTreeComponent`) —
  ONE component covering all relevant properties at once: `item`-access inputs for the
  target/address (confirmed shape: `Sheet ID`, `Start Row`, `Start Column`, all `item`), plus
  EVERY relevant style property as an **optional, `tree`-access input, parallel to a main data
  tree**, each independently omittable. Values are joined **positionally** — same branch/index
  across every tree, resolved with a safe per-position lookup (confirmed pattern:
  `CellBuilders.BuildWriteCellGrid`'s generic `At<T>(grid, row, col)` helper) — never by wiring one
  component's output into another's input for per-item joining. "One instance can express a
  computed per-cell pattern."
- Both components must emit into the **same payload contract** so they're interchangeable at the
  aggregator — the uniform and parametric paths are two ways to produce the same request shape,
  never two different shapes.

**Consolidate a common chain into one component.** The reverse direction of the same idea — a
"build the whole slide / row / section from a layout" component that exists *alongside* the granular
per-request-type components (CreateShape, InsertText, …), not instead of them — they internally chain several requests into one placed component for the common case, so
a simple ask needs one component on the canvas instead of five wired together.

- **Rule:** when a workflow's common case requires wiring several granular/primitive components
  together the same way every time, propose an *additional* consolidated component that performs
  that chain internally in one step — grounded in the workflow, named in its language (e.g. "Build
  Slide From Layout"). This is additive: keep the granular primitives for the custom/uneven cases,
  add the consolidated component for the common case. Prefer fewer components on the canvas for a
  stated workflow whenever a shortcut is genuinely faithful to that workflow — don't decompose into
  many components just because that's the more "granular" choice if the workflow itself never
  needs that granularity.
- This is the direct counterpart to the parametric-tree component above: that one says "don't
  force one uniform component to do everything, offer a parametric-per-item variant too"; this one
  says "don't force the user to hand-wire five components for one common outcome, offer the
  one-shot variant too." Both are about matching component count to the actual workflow, in both
  directions.

---

## Out of scope — native Grasshopper already does this

No custom value→color, value→size, or other remap/interpolation/gradient component belongs in a
generated plugin — that step is deliberately left to native GH (Gradient, Remap Numbers, Graph
Mapper), wired externally into a tree-access style input — no generated plugin has ever needed a
value-mapping builder of its own, by design.

**Never propose building a custom value-remapping/interpolation/gradient component.** If a
workflow needs "map a value to a color/size/position," the correct spec output is just exposing
the right `tree`-access input on the parametric component above — the mapping itself is the user's
job with stock GH components. More generally: before proposing any new component, check whether
it's just wrapping capability GH's own component library already provides, and skip it if so.

---

## Output: plugin-spec.json shape

```json
{
  "plugin_name": "[PluginName]",
  "platform": "[Platform]",
  "base_url": "[base url]",
  "auth_method": "Bearer token",
  "api_version": "[version]",
  "tab_name": "[PluginName]",
  "subcategories": [
    {
      "name": "Auth",
      "type": "http",
      "components": [
        {
          "class_name": "[Plugin]AuthComponent",
          "file_name": "[Plugin]Auth.cs",
          "type": "component",
          "role": "write",
          "endpoint_id": "auth_check",
          "inputs": [
            { "name": "Token", "nickname": "T", "type": "string", "access": "item", "default": "" }
          ],
          "outputs": [
            { "name": "Status", "nickname": "S", "type": "string", "access": "item" },
            { "name": "Response", "nickname": "R", "type": "string", "access": "item" }
          ]
        }
      ]
    }
  ],
  "builders": [
    {
      "file_name": "[Resource]Builders.cs",
      "covers": ["[Resource]"],
      "used_by": ["[Resource]JsonComponent"]
    }
  ],
  "relations": [
    {
      "from": "[Resource]JsonComponent.[Record] JSON",
      "to": "Create[Resource]Component.[Record] JSON",
      "nickname": "RJ",
      "access": "list→list"
    }
  ],
  "payload_contracts": [
    {
      "resource": "[Resource]",
      "contract": { "name": "[Record] JSON", "nickname": "RJ", "access": "list" },
      "produced_by": "[Resource]AggregatorComponent",
      "consumed_by": ["Create[Resource]Component", "Update[Resource]Component", "Append[Resource]Component"]
    }
  ]
}
```

- `role` per component: `unit` | `aggregator` | `write` | `recursive` | `preset`
- `access` per I/O: `item` | `list` | `tree`
- `relations`: explicit producer→consumer links (`from`/`to` are `Component.Port Name`); `access` is
  `producerAccess→consumerAccess`
- `payload_contracts`: the modular write contract — one payload shape per resource, consumed by every
  write verb interchangeably (see Write model below)

---

## Inline validator

Run before presenting spec to user. Check:

1. No duplicate GUIDs (GUIDs not yet assigned — flag if component_name is duplicated)
2. No duplicate nicknames within the same component
3. All declared `endpoint_id` values exist in `feasibility.json`
4. **I/O line-up check** — run the full validation below
5. All component types are one of: `component`, `button`, `preset`
6. Auth subcategory has exactly one component
7. **Workflow coverage** — every candidate component traces to a workflow in `spec/workflows.json`
   or a structural requirement (auth, a write path a workflow needs). Anything that doesn't is
   moved to a `"Proposed to skip for v1 (not used by any stated workflow):"` block, one line and a
   reason per item — never silently omitted, never silently kept just because the API has it. This
   extends the existing DELETE-endpoint opt-in convention (see Edge cases) to the general case.
8. **Display-name check** — every component's canvas `name` is traceable to workflow language, not
   an unmodified `Verb+Resource` copy of the endpoint (see "Display names are workflow language,
   not API language" above).

If any check fails: report the specific violation and proposed fix. Do not write
`plugin-spec.json` until the user confirms. Present the skip-for-v1 block (check 7) to the user at
Gate 2 alongside the structure itself, not as a separate approval step.

---

## I/O line-up check

This is the single source of truth for inputs and outputs lining up across the plugin.
It runs **here, at spec time** — before any code is generated — so wiring errors are caught
once, statically, instead of per-component at test time. The test project does **not** re-check
this; it trusts a spec that passed this gate.

Build a producer/consumer map across every component in the spec, then validate:

**1 — Every consumed input has a matching producer.**
An input is "consumed" (fed by another component, not typed by the user) when its name follows a
chain convention: `[Thing] JSON`, `[Thing] ID`, `Response` / `R`, or any name that also appears as
an output elsewhere. For each consumed input there must exist at least one component whose **output
name matches exactly** (per `pr-conventions`: output name == consuming input name).

**2 — Matched pairs agree on name, nickname, type, and access.**
A valid link requires all four to line up:
- **name** identical
- **nickname** identical (1–3 chars)
- **type** identical (a type mismatch — e.g. producer `int`, consumer `string` — is an error)
- **access** compatible per the table:

| Producer | Consumer | Allowed | Meaning |
|---|---|---|---|
| item | list | ✓ | aggregator gathers many units |
| tree | tree | ✓ | per-branch values (one branch per record) |
| list | list | ✓ | passthrough |
| list | tree | ✓ | recursive nesting (output → children of a parent) |
| item | item | ✓ | single passthrough |
| any other combination | | ✗ | flag |

**3 — Modular write-interchange holds.**
For every entry in `payload_contracts`, confirm each `consumed_by` write component declares the
payload input with the **same name + nickname + access** as the `contract`. If any write verb for a
resource diverges from the shared contract, **hard fail** — the user could not wire one producer into
all verbs. (A write verb may add a `[Thing] ID` input; it may not change the payload contract.)

**4 — Builder `used_by` is consistent.**
Every `builders[].used_by` entry names a real component, and that component has a `[Resource] JSON`
input whose name matches the builder's output. Every JSON component referenced by a builder appears
in exactly one Presets/JSON subcategory.

**5 — Report, don't silently pass.**
Print the resolved chain as a table so the user can eyeball it at Gate 2:

```
PRODUCER                    OUTPUT (nick, access)   →  CONSUMER                 INPUT (nick, access)
[Resource]JsonComponent     [Record] JSON (RJ,item) →  [Resource]Aggregator     [Record] JSON (RJ,list)   ✓
[Resource]Aggregator        [Record] JSON (RJ,list) →  Create[Resource]         [Record] JSON (RJ,list)   ✓
[Resource]Aggregator        [Record] JSON (RJ,list) →  Update[Resource]         [Record] JSON (RJ,list)   ✓  modular
[Resource]Aggregator        [Record] JSON (RJ,list) →  Append[Resource]         [Record] JSON (RJ,list)   ✓  modular
[Resource]JsonComponent     [Thing] JSON (B,list)   →  (no consumer)                                      ⚠ orphan output
—                                                   →  Append[Resource]         [Record] JSON (RJ,list)   ✗ no producer
```

- `✓` matched on name + nickname + type + access; `modular` = a write verb sharing the payload contract
- `⚠` orphan output — a producer no component consumes; warn only (may be a terminal/display output)
- `✗` unmatched input, access mismatch, or contract divergence; **hard fail**, do not write the spec

Tokens (`Token` / `T`) and user-supplied scalars are not consumed inputs — exclude them from the
check. Only flag a missing producer for inputs the conventions mark as chain values.

---

## Edge cases

- Endpoint with no clear GH param type mapping → flag, propose skip for v1, note in spec
- Resource with 30+ fields → propose splitting into required/optional variants
- Non-standard response type → string passthrough with a description note
- DELETE endpoint → propose skip for v1 by default, require explicit user opt-in
- oneOf/anyOf in body schema → flag as AMBIGUOUS, scaffold with note
- Endpoint/field not used by any workflow in `spec/workflows.json` and not structurally required →
  propose skip for v1, list it explicitly at Gate 2 with a one-line reason (validator check 7)
- A workflow implies mapping a value to a visual property (color, size, position) → do not build a
  mapping component; expose a `tree`-access input for it and note that native GH (Gradient/Remap
  Numbers/Graph Mapper) fills it (see "Out of scope" above)
