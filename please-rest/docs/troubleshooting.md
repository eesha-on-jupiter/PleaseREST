# Troubleshooting

Common issues, grounded in real dogfood runs.

## Plugin loads with zero skills / commands and no error

**Symptom:** `/reload-plugins` reports nothing wrong, but no `/rest-*` command exists and no
`pr-*` skill loads.

**Cause:** a manifest schema error — most often `skills` / `commands` / `agents` arrays added to
`plugin.json`, or a misspelled key. `commands/`, `skills/` and `agents/` are auto-discovered at the
plugin root; listing them is a schema error that loads the plugin empty and silent.

**Fix:** run `claude plugin validate <path-to-please-rest>` — it names the offending key. The
`/rest-new-plugin` preflight (Phase 1 Step 0) checks `/mcp` shows all three servers connected
before intake for the same reason.

## MCP server shows "not loaded"

**Symptom:** `/mcp` lists `pr-icon-generator` / `pr-api-extractor` / `pr-api-tester` as *not
loaded*, even though the server code runs fine.

**Cause:** a permission/config file referencing the servers under the bare `mcp__<server>__*`
name, or listing them under `enabledMcpServers` / `enabledMcpjsonServers`. Those keys are for
project `.mcp.json` servers — which PleaseREST does **not** use. Its servers come from
`plugin.json`, so Claude Code namespaces their tools as `mcp__plugin_please-rest_<server>__*`
and loads them under the plugin. A phantom `.mcp.json`-style entry has nothing backing it →
"not loaded", while the real plugin servers stay loaded under their longer names.

**Fix:**
- In any `settings.local.json`, use the plugin-scoped names —
  `mcp__plugin_please-rest_pr-icon-generator__*`, `…pr-api-extractor__*`, `…pr-api-tester__*`.
- Remove any `enabledMcpServers` / `enabledMcpjsonServers` list naming these servers.
- The `pr-permissions` skill generates the correct names; the change takes effect on the next
  session (MCP lists are read at startup).

**Sanity check the server itself:**
```
python -c "import mcp, httpx, resvg_py, PIL, yaml, bs4; print('deps ok')"     # Python >= 3.10
python please-rest/mcps/pr-icon-generator/server.py </dev/null   # should start and exit clean
```
Missing modules: `pip install -r please-rest/mcps/<server>/requirements.txt` for each server.

## All three MCP servers show "not connected" and nothing else is wrong

**Symptom:** `/mcp` lists `please-rest → pr-api-extractor, pr-api-tester, pr-icon-generator` as
failed or not connected, immediately, on a fresh install. Skills and commands load fine. The
dependency check above can't even be run the way it's written.

**Cause:** `plugin.json` launches each server with `"command": "python"`. On macOS and most Linux
distributions there is no `python` on PATH — only `python3` — and on Windows a bare `python` can
resolve to the Microsoft Store stub, which exits without running anything. The server never starts
and the failure looks like a plugin problem rather than a PATH one.

**Fix — make `python` resolve to a real Python ≥ 3.10 for the shell Claude Code launches:**
- **macOS / Linux:** install via `pyenv` / `uv` / Homebrew (all of which provide `python`), or add a
  shim — `ln -s "$(command -v python3)" ~/.local/bin/python` with `~/.local/bin` on PATH. A shell
  *alias* will not work: MCP servers are launched directly, not through your interactive shell.
- **Windows:** install from python.org (it registers `python`), and if `python` opens the Microsoft
  Store, turn off **Settings → Apps → App execution aliases → python.exe / python3.exe**.
- **Either:** activate a virtualenv before launching `claude`, so its `python` is first on PATH.

Confirm with `python --version` **in a new terminal** (not the one you just edited PATH in), then
restart Claude Code — MCP servers are started once at session start.

## net48 (Rhino 7) build fails once an icon is embedded

**Symptom:** the project builds clean while `Resources.resx` is empty, but the moment the first
Bitmap icon is embedded, `dotnet build -f net48` fails with `MSB3823` ("non-string resources
require `GenerateResourceUsePreserializedResources=true`") and `MSB3822` (requires
`System.Resources.Extensions`). `net7.0-windows` builds fine, which masks it.

**Cause:** the csproj is missing the preserialized-resources settings; binary icon resources are
universal in these plugins, so every plugin hits this on its first icon.

**Fix:** the `pr-vs-project` csproj template includes, for all targets:
```xml
<GenerateResourceUsePreserializedResources>true</GenerateResourceUsePreserializedResources>
<PackageReference Include="System.Resources.Extensions" Version="8.0.0" />
```
If a generated plugin predates this, add both and rebuild all three targets.

