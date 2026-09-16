---
name: pr-conventions
description: Base naming, namespace, comment and JSON conventions for Grasshopper REST API plugins
---

# Skill: Conventions

Base conventions for all Grasshopper REST API plugins.
Always load this skill alongside any other skill.

---

## Plugin name — the author's call, asked at intake

**There is no required naming pattern.** `AcmeConnect` is the example used throughout these skills
because a two-word PascalCase name shows the prefix rule clearly — it is **not** a convention, and
`Connect` is not a suffix PleaseREST expects, checks for, or appends. `Slate`, `TulipGH`,
`OrbitTools` and `Nimbus` are all equally valid. Ask the author what they want to call it at Phase 1
intake and use exactly that; never propose a name derived from the platform (`[Platform]Connect`)
as though it were the house style. Suggest one only if they ask.

**What the name has to satisfy,** because it is reused verbatim in several places that are not free
text:

| Used as | Where | Constraint it imposes |
|---|---|---|
| Root namespace + `[PluginName]Info` class | every `.cs` file | Must be a **valid C# identifier**: letters, digits and `_` only, not starting with a digit. No spaces, hyphens, dots or `&`. |
| `[PluginName].csproj` / `.sln` / `.gha` | the project | Same — plus it should not collide with a referenced assembly (`Grasshopper`, `Rhino`, `RhinoCommon`, `System`, `Newtonsoft`). |
| `PluginUtilities.TabName` | the Grasshopper ribbon tab | Shown to users; short enough to read on a tab. |
| Repo name | GitHub | Free-form, but keep it identical to the plugin name — `pr-gh-package` and `pr-docs` build links from it. |
| `manifest.yml` `name:` | yak / `_PackageManager` | Lowercased, no spaces — `AcmeConnect` → `acmeconnect`. Hyphens are allowed but optional; if used, the README's "search `…`" line and `docs/index.md` must match exactly. |

PascalCase is the recommendation, not a rule. If the author's preferred name breaks the identifier
constraint (`My API Tools`, `Grasshopper-Sheets`), say which place it breaks and offer the nearest
valid form (`MyApiTools`, `GrasshopperSheets`) — don't silently rewrite it.

### `plugin_prefix` — `[XX]`, derived and then confirmed

Every icon resource key is `[XX]_[Name]` (`pr-icons`, `Resources.resx`), so the prefix is fixed
early and is expensive to change later — renaming it touches every icon, `Resources.Designer.cs`
and every component's `Icon` property. Propose it at intake, **with** the name, and get a yes:

- **Multi-word PascalCase** → the word initials: `AcmeConnect` → `AC`, `OrbitTools` → `OT`,
  `TulipGH` → `TG`.
- **Single word** → its first two letters, uppercased: `Slate` → `SL`, `Nimbus` → `NI`. If those
  read badly, the first letter plus a distinctive consonant is fine (`Nimbus` → `NB`).
- **Four or more words** → the first three initials; three letters is the ceiling.
- Uppercase letters only — no digits, no underscore.

Resource keys are per-assembly, so a prefix that another Grasshopper plugin also uses is harmless —
pick for readability, not uniqueness. Write the confirmed value to `icons.json.plugin_prefix`; it is
the single source for `[XX]` everywhere else.

---

## File naming

- Component files: `[Name].cs` holding `public class [Name]Component` — the filename drops the
  `Component` suffix, the class name keeps it (e.g. `GetBoard.cs` → `GetBoardComponent`)
- Builder files: `[Entity]Builders.cs` holding `public static class [Entity]Builders`
- Preset files: `[Name]Preset.cs` holding `public class [Name]PresetComponent`
- One class per file, **with exactly two allowed exceptions** (both copied-verbatim infrastructure):
  - `Utilities/ButtonComponent.cs` — `ButtonComponent` + `ButtonAttributes` (`pr-button`)
  - `[PluginName]Info.cs` — `[PluginName]Info` + `[PluginName]CategoryIcon` (`pr-assembly`)
  Everything generated per-component / per-resource is strictly one class per file

