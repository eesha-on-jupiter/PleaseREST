---
name: pr-rhino-test
description: Build the demo .gh files for a generated Grasshopper plugin and live-test every component in Rhino via a Grasshopper MCP bridge, with an auto-fix loop, before the human gate
---

# Skill: Rhino MCP test + demo files

Runs in **Phase 12**, after `pr-build` (unit tests green) and **before HUMAN GATE 6**.

Two jobs, in order, against a **live Rhino 8 or 9 + Grasshopper** session driven through a Grasshopper
MCP bridge:

1. **Build the demo `.gh` files** into `demos/` — each canvas built once.
2. **Live-test** every component by loading the built `.gha`, placing the components, solving, and
   reading outputs. An **auto-fix loop** repairs what it can; only genuinely unfixable failures are
   flagged for the human.

The demos are the deliverable that Phase 13 (`pr-docs`) writes `docs/examples/*.md` from — so the MCP
builds each canvas **once** and it serves both as the example file and as the test fixture. No
double work.

Only when **all demos pass and `demos/` is populated** does the pipeline advance to GATE 6.

---

## Dependency: the Grasshopper MCP bridge (external)

PleaseREST does **not** ship this bridge — the user wires it in once. Any bridge that can place
components, wire inputs, solve, save `.gh`, and read component runtime messages works — **but it must
resolve components against the live Grasshopper registry**, not a static stock-component knowledge
base, or it will not see PleaseREST's custom components.

