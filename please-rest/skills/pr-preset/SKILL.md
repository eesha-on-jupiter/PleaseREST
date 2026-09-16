---
name: pr-preset
description: GH_ValueList preset structure for Grasshopper REST API plugins
---

# Skill: Preset

For GH_ValueList preset components that provide API string values.

---

```csharp
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using System;
using System.Collections.Generic;
using System.Drawing;

namespace [PluginName].Presets
{
    // [One line describing what values this preset provides.]
    // [Optional second line — omit if one line is sufficient.]
    public class [Name]PresetComponent : GH_ValueList
    {
        public [Name]PresetComponent()
        {
            Category = PluginUtilities.TabName;
            SubCategory = PluginUtilities.CategoryZYPresets;
            Name = "[Display Name]";
            NickName = "[Short Name]";
            Description = "[One sentence description ending with a period]";

            ListItems.Clear();
            foreach (var kvp in Items)
                ListItems.Add(new GH_ValueListItem(kvp.Key, $"\"{kvp.Value}\""));
        }

        private static readonly Dictionary<string, string> Items = new Dictionary<string, string>
        {
            { "[Display Label]", "[api-value]" },
        };

        protected override Bitmap Icon => Properties.Resources.[ResourceName];
        public override Guid ComponentGuid => new Guid("[UNIQUE GUID]");
    }
}
```

Rules:
- `SubCategory` is always `PluginUtilities.CategoryZYPresets` — the constant `pr-utilities` defines
  (there is no `PluginUtilities.Presets`; referencing it is CS0117)
- Namespace is always `[PluginName].Presets` — never root
- `Items` is always `private static readonly`
- `ListItems.Clear()` always called before populating
- Display labels are human-readable, values are raw API strings
- Align dictionary values with spaces so `"` characters form a clean column
- Icon and Guid always last, in that order
- No `RegisterInputParams`, `RegisterOutputParams`, or `SolveInstance`
