"""
Tests for load_config() in pr-icon-generator/server.py.
Covers: required path, always-fresh reads, missing file error, and the shipped template.

There is no default config: icons.template.json is a template pr-icons copies, never a config
the server renders from. Omitting config_path is an error, not a fallback.
"""
import json
import pytest
from pathlib import Path

import server


TEMPLATE = (Path(__file__).parent.parent.parent / "please-rest" / "mcps"
            / "pr-icon-generator" / "icons.template.json")


def _config(tmp_path, prefix="XX"):
    f = tmp_path / "icons.json"
    f.write_text(json.dumps({
        "plugin_prefix": prefix,
        "resources_path": "Icons",
        "resx_path": "Properties/Resources.resx",
        "subcategories": {},
    }))
    return f


# ── config_path is required ──────────────────────────────────────────────────

def test_load_config_without_path_raises():
    with pytest.raises(ValueError, match="config_path is required"):
        server.load_config()


def test_load_config_empty_path_raises():
    with pytest.raises(ValueError, match="config_path is required"):
        server.load_config("")


def test_load_config_error_names_the_template():
    # The message has to tell you where to start, not just that you did it wrong.
    with pytest.raises(ValueError, match="icons.template.json"):
        server.load_config()


def test_load_config_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        server.load_config(str(tmp_path / "nope" / "icons.json"))


# ── loading ──────────────────────────────────────────────────────────────────

def test_load_config_returns_dict_and_resolved_path(tmp_path):
    f = _config(tmp_path)
    config, path = server.load_config(str(f))
    assert config["plugin_prefix"] == "XX"
    assert path == f.resolve()


def test_load_config_rereads_after_edit(tmp_path):
    # A "redo all icons" / "redo just these icons" pass rewrites icons.json mid-session — the
    # next load must see the new content, not whatever was loaded first.
    f = _config(tmp_path, prefix="AA")
    first, _ = server.load_config(str(f))
    assert first["plugin_prefix"] == "AA"
    f.write_text(json.dumps({
        "plugin_prefix": "BB",
        "resources_path": "Icons",
        "resx_path": "Properties/Resources.resx",
        "subcategories": {},
    }))
    second, _ = server.load_config(str(f))
    assert second["plugin_prefix"] == "BB"


def test_load_config_different_paths_load_independently(tmp_path):
    dir_a, dir_b = tmp_path / "a", tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    ca, _ = server.load_config(str(_config(dir_a, prefix="AA")))
    cb, _ = server.load_config(str(_config(dir_b, prefix="BB")))
    assert ca["plugin_prefix"] == "AA" and cb["plugin_prefix"] == "BB"


# ── the shipped template ─────────────────────────────────────────────────────

def test_template_exists_and_is_valid_json():
    # pr-icons copies this file, so a syntax error here breaks every new plugin's icons.
    assert TEMPLATE.exists(), f"missing template: {TEMPLATE}"
    json.loads(TEMPLATE.read_text(encoding="utf-8"))


def test_template_uses_the_modern_schema():
    t = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    for key in ("defaults", "plugin_icon", "subcategories", "components"):
        assert key in t, f"template missing '{key}'"


def test_template_carries_no_legacy_keys():
    # bg_shape/bg_color/icon_color was the removed flat schema; it must not creep back in.
    raw = TEMPLATE.read_text(encoding="utf-8")
    for legacy in ("bg_shape", "bg_color", "icon_color"):
        assert legacy not in raw, f"template still references legacy key '{legacy}'"


def test_template_shape_types_all_exist():
    # A template naming a shape that isn't in backgrounds/ would fail on a user's first render.
    raw = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    available = set(server.shape_index())
    found = []
    def walk(node):
        if isinstance(node, dict):
            shape = node.get("shape")
            if isinstance(shape, dict) and "type" in shape:
                found.append(shape["type"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(raw)
    assert found, "template declares no shapes"
    assert set(found) <= available, f"unknown shapes: {set(found) - available}"


def test_template_is_documented():
    t = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    assert "_README" in t and t["_README"], "template should explain itself"