**Official bridge: [`mcneel/RhinoMCP`](https://github.com/mcneel/rhinomcp)** — McNeel's official MCP
server, shipped as **"Rhino-MCP-Platform"** in the Rhino 8/9 Package Manager and connected with the
`MCPConnect` command. It drives Rhino and Grasshopper (GH 1 and GH 2) over a local HTTP/SSE transport.
Use it as the wired-in bridge for this phase.

> **Capability check (do this once, before relying on it).** This phase needs granular GH-canvas
> control — placing PleaseREST's **custom** plugin components by **name against the live registry**,
> wiring them, solving, and reading each component's runtime messages. The official MCP documents
> Rhino control plus *building/upgrading* GH definitions; confirm at runtime that it actually places
> and resolves custom components against the live registry (discover its tool list, place one custom
> component, solve, read its output). If it can't, fall back to a community bridge or manual Gate 6
> (see *Graceful degradation*). Re-check as McNeel expands RhinoMCP's Grasshopper surface.

Community fallbacks (only if the official MCP can't resolve custom components): **[`brookstalley/cordyceps`](https://github.com/brookstalley/cordyceps)**
— full GH control (add/wire/set/group via the live registry, by name), `gh_document` (save/undo),
`gh_inspect` (read outputs + data tracing); Win/Mac (Rhino 8.21+ / .NET 8); its name-based placement
against the live registry is exactly what custom components need. **`SandMartin`** (McNeel forum) — a
simpler community GH MCP; verify it resolves custom components first. `alfredatnycu/grasshopper-mcp`
resolves from a **static** `ComponentKnowledgeBase.json` (stock components only — will not find custom
ones; not suitable).

### Wiring it up (one-time, document this for the user) — official Rhino MCP

1. **Install the plugin in Rhino 8 or 9.** Run the `PackageManager` command, search for
   **"Rhino-MCP-Platform"**, and install it (it *is* on the Package Manager — no manual `.gha` drop or
   Unblock step needed). Windows and Apple Silicon Mac are supported (no Intel Mac). Restart Rhino if
   prompted.
2. **Connect it to Claude Code.** In Rhino, run the **`MCPConnect`** command. It starts the local
   server (HTTP/SSE on a localhost port it outputs) and prints a registration prompt — copy that
   prompt into a new Claude Code session (this registers the MCP for you; there is no fixed-port
   `claude mcp add` to memorize). Restart Claude Code if prompted.
3. **Verify the bridge is up before any test.** Confirm it shows *connected* via `/mcp` (or
   `claude mcp list`) and that its tool list loaded. If it's not connected — usually `MCPConnect`
   hasn't been run in the live Rhino session — **do not** run the test; see Graceful degradation below.
4. **Auth + network.** Live calls need real credentials: read `PLEASE_REST_TOKEN` from env (same var
   `pr-api-tester` uses); prompt once if unset.

> The bridge is a configured dependency, not hardcoded. Discover its actual tool names at runtime
> (via the loaded MCP tool list) rather than assuming a fixed API — tool names and surface differ
> between the official MCP and any community fallback.

### .NET runtime-mode preflight (do this BEFORE expecting anything to load) — dogfood F6

A .NET 8 GH MCP bridge (official RhinoMCP / cordyceps) **and** the plugin's own `net7.0-windows`
build will both silently fail to load if Grasshopper is running under **.NET Framework 4.8** instead
of **.NET Core 8** — no error, the component just never appears in the Plugins/Utils list. On managed
/ corporate machines, Framework mode can be a forced default. Check and fix runtime mode first:

1. **Confirm the runtime.** Run `_SystemInfo` in Rhino and check the .NET runtime line, or run
   `SetDotNetRuntime`. It must read **.NET Core (8)** before you expect any .NET 8 bridge or the
   plugin's `net7.0-windows` target to load.
2. **If it's on Framework 4.8, switch it.** Run `SetDotNetRuntime` → **.NET Core (8)** → then do a
   **full Rhino process restart** (closing the document is not enough). The `/netcore` launch flag may
   be **policy-locked** on corporate machines (it can be rejected with "does not support the /netcore
   flag"), so `SetDotNetRuntime` is the primary lever; a dedicated `Rhino.exe /netcore` shortcut is the
   documented fallback only where the flag is allowed.
3. **Repoint the GH dev-settings load folder to the Core target.** In Core mode Rhino only loads the
   Core build — so `GrasshopperDeveloperSettings` must point at the plugin's
   `...\bin\Debug\net7.0-windows` folder (Rhino 8 Windows), **not** `net48` (Rhino 7) and **not**
   `net7.0` (Rhino 8 **Mac**). After flipping to Core, a dev-settings link still aimed at `net48` will
   stop loading the plugin — repoint it or the plugin won't appear even though the bridge now does.

If the runtime can't be moved to Core 8 (locked machine, no `SetDotNetRuntime`), the automated MCP
path is blocked — fall back to manual Gate 6 (see *Graceful degradation*).

### Rhino 9 (and any Mac) — what differs

Verified on Rhino 9.1 Mac with the official bridge (Rhino-MCP-Platform 0.4.0):

- **Runtime.** Rhino 9 is .NET 10 only — there is no Framework mode, so the preflight above is a
  Windows / Rhino 8 concern. The plugin build to load is **`net7.0-windows`** on Windows and
  **`net7.0`** on Mac (Rhino 8 Mac too); it rolls forward onto .NET 10.
- **Starting the bridge.** `MCPConnect` only opens the "connect your agent" dialog. The listener in
  an already-open Rhino is started by **`MCPStart`** (default port 10500) — until then the router's
  `list_slots` is empty and every tool call hangs or tries to spawn a second Rhino. Run `MCPStart`
  once per Rhino launch; re-check with `list_slots` before the first tool call.
- **Loading the dev build without a restart.** Rather than `GrasshopperDeveloperSettings` + a Rhino
  restart, load the freshly built `.gha` into the running Grasshopper through the bridge's C# tool:

  ```csharp
  var cs = Grasshopper.Instances.ComponentServer;
  var load = cs.GetType().GetMethods(BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Public)
               .First(m => m.Name == "LoadGHA");               // LoadGHA(GH_ExternalFile, bool)
  var file = Activator.CreateInstance(load.GetParameters()[0].ParameterType, new object[] { ghaPath });
  load.Invoke(cs, new object[] { file, false });                // true on success
  ```

  Then confirm with `cs.Libraries` / `cs.EmitObjectProxy(componentGuid)` and print
  `cs.LoadingExceptions`. An assembly can be loaded **once per Rhino process** — after a rebuild in
  the auto-fix loop, the same `.gha` name will not reload; restart Rhino (and `MCPStart` again), or
  ask the user to. On Mac a "new slot" from the bridge is a new document in the *same* process, so
  it does not give a clean reload either.
- **Pressing a `ButtonComponent`.** The bridge has no canvas-click, but its C# tool can call the
  component's public `TriggerButton()` — so on this bridge the write/HTTP components *are*
  auto-testable (see the F7 note under Job B):

  ```csharp
  var doc = Grasshopper.Instances.ActiveCanvas.Document;
  var c = (IGH_Component)doc.Objects.First(o => o.InstanceGuid == id);
  c.GetType().GetMethod("TriggerButton").Invoke(c, null);       // solves synchronously
  // then read c.Params.Output[i].VolatileData and c.RuntimeMessages(...)
  ```

---

## Inputs

| Source | Used for |
|---|---|
| The built `.gha` (Release build for the running Rhino) | the assembly to load and place from |
| `spec/plugin-spec.json` | component display names + nicknames, GUIDs, input/output params, subcategories |
| `spec/call-library-validated.json` | sample inputs + validated response shape (the expected output oracle) |
| `PLEASE_REST_TOKEN` (env) | auth token for live calls |

Place PleaseREST's **custom** components by **name against the live Grasshopper registry** — the
names/nicknames come from `plugin-spec.json`, and the components are resolvable as
soon as the built `.gha` is loaded. GUID is the fallback identifier if a bridge needs it. A bridge
that resolves only from a static stock-component knowledge base will not find them — fall back to
manual demo creation (Graceful degradation).

---

## Job A — build the demo `.gh` files

Derive a **small** demo set (3–5) from `plugin-spec.json` — do not build one demo per component:

1. **Connection check** — auth component → Status/Response (always).
2. **One representative create** — a `ButtonComponent` write (JSON builder → HTTP component).
3. **One representative read** — a GET/list component.
4. **One bulk/aggregator flow** — only if the plugin has aggregator components.

For each demo: place the components by name (live registry), wire builder→HTTP→output, set inputs from
`call-library-validated.json` sample values (token wired from `PLEASE_REST_TOKEN` **for the test
solve only**), label the group, run Job B, then **scrub and save to `demos/[demo-name].gh`**.

> **Never save a real token into a demo file.** Panel values persist inside the `.gh`; `demos/` is
> committed, shipped by `pr-gh-package`, and read by `pr-docs`. Before every save:
> 1. set the `Token` panel's text to the literal placeholder `<PASTE_TOKEN>` (or disconnect it and
>    leave the `Token` input's default empty), and
> 2. re-check: search the saved file's panel contents for the token string — the save is invalid if
>    it is found; fix and save again.
> The `ButtonComponent` cache (`LastResponse`) may also carry IDs from the test call — that is fine
> (not a secret), but if a response echoes credentials, clear it before saving.

> **Fixture quirk — bridge panels emit multi-line text as ONE list item (dogfood F7).** A GH panel
> created via the bridge with a multi-line value comes through as a single list item, not one item per
> line. For any multi-column / list fixture (e.g. a data tree into `DataTreeToTable`), use **one panel
> per cell** wired as multiple sources into the one input, rather than a single multi-line panel.
> (Also seen once: a community helper — Swiftlet "Split Text Into Lines" — silently vanishing from the
> canvas after bridge placement; prefer native fixtures.)

---

## Job B — live smoke test (with auto-fix loop)

For each demo `.gh`, open/solve it and read each component's runtime messages + outputs. Auto-checks:

- The `.gha` **loads** and every component **instantiates** (no red/"unknown component" placeholder).
- Every component **solves without an error balloon / unhandled exception**.
- Outputs are **non-empty and the correct type**; the auth/HTTP `Status` output reports success.
- The Response shape matches the validated shape in `call-library-validated.json` (smoke-level).

> **`ButtonComponent` HTTP calls are human-gated by design (dogfood F7).** Every write/HTTP op
> (Connect/Auth, Create, Update, Batch) is a `ButtonComponent` that fires only on a literal canvas
> mouse-down (`TriggerButton()`, no triggering input param). A bridge whose canvas API only covers
> sliders/panels/toggles (`gh_canvas set`) and computation-enable has **no "press button" action**, so
> it **cannot synthesize the live network call** through these components. What the bridge *can*
> auto-verify is the entire JSON-codegen surface — builders, aggregators, AEC helpers — which are
> normal `GH_Component`s that compute on recompute (this is the actual risk area). So:
> - Auto-test the builder/aggregator/AEC layer fully live (place, wire, solve, read back the request
>   JSON shape against `call-library-validated.json`).
> - **Place and wire** the `ButtonComponent` HTTP components into each demo, but treat their live
>   button-press as **human-gated at Gate 6** — not an auto-fixable failure and not a silent skip.
>   Residual risk is low because those endpoints are already live-VALIDATED in Phase 7.
> - If the wired-in bridge *does* expose a button/trigger action (e.g. a `TriggerButton()` reflection
>   hook or a GH_Document "simulate button" path), use it to drive the write calls too — discover this
>   from the bridge's runtime tool list rather than assuming it's absent.

### Auto-fix loop (per the agreed behavior)

```
for each demo:
  solve → read results
  while failing and attempts < 3:
    diagnose the failure class:
      - CODE bug (wrong param, bad request build, null deref) → fix via the relevant build skill
        (pr-component / pr-button / pr-builders / pr-client), then rebuild the .gha (pr-build)
      - WIRING/canvas (wrong input value, unconnected param)  → fix the canvas, re-save the .gh
      - AUTH (401/403)                                        → re-check token; fix once, else flag
    re-solve
  if still failing:
    if root cause is fixable in code/canvas → keep fixing (raise attempt budget once, deliberately)
    else flag for human  (e.g. live API outage, platform limitation, or a judgment call)
```

**Fix first, flag only when there is no fix.** A flagged failure is not a silent skip — write a
clear report (which demo, which component, the failure class, what was tried, why it can't be
auto-fixed) and surface it at the gate.

Log every observed failure via `pr-dogfood`: **TOOL** when it is a PleaseREST defect (bad codegen,
wrong GUID, missing wiring), **RUN** when it is the target API's fault (outage, undocumented shape).

---

## Output

- `demos/*.gh` — populated, one file per demo workflow, **token scrubbed to `<PASTE_TOKEN>`**
  (consumed by `pr-docs` in Phase 13). Or, degraded: `demos/README.md` (see Graceful degradation).
- A **pass/fail report** per demo/component (printed; feeds the GATE 6 YOUR MOVE block).
- Findings appended to the dogfood log.
- `session.json`: Phase 12 MCP test result recorded.

Advance to GATE 6 **only** when all demos pass (or every remaining failure is a human-flagged
no-fix) **and** `demos/` is populated.

---

## Then: HUMAN GATE 6

Gate 6 stays a human gate — but the demos are pre-built and pre-checked, so the user does very
little: open `demos/`, **paste their token into the `<PASTE_TOKEN>` panel** (demos ship without
one), press each write component's button, confirm the live outputs look right, and reply "all
good" or a bug report. Say the token step explicitly in the YOUR MOVE block. Any human-flagged
no-fix items are presented here for the user's call.

---

## Graceful degradation (no bridge available)

If no Grasshopper MCP bridge is configured, the status check fails, or the bridge cannot resolve the
plugin's custom components from the live registry:

- **Do not hard-fail the pipeline.** Skip Job A/B automation.
- Print a clear notice that the live MCP test was skipped and why, plus the wiring steps above.
- **Write `demos/README.md`** — the manual-build spec every no-bridge dogfood run ended up writing by
  hand. One section per demo from the Job A list (3–5), each with:
  - `**Goal:**` one line (this is what `pr-docs` `workflows.md` rephrases)
  - **Components** in wiring order, by display name + nickname (from `plugin-spec.json`)
  - **Wiring** — `Producer.Output → Consumer.Input` lines, using the exact param names
  - **Inputs to set** — sample values from `call-library-validated.json`; the Token as `<PASTE_TOKEN>`
  - **Expected result** — the validated response shape / Status text to look for
  Never fabricate `.gh` files. `pr-docs` writes `examples/*.md` from this README + the spec when no
  `.gh` exists.
- Fall back to the **fully-manual** Gate 6 (the user builds the canvases from `demos/README.md` and
  tests the components live in GH themselves); record the degradation in the Gate 6 YOUR MOVE block
  so `session.json` / the resume flow know Gate 6 was manual, not pre-checked.

---

## Rules

- Build each demo canvas **once** — it is both the example file and the test fixture.
- Place custom components by **name against the live GH registry** (via the wired-in Rhino MCP), not
  from a static stock-component knowledge base; GUID from `plugin-spec.json` is the fallback identifier.
- Fix what is fixable; flag for human only when there is genuinely no fix.
- Never advance to GATE 6 with an unpopulated `demos/` unless degrading gracefully (and say so —
  and leave `demos/README.md` behind).
- Never save a `.gh` containing a real token — scrub to `<PASTE_TOKEN>` and verify before every save.
- Discover bridge tool names at runtime; do not hardcode one bridge's API.
- Prints Restling progress messages throughout.
