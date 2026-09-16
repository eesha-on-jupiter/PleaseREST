"""
PleaseREST — pr-api-extractor MCP server
---------------------------------------
Crawls API docs or parses an OpenAPI spec (or a Google API Discovery doc). Extracts
the full request shape for every endpoint in a component list. Writes call-library.json.

Tools:
  extract_from_openapi(spec_url, component_list, output_path)
  extract_from_docs(docs_url, endpoint_path, method, component_name, output_path)
  write_call_library(entries, output_path)

Entry status: EXTRACTED (full shape) · PARTIAL (write endpoint with no resolvable
request body — enrich before testing/building) · AMBIGUOUS (oneOf/anyOf body) ·
MISSING (endpoint not found in the spec).

Spec formats: OpenAPI 3.x (`paths`), Swagger 2.0 (`swagger: "2.0"`), Google API Discovery
(`resources` → `methods`). Each entry carries `base_url`, `auth_in` (from the spec's security
schemes: "header" = Bearer, "header:<Name>" = API key header, "query:<param>" = token in query),
`body_required` (required top-level body fields) and `content_type`.

All progress output goes to stderr — stdout is the JSON-RPC stream of a stdio MCP server.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pr-api-extractor")

def _log(msg: str) -> None:
    """Progress output for a stdio MCP server MUST go to stderr — stdout is the JSON-RPC stream."""
    print(msg, file=sys.stderr, flush=True)

# ── Entry schema ───────────────────────────────────────────────────────────────

def blank_entry(endpoint_id: str, component: str, method: str, url_template: str) -> dict:
    return {
        "endpoint_id":       endpoint_id,
        "component":         component,
        "method":            method.upper(),
        "url_template":      url_template,
        "base_url":          "",          # origin to prepend when url_template is relative (pr-api-tester)
        "auth_in":           "header",    # "header" (Bearer) | "header:<Name>" | "query:<param>"
        "path_params":       [],
        "query_params":      [],
        "headers":           {"Authorization": "Bearer {token}"},
        "body_schema":       None,
        "body_required":     [],          # required top-level body field names (shape of body_schema unchanged)
        "content_type":      "application/json",
        "response_schema":   None,
        "example_request":   {},
        "example_response":  {},
        "notes":             "",
        "status":            "EXTRACTED",
    }

# ── $ref resolution ────────────────────────────────────────────────────────────

def resolve_refs(obj: Any, root: dict, visited: frozenset = frozenset(), memo: dict | None = None) -> Any:
    """Recursively resolve all $ref pointers in an OpenAPI schema fragment.

    `visited` breaks true cycles (a ref that transitively contains itself) along the
    current path. `memo` caches each ref's fully-resolved result for the lifetime of one
    top-level resolve_refs call, so a schema reached from many different parents (e.g. a
    recursive block/document union reused across dozens of sibling schemas — see GitBook's
    Document/Block model) is expanded once instead of re-walked from scratch every time
    it's encountered. Without this, resolution cost is exponential in the number of
    distinct paths through a heavily-shared/recursive schema graph, which hung this tool
    indefinitely on a GitBook-backed API's apply_change_request_content body. (dogfood TOOL F1)
    """
    if memo is None:
        memo = {}
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref = obj["$ref"]
            if ref in visited:
                return {"description": f"circular ref: {ref}"}
            if ref in memo:
                return memo[ref]
            if not ref.startswith("#"):
                # External file ref (common.yaml#/...) — not fetched. Marked so the caller can
                # flag the entry PARTIAL instead of silently emitting {"type": "object"}.
                return {"__external_ref__": ref}
            parts = [_unescape_pointer(x) for x in ref.lstrip("#/").split("/") if x != ""]
            node: Any = root
            for part in parts:
                if isinstance(node, dict):
                    node = node.get(part, {})
                elif isinstance(node, list):
                    try:
                        node = node[int(part)]
                    except (ValueError, IndexError):
                        node = {}
                else:
                    node = {}
            resolved = resolve_refs(node, root, visited | {ref}, memo)
            memo[ref] = resolved
            return resolved
        return {k: resolve_refs(v, root, visited, memo) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_refs(item, root, visited, memo) for item in obj]
    return obj

def _unescape_pointer(part: str) -> str:
    """JSON-pointer escapes: ~1 → '/', ~0 → '~' (RFC 6901)."""
    return part.replace("~1", "/").replace("~0", "~")

def has_external_ref(obj: Any) -> bool:
    """True if a resolved fragment still contains an unresolved external $ref marker."""
    if isinstance(obj, dict):
        if "__external_ref__" in obj:
            return True
        return any(has_external_ref(v) for v in obj.values())
    if isinstance(obj, list):
        return any(has_external_ref(v) for v in obj)
    return False

def schema_required(schema: dict | None) -> list:
    """Top-level required field names of a resolved object schema (allOf parts merged)."""
    if not isinstance(schema, dict):
        return []
    req = list(schema.get("required") or [])
    for part in schema.get("allOf") or []:
        if isinstance(part, dict):
            req += [r for r in (part.get("required") or []) if r not in req]
    return [r for r in req if isinstance(r, str)]

# ── Schema simplification ──────────────────────────────────────────────────────

def simplify_schema(schema: dict | None) -> dict | None:
    """Flatten an OpenAPI schema to {field: type} pairs for readability."""
    # an absent schema is None; an empty dict is a valid unconstrained schema
    if schema is None:
        return None
    if not isinstance(schema, dict):
        return None

    # oneOf / anyOf — mark ambiguous, return all variants
    for combiner in ("oneOf", "anyOf"):
        if combiner in schema:
            variants = [simplify_schema(v) for v in schema[combiner]]
            return {"__ambiguous__": combiner, "variants": variants}

    # allOf — composition (Stripe/GitHub style): merge every part's properties into one object
    if isinstance(schema.get("allOf"), list):
        merged_props: dict = {}
        for part in schema["allOf"]:
            if isinstance(part, dict):
                merged_props.update(part.get("properties", {}) or {})
        merged_props.update(schema.get("properties", {}) or {})
        if merged_props:
            return {k: (v.get("type") or v.get("$ref") or "object") if isinstance(v, dict) else "object"
                    for k, v in merged_props.items()}

    props = schema.get("properties", {})
    if props:
        return {k: (v.get("type") or v.get("$ref") or "object") for k, v in props.items()}

    # array type
    if schema.get("type") == "array":
        items = schema.get("items")
        return {"__array__": simplify_schema(items)}

    return {"type": schema.get("type", "object")}

# ── Parameter extraction ───────────────────────────────────────────────────────

def extract_params(parameters: list, root: dict) -> tuple[list, list]:
    """Split resolved parameters into path_params and query_params lists."""
    path_params, query_params = [], []
    for p in parameters:
        p = resolve_refs(p, root)
        schema = p.get("schema", {})
        record = {
            "name":     p.get("name", ""),
            "type":     schema.get("type", "string"),
            "required": p.get("required", False),
        }
        if p.get("in") == "path":
            record["required"] = True
            path_params.append(record)
        elif p.get("in") == "query":
            query_params.append(record)
    return path_params, query_params

# ── OpenAPI body extraction ────────────────────────────────────────────────────

BODY_MIMES = ("application/json", "application/x-www-form-urlencoded", "multipart/form-data")

def extract_body_schema(operation: dict, root: dict) -> tuple[dict | None, bool]:
    """Return (simplified_schema, is_ambiguous) from requestBody."""
    simplified, ambiguous, _raw, _ct = extract_body_details(operation, root)
    return simplified, ambiguous

def extract_body_details(operation: dict, root: dict) -> tuple[dict | None, bool, dict | None, str]:
    """Return (simplified_schema, is_ambiguous, raw_resolved_schema, content_type) from requestBody."""
    rb = resolve_refs(operation.get("requestBody", {}) or {}, root)
    content = rb.get("content", {}) if isinstance(rb, dict) else {}
    schema = None
    content_type = "application/json"
    for mime in BODY_MIMES:
        if mime in content:
            schema = resolve_refs((content[mime] or {}).get("schema", {}), root)
            content_type = mime
            break
    if schema is None and content:
        content_type, first = next(iter(content.items()))
        schema = resolve_refs((first or {}).get("schema", {}), root)
    simplified = simplify_schema(schema)
    ambiguous = isinstance(simplified, dict) and "__ambiguous__" in simplified
    return simplified, ambiguous, schema, content_type

def first_example(media: dict | None, schema: dict | None) -> dict:
    """Best request/response example for a media-type object: `example`, else the first entry
    of the OpenAPI 3 `examples` map (its `value`), else a schema-level `example` / `default`."""
    media = media or {}
    ex = media.get("example")
    if isinstance(ex, dict) and ex:
        return ex
    examples = media.get("examples")
    if isinstance(examples, dict):
        for v in examples.values():
            val = v.get("value") if isinstance(v, dict) else None
            if isinstance(val, dict) and val:
                return val
    if isinstance(schema, dict):
        for key in ("example", "default"):
            val = schema.get(key)
            if isinstance(val, dict) and val:
                return val
    return {}

# ── OpenAPI response extraction ────────────────────────────────────────────────

def extract_response_schema(operation: dict, root: dict) -> dict | None:
    responses = operation.get("responses", {})
    for code in ("200", "201", "204"):
        if code in responses:
            resp = resolve_refs(responses[code], root)
            content = resp.get("content", {})
            for mime in ("application/json", "*/*"):
                if mime in content:
                    schema = resolve_refs(content[mime].get("schema", {}), root)
                    return simplify_schema(schema)
            return None
    return None

# ── Security schemes → auth_in ─────────────────────────────────────────────────

def auth_in_from_spec(spec: dict, operation: dict | None = None) -> str:
    """Derive the entry's auth_in from OpenAPI 3 securitySchemes / Swagger 2 securityDefinitions.

    Picks the first scheme named by the operation's `security` (else the global `security`,
    else the first defined scheme):
      http bearer / oauth2 / openIdConnect → "header"           (Authorization: Bearer)
      apiKey in header                     → "header:<Name>"    (raw token in that header)
      apiKey in query                      → "query:<param>"
      http basic                           → "header"           (noted by caller)
    """
    schemes = ((spec.get("components") or {}).get("securitySchemes")
               or spec.get("securityDefinitions") or {})
    if not isinstance(schemes, dict) or not schemes:
        return "header"
    requirement = None
    for source in ((operation or {}).get("security"), spec.get("security")):
        if isinstance(source, list) and source:
            requirement = source[0]
            break
    names = list(requirement.keys()) if isinstance(requirement, dict) and requirement else list(schemes.keys())
    for name in names:
        sch = schemes.get(name)
        if not isinstance(sch, dict):
            continue
        typ = str(sch.get("type", "")).lower()
        if typ == "apikey":
            loc = str(sch.get("in", "header")).lower()
            pname = sch.get("name") or "api_key"
            if loc == "query":
                return f"query:{pname}"
            if loc == "header":
                return "header" if pname.lower() == "authorization" else f"header:{pname}"
            continue  # cookie → unsupported, try the next
        return "header"  # http (bearer/basic), oauth2, openIdConnect
    return "header"

def apply_auth_in(entry: dict, auth_in: str) -> None:
    """Set auth_in and keep the headers template consistent with it."""
    entry["auth_in"] = auth_in
    if auth_in.startswith("header:"):
        entry["headers"].pop("Authorization", None)
        entry["headers"][auth_in.split(":", 1)[1]] = "{token}"
    elif auth_in.startswith("query:"):
        entry["headers"].pop("Authorization", None)

# ── Swagger 2.0 ────────────────────────────────────────────────────────────────

def is_swagger2(spec: dict) -> bool:
    return isinstance(spec, dict) and str(spec.get("swagger", "")).startswith("2")

def swagger2_body(operation: dict, path_obj: dict, root: dict) -> tuple[dict | None, bool, dict | None, str]:
    """Swagger 2.0 request body: the single `in: body` parameter's `schema`; form params otherwise."""
    params = [resolve_refs(p, root) for p in (path_obj.get("parameters", []) + operation.get("parameters", []))]
    consumes = operation.get("consumes") or root.get("consumes") or ["application/json"]
    content_type = consumes[0] if isinstance(consumes, list) and consumes else "application/json"
    for p in params:
        if isinstance(p, dict) and p.get("in") == "body":
            schema = resolve_refs(p.get("schema", {}), root)
            simplified = simplify_schema(schema)
            ambiguous = isinstance(simplified, dict) and "__ambiguous__" in simplified
            return simplified, ambiguous, schema, content_type
    form = {p["name"]: p.get("type", "string") for p in params
            if isinstance(p, dict) and p.get("in") == "formData" and p.get("name")}
    if form:
        return form, False, {"properties": {k: {"type": v} for k, v in form.items()},
                             "required": [p["name"] for p in params
                                          if isinstance(p, dict) and p.get("in") == "formData" and p.get("required")]}, \
               "application/x-www-form-urlencoded"
    return None, False, None, content_type

