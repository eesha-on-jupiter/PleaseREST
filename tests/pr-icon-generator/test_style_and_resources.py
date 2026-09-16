"""
Tests for resolve_style() precedence / explicit-empty backgrounds, `custom: true` skipping,
Iconify id parsing + cache, and the Resources.Designer.cs edit in add_to_resources().
"""
import asyncio
import json
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import server


SQUARE_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24">'
    b'<rect x="4" y="4" width="16" height="16" fill="#000000"/></svg>'
)

CFG = {
    "plugin_name": "TestPlugin", "plugin_prefix": "TP",
    "resources_path": "Icons", "resx_path": "Properties/Resources.resx",
    "defaults": {"size": 24, "fg_color": "#FFFFFF",
                 "background": {"shape": {"type": "rounded-square", "fill": "#2D6CDF"}}},
    "subcategories": {"Boards": {
        "background": {"shape": {"type": "rounded-square", "fill": "#123456"},
                       "icon": {"iconify_id": "mdi:view-dashboard", "color": "#FFFFFF", "opacity": 0.45}},
        "fg": {"from": "#FFFFFF", "to": "#AAAAAA", "angle": 90}}},
    "components": [
        {"name": "Inherit", "subcategory": "Boards", "fg_iconify_id": "mdi:magnify"},
        {"name": "NoBg", "subcategory": "Boards", "fg_iconify_id": "mdi:magnify", "background": {}},
        {"name": "OwnShapeNoIcon", "subcategory": "Boards", "fg_iconify_id": "mdi:magnify",
         "background": {"shape": {"type": "circle", "fill": "#000000"}, "icon": {}}},
        {"name": "SolidOverGradient", "subcategory": "Boards", "fg_iconify_id": "mdi:magnify",
         "fg_color": "#FF0000"},
        {"name": "BothAtComp", "subcategory": "Boards", "fg_iconify_id": "mdi:magnify",
         "fg_color": "#FF0000", "fg": {"from": "#000000", "to": "#111111"}},
        {"name": "HandMade", "subcategory": "Boards", "custom": True},
    ],
}


# ── resolve_style ──────────────────────────────────────────────────────────────

def test_component_inherits_subcategory_background():
    _, fg, bg, _, _ = server.resolve_style(CFG, "Inherit")
    assert bg["shape"]["fill"] == "#123456"
    assert bg["icon"]["iconify_id"] == "mdi:view-dashboard"
    assert isinstance(fg, dict)        # subcategory gradient inherited


def test_explicit_empty_background_removes_everything():
    _, _, bg, _, _ = server.resolve_style(CFG, "NoBg")
    assert bg == {}
    assert server.has_background(bg) is False


def test_explicit_empty_icon_layer_drops_inherited_icon_keeps_own_shape():
    _, _, bg, _, _ = server.resolve_style(CFG, "OwnShapeNoIcon")
    assert bg["shape"] == {"type": "circle", "fill": "#000000"}
    assert "icon" not in bg
    assert server.has_background(bg) is True


def test_component_fg_color_overrides_inherited_gradient():
    _, fg, _, _, _ = server.resolve_style(CFG, "SolidOverGradient")
    assert fg == (255, 0, 0)


def test_gradient_wins_only_when_both_set_at_same_level():
    _, fg, _, _, _ = server.resolve_style(CFG, "BothAtComp")
    assert isinstance(fg, dict) and fg["from"] == "#000000"


def test_merge_none_inherits_and_empty_wipes():
    assert server._merge({"shape": {"type": "a"}}, None) == {"shape": {"type": "a"}}
    assert server._merge({"shape": {"type": "a"}}, {}) == {}
    assert server._merge({}, {"shape": {"type": "a"}}) == {"shape": {"type": "a"}}


# ── custom: true ───────────────────────────────────────────────────────────────

