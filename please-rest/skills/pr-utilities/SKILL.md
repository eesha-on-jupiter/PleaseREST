---
name: pr-utilities
description: PluginUtilities.cs pattern for Grasshopper REST API plugins
---

# Skill: Utilities

For `PluginUtilities.cs` in `Utilities/`.

---

## Pattern

```csharp
using System;
using System.Collections.Generic;
using System.Linq;

namespace [PluginName]
{
    public static class PluginUtilities
    {
        // Shared enum helper — used by any preset component backed by an enum
        public static IEnumerable<T> GetValues<T>()
        {
            return Enum.GetValues(typeof(T)).Cast<T>();
        }

        internal static readonly string TabName = "[PluginName]";

        // Subcategory constants — one per subcategory, in display order
        // Variable name: Category + two-letter sort key + descriptor (controls alphabetical order in GH)
        // String value: "[n]. [Display Name]" (the number controls toolbar order)
        internal static readonly string CategoryAAAuth        = "1. Auth";
        internal static readonly string CategoryAB[Sub1]     = "2. [Sub1 name]";
        internal static readonly string CategoryAC[Sub2]     = "3. [Sub2 name]";
        internal static readonly string CategoryAD[Sub3]     = "4. [Sub3 name]";
        // ... one per subcategory from plugin-spec.json
        internal static readonly string CategoryZYPresets    = "[n]. Presets";
        internal static readonly string CategoryZZUtilities  = "[n]. Utilities";
    }
}
```

---

## Subcategory constant naming rules

| Part | Rule | Example |
|---|---|---|
| Variable prefix | Always `Category` | `Category` |
| Sort key | Two uppercase letters — controls alphabetical ordering, which controls toolbar order | `AA`, `AB`, `AC` |
| Descriptor | PascalCase, no spaces, matches subcategory concept | `Auth`, `Boards`, `ItemsJson` |
| String value | `"[n]. [Display Name]"` — number controls position in GH panel | `"1. Auth"`, `"2. Boards"` |

- Auth is always first: `CategoryAAAuth = "1. Auth"`
- Presets and Utilities are always last: use `ZY` / `ZZ` sort keys
- JSON subcategories sit after their corresponding HTTP subcategory in sort order (resource model)
  - e.g. HTTP `CategoryABBoards = "2. Boards"`, JSON `CategoryACBoardsJson = "3. Boards JSON"`
- Gap sort keys between functional groups (AA, AB, AC ... then BA, BB ... ) so new subcategories can be inserted without renaming all constants

---

## Content-type model (batch-style APIs)

When `pr-spec` selects the content-type model, the pairing rule (JSON follows its corresponding HTTP
tab) does **not** apply. HTTP and JSON form two separate groups with a fixed ordering between them.

**Ordering:**
1. Auth (AA) — always first
2. HTTP read/write tabs (AB, AC, ...) — all HTTP tabs together, before any JSON tabs
3. JSON content-type tabs (continuing from last HTTP sort key) — outermost object type first, innermost detail last
4. Compose — immediately after the last content-type tab
5. Geometry (optional) — only when the API involves geometric/coordinate data; sits after Compose, before Presets
6. Presets (ZY)
7. Utilities (ZZ)

**Naming:** content-type tab constants do NOT carry a `Json` descriptor — the type name alone is enough.

```csharp
// Example — Google Slides pattern (content-type model)
internal static readonly string CategoryAAAuth          = "1. Auth";
internal static readonly string CategoryABPresentation  = "2. Presentation";  // HTTP: CreatePresentation, GetPresentation, BatchUpdate
internal static readonly string CategoryACPages         = "3. Pages";          // HTTP: GetPage, GetPageThumbnail
internal static readonly string CategoryADSlides        = "4. Slides";         // JSON builders
internal static readonly string CategoryAEShapes        = "5. Shapes";
internal static readonly string CategoryAFText          = "6. Text";
internal static readonly string CategoryAGTables        = "7. Tables";
internal static readonly string CategoryAHMedia         = "8. Media";
internal static readonly string CategoryAIStyle         = "9. Style";
internal static readonly string CategoryAJCompose       = "10. Compose";       // aggregator + assembly
internal static readonly string CategoryAKGeometry      = "11. Geometry";      // omit if no spatial data
internal static readonly string CategoryZYPresets       = "12. Presets";
internal static readonly string CategoryZZUtilities     = "13. Utilities";
```

Adjust sort keys and display numbers to match the actual tab count for the plugin being built.

---

## GetValues\<T\>() helper

Used by preset components that are backed by a C# enum.

```csharp
// In a preset component constructor:
foreach (var value in PluginUtilities.GetValues<MyEnum>())
    ListItems.Add(new GH_ValueListItem(value.ToString(), $"\"{value}\""));
```

Only use `GetValues<T>()` if the plugin actually defines enums for preset values.
If presets use a plain dictionary (see pr-preset skill), this helper is not needed.

---

## Rules

- Constants are `internal static readonly string` — never `public const string`
- `TabName` is always `internal static readonly string` equal to the plugin display name
- Every subcategory in `plugin-spec.json` gets exactly one constant here
- Components always reference `PluginUtilities.TabName` and `PluginUtilities.Category[XX]` — never hardcode strings
- No GH_Component inheritance — pure static class
- `GetValues<T>()` is the only shared method — add other helpers only if used by more than one component

---

## Usage in components

```csharp
: base("[Display Name]", "[Nick]", "[Desc].",
       PluginUtilities.TabName, PluginUtilities.CategoryAA[Subcategory])
```