def swagger2_response(operation: dict, root: dict) -> tuple[dict | None, dict]:
    responses = operation.get("responses", {}) or {}
    for code in ("200", "201", "204"):
        if code in responses:
            resp = resolve_refs(responses[code], root) or {}
            schema = resolve_refs(resp.get("schema"), root) if resp.get("schema") is not None else None
            example = {}
            ex = resp.get("examples")
            if isinstance(ex, dict):
                for v in ex.values():
                    if isinstance(v, dict) and v:
                        example = v
                        break
            return simplify_schema(schema), example
    return None, {}

# ── Google API Discovery format ─────────────────────────────────────────────────
# Google APIs (Slides, Sheets, Docs, Drive, Gmail, Calendar, …) publish a Google API
# *Discovery* document, NOT OpenAPI: top-level `resources` → `methods` (with `path`,
# `httpMethod`, `parameters`, `request.$ref`, `response.$ref`) and a top-level `schemas`
# map. The OpenAPI walker keys off `paths{}`, which a discovery doc has none of, so every
# endpoint comes back MISSING. These helpers walk the discovery shape instead. (dogfood Slides F2)

def is_discovery_spec(spec: dict) -> bool:
    """True for a Google API Discovery document (resources→methods), not OpenAPI (paths)."""
    return isinstance(spec, dict) and "paths" not in spec and (
        "discoveryVersion" in spec or "resources" in spec)

