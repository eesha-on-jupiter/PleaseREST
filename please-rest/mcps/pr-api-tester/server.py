"""
PleaseREST — pr-api-tester MCP server
-------------------------------------
Fires real HTTP calls against every EXTRACTED entry in call-library.json.
Writes call-library-validated.json with per-entry result tags.

Tools:
  test_endpoint(entry, token, seed_ids, base_url)
  run_all_tests(call_library_path, output_path, token, skip_destructive, base_url)
  retest_entries(entry_ids, call_library_path, output_path, token, base_url)

Auth token is read from PLEASE_REST_TOKEN env var. If not set, the tool
returns an error message prompting the user to set it before running.

Relative url_templates are joined to a base URL (the entry's own "base_url" field, else the
base_url argument). Token placement is driven by the entry's "auth_in":
  "header"              → Authorization: Bearer <token>   (default)
  "header:<HeaderName>" → raw token in that header (API-key style, no "Bearer")
  "query:<param>"       → token as that query parameter

All progress output goes to stderr — stdout is the JSON-RPC stream of a stdio MCP server.
"""

import asyncio
import json
import os
import re
import sys
import time
from copy import deepcopy
from pathlib import Path
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pr-api-tester")

DESTRUCTIVE_METHODS = {"DELETE"}
RETRY_LIMIT         = 3
TIMEOUT_RETRIES     = 1
TIMEOUT_SECONDS     = 15.0
RETRY_AFTER_CAP     = 30.0
RESPONSE_BODY_KEEP  = 2000   # chars of response_body kept in results (parsing uses the full text)
ERROR_BODY_KEEP     = 500    # chars of error_body kept for pr-api-scout

def _log(msg: str) -> None:
    """Progress output for a stdio MCP server MUST go to stderr — stdout is the JSON-RPC stream."""
    print(msg, file=sys.stderr, flush=True)

# ── Seed-key naming ────────────────────────────────────────────────────────────

def _to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()

def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])

def seed_key_variants(name: str) -> list[str]:
    """camelCase and snake_case spellings of a seed key (e.g. boardId / board_id), original first."""
    out = [name]
    for v in (_to_camel(name), _to_snake(name)):
        if v not in out:
            out.append(v)
    return out

def lookup_seed(seed_ids: dict, name: str):
    """Look a path/query param up in seed_ids under either its camelCase or snake_case spelling."""
    for key in seed_key_variants(name):
        if key in seed_ids and seed_ids[key] is not None:
            return seed_ids[key]
    return None

# ── URL builder ────────────────────────────────────────────────────────────────

def build_url(url_template: str, path_params: list[dict], seed_ids: dict) -> tuple[str, str]:
    """Fill path parameter placeholders. Returns (filled_url, error_or_empty).

    Seed values are looked up under both camelCase and snake_case spellings of the param name
    and are percent-encoded before substitution. `{+name}` reserved-expansion placeholders
    (Google Cloud / Firestore style) are reported as unfilled with a clear message.
    """
    url = url_template
    for param in path_params:
        name = param["name"]
        placeholder = f"{{{name}}}"
        value = lookup_seed(seed_ids, name)
        if value is None:
            return url, f"Missing seed ID for path param '{name}'"
        url = url.replace(placeholder, quote(str(value), safe=""))
    # Check for any remaining unfilled placeholders
    reserved = re.findall(r"\{\+(\w+)\}", url)
    if reserved:
        return url, (f"Unfilled reserved-expansion path params {reserved} — '{{+name}}' takes a "
                     f"full resource path; add it to seed_ids under that name")
    remaining = re.findall(r"\{(\w+)\}", url)
    if remaining:
        return url, f"Unfilled path params: {remaining}"
    return url, ""

# ── Seed-ID harvesting ─────────────────────────────────────────────────────────

def derive_seed_key(endpoint_id: str) -> str | None:
    """
    Derive a path-param seed key from a 'list_X' / 'get_X' / 'create_X' endpoint_id,
    e.g. 'list_organizations' -> 'organizationId', 'list_change_requests' -> 'changeRequestId'.
    Lets GET-hierarchy APIs (list -> get by id, no POST-create step) self-seed.
    """
    for prefix in ("list_", "get_", "create_"):
        if endpoint_id.startswith(prefix):
            resource = endpoint_id[len(prefix):]
            break
    else:
        return None
    if resource.endswith("ies"):
        resource = resource[:-3] + "y"
    elif resource.endswith("s") and not resource.endswith("ss"):
        resource = resource[:-1]
    if not resource:
        return None
    parts = resource.split("_")
    camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
    return camel + "Id"

