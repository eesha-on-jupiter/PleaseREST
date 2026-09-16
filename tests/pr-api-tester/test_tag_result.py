"""
Tests for tag_result() in pr-api-tester/server.py.
"""
import json
import server


BLANK_ENTRY = {
    "endpoint_id": "test",
    "component": "TestComp",
    "method": "GET",
    "url_template": "https://api.example.com/test",
    "response_schema": None,
}


def _entry(response_schema=None):
    e = dict(BLANK_ENTRY)
    e["response_schema"] = response_schema
    return e


# ── Status code rules ──────────────────────────────────────────────────────────

def test_tag_result_200_with_body_validated():
    assert server.tag_result(200, '{"id": "abc"}', _entry()) == "VALIDATED"


def test_tag_result_201_with_body_validated():
    assert server.tag_result(201, '{"id": "new"}', _entry()) == "VALIDATED"


def test_tag_result_204_no_body_validated():
    assert server.tag_result(204, "", _entry()) == "VALIDATED"


def test_tag_result_401_is_failed():
    assert server.tag_result(401, '{"error": "unauthorized"}', _entry()) == "FAILED"


def test_tag_result_403_is_failed():
    assert server.tag_result(403, '{"error": "forbidden"}', _entry()) == "FAILED"


def test_tag_result_404_is_failed():
    assert server.tag_result(404, '{"error": "not found"}', _entry()) == "FAILED"


def test_tag_result_500_is_failed():
    assert server.tag_result(500, '{"error": "server error"}', _entry()) == "FAILED"


def test_tag_result_200_empty_body_is_partial():
    assert server.tag_result(200, "", _entry()) == "PARTIAL"


def test_tag_result_200_whitespace_body_is_partial():
    assert server.tag_result(200, "   ", _entry()) == "PARTIAL"


# ── Schema matching ────────────────────────────────────────────────────────────

def test_tag_result_all_schema_keys_present_is_validated():
    schema = {"id": "str", "name": "str"}
    body = json.dumps({"id": "abc", "name": "Board A"})
    assert server.tag_result(200, body, _entry(response_schema=schema)) == "VALIDATED"


def test_tag_result_missing_schema_keys_is_partial():
    schema = {"id": "str", "name": "str", "description": "str"}
    body = json.dumps({"id": "abc", "name": "Board A"})  # description missing
    assert server.tag_result(200, body, _entry(response_schema=schema)) == "PARTIAL"


def test_tag_result_extra_keys_in_body_still_validated():
    schema = {"id": "str"}
    body = json.dumps({"id": "abc", "extra_field": "bonus"})
    assert server.tag_result(200, body, _entry(response_schema=schema)) == "VALIDATED"


def test_tag_result_brace_json_parse_error_is_partial():
    # Body starts with '{' so the JSON branch runs — parse failure → PARTIAL
    schema = {"id": "str"}
    body = "{not valid json"
    assert server.tag_result(200, body, _entry(response_schema=schema)) == "PARTIAL"


def test_tag_result_non_brace_body_with_schema_is_validated():
    # Body doesn't start with '{' — JSON branch skipped entirely → VALIDATED
    schema = {"id": "str"}
    body = "not-json"
    assert server.tag_result(200, body, _entry(response_schema=schema)) == "VALIDATED"


def test_tag_result_no_schema_non_json_body_is_validated():
    # No declared schema — any non-empty body is VALIDATED
    assert server.tag_result(200, "some plain text", _entry()) == "VALIDATED"