def collect_discovery_methods(spec: dict) -> dict:
    """Walk resources[].methods[] (recursively, resources nest) → {(path, METHOD): method_obj}."""
    out: dict = {}

    def walk(resources: dict):
        for res in (resources or {}).values():
            for m in (res.get("methods") or {}).values():
                norm_path = "/" + m.get("path", "").lstrip("/")
                out[(norm_path, m.get("httpMethod", "GET").upper())] = m
            if res.get("resources"):
                walk(res["resources"])

    walk(spec.get("resources", {}))
    return out

def extract_discovery_params(params: dict) -> tuple[list, list]:
    """Split a discovery `parameters` dict into path_params and query_params."""
    path_params, query_params = [], []
    for name, p in (params or {}).items():
        record = {"name": name, "type": p.get("type", "string"), "required": p.get("required", False)}
        if p.get("location") == "path":
            record["required"] = True
            path_params.append(record)
        else:  # discovery defaults non-path params to query
            query_params.append(record)
    return path_params, query_params

def discovery_schema(ref_obj: dict | None, spec: dict) -> dict | None:
    """Resolve a discovery request/response {'$ref': 'Name'} against top-level `schemas`, simplified."""
    if not ref_obj:
        return None
    ref = ref_obj.get("$ref")
    schema = spec.get("schemas", {}).get(ref) if ref else ref_obj
    return simplify_schema(schema)

