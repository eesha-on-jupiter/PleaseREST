---
name: pr-bulk-data
description: Grasshopper data-tree conventions for bulk/mass data upload in REST API plugins
---

# Skill: Bulk data (trees)

How a generated plugin uses Grasshopper **data trees** to upload many records in one go. Load
alongside `pr-component` / `pr-builders` when building unit, aggregator, or bulk-write components.
This is the pattern that turns "one record per component" into "a whole table per solve."

---

## The two-axis model

Bulk upload maps a 2-D table onto GH structure on two axes:

- **Field axis → list.** Each unit/field component emits its schema as an `item`; the aggregator
  gathers these as a `list` — one entry per column/field.
- **Record axis → tree.** Each unit emits its per-record values as a `tree` — **one branch per
  record** (`GH_Path(i)`, where `i` is the record index). The aggregator gathers these as a `tree`.

```
Field A unit   schema (item) ─┐          branch{0} = record 0's field values ─┐
Field B unit   schema (item) ─┼─ list    branch{1} = record 1's field values ─┼─ tree
Field C unit   schema (item) ─┘          ...                                  ─┘
                                         (one branch per record; items in a branch = that record's values)
```

---

## Unit component — emit values as a tree
- Schema output (`[Field] schema`): `item`
- Value output (`[Record] JSON`): `tree`, **one branch per record**, built with `new GH_Path(i)`
- One item per branch normally; for a **multi-valued field**, read all items in the incoming branch
  into a list and emit a single value JSON per branch (nested list → one value)

## Aggregator — zip columns × rows
- Inputs: schema as `list` (N fields), values as `tree` (branches = records)
- For each branch (record), pair the N field names with that branch's items
- **Ragged handling:** when field count ≠ branch item count, use `Min(fields, items)`, process the
  pairs that line up, add a per-record warning — **never throw, never drop the whole upload**
- Skip empty/blank value items with a per-record note; keep going
- Output: `[Record] JSON` as a `list` — one assembled payload per record, **in record order**

### The zip logic lives in a pure builder method (so it is testable)
The component must **not** bury the assembly logic inside `SolveInstance` — `IGH_DataAccess` and
`GH_Structure` are not unit-testable headless (dogfood F6/F7). Split it:

- A **pure builder method** does the work, on plain types only (no Grasshopper):
  ```csharp
  // returns (one payload JSON per record, one warning per record — empty if OK)
  public static (List<string> payloads, List<string> warnings)
      AssembleRecords(IList<string> fieldNames, IList<IList<string>> recordValues)
  ```
  It applies the ragged `Min`, empty-skip, and ordering rules above. This is what `BulkAssemblyTests`
  exercises (see `pr-unit-tests`).
- The **component** is a thin adapter: read the schema `list` and the value `tree` into plain
  `List<string>` / `List<IList<string>>`, call `AssembleRecords`, set the payload `list` output and
  surface the warnings as runtime messages. No assembly logic in `SolveInstance`.

### Reading the tree input — the adapter code
Tree access needs Goo types: `DA.GetDataTree<T>` requires `T : IGH_Goo`, so
`GetDataTree<string>` does **not** compile. The Text carrier is `GH_String`:

```csharp
using Grasshopper.Kernel.Data;    // GH_Structure, GH_Path
using Grasshopper.Kernel.Types;   // GH_String

// inputs: 0 = schema (list), 1 = values (tree)
var fieldNames = new List<string>();
if (!DA.GetDataList(0, fieldNames)) return;

GH_Structure<GH_String> tree;
if (!DA.GetDataTree(1, out tree)) return;

var records = new List<IList<string>>();
foreach (var path in tree.Paths)                       // one branch per record, in path order
{
    var branch = tree.get_Branch(path);
    var values = new List<string>();
    foreach (var goo in branch)
        values.Add((goo as GH_String)?.Value ?? "");   // null item → "" (assembler skips + notes it)
    records.Add(values);
}

var (payloads, warnings) = [Resource]Builders.AssembleRecords(fieldNames, records);
for (int i = 0; i < warnings.Count; i++)
    if (!string.IsNullOrEmpty(warnings[i]))
        AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "Record " + i + ": " + warnings[i]);
DA.SetDataList(0, payloads);
```

- Register the value input with `GH_ParamAccess.tree` and the schema input with `GH_ParamAccess.list`
- `Grasshopper.Kernel.Data` + `Grasshopper.Kernel.Types` usings are required — `GH_Structure`/`GH_Path`
  and `GH_String` live there, not in `Grasshopper.Kernel`
- Emitting a tree output is the mirror: build a `GH_Structure<GH_String>`, `Append(new GH_String(v),
  new GH_Path(i))`, then `DA.SetDataTree(0, structure)`

### Field ↔ value alignment is positional — make it robust
Grasshopper merges same-path items from multiple sources in **wire-connection order**. The schema
`list` (field N) and each record branch (item N) only line up if the user wired the unit outputs into
the aggregator's two inputs in the **same order** — a swapped wire silently puts values under the
wrong field. So:
- **Every value JSON carries its field name** (`{"field":"Name","value":"…"}`), emitted by the same
  unit that emits the schema item for that field — the shared builder guarantees both use the same
  key
- `AssembleRecords` **matches by field name first** (`field` key in the value JSON ↔ `name` in the
  schema JSON) and falls back to index only when a value has no `field` key; a value whose field
  isn't in the schema gets a per-record warning, not a crash
- Positional `Min`/ragged handling below still applies to the fallback path

## Bulk-write component — loop the list
- Input: `[Record] JSON` as a `list`
- Iterate the list, one API call per record — **each call through the sync call site**
  (`Task.Run(() => client.CreateXAsync(p)).GetAwaiter().GetResult()`, see `pr-component`); never
  `await` inside `SolveInstance`
- **Rate limit:** pacing lives in the **client**, not the component — `[PluginName]Client` exposes a
  `Create[Thing]BatchAsync(IList<string> payloads)` that posts sequentially with `await Task.Delay(350)`
  between calls and returns index-aligned results; the component makes **one** sync call to it. If a
  component must pace itself (rare), `Thread.Sleep(350)` is the only correct form in a sync solve
- **Batch parallel sub-steps** (e.g. a pre-clear / archive pass) in small groups with `Task.WhenAll`
  and a delay between batches (e.g. size 3, 400 ms) — again inside the client's async batch method
- **Order:** post sequentially when record order must be preserved
- **Index-aligned results:** outputs are parallel `list`s sized to the input — `[Thing] ID` per
  record and `Error` per record — so position `i` of every output maps to input record `i`
- Empty payload at position `i` → set that slot empty + an error note, do **not** abort the batch

---

## Index-alignment contract

The whole chain preserves record order and count:

```
unit branch i  →  aggregator list[i]  →  write output[i]
```

The user can trace any result or error back to its source record by index. Never reorder or compact
mid-chain — a skipped record still occupies its slot (empty value + note).

---

## Rules
- Branch = record; item-in-branch = field value (or a nested list for multi-valued fields)
- Tree inputs are read as `GH_Structure<GH_String>` and unwrapped to `string` — never `GetDataTree<string>`
- Value JSON carries its field name; aggregators key-match on it and fall back to index
- Aggregators must handle ragged trees (min + warn) — never crash on mismatch
- HTTP pacing (`Task.Delay`) lives in the client's async batch method; components never `await`
- Write outputs are always index-aligned `list`s, the same length as the input
- Bulk writes always rate-limit; parallel sub-steps always batch with a delay
- Trace the tree: branch count in == payload count out == result count out
