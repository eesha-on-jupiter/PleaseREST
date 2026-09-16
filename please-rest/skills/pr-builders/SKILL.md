---
name: pr-builders
description: Static JSON builder class organisation and rules for Grasshopper REST API plugins
---

# Skill: Builders

For static builder classes that produce JSON — no GH_Component inheritance.

---

## Organisation

Always use `#region` separators in this order:

```
#region Private helpers
#region [Resource group 1]
#region [Resource group 2]
#region Parse helpers
```

Rules:
- Private helpers always first, before any public methods
- Every public method gets a single category tag comment directly above it
- Tag is lowercase, no punctuation: `// item`, `// connector`, `// geometry`
- Private helpers get a comment only if logic is non-obvious
- No blank lines inside a method body unless separating a guard clause from main logic
- Null-coalesce all string parameters: `content ?? ""`
- Default parameter values defined in the signature — never checked inline unless validating a range

---

## Pattern

```csharp
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace [PluginName]
{
    public static class [Resource]Builders
    {
        #region Private helpers

        // Generic: shared helper used by multiple build methods
        private static JObject BuildInner(string type, JObject content)
        {
            return new JObject
            {
                ["type"] = type,
                [type] = content ?? new JObject()
            };
        }

        #endregion

        #region [Resource group]

        // [resource type]
        public static string Build[Name]([params])
        {
            var inner = new JObject { ... };
            return BuildInner("[type]", inner).ToString(Formatting.None);
        }

        #endregion

        #region Parse helpers

        public static JObject Parse(string json)
            => string.IsNullOrWhiteSpace(json) ? null : JObject.Parse(json);

        #endregion
    }
}
```

Rules:
- One builder file per resource family — never mix unrelated resources
- Builder methods called by JSON components only — never by HTTP components
- Private helpers shared across multiple builder files go into `SharedBuilders.cs`
- `Formatting.None` always — never pretty-print in production methods
- **Builders stay pure:** only `Newtonsoft.Json` + BCL types — no `Grasshopper` / `RhinoCommon`. This
  is what lets the test project compile builder sources directly on net8.0 (see `pr-unit-tests`)
- **Body shapes match the validated call:** a builder that produces a request body must match the
  `body_schema` / `example_request` of its endpoint in `spec/call-library-validated.json` — the
  builder is the code form of the MCP-validated shape, not an independent guess
- **Bulk assembly is a builder method:** the tree→list record assembly for aggregators lives here as a
  pure method (e.g. `AssembleRecords(fieldNames, recordValues)` returning payloads + per-record
  warnings), not inside a component's `SolveInstance` (see `pr-bulk-data`) — keeps it unit-testable.
  Unit value builders emit `{"field": "<name>", "value": …}` so `AssembleRecords` can match values to
  schema entries **by field name** and only fall back to position when `field` is absent
- **Required fields come from the validated entry:** `body_required` in `call-library-validated.json`
  lists the top-level body keys the API requires — a builder must always emit those (null-coalesced),
  and may omit optional keys when their input is empty