def spec_base_url(spec: dict, discovery: bool) -> str:
    """Best-effort origin/base for relative url_templates, written onto each entry's base_url.

    OpenAPI: servers[0].url (the spec guarantees full = server.url + pathKey). Discovery: the
    scheme://host origin of rootUrl/baseUrl (Google method paths carry the version, so the origin
    joins cleanly with a component path like '/v1/presentations'). (dogfood Docs F3 / Slides F3)
    """
    if discovery:
        root = spec.get("rootUrl") or spec.get("baseUrl") or ""
        p = urlparse(root)
        if not (p.scheme and p.netloc):
            return ""
        # rootUrl + servicePath — Drive is https://www.googleapis.com/ + drive/v3/, so dropping
        # servicePath would call https://www.googleapis.com/files/{id}. Slides/Docs/Sheets have an
        # empty servicePath (their method paths carry the version), so this is a no-op there.
        service_path = str(spec.get("servicePath") or "").strip("/")
        base = f"{p.scheme}://{p.netloc}"
        return f"{base}/{service_path}" if service_path else base
    if is_swagger2(spec):
        host = spec.get("host")
        if not host:
            return ""
        schemes = spec.get("schemes") or ["https"]
        scheme = "https" if "https" in schemes else schemes[0]
        base_path = str(spec.get("basePath") or "").rstrip("/")
        return f"{scheme}://{host}{base_path}"
    servers = spec.get("servers") or []
    if isinstance(servers, list) and servers and isinstance(servers[0], dict):
        url = servers[0].get("url", "") or ""
        # Substitute server variables with their defaults: https://{region}.api.x.com/{basePath}
        for var, meta in (servers[0].get("variables") or {}).items():
            default = (meta or {}).get("default") if isinstance(meta, dict) else None
            if default is not None:
                url = url.replace("{" + var + "}", str(default))
        return url
    return ""

