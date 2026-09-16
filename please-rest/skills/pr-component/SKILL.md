---
name: pr-component
description: GH_Component file structure and rules for Grasshopper REST API plugins
---

# Skill: Component

Structure for all GH_Component files in a REST API plugin.

---

```csharp
using Grasshopper.Kernel;
using System;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace [PluginName]
{
    // [One line describing what this component does.]
    // [Optional second line — omit if one line is sufficient.]
    public class [Name]Component : GH_Component
    {
        public [Name]Component()
          : base("[Display Name]", "[Nickname]",
              "[One sentence description ending with a period]",
              PluginUtilities.TabName, PluginUtilities.Category[XX][Descriptor])
        { }

        protected override void RegisterInputParams(GH_InputParamManager pManager)
        {
            // one pManager.Add per param, default value always supplied
        }

        protected override void RegisterOutputParams(GH_OutputParamManager pManager)
        {
            // one pManager.Add per param
        }

        protected override void SolveInstance(IGH_DataAccess DA)
        {
            // 1. Declare variables with defaults
            // 2. DA.GetData calls
            // 3. Guard clauses / clamping
            // 4. Logic  (HTTP components: see "Calling the client" below)
            // 5. DA.SetData calls
        }

        protected override System.Drawing.Bitmap Icon => Properties.Resources.[XX]_[Name];
        public override Guid ComponentGuid => new Guid("[UNIQUE GUID]");
    }
}
```

Rules:
- Description always ends with a period
- Input params always supply a default value as the last argument
- SolveInstance always follows the 5-step order — never mix declaration and logic
- Icon and Guid always last, in that order
- One using per line, no global usings
- No regions inside component files
- Constructor subcategory is always a `PluginUtilities.Category[XX][Descriptor]` constant from
  `pr-utilities` (e.g. `PluginUtilities.CategoryABBoards`) — never a bare string, never a name
  that isn't defined there

---

## Calling the client from SolveInstance (HTTP components)

`SolveInstance` is **synchronous** and runs on Grasshopper's UI thread; every `[PluginName]Client`
method is `async Task<Tuple<bool, string, string>>`. Bridge the two exactly like this — step 4 of
every HTTP component:

```csharp
// 4. Logic
var client = new [PluginName]Client(token);           // thin wrapper; the HttpClient inside is shared
var (ok, json, err) = Task.Run(() => client.[Action]Async(arg1, arg2)).GetAwaiter().GetResult();

if (!ok)
{
    AddRuntimeMessage(GH_RuntimeMessageLevel.Error, err);
    DA.SetData(0, "Error: " + err);                  // Status output still populated
    return;
}

JObject parsed = null;
try { parsed = JObject.Parse(json); }
catch (JsonException)
{
    AddRuntimeMessage(GH_RuntimeMessageLevel.Warning,
        "Response was not JSON: " + (json.Length > 200 ? json.Substring(0, 200) + "…" : json));
}

// 5. DA.SetData calls — Status, Response (raw json), then parsed fields (null-safe: parsed?["id"])
```

Rules for the call site:
- **Always** `Task.Run(() => …).GetAwaiter().GetResult()` — `Task.Run` moves the await off the UI
  thread so the client's `ConfigureAwait(false)` continuations can't deadlock it, and `GetAwaiter()`
  unwraps the real exception instead of an `AggregateException`
- **Never** `async void SolveInstance` — it returns before the call completes, so `DA.SetData` runs
  after the solve has finished (empty outputs) and any exception crashes Rhino on .NET Core
- **Never** `.Result` / `.Wait()` directly on the task on the UI thread
- On `ok == false`: `AddRuntimeMessage(Error, err)` **and** set the `Status` output — the error must be
  visible both as the red balloon and downstream as text
- Wrap `JObject.Parse` / `JArray.Parse` in `try/catch (JsonException)` — APIs return HTML error pages
  and empty bodies; a bare parse throws inside the solve and shows as an unhandled exception
- The client tuple is `(success, result, error)` — deconstruct it, never index `.Item1`
- The client is constructed per solve (cheap wrapper), but its `HttpClient` is a shared static — see
  `pr-client`. Never `new HttpClient()` in a component
- Every call blocks the UI thread for up to the client's timeout (30 s); item-access inputs multiply
  that by item count — for lists use the bulk pattern in `pr-bulk-data`, never a per-item HTTP
  component wired to a long list

Icon reference:
- Always `Properties.Resources.[XX]_[Name]` where `[XX]` is the plugin prefix from `icons.json`.
  pr-icon-generator registers every resource prefixed (`[XX]_[ComponentName]`), and the Designer lives in the
  `[PluginName].Properties` namespace, so the `Properties.` qualifier is required — bare
  `Resources.[Name]` or an unprefixed name fails to compile (CS0103). Matches `pr-assembly`'s
  category-icon reference. (dogfood Slides F6)
