"""
Tests for _write_validated() in pr-api-tester/server.py.
Covers: merge logic, order preservation, untested entries retained.
"""
import json
import pytest
from pathlib import Path

import server


def _make_entry(endpoint_id, status="EXTRACTED"):
    return {
        "endpoint_id":    endpoint_id,
        "component":      f"Comp_{endpoint_id}",
        "method":         "GET",
        "url_template":   f"https://api.example.com/{endpoint_id}",
        "path_params":    [],
        "query_params":   [],
        "headers":        {"Authorization": "Bearer {token}"},
        "body_schema":    None,
        "response_schema": None,
        "example_request":  {},
        "example_response": {},
        "notes":          "",
        "status":         status,
    }


def test_write_validated_creates_file(tmp_path):
    original = [_make_entry("a"), _make_entry("b")]
    tested   = []
    out = tmp_path / "validated.json"
    server._write_validated(original, tested, str(out))
    assert out.exists()


def test_write_validated_tested_entry_replaces_original(tmp_path):
    original = [_make_entry("a")]
    tested_entry = dict(_make_entry("a"))
    tested_entry["status"] = "VALIDATED"
    tested_entry["test_result"] = {"tag": "VALIDATED", "status_code": 200, "latency_ms": 120, "error": ""}

    out = tmp_path / "validated.json"
    server._write_validated(original, [tested_entry], str(out))

    result = json.loads(out.read_text())
    assert len(result) == 1
    assert result[0]["status"] == "VALIDATED"
    assert "test_result" in result[0]


def test_write_validated_untested_entry_retained(tmp_path):
    original = [_make_entry("a"), _make_entry("b")]
    tested_a = dict(_make_entry("a"))
    tested_a["status"] = "VALIDATED"

    out = tmp_path / "validated.json"
    server._write_validated(original, [tested_a], str(out))

    result = json.loads(out.read_text())
    assert len(result) == 2
    b_entry = next(e for e in result if e["endpoint_id"] == "b")
    assert b_entry["status"] == "EXTRACTED"  # original status preserved


def test_write_validated_order_follows_original(tmp_path):
    original = [_make_entry("a"), _make_entry("b"), _make_entry("c")]
    tested_b = dict(_make_entry("b"))
    tested_b["status"] = "FAILED"

    out = tmp_path / "validated.json"
    server._write_validated(original, [tested_b], str(out))

    result = json.loads(out.read_text())
    ids = [e["endpoint_id"] for e in result]
    assert ids == ["a", "b", "c"]


def test_write_validated_creates_parent_directory(tmp_path):
    original = [_make_entry("a")]
    nested = tmp_path / "deep" / "path" / "validated.json"
    server._write_validated(original, [], str(nested))
    assert nested.exists()


def test_write_validated_all_failed(tmp_path):
    original = [_make_entry("a"), _make_entry("b")]
    tested = []
    for e in original:
        t = dict(e)
        t["status"] = "FAILED"
        t["test_result"] = {"tag": "FAILED", "status_code": 404, "latency_ms": 50, "error": "HTTP 404"}
        tested.append(t)

    out = tmp_path / "validated.json"
    server._write_validated(original, tested, str(out))

    result = json.loads(out.read_text())
    assert all(e["status"] == "FAILED" for e in result)