# ── Tool: extract_from_openapi ─────────────────────────────────────────────────

@mcp.tool()
async def extract_from_openapi(spec_url: str, component_list: list[dict],
                                output_path: str | None = None) -> str:
    """
    Fetch an OpenAPI spec OR a Google API Discovery doc (JSON or YAML), resolve refs, and
    extract the full call shape for each entry in component_list.

    Auto-detects the format: an OpenAPI spec is walked via `paths{}`; a Google API Discovery
    doc (Slides/Sheets/Docs/Drive/Gmail/Calendar — has `resources`/`discoveryVersion`, no
    `paths`) is walked via `resources[].methods[]`. Point this at
    `https://<api>.googleapis.com/$discovery/rest?version=v1` for Google APIs.

    Args:
        spec_url:       URL or file path to the OpenAPI spec or Google Discovery doc (JSON/YAML).
        component_list: List of {endpoint_id, component, method, path} dicts to extract.
                        Example: [{"endpoint_id": "get_board", "component": "GetBoardComponent",
                                   "method": "GET", "path": "/v2/boards/{board_id}"}]
        output_path:    If provided, writes call-library.json to this path.

    Returns:
        JSON string of extracted entries, plus a summary line. A write endpoint whose request
        body cannot be resolved is tagged PARTIAL (not EXTRACTED) so it gets enriched.
    """
    _log(f"Restling through {len(component_list)} endpoints...")

    # Load spec
    try:
        if spec_url.startswith("http://") or spec_url.startswith("https://"):
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(spec_url)
                resp.raise_for_status()
                raw = resp.text
        else:
            raw = Path(spec_url).read_text(encoding="utf-8")
    except Exception as e:
        return f"Restling failed — could not load spec: {e}"

    # Parse JSON or YAML
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError:
        try:
            spec = yaml.safe_load(raw)
        except Exception as e:
            return f"Restling failed — could not parse spec as JSON or YAML: {e}"
    if not isinstance(spec, dict):
        return ("Restling failed — spec is not a JSON/YAML object (got HTML or a scalar?). "
                f"Check that {spec_url} is the raw spec, not a docs page.")

    discovery    = is_discovery_spec(spec)
    swagger2     = (not discovery) and is_swagger2(spec)
    disc_methods = collect_discovery_methods(spec) if discovery else {}
    if discovery:
        _log("  Google API Discovery format detected — walking resources[].methods[].")
    elif swagger2:
        _log("  Swagger 2.0 detected — reading host/basePath, in:body params, response schema.")
    base_url = spec_base_url(spec, discovery)
    base_note = ""
    if base_url and not base_url.startswith(("http://", "https://")):
        base_note = f"relative server URL '{base_url}' — set base_url on the entry or pass it to run_all_tests"
    global_auth_in = auth_in_from_spec(spec)
    paths = spec.get("paths", {}) if isinstance(spec.get("paths"), dict) else {}
    entries = []
    extracted = ambiguous = partial = missing = 0

    for item in component_list:
        endpoint_id = item.get("endpoint_id", "")
        component   = item.get("component", "")
        method      = item.get("method", "GET").upper()
        path        = item.get("path", "")

        entry = blank_entry(endpoint_id, component, method, path)
        if base_url:
            entry["base_url"] = base_url
        extra_notes: list[str] = [base_note] if base_note else []
        apply_auth_in(entry, global_auth_in)

        is_ambiguous = False
        raw_body = None

        if discovery:
            operation = disc_methods.get((path, method))
            if operation is None:
                entry["status"] = "MISSING"
                entry["notes"] = f"'{method} {path}' not found in discovery doc"
                missing += 1
                entries.append(entry)
                continue
            entry["path_params"], entry["query_params"] = extract_discovery_params(
                operation.get("parameters", {}))
            entry["body_schema"]     = discovery_schema(operation.get("request"), spec)
            entry["response_schema"] = discovery_schema(operation.get("response"), spec)
            req_ref = (operation.get("request") or {}).get("$ref")
            raw_body = (spec.get("schemas") or {}).get(req_ref) if req_ref else None
            entry["body_required"] = schema_required(raw_body)
            if operation.get("parameterOrder"):
                extra_notes.append(f"parameterOrder: {operation['parameterOrder']}")
        else:
            path_obj = paths.get(path)
            if path_obj is None:
                entry["status"] = "MISSING"
                entry["notes"] = f"Path '{path}' not found in spec"
                missing += 1
                entries.append(entry)
                continue

            operation = path_obj.get(method.lower())
            if operation is None:
                entry["status"] = "MISSING"
                entry["notes"] = f"Method {method} not found for path '{path}'"
                missing += 1
                entries.append(entry)
                continue

            # Parameters (merge path-level and operation-level)
            all_params = path_obj.get("parameters", []) + operation.get("parameters", [])
            entry["path_params"], entry["query_params"] = extract_params(all_params, spec)

            # Per-operation security overrides the global scheme
            if operation.get("security") is not None:
                apply_auth_in(entry, auth_in_from_spec(spec, operation))

            if swagger2:
                body, is_ambiguous, raw_body, content_type = swagger2_body(operation, path_obj, spec)
                entry["body_schema"]   = body
                entry["content_type"]  = content_type
                entry["response_schema"], entry["example_response"] = swagger2_response(operation, spec)
            else:
                # Body schema (+ raw for required fields, content type)
                body, is_ambiguous, raw_body, content_type = extract_body_details(operation, spec)
                entry["body_schema"]  = body
                entry["content_type"] = content_type

                # Response schema
                entry["response_schema"] = extract_response_schema(operation, spec)

                # Examples — `example`, the OpenAPI 3 `examples` map, or schema example/default
                rb = resolve_refs(operation.get("requestBody", {}) or {}, spec)
                content = rb.get("content", {}) if isinstance(rb, dict) else {}
                media = content.get(content_type) or content.get("application/json")
                entry["example_request"] = first_example(media, raw_body)

                responses = operation.get("responses", {})
                for code in ("200", "201"):
                    if code in responses:
                        resp_obj = resolve_refs(responses[code], spec)
                        resp_content = resp_obj.get("content", {}) if isinstance(resp_obj, dict) else {}
                        resp_media = resp_content.get("application/json") or (
                            next(iter(resp_content.values())) if resp_content else None)
                        resp_schema = (resp_media or {}).get("schema") if isinstance(resp_media, dict) else None
                        entry["example_response"] = first_example(resp_media, resp_schema)
                        break

            entry["body_required"] = schema_required(raw_body)
            if entry["content_type"] not in ("application/json", None):
                extra_notes.append(f"request content type {entry['content_type']} — pr-api-tester sends "
                                   f"JSON only; validate form/multipart calls by hand")
            if has_external_ref(raw_body) or has_external_ref(entry.get("response_schema")):
                extra_notes.append("external $ref (another file) not resolved — enrich the schema")
                if method in ("POST", "PUT", "PATCH"):
                    entry["body_schema"] = None if not (raw_body or {}).get("properties") else entry["body_schema"]

        # Pagination detection
        param_names = [p["name"] for p in entry["query_params"]]
        for pg_key in ("cursor", "page", "offset", "next_page_token", "after",
                       "pageToken", "page_token", "starting_after", "since", "next"):
            if pg_key in param_names:
                extra_notes.insert(0, f"Paginated — pagination key: {pg_key}")
                break

        entry["notes"] = " | ".join(extra_notes)

        if is_ambiguous:
            entry["status"] = "AMBIGUOUS"
            entry["notes"] = (entry["notes"] + " | body schema uses oneOf/anyOf").lstrip(" | ")
            ambiguous += 1
        elif method in ("POST", "PUT", "PATCH") and entry["body_schema"] is None:
            # A write endpoint with no resolvable request body is NOT fully extracted. Common when
            # docs render the body client-side (JS) or a discovery $ref didn't resolve. Flag PARTIAL
            # rather than a misleading EXTRACTED so it gets enriched before the client is built.
            # (dogfood Docs F2 / Sheets F1)
            entry["status"] = "PARTIAL"
            entry["notes"] = (entry["notes"] +
                              " | no request body_schema resolved — enrich before building").lstrip(" | ")
            partial += 1
        else:
            entry["status"] = "EXTRACTED"
            extracted += 1

        entries.append(entry)
        _log(f"  Restling through {endpoint_id}... {entry['status']}")

    if output_path:
        _write_json(entries, output_path)

    summary = (
        f"\nRestling complete.\n"
        f"  Extracted:  {extracted}\n"
        f"  Partial:    {partial}\n"
        f"  Ambiguous:  {ambiguous}\n"
        f"  Missing:    {missing}\n"
    )
    if partial:
        summary += "  PARTIAL entries have an unresolved request body — enrich before Phase 7/9.\n"
    if output_path:
        summary += f"  Written to: {output_path}\n"
    _log(summary)
    return json.dumps(entries, indent=2) + "\n" + summary