def extract_first_id(body_json):
    """Depth-first search for the first 'id' field — works whether the response is a bare
    object, a bare array, or wrapped under an arbitrary key (items/results/<resource>/...)."""
    found_id, _ = extract_first_id_and_path(body_json)
    return found_id

def extract_first_id_and_path(body_json):
    """Depth-first search for the first object with an 'id' field. Returns (id, path) using
    that SAME object's 'path' sibling if present — lets slugged resources (pages, docs, ...)
    self-seed both their id param and a path-style param from one list/get response."""
    if isinstance(body_json, dict):
        if isinstance(body_json.get("id"), (str, int)):
            return body_json["id"], body_json.get("path")
        for v in body_json.values():
            if isinstance(v, (dict, list)):
                found_id, found_path = extract_first_id_and_path(v)
                if found_id is not None:
                    return found_id, found_path
    elif isinstance(body_json, list):
        for item in body_json:
            found_id, found_path = extract_first_id_and_path(item)
            if found_id is not None:
                return found_id, found_path
    return None, None

def seed_candidates(full_text: str) -> dict | None:
    """Compact seed material from a FULL 2xx JSON body: the first object's id/path plus any
    top-level `id`/`*_id` keys. Computed in test_endpoint before the body is truncated for
    storage, so harvesting never depends on the 2000-char response_body excerpt."""
    try:
        body_json = json.loads(full_text)
    except (json.JSONDecodeError, TypeError):
        return None
    found_id, found_path = extract_first_id_and_path(body_json)
    top = {}
    if isinstance(body_json, dict):
        top = {k: v for k, v in body_json.items()
               if (k.endswith("_id") or k == "id") and isinstance(v, (str, int))}
    return {"first_id": found_id, "first_path": found_path, "top_ids": top}

def harvest_seed_ids(eid: str, result: dict, seed_ids: dict) -> None:
    """Update seed_ids in place from any successful 2xx response — not just POST — so
    GET list/get hierarchies (the common case) can seed their own downstream path params.

    Prefers result["seed_candidates"] (built from the full body by test_endpoint); falls back
    to parsing result["response_body"] for callers that only have the stored excerpt."""
    status = result.get("status_code")
    if not status or not (200 <= status < 300):
        return
    cands = result.get("seed_candidates")
    if not cands:
        body = result.get("response_body")
        if not body:
            return
        cands = seed_candidates(body)
        if cands is None:
            return
    seed_key = derive_seed_key(eid)
    if seed_key and lookup_seed(seed_ids, seed_key) is None:
        found_id, found_path = cands.get("first_id"), cands.get("first_path")
        if found_id is not None:
            # Store BOTH spellings (boardId / board_id) — specs are split on the convention.
            for k in seed_key_variants(seed_key):
                seed_ids.setdefault(k, found_id)
            # Sibling 'path'/slug field on the same object — seed the analogous "...Path"
            # param (e.g. pageId -> pagePath) so path-addressed lookups can self-seed too.
            if found_path is not None and seed_key.endswith("Id"):
                path_key = seed_key[:-2] + "Path"
                for k in seed_key_variants(path_key):
                    seed_ids.setdefault(k, found_path)
    for key, val in (cands.get("top_ids") or {}).items():
        if key not in seed_ids:
            seed_ids[key] = val

# ── Result tag helpers ─────────────────────────────────────────────────────────

def tag_result(status_code: int, body: str, entry: dict) -> str:
    """Assign VALIDATED / PARTIAL / FAILED based on status and response shape.

    An entry may declare "expected_status_codes": [...] for calls where the API's documented,
    correct behavior includes a non-2xx response (e.g. a sync/rebase endpoint returning 409
    "already up-to-date" when there's nothing to do) — such codes are treated like success
    instead of being blanket-FAILED, so real call defects aren't masked by this exception.
    """
    if status_code in (401, 403):
        return "FAILED"
    if status_code == 204:
        return "VALIDATED"
    if 300 <= status_code < 400:
        # follow_redirects is off: a redirect means the base_url/path is off, not that the
        # call shape is right. Never VALIDATED.
        return "PARTIAL"
    expected = entry.get("expected_status_codes") or []
    if status_code >= 400 and status_code not in expected:
        return "FAILED"
    if not body.strip():
        return "PARTIAL"
    # Check if response shape matches declared response_schema
    declared = entry.get("response_schema")
    if declared and body.strip().startswith("{"):
        try:
            actual = json.loads(body)
            if isinstance(actual, dict) and isinstance(declared, dict):
                missing_keys = set(declared.keys()) - set(actual.keys())
                if missing_keys:
                    return "PARTIAL"
        except json.JSONDecodeError:
            return "PARTIAL"
    return "VALIDATED"

