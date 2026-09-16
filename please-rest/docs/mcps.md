# MCP Servers

PleaseREST ships three MCP servers, declared in `.claude-plugin/plugin.json` and launched with
`python`. Because they are **plugin** servers, Claude Code namespaces their tools as
`mcp__plugin_please-rest_<server>__<tool>` — not the bare `mcp__<server>__*`.

```json
"mcpServers": {
  "pr-api-extractor":  { "command": "python", "args": ["${CLAUDE_PLUGIN_ROOT}/mcps/pr-api-extractor/server.py"] },
  "pr-api-tester":     { "command": "python", "args": ["${CLAUDE_PLUGIN_ROOT}/mcps/pr-api-tester/server.py"] },
  "pr-icon-generator": { "command": "python", "args": ["${CLAUDE_PLUGIN_ROOT}/mcps/pr-icon-generator/server.py"] }
}
```

> **Dependencies** (per each server's `requirements.txt`): `mcp[cli]`, `httpx`; the icon
> generator adds `resvg-py`, `pillow`; the extractor adds `pyyaml`, `beautifulsoup4`. Python ≥ 3.10.
> Install them into the Python that Claude Code launches MCP servers with:
> `pip install -r mcps/pr-api-extractor/requirements.txt -r mcps/pr-api-tester/requirements.txt -r mcps/pr-icon-generator/requirements.txt`.
> `/rest-new-plugin`'s preflight checks this before intake.

Verify all three are connected with `/mcp`. If one shows **not loaded**, see
[troubleshooting](troubleshooting.md#mcp-server-shows-not-loaded).

---

## `pr-api-extractor`

Crawls API docs or parses an OpenAPI spec / Google API Discovery document, and writes
`call-library.json`.

| Tool | Purpose |
|---|---|
| `extract_from_openapi(spec_url, component_list, output_path?)` | Auto-detects OpenAPI (`paths`) vs Google Discovery (`resources → methods`); fills each entry's `base_url` / `auth_in` |
| `extract_from_docs(docs_url, endpoint_path, method, component_name, endpoint_id, output_path?)` | Extract one endpoint from prose docs |
| `write_call_library(entries, output_path)` | Write a call library from prepared entries |

Status tags on entries: `EXTRACTED` · `PARTIAL` (write endpoint with no resolvable body —
enrich before testing) · `AMBIGUOUS` (oneOf/anyOf) · `MISSING`.

Each entry also carries `auth_in` — `"header"` (Authorization: Bearer), `"header:<HeaderName>"`
(raw token in a named header, e.g. `X-API-Key`) or `"query:<param>"` — filled from the spec's
`securitySchemes` / `security`; `body_required` (required top-level body fields) and `content_type`.
Handles OpenAPI 3 (incl. `examples`, server variables), Swagger 2.0, and Google Discovery docs
(`rootUrl` + `servicePath` → `base_url`).

## `pr-api-tester`

Fires real HTTP calls and writes `call-library-validated.json`.

| Tool | Purpose |
|---|---|
| `test_endpoint(entry, token?, seed_ids?, base_url?)` | Test one endpoint (token falls back to `PLEASE_REST_TOKEN`) |
| `run_all_tests(call_library_path, output_path, token?, skip_destructive?, base_url?, seed_ids?)` | Test the whole library; DELETEs are `skip_destructive` by default; `seed_ids` seeds path params |
| `retest_entries(entry_ids, call_library_path, output_path, token?, base_url?, seed_ids?)` | Retest specific entries (used by `pr-api-scout`, and for 401 mid-run resume) |

Joins a `base_url` to relative `url_template`s (entry `base_url` wins over the arg). Token
placement follows the entry's `auth_in` (`header` → `Authorization: Bearer`; `header:<Name>` →
raw token in that header; `query:<param>`). Reads the token from the `PLEASE_REST_TOKEN` env var —
never pass it as an argument. Seed IDs are harvested from every 2xx response (both `boardId` and
`board_id` forms); the response is parsed in full, and only the stored `response_body` is
truncated to 2000 chars. Each `test_result` carries `tag`, `status_code`, `error` and `error_body`
(the first 500 chars of a failing response, for `pr-api-scout`).

**What is not tested:** `PARTIAL` entries (no request body example) are never fired with an empty
body — they are listed as "skipped — PARTIAL (enrich example_request, then retest_entries)" and
written with tag `PARTIAL`. Redirects (3xx) tag `PARTIAL` with "redirect — check base_url". 429s
honour `Retry-After`.

## `pr-icon-generator`

Renders layered icons and injects them into the plugin's resources. Driven by `icons.json`
(authored by `pr-icons` after the spec is final).

| Tool | Purpose |
|---|---|
| `generate_icon(component_name, config_path, subcategory?, iconify_id?)` | One 24×24 component icon |
| `generate_plugin_icon(config_path, size?, out_name?)` | The 16×16 plugin / ribbon category icon; `size=1024, out_name="[XX]_Plugin_Icon.png"` renders the large README / Food4Rhino logo to the plugin root instead |
| `list_background_shapes()` | The background shape names currently available |
| `preview_backgrounds(output_dir, fg_iconify_id?, styles?, shapes?, size?, fill?, gradient_from?, gradient_to?, gradient_angle?, fg_color?, bg_icon_iconify_id?)` | Render every shape in each fill style so the options can be **seen** before choosing |
| `add_to_resources(component_name, config_path)` | Embed a generated PNG into `Resources.resx` + `Resources.Designer.cs` |

**Seeing the options.** `preview_backgrounds` renders every shape × requested style through the same
path `generate_icon` uses, so a preview is exactly what you'd get. `styles` is any of
`gradient` (two-colour linear gradient), `solid` (one flat colour) and `none` (no background at all —
the glyph alone, rendered once as `preview_none.png`); `shapes` narrows it to named slugs. It writes
`preview_<slug>_<style>.png` per tile plus a labelled `contact-sheet.png` into `output_dir`, and
returns a catalog with paste-ready `icons.json` snippets and every slug. Pass
`bg_icon_iconify_id` to see the watermark layer as well. `/rest-icon-preview` wraps it.
It needs no `icons.json` — it takes its colours as arguments, so it works before a plugin exists.

Rendering composes independent optional layers — a background shape (solid or gradient), a
background Iconify glyph, and a foreground glyph — any colour or gradient via silhouette+tint,
rendered at 4× and downscaled with LANCZOS. There is no drop-shadow layer. The foreground glyph is
always trimmed to its own ink before placing — Iconify glyphs carry internal viewBox padding that
would otherwise leave the icon visibly smaller than intended — so it fills ~95-100% of its target
area: the full 24px canvas with no background, or the authored glyph box on a background shape.
`icons.json` is re-read from disk on every call (never cached), so edits are always picked up.
Always pass `config_path` = the plugin's `icons.json`. A component with `"custom": true` is
skipped by `generate_icon` (a hand-made PNG in `Icons/` is kept); `"background": {}` really removes
the inherited background. `add_to_resources` shells out to PowerShell and is **Windows-only**.

**Background shapes are artwork, not code.** They're the SVG files in the MCP's `backgrounds/`
folder, addressed by filename slug — `bg-icon_Arrow-Square.svg` becomes `"type": "arrow-square"`.
Run `list_background_shapes()` for the current set. Foreground and background *glyphs* still come
from Iconify by `prefix:name`.

Each shape SVG holds both halves of the design: the background silhouette, and a `#ed1c24` rect
marking where the foreground glyph sits. That rect is stripped before rendering — it never appears
in output — and read as the glyph's placement, so **where the icon lands is a drawing decision, not
a setting**. To add a shape, draw it in a square viewBox with unfilled paths, add its glyph box, and
save as `bg-icon_<Name>.svg`; it works immediately with no code change. Raster `<image>` elements are
rejected, since a bitmap can't be tinted.

A few shapes (`trapezoid`, `saddle-shape`, `database`, `l-border`, `quarter-circle-right`,
`right-triangle`, `half-circle`) put the glyph box partly outside the artwork on purpose — the shape
acts as a base under the glyph rather than a container. Use a dark foreground with these; a white
glyph vanishes where it leaves the shape.

---

## External: the Grasshopper MCP bridge

The Phase 12 **live** Rhino test (`pr-rhino-test`) needs a Grasshopper MCP bridge to place,
wire, solve, and read components on a live canvas. This is **not shipped** by PleaseREST — you
wire it in once (official `mcneel/RhinoMCP`, or the community `cordyceps` / `SandMartin`
fallbacks). Its server name is chosen at registration and discovered at runtime, so it is never
hardcoded. See [troubleshooting](troubleshooting.md#grasshopper-mcp-bridge).