# ── Tool: extract_from_docs ────────────────────────────────────────────────────

@mcp.tool()
async def extract_from_docs(docs_url: str, endpoint_path: str, method: str,
                             component_name: str, endpoint_id: str,
                             output_path: str | None = None) -> str:
    """
    Fetch one endpoint's docs page and parse the call shape from HTML.
    Handles common docs platforms: Readme.io, GitBook, Stoplight, Redoc, raw HTML.
    Does NOT attempt headless rendering — marks MISSING if JS-only.

    Args:
        docs_url:       URL of the specific endpoint docs page.
        endpoint_path:  URL path template e.g. '/v2/boards/{board_id}'
        method:         HTTP method e.g. 'GET'
        component_name: e.g. 'GetBoardComponent'
        endpoint_id:    e.g. 'get_board'
        output_path:    If provided, appends/writes this single entry to call-library.json.

    Returns:
        JSON string of the single extracted entry.
    """
    entry = blank_entry(endpoint_id, component_name, method, endpoint_path)

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(docs_url, headers={"User-Agent": "PleaseREST/1.0"})
    except httpx.TimeoutException:
        entry["status"] = "MISSING"
        entry["notes"] = "Request timed out"
        return json.dumps(entry, indent=2)
    except (httpx.HTTPError, ValueError) as e:   # ConnectError, InvalidURL, UnsupportedProtocol…
        entry["status"] = "MISSING"
        entry["notes"] = f"Could not fetch docs page: {type(e).__name__}: {e}"
        return json.dumps(entry, indent=2)

    if resp.status_code == 404:
        entry["status"] = "MISSING"
        entry["notes"] = "Docs page returned 404"
        return json.dumps(entry, indent=2)

    if not resp.is_success:
        entry["status"] = "MISSING"
        entry["notes"] = f"Docs page returned HTTP {resp.status_code}"
        return json.dumps(entry, indent=2)

    html = resp.text

    # If the page is essentially empty (JS-only), mark MISSING
    soup = BeautifulSoup(html, "html.parser")
    visible_text = soup.get_text(separator=" ", strip=True)
    if len(visible_text) < 200:
        entry["status"] = "MISSING"
        entry["notes"] = "Docs page requires JavaScript to render — cannot extract"
        return json.dumps(entry, indent=2)

    notes = []
    ambiguous = False

    # Extract path parameters from URL template
    path_params = re.findall(r"\{(\w+)\}", endpoint_path)
    entry["path_params"] = [{"name": p, "type": "string", "required": True} for p in path_params]

    # Look for parameter tables (common in Readme.io, Stoplight)
    tables = soup.find_all("table")
    for table in tables:
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if not any(h in headers for h in ("name", "parameter", "param")):
            continue
        name_idx = next((i for i, h in enumerate(headers) if h in ("name", "parameter", "param")), None)
        type_idx = next((i for i, h in enumerate(headers) if "type" in h), None)
        req_idx  = next((i for i, h in enumerate(headers) if "required" in h or "req" in h), None)
        in_idx   = next((i for i, h in enumerate(headers) if h in ("in", "location")), None)
        for row in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) <= (name_idx or 0):
                continue
            name     = cells[name_idx] if name_idx is not None else ""
            ptype    = cells[type_idx] if type_idx is not None and type_idx < len(cells) else "string"
            required = cells[req_idx].lower() in ("true", "yes", "required") if req_idx is not None and req_idx < len(cells) else False
            location = cells[in_idx].lower() if in_idx is not None and in_idx < len(cells) else "query"
            if not name:
                continue
            param = {"name": name, "type": ptype, "required": required}
            if location == "path" or name in path_params:
                if not any(p["name"] == name for p in entry["path_params"]):
                    entry["path_params"].append(param)
            else:
                entry["query_params"].append(param)

    # Extract code blocks — look for JSON request/response examples
    code_blocks = [
        el.get_text(strip=True)
        for el in soup.find_all(["code", "pre"])
        if el.get_text(strip=True).startswith("{")
    ]

    json_objects = []
    for block in code_blocks:
        try:
            obj = json.loads(block)
            if isinstance(obj, dict):
                json_objects.append(obj)
        except json.JSONDecodeError:
            pass

    if len(json_objects) == 1:
        # Ambiguous — one block could be request or response
        entry["example_request"]  = json_objects[0]
        entry["example_response"] = json_objects[0]
        notes.append("single JSON example found — assigned to both request and response")
        ambiguous = True
    elif len(json_objects) >= 2:
        entry["example_request"]  = json_objects[0]
        entry["example_response"] = json_objects[1]
        if len(json_objects) > 2:
            notes.append(f"{len(json_objects)} JSON examples found — used first two")
            ambiguous = True

    # Derive body schema from request example if method has a body
    if method.upper() in ("POST", "PUT", "PATCH") and entry["example_request"]:
        entry["body_schema"] = {k: type(v).__name__ for k, v in entry["example_request"].items()}

    # Derive response schema from response example
    if entry["example_response"]:
        entry["response_schema"] = {k: type(v).__name__ for k, v in entry["example_response"].items()}

    parsed_anything = bool(entry["query_params"] or json_objects
                           or [p for p in entry["path_params"] if p["name"] not in path_params])
    if ambiguous:
        entry["status"] = "AMBIGUOUS"
    elif method.upper() in ("POST", "PUT", "PATCH") and entry["body_schema"] is None:
        # Write endpoint, no body parsed — usually a JS-rendered docs page (Google et al.). Mark
        # PARTIAL, not a misleading EXTRACTED, so the body gets enriched. (dogfood Docs F2 / Sheets F1)
        entry["status"] = "PARTIAL"
        notes.append("no request body_schema parsed (likely JS-rendered) — enrich before building")
    elif not parsed_anything:
        # A GET page where nothing beyond the URL template itself was parsed is not "extracted".
        entry["status"] = "PARTIAL"
        notes.append("no params or examples parsed from the page (likely JS-rendered) — verify by hand")
    else:
        entry["status"] = "EXTRACTED"
    entry["notes"] = " | ".join(notes)

    if output_path:
        _append_or_write_entry(entry, output_path)

    return json.dumps(entry, indent=2)