# ── Tool: test_endpoint ────────────────────────────────────────────────────────

def _result(status_code, body, latency_ms, tag, error, error_body=""):
    out = {
        "status_code": status_code,
        "response_body": (body or "")[:RESPONSE_BODY_KEEP],
        "latency_ms": latency_ms,
        "validated": tag == "VALIDATED",
        "tag": tag,
        "error": error,
        "error_body": (error_body or "")[:ERROR_BODY_KEEP],
    }
    if status_code and 200 <= status_code < 300 and body:
        cands = seed_candidates(body)          # from the FULL body, before truncation
        if cands is not None:
            out["seed_candidates"] = cands
    return out

def _retry_after_seconds(resp, fallback: float) -> float:
    """Honour a Retry-After header (seconds form) on 429, capped; else the exponential fallback."""
    try:
        raw = resp.headers.get("Retry-After") if getattr(resp, "headers", None) else None
        if raw is not None and str(raw).strip():
            return min(float(str(raw).strip()), RETRY_AFTER_CAP)
    except (TypeError, ValueError, AttributeError):
        pass
    return fallback

@mcp.tool()
async def test_endpoint(entry: dict, token: str | None = None, seed_ids: dict | None = None,
                        base_url: str = "") -> dict:
    """
    Fire one HTTP request using the call-library entry's call shape.

    Args:
        entry:    A call-library entry dict.
        token:    API token. Omit (or pass empty) to use the PLEASE_REST_TOKEN env var —
                  preferred, so the secret never appears in a tool call.
        seed_ids: Dict of resource name → ID for path params. e.g. {"board_id": "abc123"}
                  (either camelCase or snake_case spelling is matched).
        base_url: Origin to prepend when the entry's url_template is relative (e.g.
                  "https://slides.googleapis.com"). The entry's own "base_url" wins if present.

    Token placement follows the entry's `auth_in`: "header" (default, `Authorization: Bearer`),
    "header:<HeaderName>" (raw token in that header — API-key style), or "query:<param>".

    A POST/PUT/PATCH entry with a body_schema but no example_request is NOT fired — it comes
    back PARTIAL ("not tested — no request body example") so it can be enriched, instead of
    producing a spurious 400 that sends pr-api-scout chasing a non-defect.

    Returns:
        Result dict with status_code, response_body (truncated), latency_ms, validated (bool),
        tag (VALIDATED/FAILED/PARTIAL), error (str), error_body (first 500 chars of a non-OK
        response, for pr-api-scout), seed_candidates (ids harvested from the full body).
        The token never appears in the result.
    """
    seed_ids = seed_ids or {}
    token    = token or os.environ.get("PLEASE_REST_TOKEN", "")
    if not token:
        return _result(None, "", 0, "FAILED",
                       "no API token — set PLEASE_REST_TOKEN or pass token")
    method   = entry.get("method", "GET").upper()
    url_tmpl = entry.get("url_template", "")
    headers  = {str(k): str(v).replace("{token}", token)
                for k, v in (entry.get("headers") or {}).items()}

    url, url_error = build_url(url_tmpl, entry.get("path_params", []), seed_ids)
    if url_error:
        return _result(None, "", 0, "FAILED", url_error)

    # Join a base URL when the template is relative. The entry's own base_url wins, else the
    # base_url argument (threaded from run_all_tests / plugin-spec). (dogfood Docs F3 / Slides F3)
    if not url.startswith(("http://", "https://")):
        resolved_base = entry.get("base_url") or base_url
        if not resolved_base:
            return _result(None, "", 0, "FAILED",
                           f"Relative url_template '{url}' and no base_url — pass base_url to "
                           f"run_all_tests or add a base_url field to the entry.")
        url = resolved_base.rstrip("/") + "/" + url.lstrip("/")

    # Build query string from seed_ids (either spelling); note required ones we couldn't fill.
    params = {}
    unfilled_query = []
    for qp in entry.get("query_params", []):
        name = qp.get("name", "")
        value = lookup_seed(seed_ids, name)
        if value is not None:
            params[name] = value
        elif qp.get("required"):
            unfilled_query.append(name)
    query_note = f"unfilled query param(s) {unfilled_query}" if unfilled_query else ""

    # Token placement (entry.auth_in): header (Bearer) | header:<Name> | query:<param>
    auth_in = entry.get("auth_in", "header")
    if isinstance(auth_in, str) and auth_in.startswith("query:"):
        params[auth_in.split(":", 1)[1]] = token
        headers.pop("Authorization", None)
    elif isinstance(auth_in, str) and auth_in.startswith("header:"):
        header_name = auth_in.split(":", 1)[1].strip()
        if header_name:
            headers.pop("Authorization", None)
            headers[header_name] = token

    # Request body: example_request, else — for a write endpoint that declares a body — PARTIAL.
    json_body = None
    if method in ("POST", "PUT", "PATCH"):
        example = entry.get("example_request") or {}
        if example:
            json_body = example
        elif entry.get("body_schema"):
            return _result(None, "", 0, "PARTIAL",
                           "not tested — no request body example (enrich example_request, "
                           "then retest_entries)")

    def _note(err: str) -> str:
        return " | ".join(x for x in (err, query_note) if x)

    retries = 0
    timeout_retries = 0
    while retries <= RETRY_LIMIT:
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.request(
                    method, url,
                    headers=headers,
                    params=params if params else None,
                    json=json_body,
                )
            latency_ms = round((time.monotonic() - start) * 1000)
            full_text = resp.text or ""          # parse the FULL text; truncate only what we store

            if resp.status_code == 429:
                if retries < RETRY_LIMIT:
                    wait = _retry_after_seconds(resp, float(2 ** retries))
                    _log(f"  Rate limited — waiting {wait}s before retry {retries + 1}/{RETRY_LIMIT}")
                    await asyncio.sleep(wait)
                    retries += 1
                    continue
                return _result(429, full_text, latency_ms, "PARTIAL",
                               _note("Rate limited after max retries — marked PARTIAL not FAILED"),
                               full_text)

            tag = tag_result(resp.status_code, full_text, entry)
            if tag == "VALIDATED":
                error, error_body = query_note, ""
            elif 300 <= resp.status_code < 400:
                error, error_body = _note(f"HTTP {resp.status_code} redirect — check base_url"), full_text
            else:
                error, error_body = _note(f"HTTP {resp.status_code}"), full_text
            return _result(resp.status_code, full_text, latency_ms, tag, error, error_body)

        except httpx.TimeoutException:
            if timeout_retries < TIMEOUT_RETRIES:
                timeout_retries += 1
                await asyncio.sleep(5)
                continue
            return _result(None, "", 0, "FAILED", _note("Request timeout after retry"))
        except Exception as e:
            return _result(None, "", 0, "FAILED", _note(str(e)))

    # Should never reach here
    return _result(None, "", 0, "FAILED", "Max retries exceeded")

