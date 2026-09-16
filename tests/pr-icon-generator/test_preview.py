"""
Tests for preview_backgrounds() in pr-icon-generator/server.py — the "show me the options"
tool that renders every background shape in each fill style plus a labelled contact sheet.

The Iconify fetch is mocked throughout (no network); background shape SVGs are rasterised for
real from backgrounds/, so tiles are rendered small to keep the suite quick.

preview_backgrounds(output_dir, fg_iconify_id, styles, shapes, size, fill,
                    gradient_from, gradient_to, gradient_angle, fg_color, bg_icon_iconify_id)
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

import server


# A square glyph: after trim_alpha it fills its whole target box, so no transparent corners.
SQUARE_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24">'
    b'<rect x="4" y="4" width="16" height="16" fill="#000000"/></svg>'
)
# A round glyph: its bounding box has transparent corners, which is what lets the
# "no background is really transparent" assertion below mean something.
CIRCLE_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24">'
    b'<circle cx="12" cy="12" r="10" fill="#000000"/></svg>'
)

THREE = "circle,bubble,hexagon"


def _run(tmp_path, **kw):
    kw.setdefault("shapes", THREE)
    kw.setdefault("size", 16)
    return asyncio.run(server.preview_backgrounds(str(tmp_path), **kw))


# ── style / shape parsing ─────────────────────────────────────────────────────

def test_parse_styles_canonical_order_and_dedupe():
    # Given in any order, the sheet still groups gradient → solid → none.
    assert server.parse_preview_styles("none,solid,gradient") == ["gradient", "solid", "none"]
    assert server.parse_preview_styles("solid,solid") == ["solid"]


def test_parse_styles_rejects_unknown_and_lists_the_valid_ones():
    with pytest.raises(ValueError) as e:
        server.parse_preview_styles("glow")
    assert "glow" in str(e.value)
    for valid in ("gradient", "solid", "none"):
        assert valid in str(e.value)


def test_parse_styles_rejects_empty():
    with pytest.raises(ValueError, match="No styles given"):
        server.parse_preview_styles("  ")


def test_parse_shapes_empty_means_every_shape():
    index = server.shape_index()
    assert server.parse_preview_shapes("", index) == sorted(index)


def test_parse_shapes_rejects_unknown_by_name():
    index = server.shape_index()
    with pytest.raises(ValueError) as e:
        server.parse_preview_shapes("circle,nosuchshape", index)
    assert "nosuchshape" in str(e.value)


def test_parse_shapes_preserves_given_order_and_dedupes():
    index = server.shape_index()
    assert server.parse_preview_shapes("hexagon,circle,hexagon", index) == ["hexagon", "circle"]


# ── the background block each tile stands for ────────────────────────────────

def test_preview_spec_gradient_solid_none():
    grad = server.preview_background_spec("gradient", "circle", "#111111",
                                          "#AAAAAA", "#BBBBBB", 90, "")
    assert grad["shape"]["gradient"] == {"from": "#AAAAAA", "to": "#BBBBBB", "angle": 90}
    assert "fill" not in grad["shape"]

    solid = server.preview_background_spec("solid", "circle", "#111111",
                                           "#AAAAAA", "#BBBBBB", 90, "")
    assert solid["shape"] == {"type": "circle", "fill": "#111111"}

    assert server.preview_background_spec("none", "circle", "#111111",
                                          "#AAAAAA", "#BBBBBB", 90, "") == {}


def test_preview_spec_adds_watermark_layer_only_when_asked():
    without = server.preview_background_spec("solid", "circle", "#111111", "#A", "#B", 90, "")
    assert "icon" not in without
    with_wm = server.preview_background_spec("solid", "circle", "#111111", "#A", "#B", 90,
                                             "mdi:cloud")
    assert with_wm["icon"]["iconify_id"] == "mdi:cloud"
    assert with_wm["icon"]["opacity"] == server.BG_ICON_OPACITY
    # 'none' has nothing to sit behind, so it never gets a watermark.
    assert server.preview_background_spec("none", "circle", "#111111", "#A", "#B", 90,
                                          "mdi:cloud") == {}


# ── files written ─────────────────────────────────────────────────────────────

@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_writes_one_png_per_shape_and_style(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    _run(tmp_path, styles="gradient,solid")
    for slug in ("circle", "bubble", "hexagon"):
        for style in ("gradient", "solid"):
            assert (tmp_path / f"preview_{slug}_{style}.png").exists()
    assert not (tmp_path / "preview_none.png").exists()


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_none_is_rendered_once_not_per_shape(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    _run(tmp_path, styles="none")
    assert (tmp_path / "preview_none.png").exists()
    # no per-shape 'none' tiles — with no shape there is nothing to vary
    assert list(tmp_path.glob("preview_*_none.png")) == []
    assert len(list(tmp_path.glob("preview_*.png"))) == 1


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_none_tile_is_actually_transparent(mock_fetch, tmp_path):
    mock_fetch.return_value = CIRCLE_SVG
    _run(tmp_path, styles="none,solid", size=32)
    none_px = Image.open(tmp_path / "preview_none.png").convert("RGBA")
    assert none_px.getpixel((0, 0))[3] == 0, "no background must leave the corners empty"
    # the same glyph over a square shape fills those corners, so the assertion above is real
    solid = Image.open(tmp_path / "preview_circle_solid.png").convert("RGBA")
    assert solid.getpixel((solid.width // 2, solid.height // 2))[3] > 0


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_shape_subset_is_honoured(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    _run(tmp_path, styles="solid", shapes="circle")
    assert (tmp_path / "preview_circle_solid.png").exists()
    assert len(list(tmp_path.glob("preview_*_solid.png"))) == 1


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_tiles_are_rendered_at_the_requested_size(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    _run(tmp_path, styles="solid", shapes="circle", size=48)
    assert Image.open(tmp_path / "preview_circle_solid.png").size == (48, 48)


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_output_dir_is_created(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    nested = tmp_path / "Icons" / "_preview"
    asyncio.run(server.preview_backgrounds(str(nested), styles="solid",
                                           shapes="circle", size=16))
    assert (nested / "preview_circle_solid.png").exists()


# ── contact sheet ─────────────────────────────────────────────────────────────

@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_contact_sheet_is_bigger_than_a_single_tile(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    size = 24
    _run(tmp_path, size=size)
    sheet = Image.open(tmp_path / "contact-sheet.png")
    assert sheet.width > size and sheet.height > size
    # three shapes across, plus two style groups stacked → taller than it is wide
    assert sheet.height > sheet.width


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_contact_sheet_path_is_in_the_catalog(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    out = _run(tmp_path)
    assert "contact-sheet.png" in out


# ── the returned catalog ──────────────────────────────────────────────────────

@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_catalog_lists_every_shape_slug(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    out = asyncio.run(server.preview_backgrounds(str(tmp_path), styles="solid", size=16))
    for slug in server.shape_index():
        assert slug in out, f"catalog omits shape '{slug}'"


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_catalog_carries_a_paste_ready_snippet_for_each_style(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    out = _run(tmp_path)
    assert "GRADIENT" in out and "SOLID" in out and "NONE" in out
    assert '"gradient": {' in out          # gradient snippet
    assert '"fill": "#2D6CDF"' in out      # solid snippet
    assert '"background": {}' in out       # none snippet
    assert '"angle": 135' in out
    # and the watermark is offered as the fourth treatment
    assert "bg_icon_iconify_id" in out and '"opacity": 0.45' in out


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_catalog_warns_that_a_bare_glyph_needs_contrast(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    out = _run(tmp_path, styles="none")
    assert "dark" in out.lower()


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_catalog_names_the_sample_glyph(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    out = _run(tmp_path, fg_iconify_id="ph:eye", fg_color="#101010")
    assert "ph:eye" in out and "#101010" in out


# ── watermark layer end to end ────────────────────────────────────────────────

@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_bg_icon_is_fetched_and_drawn_on_every_shape_tile(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    _run(tmp_path, styles="solid", shapes="circle", bg_icon_iconify_id="mdi:cloud")
    fetched = {call.args[0] for call in mock_fetch.await_args_list}
    assert "mdi:cloud" in fetched, "watermark glyph was never fetched"


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_watermark_changes_the_rendered_tile(mock_fetch, tmp_path):
    mock_fetch.return_value = CIRCLE_SVG
    plain = tmp_path / "plain"
    marked = tmp_path / "marked"
    asyncio.run(server.preview_backgrounds(str(plain), styles="solid", shapes="square", size=32))
    asyncio.run(server.preview_backgrounds(str(marked), styles="solid", shapes="square",
                                           size=32, bg_icon_iconify_id="mdi:cloud"))
    a = Image.open(plain / "preview_square_solid.png").convert("RGBA")
    b = Image.open(marked / "preview_square_solid.png").convert("RGBA")
    assert a.tobytes() != b.tobytes(), "watermark layer had no visible effect"


# ── error handling (the tool reports, it does not raise) ─────────────────────

@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_unknown_style_is_reported_not_raised(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    out = _run(tmp_path, styles="glow")
    assert out.startswith("Error:") and "glow" in out
    assert "gradient" in out and "solid" in out and "none" in out


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_unknown_shape_is_reported_not_raised(mock_fetch, tmp_path):
    mock_fetch.return_value = SQUARE_SVG
    out = _run(tmp_path, shapes="nosuchshape")
    assert out.startswith("Error:") and "nosuchshape" in out


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_iconify_http_error_is_reported(mock_fetch, tmp_path):
    import httpx
    from unittest.mock import MagicMock
    mock_fetch.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock(status_code=404))
    out = _run(tmp_path, styles="solid", shapes="circle")
    assert "Failed to fetch" in out and "404" in out