---

## Namespace

- Root namespace matches plugin name exactly
- Only `[PluginName].Presets` gets a sub-namespace — everything else uses root

---

## Naming

| Thing | Convention | Example |
|---|---|---|
| Class | PascalCase | `ItemBuilders` |
| Preset class | PascalCase + `PresetComponent` | `ShapeTypePresetComponent` |
| Public method | PascalCase | `BuildItemBody()` |
| Private method | PascalCase | `FormatColor()` |
| Parameter | camelCase | `fillColor`, `strokeWidth` |
| Local variable | camelCase | `inner`, `payload` |
| Resource name | `[XX]_` prefix + PascalCase | `AC_ItemIcon` |
| Nickname | 1–3 chars | `"T"`, `"B"`, `"ID"` |

---

## Input and output naming

- Output name of a JSON component must exactly match the input name of whatever consumes it
- `[Thing] JSON` pattern for all serialised outputs — e.g. `Item JSON`, `Connector JSON`
- `[Thing] ID` for all IDs — e.g. `Board ID`, `Item ID`
- `Token` / `T` — always, across all plugins
- `Status` / `S` — always for status outputs
- `Response` / `R` — always for raw response outputs
- Trace the chain: output → input → output — every link must match

---

## Component wiring and modularity

The most important design goal of a generated plugin: components must wire together cleanly on the
Grasshopper canvas, and the user must be able to compose them **modularly** — reusing the same
upstream JSON to create, update, or append to a resource without rebuilding anything.

### Wiring contract — what makes a link valid
A producer output may feed a consumer input only when all three agree:
1. **Name** — identical (e.g. `[Record] JSON` out → `[Record] JSON` in)
2. **Nickname** — identical (1–3 chars)
3. **Data access** — compatible (table below)

Carrier type for structured data is always a **Text** param holding serialised JSON — never a custom
GH type. The contract is the JSON shape (guaranteed by shared builders), not the .NET type.

### Data-access rules across a link
| Producer access | Consumer access | Meaning |
|---|---|---|
| item | list | aggregator gathers many units into one collection |
| tree | tree | per-branch values preserved (one branch per record) |
| list | list | passthrough |
| list | tree | recursive nesting — output becomes the children of a parent |

### Component tiers
- **Unit** — produces one piece of payload JSON from user inputs (e.g. a single field). Emits a
  schema JSON (item) and/or a value JSON (tree)
- **Aggregator** — gathers many unit outputs (list + tree) into a record payload (list)
- **Write** — sends a payload to the API: create / update / append / delete
- **Recursive** — output feeds the same-nickname input of another instance (nesting)
- **Preset** — supplies fixed API string values

### Modularity — the core rule
All write operations on the same resource expose the **same payload input contract** — identical
name + nickname + access. The user wires one aggregator output into Create, Update, **or** Append
interchangeably, without redefining anything.
- Write components differ only by verb + endpoint (plus an extra `[Thing] ID` input when the verb
  targets an existing record)
- Never define a different, incompatible payload shape per verb — one resource → one payload
  contract → many write verbs
- The payload producer (unit / aggregator) is **decoupled** from the consumer: it neither knows nor
  cares which write operation consumes it
- Shared builder vocabulary makes this safe — both ends use the same `[Entity]Builders` methods, so
  the JSON a unit emits is exactly what every write verb expects

Whether one body can serve every verb is platform-dependent — `pr-spec` decides the write model per
API and keeps the payload contract shared wherever the API allows, flagging where it cannot.

---

## Comment style

- Single-line `//` only, one space after
- Sentence case, no period at end
- Describe what the method produces, not how
- Category tag above every public builder method: `// item`, `// connector`, `// geometry`
- Tag is lowercase, no punctuation

---

## JSON rules

- Always use `Newtonsoft.Json.Linq` — never string interpolation for JSON
- Null-coalesce all string parameters: `content ?? ""`
- `Formatting.None` for all serialised output
- Optional children: check `!= null && Count > 0` before adding