# ── Tool: run_all_tests ────────────────────────────────────────────────────────

def _test_result_block(result: dict) -> dict:
    """The per-entry record written to call-library-validated.json. Never contains the token."""
    return {
        "tag":         result["tag"],
        "status_code": result["status_code"],
        "latency_ms":  result["latency_ms"],
        "error":       result["error"],
        "error_body":  result.get("error_body", ""),
    }

PARTIAL_SKIP_ERROR = "not tested — no request body example"

@mcp.tool()
async def run_all_tests(call_library_path: str, output_path: str,
                         token: str | None = None,
                         skip_destructive: bool = True,
                         base_url: str = "",
                         seed_ids: dict | None = None) -> str:
    """
    Run HTTP validation for all EXTRACTED entries in call-library.json.
    Writes call-library-validated.json with per-entry result tags.

    Token is read from PLEASE_REST_TOKEN env var if not supplied as argument.
    If neither is available, returns an error before making any requests.

    PARTIAL entries (write endpoints whose request body was never resolved) are NOT fired —
    they are listed in the summary under "skipped — PARTIAL" and written with a PARTIAL
    test_result so nothing is silently dropped. Enrich their example_request, then run
    retest_entries on them.

    Args:
        call_library_path: Path to call-library.json.
        output_path:       Destination for call-library-validated.json.
        token:             API token. Omit to use PLEASE_REST_TOKEN env var (preferred).
        skip_destructive:  If True, skip DELETE methods (default True).
        base_url:          Origin to prepend to relative url_templates (e.g. the plugin-spec
                           base_url like "https://slides.googleapis.com"). An entry's own
                           "base_url" field overrides this.
        seed_ids:          Starting resource IDs for path/query params, e.g. {"board_id": "abc"}
                           — for GET-only hierarchies that can't self-seed from a create call.
                           IDs harvested from responses are merged on top.

    Returns:
        Summary report string.
    """
    resolved_token = token or os.environ.get("PLEASE_REST_TOKEN", "")
    if not resolved_token:
        return (
            "Restling failed — no API token found.\n"
            "Set PLEASE_REST_TOKEN in your environment, or pass token as an argument:\n"
            "  run_all_tests(call_library_path=..., output_path=..., token='your_token')"
        )

    try:
        entries = json.loads(Path(call_library_path).read_text(encoding="utf-8"))
    except Exception as e:
        return f"Restling failed — could not read {call_library_path}: {e}"
    if not isinstance(entries, list):
        return f"Restling failed — {call_library_path} is not a JSON list of entries."

    to_test   = [e for e in entries if e.get("status") == "EXTRACTED"]
    partials  = [e for e in entries if e.get("status") == "PARTIAL"]
    skipped   = []
    results   = []
    seed_ids  = dict(seed_ids or {})
    validated = failed = partial = 0

    _log(f"Restling with API... {len(to_test)} endpoints to test"
         + (f", {len(partials)} PARTIAL skipped" if partials else ""))

    # PARTIAL entries: recorded, never fired, never silently dropped.
    partial_skipped = []
    for entry in partials:
        eid = entry.get("endpoint_id", "")
        partial_skipped.append(eid)
        result_entry = deepcopy(entry)
        result_entry["status"] = "PARTIAL"
        result_entry["test_result"] = {
            "tag": "PARTIAL", "status_code": None, "latency_ms": 0,
            "error": PARTIAL_SKIP_ERROR, "error_body": "",
        }
        results.append(result_entry)

    for entry in to_test:
        method = entry.get("method", "GET").upper()
        eid    = entry.get("endpoint_id", "")
        comp   = entry.get("component", "")

        if skip_destructive and method in DESTRUCTIVE_METHODS:
            _log(f"  Skipped (destructive): {eid}")
            skipped.append(eid)
            result_entry = deepcopy(entry)
            result_entry["test_result"] = {
                "tag": "SKIPPED", "reason": "skip_destructive=True",
                "status_code": None, "latency_ms": 0,
            }
            results.append(result_entry)
            continue

        _log(f"  Restling with {comp}...")
        result = await test_endpoint(entry, resolved_token, seed_ids, base_url)

        # Harvest resource IDs from any successful response for downstream tests — covers
        # both POST-create flows and GET list/get hierarchies (no create step to harvest from).
        harvest_seed_ids(eid, result, seed_ids)

        # 401 mid-run: halt and report — do not mark everything FAILED
        if result.get("status_code") == 401:
            _log(f"\n  Auth failure on {eid} — halting run.")
            _write_validated(entries, results, output_path)
            return (
                f"Restling halted — 401 Unauthorized on '{eid}'.\n"
                f"Check that PLEASE_REST_TOKEN is valid and has the required scopes.\n"
                f"Partial results written to: {output_path}\n"
                f"Resume with retest_entries() after refreshing the token."
            )

        result_entry = deepcopy(entry)
        result_entry["test_result"] = _test_result_block(result)
        if result["tag"] == "VALIDATED":
            result_entry["status"] = "VALIDATED"
            validated += 1
        elif result["tag"] == "PARTIAL":
            result_entry["status"] = "PARTIAL"
            partial += 1
        else:
            result_entry["status"] = "FAILED"
            failed += 1

        results.append(result_entry)

    _write_validated(entries, results, output_path)

    summary = (
        f"\nRestling complete.\n"
        f"  Validated:  {validated}\n"
        f"  Partial:    {partial}\n"
        f"  Failed:     {failed}\n"
        f"  Skipped:    {len(skipped)}\n"
        f"  Written to: {output_path}\n"
    )
    if partial_skipped:
        summary += (f"  Skipped — PARTIAL (enrich example_request, then retest_entries): "
                    f"{len(partial_skipped)} → {partial_skipped}\n")
    if failed or partial:
        summary += "\nFAILED/PARTIAL entries need attention — run pr-api-scout or retest_entries after fixing."
    _log(summary)
    return summary

