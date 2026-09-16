"""
Tests for generate_icon(), generate_plugin_icon() and add_to_resources() in
pr-icon-generator/server.py (post-rewrite API). The Iconify fetch is mocked throughout, so
no network is touched; PNGs are rendered into tmp_path.

generate_icon(component_name, config_path, subcategory=None, iconify_id=None)
generate_plugin_icon(config_path=None)
add_to_resources(component_name, config_path=None)
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import server


SQUARE_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24">'
    b'<rect x="4" y="4" width="16" height="16" fill="#000000"/></svg>'
)


# ── config builders ────────────────────────────────────────────────────────────

def _new_config(tmp_path):
    """Post-spec icons.json: defaults < subcategory < component, plus a plugin_icon block."""
    defaults = {"size": 24, "fg_color": "#FFFFFF",
                "background": {"shape": {"type": "rounded-square", "fill": "#2D6CDF"}}}
    return {
        "plugin_name": "TestPlugin",
        "plugin_prefix": "TP",
        "resources_path": str(tmp_path / "Icons"),
        "resx_path": str(tmp_path / "Resources.resx"),
        "defaults": defaults,
        "plugin_icon": {"size": 16, "fg_iconify_id": "mdi:star", "fg_color": "#FFFFFF",
                        "background": {"shape": {"type": "rounded-square", "fill": "#2D6CDF"}}},
        "subcategories": {"Boards": {"fg_color": "#FFFFFF"}},
        "components": [{"name": "FindBoard", "subcategory": "Boards", "fg_iconify_id": "mdi:magnify"}],
    }


def _write(tmp_path, config, name="icons.json"):
    f = tmp_path / name
    f.write_text(json.dumps(config))
    return str(f)


# ── generate_icon — happy paths ────────────────────────────────────────────────

@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_generate_icon_without_config_path_reports_the_error(mock_fetch, tmp_path):
    # config_path is required; the tool catches the ValueError and surfaces it as a message.
    mock_fetch.return_value = SQUARE_SVG
    result = asyncio.run(server.generate_icon("FindBoard"))
    assert "config_path is required" in result


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_generate_icon_new_config_uses_component_glyph(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    cfg = _write(tmp_path, _new_config(tmp_path))
    result = asyncio.run(server.generate_icon("FindBoard", config_path=cfg))
    assert "Icon saved" in result
    assert (tmp_path / "Icons" / "TP_FindBoard.png").exists()


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_generate_icon_prefix_comes_from_config(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    cfg = _write(tmp_path, _new_config(tmp_path))
    asyncio.run(server.generate_icon("FindBoard", config_path=cfg))
    assert (tmp_path / "Icons" / "TP_FindBoard.png").exists()
    assert not (tmp_path / "Icons" / "FindBoard.png").exists()


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_generate_icon_iconify_override(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    cfg = _write(tmp_path, _new_config(tmp_path))
    result = asyncio.run(server.generate_icon(
        "FindBoard", config_path=cfg, iconify_id="ph:eye"))
    assert "Icon saved" in result
    mock_fetch.assert_awaited()
    assert mock_fetch.await_args.args[0] == "ph:eye"  # override reached the fetch


# ── generate_icon — missing glyph / errors ─────────────────────────────────────

@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_generate_icon_no_foreground_returns_message(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    cfg = _write(tmp_path, _new_config(tmp_path))
    # Component not in config and no iconify_id → nothing to draw.
    result = asyncio.run(server.generate_icon("GhostComponent", config_path=cfg, subcategory="Boards"))
    assert "No foreground icon" in result
    mock_fetch.assert_not_awaited()


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_generate_icon_http_error_returns_message(mock_fetch, tmp_path):
    import httpx
    mock_fetch.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock(status_code=404))
    cfg = _write(tmp_path, _new_config(tmp_path))
    result = asyncio.run(server.generate_icon("FindBoard", config_path=cfg))
    assert "Failed to fetch" in result
    assert "404" in result


# ── generate_plugin_icon ───────────────────────────────────────────────────────

@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_generate_plugin_icon_saves_logo(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    cfg = _write(tmp_path, _new_config(tmp_path))
    result = asyncio.run(server.generate_plugin_icon(config_path=cfg))
    assert "Plugin icon saved" in result
    saved = tmp_path / "Icons" / "TP_TestPluginLogo.png"   # <prefix>_<PluginName>Logo.png
    assert saved.exists() and saved.stat().st_size > 0


def test_generate_plugin_icon_missing_glyph_returns_message(tmp_path):
    cfg_dict = _new_config(tmp_path)
    cfg_dict["plugin_icon"] = {"size": 16}  # no fg_iconify_id
    cfg = _write(tmp_path, cfg_dict)
    result = asyncio.run(server.generate_plugin_icon(config_path=cfg))
    assert "No plugin_icon.fg_iconify_id" in result


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_generate_plugin_icon_is_16px(mock_fetch, tmp_path):
    from PIL import Image
    mock_fetch.return_value = SQUARE_SVG
    cfg = _write(tmp_path, _new_config(tmp_path))
    asyncio.run(server.generate_plugin_icon(config_path=cfg))
    img = Image.open(tmp_path / "Icons" / "TP_TestPluginLogo.png")
    assert img.size == (16, 16)


# ── generate_plugin_icon — large marketing logo (size / out_name overrides) ────

@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_generate_plugin_icon_size_and_out_name_write_the_big_logo(mock_fetch, tmp_path):
    from PIL import Image
    mock_fetch.return_value = SQUARE_SVG
    cfg = _write(tmp_path, _new_config(tmp_path))
    result = asyncio.run(server.generate_plugin_icon(
        config_path=cfg, size=1024, out_name="TP_Plugin_Icon.png"))
    assert "1024x1024" in result
    big = tmp_path / "TP_Plugin_Icon.png"          # plugin root, not Icons/
    assert big.exists()
    assert Image.open(big).size == (1024, 1024)
    # the 16px ribbon icon is untouched by the big render
    assert not (tmp_path / "Icons" / "TP_TestPluginLogo.png").exists()


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_generate_plugin_icon_out_name_may_not_escape_the_plugin_folder(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    cfg = _write(tmp_path, _new_config(tmp_path))
    result = asyncio.run(server.generate_plugin_icon(
        config_path=cfg, size=512, out_name="../escaped.png"))
    assert "must stay inside the plugin folder" in result
    assert not (tmp_path.parent / "escaped.png").exists()


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_generate_plugin_icon_rejects_a_bad_size(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    cfg = _write(tmp_path, _new_config(tmp_path))
    assert "positive integer" in asyncio.run(
        server.generate_plugin_icon(config_path=cfg, size=0))


# ── add_to_resources — validation ─────────────────────────────────────────────

def test_add_to_resources_missing_icon_returns_error(tmp_path):
    cfg = _write(tmp_path, _new_config(tmp_path))
    result = server.add_to_resources("FindBoard", config_path=cfg)
    assert "not found" in result
    assert "run generate_icon first" in result


def test_add_to_resources_missing_resx_returns_error(tmp_path):
    icons_dir = tmp_path / "Icons"
    icons_dir.mkdir()
    (icons_dir / "TP_FindBoard.png").write_bytes(b"fakepng")
    cfg = _write(tmp_path, _new_config(tmp_path))  # resx path does not exist
    result = server.add_to_resources("FindBoard", config_path=cfg)
    assert "Resources.resx not found" in result