## Category / plugin icon resolves to null

**Symptom:** the ribbon/category icon is missing, or `Info.cs` fails to compile referencing the
logo resource.

**Cause:** a name mismatch — `pr-assembly` expects the resource `[PluginName]Logo`. Make sure
`generate_plugin_icon` + `add_to_resources` register the plugin icon under that exact key, and
that the `Resources` namespace matches between component code (`Properties.Resources.X`) and
`Info.cs`.

## Grasshopper MCP bridge

The Phase 12 live test needs an external bridge — it is **not** part of PleaseREST.

**Wire it up once (official McNeel RhinoMCP):**
1. In Rhino 8/9, run `PackageManager`, search **"Rhino-MCP-Platform"**, install it.
2. In Rhino, run **`MCPConnect`**. It starts a local HTTP/SSE server and prints a registration
   prompt — paste that into a Claude Code session (this auto-registers the MCP; there's no fixed
   `claude mcp add`).
3. Verify it's connected: `claude mcp list` (pre-approved in generated plugins) or `/mcp`.

**Notes:**
- The bridge must resolve components against the **live** Grasshopper registry (so it sees your
  custom components), not a static component knowledge base.
- Community fallbacks if the official one can't resolve custom components: `cordyceps`,
  `SandMartin`. (`alfredatnycu/grasshopper-mcp` uses a static knowledge base — stock components
  only, not suitable.)
- The bridge's own MCP tools cannot be pre-approved (its server name is chosen at registration),
  so the first live-test tool call prompts once — that's expected.
- **No bridge?** The pipeline degrades gracefully: it skips automation, prints these steps,
  leaves `demos/` for manual creation, and Gate 6 becomes fully manual. It never hard-fails.

## Too many permission prompts during a build

The `pr-permissions` skill pre-approves the pipeline's commands in the generated plugin's
**`.claude/settings.local.json`** at Phase 1 — git, dotnet (build/test/publish/pack/nuget/tool/…),
msbuild, nuget, yak, python/pip, powershell, file ops, `claude mcp list`, and every tool of the
three MCP servers. Review and approve that file at intake. If a build needs something new (e.g. a
custom AEC feature command), it's appended and you're asked to re-approve before continuing.

**Still prompting for everything?** Check the file's location. Claude Code only reads
`.claude/settings.local.json`; a `settings.local.json` sitting at the plugin root (where pre-1.0.0
builds put it) is ignored. Move it into `.claude/` and start a new session.

## Every call FAILED in Phase 7

If all entries fail with the **same** message — "Request URL is missing an 'http://' …", all 401,
all "Missing seed ID for path param …" — it is one harness problem, not N API bugs: set the
entry / arg `base_url`, refresh `PLEASE_REST_TOKEN`, or supply seed IDs (`decisions.seed_ids`, or
the "Test workspace / seed IDs" intake question). Fix once and rerun `/rest-test-api`. Do not let
`pr-api-scout` chase each entry.

`PARTIAL — not tested — no request body example` means the extractor found a write endpoint but no
example body (typical for JS-rendered docs): fill `example_request` in `call-library.json`, then
`retest_entries` for those IDs. `PARTIAL — redirect — check base_url` means a 3xx — usually a
missing trailing path segment or `http` vs `https`.

## Tokens and the demo `.gh` files

`demos/*.gh` are committed and shipped by `pr-docs`, so the pipeline blanks the Token panel before
saving them (Phase 12 Step B). When opening a demo at Gate 6, paste your token into the Token panel
first. If you find a real token in a saved demo (pre-1.0.0 builds), blank it and
rotate the token.

## Auth / token

Phases 7 (and the live test) make real HTTP calls and read the token from the
`PLEASE_REST_TOKEN` environment variable. Set it before the auth verify:
```
export PLEASE_REST_TOKEN="…"      # bash
$env:PLEASE_REST_TOKEN = "…"      # PowerShell
```
Token readiness is re-derived from the actual environment on resume — a persisted "ready" flag
is never trusted on its own. The token is never passed as an MCP tool argument (the tester reads
the env var), never written to `call-library-validated.json` or `session.json`, and never saved in
a demo `.gh`. OAuth2 access tokens (Google APIs: ~1 hour) expire mid-run: on a 401 the tester
halts and writes what it has; refresh the token and `retest_entries` the remaining IDs.