# ── Tool: retest_entries ───────────────────────────────────────────────────────

@mcp.tool()
async def retest_entries(entry_ids: list[str], call_library_path: str,
                          output_path: str, token: str | None = None,
                          base_url: str = "",
                          seed_ids: dict | None = None) -> str:
    """
    Re-run tests for specific entry IDs only.
    Used by pr-api-scout after patching failed entries in call-library.json.

    Args:
        entry_ids:         List of endpoint_id strings to retest.
        call_library_path: Path to the (patched) call-library.json.
        output_path:       Path to the existing call-library-validated.json to update.
        token:             API token. Omit to use PLEASE_REST_TOKEN env var (preferred).
        base_url:          Origin to prepend to relative url_templates (entry "base_url" wins).
        seed_ids:          Starting resource IDs for path/query params (harvested IDs merge on top).

    Returns:
        Summary of retest results. The validated file keeps the call-library's entry order.
    """
    resolved_token = token or os.environ.get("PLEASE_REST_TOKEN", "")
    if not resolved_token:
        return "Restling failed — no API token found. Set PLEASE_REST_TOKEN or pass token as argument."

    try:
        library = json.loads(Path(call_library_path).read_text(encoding="utf-8"))
    except Exception as e:
        return f"Restling failed — could not read {call_library_path}: {e}"
    if not isinstance(library, list):
        return f"Restling failed — {call_library_path} is not a JSON list of entries."

    existing_validated: list[dict] = []
    if Path(output_path).exists():
        try:
            loaded = json.loads(Path(output_path).read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing_validated = loaded
        except Exception:
            pass

    to_retest = {e["endpoint_id"]: e for e in library
                 if e.get("endpoint_id") and e.get("endpoint_id") in entry_ids}
    if not to_retest:
        return f"No matching entries found for IDs: {entry_ids}"

    _log(f"Restling — retesting {len(to_retest)} entries...")
    updated = {e["endpoint_id"]: e for e in existing_validated if e.get("endpoint_id")}
    validated = failed = partial = 0
    seed_ids = dict(seed_ids or {})

    for eid, entry in to_retest.items():
        _log(f"  Retesting {eid}...")
        result = await test_endpoint(entry, resolved_token, seed_ids, base_url=base_url)

        # Harvest resource IDs from any successful response so a batch of retest_entries
        # (e.g. list -> get, or create -> the rest of a resource chain) can self-seed
        # downstream path params, same as run_all_tests does.
        harvest_seed_ids(eid, result, seed_ids)

        result_entry = deepcopy(entry)
        result_entry["test_result"] = _test_result_block(result)
        result_entry["status"] = result["tag"] if result["tag"] in ("VALIDATED", "PARTIAL") else "FAILED"
        updated[eid] = result_entry
        if result["tag"] == "VALIDATED":
            validated += 1
        elif result["tag"] == "PARTIAL":
            partial += 1
        else:
            failed += 1

    # Preserve the call-library's order; anything only in the old validated file trails.
    ordered: list[dict] = []
    seen: set = set()
    for entry in library:
        eid = entry.get("endpoint_id")
        if eid in updated and eid not in seen:
            ordered.append(updated[eid]); seen.add(eid)
    for eid, entry in updated.items():
        if eid not in seen:
            ordered.append(entry); seen.add(eid)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ordered, indent=2), encoding="utf-8")

    summary = (
        f"\nRetest complete.\n"
        f"  Validated:  {validated}\n"
        f"  Partial:    {partial}\n"
        f"  Failed:     {failed}\n"
        f"  Written to: {output_path}\n"
    )
    if failed:
        summary += "\nStill-failing entries should be escalated to human review."
    _log(summary)
    return summary

# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_validated(original_entries: list[dict], tested: list[dict], output_path: str) -> None:
    """Merge tested results back over original entries and write output."""
    tested_by_id = {e["endpoint_id"]: e for e in tested if e.get("endpoint_id")}
    merged = []
    for entry in original_entries:
        eid = entry.get("endpoint_id")
        merged.append(tested_by_id.get(eid, entry))
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(merged, indent=2), encoding="utf-8")

# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
