---
name: pr-assembly
description: AssemblyInfo file pattern for Grasshopper REST API plugins
---

# Skill: Assembly info

For the [PluginName]Info.cs file in the root namespace.
Every plugin has exactly one of these.

---

```csharp
using Grasshopper;
using Grasshopper.Kernel;
using System;
using System.Drawing;

namespace [PluginName]
{
    public class [PluginName]Info : GH_AssemblyInfo
    {
        public override string Name => "[PluginName]";
        // Same 16×16 logo as the category icon — shown in Grasshopper's loaded-libraries list
        public override Bitmap Icon => Properties.Resources.[XX]_[PluginName]Logo;
        public override string Description => "[One sentence describing the plugin purpose.]";
        public override Guid Id => new Guid("[UNIQUE GUID]");
        public override string AuthorName => "[AuthorName]";
        public override string AuthorContact => "[AuthorContact]";
        // Single source of truth is the .csproj <Version> — never a second hardcoded string here
        public override string AssemblyVersion => GetType().Assembly.GetName().Version.ToString(3);
    }

    public class [PluginName]CategoryIcon : GH_AssemblyPriority
    {
        public override GH_LoadingInstruction PriorityLoad()
        {
            Instances.ComponentServer.AddCategoryIcon("[PluginName]", Properties.Resources.[XX]_[PluginName]Logo);
            Instances.ComponentServer.AddCategorySymbolName("[PluginName]", '[FirstLetter]');
            return GH_LoadingInstruction.Proceed;
        }
    }
}
```

Rules:
- Both classes in one file, root namespace, no other classes
- `Icon` on `GH_AssemblyInfo` returns the same `[XX]_[PluginName]Logo` resource the category icon
  uses — the *category* icon is still registered via `GH_AssemblyPriority` (this property alone
  does not do that)
- **`AssemblyVersion` reads the compiled assembly version** — `GetType().Assembly.GetName().Version.ToString(3)`
  — so the `.csproj` `<Version>` (which `pr-vs-project` sets and CI overrides with `-p:Version`) is the
  single source; the yak `manifest.yml` and `docs/changelog.md` copy from it. Never write `"1.0.0"` here
- **GUID and parameter stability — never change after the first release.** `Id` here and every
  component's `ComponentGuid`, plus each component's input/output **order**, are what saved `.gh` files
  bind to. Changing them turns every existing user canvas into "unknown component" placeholders.
  Adding a feature post-ship (`/rest-add-feature`) means *new* GUIDs for *new* components and
  appending new params at the end — never renumbering existing ones

### Category icon resource

The category icon is the **16×16 plugin icon** — generated as a distinct step, separate from the
24×24 component icons. `pr-icons` produces it via the pr-icon-generator MCP:
`generate_plugin_icon(config_path)` then `add_to_resources("[PluginName]Logo", config_path)`.
That registers the resource as **`[XX]_[PluginName]Logo`** (prefix + name + `Logo`), which is exactly
what `AddCategoryIcon` references above — keep these names in lockstep:
- `[XX]` is the plugin's `plugin_prefix` from `icons.json` (e.g. `AC`)
- e.g. for AcmeConnect → `Properties.Resources.AC_AcmeConnectLogo`

**`[AuthorName]` / `[AuthorContact]` are the *user's*, not PleaseREST's.** Both come from
`session.json.author` (`{ name, contact }`), captured at Phase 1 intake — see `pr-session`. They are
what Grasshopper shows in its loaded-libraries list and what `yak` puts in `manifest.yml`, so a
generated plugin must never ship someone else's name. If `author` is missing on an older session,
ask once and write it before generating this file; never fall back to a hardcoded person.

**Namespace — always `Properties.Resources`, never bare `Resources`.** The McNeel template emits
`Resources.Designer.cs` in the `[PluginName].Properties` namespace, so from `[PluginName]Info.cs`
(root namespace) a bare `Resources.X` fails to compile (CS0103). `pr-component` references icons the
same way (`Properties.Resources.[XX]_[ComponentName]`), so the whole plugin stays consistent. (dogfood
Slides F5/F6)

**Scaffold-time placeholder:** `[PluginName]Info.cs` references `[XX]_[PluginName]Logo` from Phase 9,
but the real plugin icon isn't rendered until Phase 11. `pr-vs-project` seeds a placeholder
`[XX]_[PluginName]Logo` resource at scaffold so the project compiles in between; Phase 11 overwrites
that same resource key with the real 16×16 icon.
