"""
Tests for run_all_tests() / retest_entries() and the seed/auth/truncation helpers in
pr-api-tester/server.py. HTTP is mocked via httpx.MockTransport (no live network).
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import server


def _entry(eid, method="GET", url="/v1/items", **kw):
    e = {
        "endpoint_id": eid, "component": eid.title(), "method": method,
        "url_template": url, "base_url": "https://api.example.com", "auth_in": "header",
        "path_params": [], "query_params": [],
        "headers": {"Authorization": "Bearer {token}"},
        "body_schema": None, "response_schema": None,
        "example_request": {}, "example_response": {},
        "notes": "", "status": "EXTRACTED",
    }
    e.update(kw)
    return e


def _patch_transport(handler):
    """Route httpx.AsyncClient(...) inside server through a MockTransport handler."""
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    return patch("httpx.AsyncClient", side_effect=factory)


# ── seed keys ──────────────────────────────────────────────────────────────────

def test_seed_key_variants_both_spellings():
    assert set(server.seed_key_variants("boardId")) == {"boardId", "board_id"}
    assert set(server.seed_key_variants("board_id")) == {"board_id", "boardId"}
    assert server.seed_key_variants("id") == ["id"]


def test_lookup_seed_matches_either_spelling():
    assert server.lookup_seed({"boardId": "b1"}, "board_id") == "b1"
    assert server.lookup_seed({"board_id": "b1"}, "boardId") == "b1"
    assert server.lookup_seed({}, "board_id") is None


def test_build_url_accepts_snake_seed_for_camel_param():
    params = [{"name": "boardId", "type": "string", "required": True}]
    url, err = server.build_url("/boards/{boardId}", params, {"board_id": "b 1"})
    assert err == ""
    assert url == "/boards/b%201"          # also URL-encoded


def test_build_url_flags_reserved_expansion():
    url, err = server.build_url("/v1/{+name}", [], {})
    assert "reserved-expansion" in err and "name" in err


def test_harvest_seeds_both_spellings():
    seeds = {}
    result = {"status_code": 200, "response_body": json.dumps({"data": [{"id": "b1"}]})}
    server.harvest_seed_ids("list_boards", result, seeds)
    assert seeds["boardId"] == "b1" and seeds["board_id"] == "b1"


# ── truncation vs parse ────────────────────────────────────────────────────────

def test_large_response_still_validated_and_harvested():
    big = {"id": "doc-123", "padding": "x" * 5000, "title": "T"}
    entry = _entry("create_document", "POST", "/v1/documents",
                   example_request={"title": "T"},
                   response_schema={"id": "string", "title": "string"})

    def handler(request):
        return httpx.Response(200, json=big)

    with _patch_transport(handler):
        result = asyncio.run(server.test_endpoint(entry, "tok", {}))
    assert result["tag"] == "VALIDATED"
    assert len(result["response_body"]) == server.RESPONSE_BODY_KEEP   # stored truncated
    seeds = {}
    server.harvest_seed_ids("create_document", {"status_code": 200,
                                                 "response_body": json.dumps(big)}, seeds)
    assert seeds["documentId"] == "doc-123"


def test_run_all_tests_harvests_from_large_body(tmp_path):
    big_list = {"items": [{"id": "b1", "blob": "y" * 4000}]}
    lib = [_entry("list_boards", "GET", "/boards"),
           _entry("get_board", "GET", "/boards/{board_id}",
                  path_params=[{"name": "board_id", "type": "string", "required": True}])]
    (tmp_path / "lib.json").write_text(json.dumps(lib))
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if request.url.path == "/boards":
            return httpx.Response(200, json=big_list)
        return httpx.Response(200, json={"id": "b1"})

    with _patch_transport(handler):
        summary = asyncio.run(server.run_all_tests(str(tmp_path / "lib.json"),
                                                   str(tmp_path / "out.json"), token="tok"))
    assert "Validated:  2" in summary
    assert any(u.endswith("/boards/b1") for u in seen)


# ── auth_in ────────────────────────────────────────────────────────────────────

def test_auth_in_header_name_places_raw_token():
    captured = {}

    def handler(request):
        captured.update(dict(request.headers))
        return httpx.Response(200, json={"ok": True})

    entry = _entry("ping", auth_in="header:X-API-Key")
    with _patch_transport(handler):
        asyncio.run(server.test_endpoint(entry, "sekrit", {}))
    assert captured.get("x-api-key") == "sekrit"
    assert "authorization" not in captured


def test_auth_in_query_places_token_param():
    captured = {}

    def handler(request):
        captured["q"] = dict(request.url.params)
        captured["h"] = dict(request.headers)
        return httpx.Response(200, json={"ok": True})

    entry = _entry("ping", auth_in="query:access_token")
    with _patch_transport(handler):
        asyncio.run(server.test_endpoint(entry, "sekrit", {}))
    assert captured["q"]["access_token"] == "sekrit"
    assert "authorization" not in captured["h"]


def test_test_endpoint_falls_back_to_env_token(monkeypatch):
    monkeypatch.setenv("PLEASE_REST_TOKEN", "envtok")
    captured = {}

    def handler(request):
        captured.update(dict(request.headers))
        return httpx.Response(200, json={"ok": True})

    with _patch_transport(handler):
        result = asyncio.run(server.test_endpoint(_entry("ping")))
    assert result["tag"] == "VALIDATED"
    assert captured["authorization"] == "Bearer envtok"


def test_test_endpoint_no_token_anywhere_fails(monkeypatch):
    monkeypatch.delenv("PLEASE_REST_TOKEN", raising=False)
    result = asyncio.run(server.test_endpoint(_entry("ping")))
    assert result["tag"] == "FAILED" and "PLEASE_REST_TOKEN" in result["error"]


# ── PARTIAL handling, redirects, error_body ────────────────────────────────────

def test_write_with_schema_but_no_example_is_partial_not_fired():
    fired = []

    def handler(request):
        fired.append(1)
        return httpx.Response(400)

    entry = _entry("create_item", "POST", body_schema={"name": "string"})
    with _patch_transport(handler):
        result = asyncio.run(server.test_endpoint(entry, "tok", {}))
    assert result["tag"] == "PARTIAL"
    assert "no request body example" in result["error"]
    assert fired == []


def test_redirect_is_partial_with_error_body():
    def handler(request):
        return httpx.Response(301, headers={"Location": "https://elsewhere"}, text="<html>Moved</html>")

    with _patch_transport(handler):
        result = asyncio.run(server.test_endpoint(_entry("ping"), "tok", {}))
    assert result["tag"] == "PARTIAL"
    assert "redirect" in result["error"]
    assert "Moved" in result["error_body"]


def test_error_body_captured_on_4xx_and_empty_on_2xx():
    def handler(request):
        if request.url.path == "/bad":
            return httpx.Response(422, json={"message": "name is required"})
        return httpx.Response(200, json={"ok": True})

    with _patch_transport(handler):
        bad = asyncio.run(server.test_endpoint(_entry("bad", url="/bad"), "tok", {}))
        good = asyncio.run(server.test_endpoint(_entry("good", url="/good"), "tok", {}))
    assert "name is required" in bad["error_body"]
    assert len(bad["error_body"]) <= server.ERROR_BODY_KEEP
    assert good["error_body"] == ""
    assert "Bearer tok" not in json.dumps(bad) and "Bearer tok" not in json.dumps(good)


def test_retry_after_header_honoured_and_capped():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "999"})
        return httpx.Response(200, json={"ok": True})

    with _patch_transport(handler), patch("asyncio.sleep", new_callable=AsyncMock) as sl:
        result = asyncio.run(server.test_endpoint(_entry("ping"), "tok", {}))
    assert result["tag"] == "VALIDATED"
    assert sl.await_args.args[0] == server.RETRY_AFTER_CAP


def test_required_query_param_unfilled_is_noted_but_fired():
    fired = []

    def handler(request):
        fired.append(str(request.url))
        return httpx.Response(200, json={"ok": True})

    entry = _entry("list", query_params=[{"name": "key", "type": "string", "required": True}])
    with _patch_transport(handler):
        result = asyncio.run(server.test_endpoint(entry, "tok", {}))
    assert fired
    assert result["tag"] == "VALIDATED"
    assert "unfilled query param" in result["error"]


# ── run_all_tests ──────────────────────────────────────────────────────────────

def test_run_all_tests_partial_entries_recorded_not_fired_and_seed_ids_param(tmp_path):
    lib = [
        _entry("get_board", "GET", "/boards/{board_id}",
               path_params=[{"name": "board_id", "type": "string", "required": True}]),
        _entry("create_board", "POST", "/boards", status="PARTIAL", body_schema={"name": "string"}),
        _entry("nuke", "DELETE", "/boards/{board_id}",
               path_params=[{"name": "board_id", "type": "string", "required": True}]),
    ]
    (tmp_path / "lib.json").write_text(json.dumps(lib))
    fired = []

    def handler(request):
        fired.append((request.method, request.url.path))
        return httpx.Response(200, json={"id": "given"})

    with _patch_transport(handler):
        summary = asyncio.run(server.run_all_tests(
            str(tmp_path / "lib.json"), str(tmp_path / "out.json"),
            "tok", True, "", {"board_id": "given"}))          # seed_ids positional (last)

    assert fired == [("GET", "/boards/given")]                 # PARTIAL + DELETE never fired
    assert "Skipped — PARTIAL" in summary and "create_board" in summary
    out = json.loads((tmp_path / "out.json").read_text())
    by_id = {e["endpoint_id"]: e for e in out}
    assert by_id["get_board"]["status"] == "VALIDATED"
    assert by_id["get_board"]["test_result"]["error_body"] == ""
    assert by_id["create_board"]["status"] == "PARTIAL"
    assert by_id["create_board"]["test_result"]["tag"] == "PARTIAL"
    assert by_id["create_board"]["test_result"]["error"] == server.PARTIAL_SKIP_ERROR
    assert by_id["nuke"]["test_result"]["tag"] == "SKIPPED"
    written = (tmp_path / "out.json").read_text()
    assert "Bearer tok" not in written and "seed_candidates" not in written   # token + scratch never persisted


def test_run_all_tests_error_body_written(tmp_path):
    lib = [_entry("broken", "GET", "/broken")]
    (tmp_path / "lib.json").write_text(json.dumps(lib))

    def handler(request):
        return httpx.Response(400, json={"error": "bad shape"})

    with _patch_transport(handler):
        asyncio.run(server.run_all_tests(str(tmp_path / "lib.json"), str(tmp_path / "out.json"), token="tok"))
    out = json.loads((tmp_path / "out.json").read_text())
    assert out[0]["status"] == "FAILED"
    assert "bad shape" in out[0]["test_result"]["error_body"]


def test_run_all_tests_rejects_non_list_library(tmp_path):
    (tmp_path / "lib.json").write_text(json.dumps({"not": "a list"}))
    summary = asyncio.run(server.run_all_tests(str(tmp_path / "lib.json"), str(tmp_path / "out.json"), token="tok"))
    assert "not a JSON list" in summary


# ── retest_entries ─────────────────────────────────────────────────────────────

def test_retest_entries_preserves_library_order_and_mkdirs(tmp_path):
    lib = [_entry("a", url="/a"), _entry("b", url="/b"), _entry("c", url="/c"), {"component": "NoId"}]
    (tmp_path / "lib.json").write_text(json.dumps(lib))
    existing = [dict(_entry("c", url="/c"), status="FAILED"), dict(_entry("a", url="/a"), status="FAILED")]
    out_path = tmp_path / "nested" / "dir" / "out.json"
    out_path.parent.mkdir(parents=True)
    out_path.write_text(json.dumps(existing))

    def handler(request):
        return httpx.Response(200, json={"ok": True})

    with _patch_transport(handler):
        summary = asyncio.run(server.retest_entries(
            ["a", "b"], str(tmp_path / "lib.json"), str(out_path), "tok", "", {"x": 1}))
    assert "Validated:  2" in summary
    out = json.loads(out_path.read_text())
    assert [e["endpoint_id"] for e in out] == ["a", "b", "c"]   # library order, not existing order
    assert out[2]["status"] == "FAILED"                          # untouched entry retained
    assert out[0]["test_result"]["error_body"] == ""