# ── Tool: write_call_library ───────────────────────────────────────────────────

@mcp.tool()
def write_call_library(entries: list[dict], output_path: str) -> str:
    """
    Write a list of call-library entries to call-library.json.

    Args:
        entries:     List of entry dicts (as produced by extract_from_openapi or extract_from_docs).
        output_path: Destination file path.

    Returns:
        Summary string with counts and file path.
    """
    extracted = sum(1 for e in entries if e.get("status") == "EXTRACTED")
    partial   = sum(1 for e in entries if e.get("status") == "PARTIAL")
    ambiguous = sum(1 for e in entries if e.get("status") == "AMBIGUOUS")
    missing   = sum(1 for e in entries if e.get("status") == "MISSING")

    _write_json(entries, output_path)

    return (
        f"Restling complete.\n"
        f"  Extracted:  {extracted}\n"
        f"  Partial:    {partial}\n"
        f"  Ambiguous:  {ambiguous}\n"
        f"  Missing:    {missing}\n"
        f"  Written to: {output_path}\n"
    )

# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_json(data: Any, path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")

def _append_or_write_entry(entry: dict, path: str) -> None:
    p = Path(path)
    if p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = None
        if not isinstance(existing, list):
            # Corrupt or not a list — keep the user's file, start a fresh list.
            p.replace(p.with_suffix(p.suffix + ".bak"))
            existing = []
        existing = [e for e in existing if isinstance(e, dict) and e.get("endpoint_id") != entry["endpoint_id"]]
        existing.append(entry)
        _write_json(existing, path)
    else:
        _write_json([entry], path)

# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