@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_custom_component_is_skipped_and_png_kept(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    cfg = dict(CFG, resources_path=str(tmp_path / "Icons"), resx_path=str(tmp_path / "R.resx"))
    (tmp_path / "Icons").mkdir()
    png = tmp_path / "Icons" / "TP_HandMade.png"
    png.write_bytes(b"hand-made")
    cfg_path = tmp_path / "icons.json"
    cfg_path.write_text(json.dumps(cfg))
    result = asyncio.run(server.generate_icon("HandMade", config_path=str(cfg_path)))
    assert "Skipped" in result and "custom" in result
    assert png.read_bytes() == b"hand-made"
    mock_fetch.assert_not_awaited()


def test_template_documents_custom_flag():
    tpl = json.loads(server.CONFIG_TEMPLATE.read_text(encoding="utf-8"))
    assert any(c.get("custom") is True for c in tpl["components"])
    assert any("custom" in line for line in tpl["_README"])


# ── Iconify id parsing + cache ────────────────────────────────────────────────

def test_parse_iconify_id_errors_clearly():
    with pytest.raises(ValueError, match="prefix:name"):
        server.parse_iconify_id("mdiplus")
    with pytest.raises(ValueError, match="prefix:name"):
        server.parse_iconify_id("mdi:")
    assert server.parse_iconify_id("mdi:plus") == ("mdi", "plus")


def test_fetch_icon_svg_caches_per_id():
    server._ICONIFY_CACHE.clear()
    calls = {"n": 0}

    class FakeResp:
        status_code = 200
        text = SQUARE_SVG.decode()
        def raise_for_status(self): pass

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            calls["n"] += 1
            return FakeResp()

    with patch("httpx.AsyncClient", FakeClient):
        asyncio.run(server.fetch_icon_svg("mdi:plus", 96))
        asyncio.run(server.fetch_icon_svg("mdi:plus", 64))
    assert calls["n"] == 1
    server._ICONIFY_CACHE.clear()


# ── add_to_resources Designer.cs edit ─────────────────────────────────────────

DESIGNER = """namespace TestPlugin.Properties {
    internal class Resources {
        internal static System.Drawing.Bitmap TP_Existing {
            get {
                object obj = ResourceManager.GetObject("TP_Existing", resourceCulture);
                return ((System.Drawing.Bitmap)(obj));
            }
        }
    }
}
"""


def _setup(tmp_path, designer=DESIGNER):
    (tmp_path / "Icons").mkdir()
    (tmp_path / "Properties").mkdir()
    (tmp_path / "Icons" / "TP_FindBoard.png").write_bytes(b"png")
    (tmp_path / "Icons" / "TP_Existing.png").write_bytes(b"png")
    (tmp_path / "Properties" / "Resources.resx").write_text("<root/>")
    if designer is not None:
        (tmp_path / "Properties" / "Resources.Designer.cs").write_text(designer, encoding="utf-8")
    cfg = dict(CFG)
    cfg_path = tmp_path / "icons.json"
    cfg_path.write_text(json.dumps(cfg))
    return str(cfg_path)


def _ok_run(*a, **k):
    return subprocess.CompletedProcess(a, 0, stdout="OK\n", stderr="")


@patch("server.platform.system", return_value="Windows")
@patch("server.subprocess.run", side_effect=_ok_run)
def test_add_to_resources_appends_property_once(mock_run, _sys, tmp_path):
    cfg = _setup(tmp_path)
    r1 = server.add_to_resources("FindBoard", config_path=cfg)
    assert "Resources.Designer.cs" in r1 and "already" not in r1
    text = (tmp_path / "Properties" / "Resources.Designer.cs").read_text(encoding="utf-8")
    assert text.count("Bitmap TP_FindBoard") == 1
    assert text.rstrip().endswith("}\n}") or text.rstrip().endswith("}")
    # second call: resx updated, Designer untouched
    r2 = server.add_to_resources("FindBoard", config_path=cfg)
    assert "already declares" in r2
    text2 = (tmp_path / "Properties" / "Resources.Designer.cs").read_text(encoding="utf-8")
    assert text2.count("Bitmap TP_FindBoard") == 1


@patch("server.platform.system", return_value="Windows")
@patch("server.subprocess.run", side_effect=_ok_run)
def test_add_to_resources_dedupes_hand_edited_property(mock_run, _sys, tmp_path):
    designer = DESIGNER.replace("TP_Existing", "TP_FindBoard").replace("System.Drawing.Bitmap TP_FindBoard", "Bitmap TP_FindBoard")
    cfg = _setup(tmp_path, designer)
    r = server.add_to_resources("FindBoard", config_path=cfg)
    assert "already declares" in r
    text = (tmp_path / "Properties" / "Resources.Designer.cs").read_text(encoding="utf-8")
    assert text.count("TP_FindBoard {") == 1


@patch("server.platform.system", return_value="Windows")
@patch("server.subprocess.run", side_effect=_ok_run)
def test_add_to_resources_unrecognised_designer_is_not_corrupted(mock_run, _sys, tmp_path):
    cfg = _setup(tmp_path, designer="// not a designer file at all")
    r = server.add_to_resources("FindBoard", config_path=cfg)
    assert "by hand" in r
    assert (tmp_path / "Properties" / "Resources.Designer.cs").read_text() == "// not a designer file at all"


@patch("server.platform.system", return_value="Darwin")
def test_add_to_resources_non_windows_clear_error(_sys, tmp_path):
    cfg = _setup(tmp_path)
    r = server.add_to_resources("FindBoard", config_path=cfg)
    assert "Windows-only" in r
