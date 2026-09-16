"""
Tests for the rendering pipeline in pr-icon-generator/server.py (post-rewrite API).

Covers the pure helpers — hex_to_rgb, shape discovery/loading, glyph_box parsing,
linear_gradient, fill_from_alpha, scale_alpha, make_solid, place_glyph, resolve_placement —
and the async build_background / _render composition. No network: fetch_icon_svg is mocked
wherever a glyph is needed.

Background shapes are the SVGs in mcps/pr-icon-generator/backgrounds/, so the shape tests run
against the real shipped artwork rather than a fixed list of built-in shapes.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image, ImageDraw

import server


# A tiny, self-contained SVG so svg_to_alpha produces a solid glyph with no network.
SQUARE_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24">'
    b'<rect x="4" y="4" width="16" height="16" fill="#000000"/></svg>'
)

# Shapes whose artwork is known-unfinished. They stay in backgrounds/ so they are visible as
# outstanding work, but are excluded from the "every shape renders" sweep. Remove a name here the
# moment its SVG is re-exported — test_pending_shapes_still_pending fails if you forget.
PENDING_SHAPES: set[str] = set()

# Every shape actually shipped in backgrounds/ — parametrised so a newly added SVG is covered
# automatically, and a broken one fails the suite.
SHAPES = sorted(set(server.shape_index()) - PENDING_SHAPES)


# ── hex_to_rgb ─────────────────────────────────────────────────────────────────

def test_hex_to_rgb_black():
    assert server.hex_to_rgb("#000000") == (0, 0, 0)


def test_hex_to_rgb_white():
    assert server.hex_to_rgb("#FFFFFF") == (255, 255, 255)


def test_hex_to_rgb_no_hash():
    assert server.hex_to_rgb("FF0000") == (255, 0, 0)


def test_hex_to_rgb_shorthand_expands():
    assert server.hex_to_rgb("#abc") == (170, 187, 204)


def test_hex_to_rgb_none_defaults_black():
    assert server.hex_to_rgb(None) == (0, 0, 0)


def test_hex_to_rgb_returns_three_ints():
    r, g, b = server.hex_to_rgb("#1A2B3C")
    assert all(isinstance(c, int) for c in (r, g, b))


# ── shape discovery ──────────────────────────────────────────────────────────

def test_shape_index_is_not_empty():
    assert SHAPES, "no background SVGs found in backgrounds/"


def test_shape_slug_strips_prefix_and_lowercases():
    from pathlib import Path
    assert server.shape_slug(Path("bg-icon_Arrow-Square.svg")) == "arrow-square"


def test_shape_index_slugs_carry_no_prefix():
    assert not any(s.startswith("bg-icon") for s in SHAPES)


def test_size_svg_root_only_touches_the_root_element():
    # The background SVGs are built from <rect> elements with their own width/height; a blanket
    # width="..." substitution would resize the geometry instead of the canvas.
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 360">'
           '<rect x="0" width="360" height="360"/></svg>')
    out = server.size_svg_root(svg, 96)
    assert '<rect x="0" width="360" height="360"/>' in out
    assert 'width="96" height="96"' in out


def test_size_svg_root_replaces_existing_root_dimensions():
    svg = '<svg width="24" height="24" viewBox="0 0 24 24"><rect width="24" height="24"/></svg>'
    out = server.size_svg_root(svg, 96)
    assert out.count('width="96"') == 1
    assert 'width="24" height="24" viewBox' not in out


# ── load_shape_mask ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("shape", SHAPES)
def test_shape_mask_size_and_mode(shape):
    m = server.load_shape_mask(shape, 96)
    assert m.size == (96, 96)
    assert m.mode == "L"


@pytest.mark.parametrize("shape", SHAPES)
def test_shape_mask_has_fill(shape):
    m = server.load_shape_mask(shape, 96)
    assert m.getbbox() is not None, f"shape '{shape}' produced an empty mask"


def test_shape_mask_unknown_raises_and_lists_available():
    with pytest.raises(ValueError) as e:
        server.load_shape_mask("nonexistent_shape", 96)
    assert "nonexistent_shape" in str(e.value)
    assert SHAPES[0] in str(e.value), "error should list the available shapes"


def test_shape_mask_is_cached_per_size(tmp_path):
    a = server.load_shape_mask(SHAPES[0], 64)
    b = server.load_shape_mask(SHAPES[0], 64)
    assert a is b


def test_shape_mask_rejects_raster_image_svg(tmp_path, monkeypatch):
    # An <image> element can't be tinted, so it must fail loudly rather than render a black box.
    d = tmp_path / "backgrounds"
    d.mkdir()
    (d / "bg-icon_Raster.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 360">'
        '<image width="512" height="512" xlink:href="x.png"/></svg>', encoding="utf-8")
    monkeypatch.setattr(server, "BACKGROUNDS_DIR", d)
    with pytest.raises(ValueError, match="raster"):
        server.load_shape_mask("raster", 96)


def test_shape_mask_rejects_empty_svg(tmp_path, monkeypatch):
    d = tmp_path / "backgrounds"
    d.mkdir()
    (d / "bg-icon_Empty.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 360"/>', encoding="utf-8")
    monkeypatch.setattr(server, "BACKGROUNDS_DIR", d)
    with pytest.raises(ValueError, match="empty"):
        server.load_shape_mask("empty", 96)


# ── glyph box (authored placement) ───────────────────────────────────────────

def test_pending_shapes_still_pending():
    # Guards PENDING_SHAPES from going stale: once the artwork is fixed, the shape renders and
    # this fails, prompting you to drop it from the exclusion set.
    for name in PENDING_SHAPES:
        with pytest.raises(ValueError):
            server.load_shape_mask(name, 64)


@pytest.mark.parametrize("shape", SHAPES)
def test_every_shape_annotates_a_glyph_box(shape):
    # A shape with no box silently falls back to DEFAULT_GLYPH_BOX, which would look like a
    # placement bug rather than missing artwork — so assert the annotation is really there.
    _, box = server.split_glyph_box(server.shape_index()[shape].read_text(encoding="utf-8"))
    assert box is not None, f"{shape} has no {server.GLYPH_BOX_COLOR} glyph box"


@pytest.mark.parametrize("shape", SHAPES)
def test_glyph_box_normalised_and_on_canvas(shape):
    x, y, w, h = server.glyph_box(shape)
    assert 0.0 < w <= 1.0 and 0.0 < h <= 1.0
    assert -0.01 <= x and -0.01 <= y
    assert x + w <= 1.01 and y + h <= 1.01


def test_glyph_box_reads_authored_rect():
    # bg-icon_Square.svg's box is x=21.9 y=24.12 w=311.77 h=311.77 in a 360 viewBox.
    x, y, w, h = server.glyph_box("square")
    assert (x, y) == pytest.approx((21.9 / 360, 24.12 / 360), abs=1e-4)
    assert (w, h) == pytest.approx((311.77 / 360, 311.77 / 360), abs=1e-4)


def test_glyph_box_supports_non_square_boxes():
    # Document's box is 261x192 — wider than tall. A square glyph must fit the shorter side.
    _, _, w, h = server.glyph_box("document")
    assert w > h
    assert server.box_to_fit_anchor((0, 0, w, h))[0] == pytest.approx(h)


def test_glyph_box_falls_back_when_unannotated(tmp_path, monkeypatch):
    d = tmp_path / "backgrounds"
    d.mkdir()
    (d / "bg-icon_Plain.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 360">'
        '<rect width="360" height="360"/></svg>', encoding="utf-8")
    monkeypatch.setattr(server, "BACKGROUNDS_DIR", d)
    assert server.glyph_box("plain") == server.DEFAULT_GLYPH_BOX


def test_glyph_box_resolved_by_colour_not_class_name(tmp_path, monkeypatch):
    # Illustrator renumbers cls-N between exports, so matching the class name would break.
    d = tmp_path / "backgrounds"
    d.mkdir()
    (d / "bg-icon_Renamed.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 360">'
        f'<defs><style>.cls-7 {{ fill: {server.GLYPH_BOX_COLOR}; }}</style></defs>'
        '<rect width="360" height="360"/>'
        '<rect class="cls-7" x="90" y="90" width="180" height="180"/></svg>', encoding="utf-8")
    monkeypatch.setattr(server, "BACKGROUNDS_DIR", d)
    assert server.glyph_box("renamed") == pytest.approx((0.25, 0.25, 0.5, 0.5))


def test_glyph_box_is_stripped_from_the_rendered_mask(tmp_path, monkeypatch):
    # The box is an annotation; if it leaked into the silhouette it would tint as artwork.
    d = tmp_path / "backgrounds"
    d.mkdir()
    common = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 360">'
              '<rect x="0" y="0" width="180" height="180"/>')
    (d / "bg-icon_Clean.svg").write_text(common + '</svg>', encoding="utf-8")
    (d / "bg-icon_Boxed.svg").write_text(
        common + f'<rect fill="{server.GLYPH_BOX_COLOR}" x="200" y="200" '
                 f'width="100" height="100"/></svg>', encoding="utf-8")
    monkeypatch.setattr(server, "BACKGROUNDS_DIR", d)
    clean = list(server.load_shape_mask("clean", 48).getdata())
    boxed = list(server.load_shape_mask("boxed", 48).getdata())
    assert clean == boxed


# ── trim_alpha / no-background glyphs fill the canvas ────────────────────────

# An SVG whose ink occupies only the middle half of its viewBox — the padding Iconify glyphs
# carry, exaggerated so the assertions are unambiguous.
PADDED_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24">'
    b'<rect x="6" y="6" width="12" height="12" fill="#000000"/></svg>'
)
# Ink 12 wide x 6 tall in a 24 viewBox — non-square, to check aspect is preserved.
WIDE_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24">'
    b'<rect x="6" y="9" width="12" height="6" fill="#000000"/></svg>'
)


def _ink(img, threshold=40):
    """Bounding box of the visibly opaque pixels, ignoring anti-aliasing haze."""
    alpha = img.split()[-1] if img.mode == "RGBA" else img
    return alpha.point(lambda p: 255 if p > threshold else 0).getbbox()


def test_trim_alpha_crops_to_ink():
    alpha = Image.new("L", (40, 40), 0)
    ImageDraw.Draw(alpha).rectangle([10, 15, 29, 24], fill=255)
    assert server.trim_alpha(alpha).size == (20, 10)


def test_trim_alpha_leaves_a_full_bleed_glyph_alone():
    alpha = Image.new("L", (32, 32), 255)
    assert server.trim_alpha(alpha).size == (32, 32)


def test_trim_alpha_survives_an_empty_mask():
    alpha = Image.new("L", (16, 16), 0)
    assert server.trim_alpha(alpha).size == (16, 16)   # nothing to crop to; must not crash


def test_trim_alpha_ignores_antialiasing_haze():
    # A faint wash must not count as ink, or nothing would ever be trimmed.
    alpha = Image.new("L", (40, 40), server.GLYPH_INK_THRESHOLD)
    ImageDraw.Draw(alpha).rectangle([10, 10, 19, 19], fill=255)
    assert server.trim_alpha(alpha).size == (10, 10)


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_no_background_glyph_fills_the_canvas(mock_fetch):
    # The whole point: with no background the glyph IS the icon, so its long side must reach the
    # edge. Without trimming this padded glyph would only cover half the canvas.
    mock_fetch.return_value = PADDED_SVG
    img = asyncio.run(server._render("mdi:x", (0, 0, 0), {}, 24))
    x0, y0, x1, y1 = _ink(img)
    assert max(x1 - x0, y1 - y0) == 24


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_no_background_glyph_keeps_its_aspect_ratio(mock_fetch):
    # Fills on the long side only; the short side scales with it rather than stretching.
    mock_fetch.return_value = WIDE_SVG
    img = asyncio.run(server._render("mdi:x", (0, 0, 0), {}, 24))
    x0, y0, x1, y1 = _ink(img)
    assert (x1 - x0) == 24
    assert (y1 - y0) == pytest.approx(12, abs=1)


def _light_ink(img, threshold=200):
    """Bounding box of near-white pixels — the glyph, when drawn white on a dark background."""
    grey = img.convert("RGB").convert("L")
    return grey.point(lambda p: 255 if p > threshold else 0).getbbox()


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_backgrounded_glyph_is_trimmed(mock_fetch):
    # With a background the glyph still sits in the authored box, but its own viewBox padding
    # isn't breathing room the user asked for — it just makes the icon look too small. PADDED_SVG's
    # ink is half its viewBox; trimmed, it must fill the box's long side, not half of it.
    mock_fetch.return_value = PADDED_SVG
    size = 48
    img = asyncio.run(server._render(
        "mdi:x", (255, 255, 255), {"shape": {"type": "square", "fill": "#000000"}}, size))
    fit, _ = server.resolve_placement({"shape": {"type": "square"}}, None)
    box_px = fit * size
    x0, y0, x1, y1 = _light_ink(img)
    assert max(x1 - x0, y1 - y0) == pytest.approx(box_px, abs=2), "glyph padding was not stripped"


def test_has_background_detects_each_layer():
    assert server.has_background({"shape": {"type": "square"}})
    assert server.has_background({"icon": {"iconify_id": "mdi:star"}})
    assert not server.has_background({})
    assert not server.has_background(None)
    assert not server.has_background({"shape": {}})          # shape with no type draws nothing
    assert not server.has_background({"icon": {"color": "#FFF"}})   # icon with no id draws nothing


# ── box ↔ fit/anchor conversion ──────────────────────────────────────────────

def test_box_to_fit_anchor_centred_box():
    fit, anchor = server.box_to_fit_anchor((0.1, 0.1, 0.8, 0.8))
    assert fit == pytest.approx(0.8)
    assert anchor == pytest.approx(server.CENTER)


def test_box_to_fit_anchor_full_canvas_box_is_centred():
    fit, anchor = server.box_to_fit_anchor((0.0, 0.0, 1.0, 1.0))
    assert fit == pytest.approx(1.0)
    assert anchor == pytest.approx(server.CENTER)   # no free space; must not divide by zero


def test_box_to_fit_anchor_corner_box():
    fit, anchor = server.box_to_fit_anchor((0.0, 0.0, 0.5, 0.5))
    assert fit == pytest.approx(0.5)
    assert anchor == pytest.approx((0.0, 0.0))


@pytest.mark.parametrize("box", [(0.1, 0.2, 0.5, 0.5), (0.0, 0.0, 0.8, 0.8), (0.3, 0.1, 0.6, 0.6)])
def test_fit_anchor_round_trips_for_square_boxes(box):
    fit, anchor = server.box_to_fit_anchor(box)
    assert server.fit_anchor_to_box(fit, anchor) == pytest.approx(box)


# ── linear_gradient ──────────────────────────────────────────────────────────

def test_linear_gradient_size_and_mode():
    g = server.linear_gradient(32, (0, 0, 0), (255, 255, 255), 0)
    assert g.size == (32, 32)
    assert g.mode == "RGB"


def test_linear_gradient_endpoints_differ():
    g = server.linear_gradient(32, (0, 0, 0), (255, 255, 255), 0)  # 0° = left→right
    assert sum(g.getpixel((0, 16))) < sum(g.getpixel((31, 16)))


# ── fill_from_alpha ──────────────────────────────────────────────────────────

def test_fill_from_alpha_tuple_returns_rgba():
    alpha = Image.new("L", (10, 10), 255)
    out = server.fill_from_alpha(alpha, (255, 0, 0))
    assert out.mode == "RGBA"
    assert out.getpixel((5, 5)) == (255, 0, 0, 255)


def test_fill_from_alpha_respects_mask():
    alpha = Image.new("L", (10, 10), 0)
    alpha.putpixel((5, 5), 255)
    out = server.fill_from_alpha(alpha, (0, 255, 0))
    assert out.getpixel((5, 5))[3] == 255
    assert out.getpixel((0, 0))[3] == 0


def test_fill_from_alpha_accepts_image_fill():
    alpha = Image.new("L", (16, 16), 255)
    grad = server.linear_gradient(8, (0, 0, 0), (255, 255, 255), 0)  # different size on purpose
    out = server.fill_from_alpha(alpha, grad)
    assert out.mode == "RGBA"
    assert out.size == (16, 16)  # fill image resized to the mask


# ── scale_alpha ───────────────────────────────────────────────────────────────

def test_scale_alpha_reduces_alpha_to_factor():
    img = Image.new("RGBA", (10, 10), (200, 100, 50, 255))
    out = server.scale_alpha(img, 0.65)
    px = out.getpixel((5, 5))
    assert px[:3] == (200, 100, 50)        # colour preserved
    assert px[3] == round(255 * 0.65)       # 166


def test_scale_alpha_zero_is_transparent():
    img = Image.new("RGBA", (4, 4), (10, 20, 30, 255))
    out = server.scale_alpha(img, 0.0)
    assert out.getbbox() is None


# ── make_solid ───────────────────────────────────────────────────────────────

def test_make_solid_leaves_solid_icon_unchanged():
    alpha = Image.new("L", (96, 96), 0)
    ImageDraw.Draw(alpha).rectangle([10, 10, 86, 86], fill=255)
    solid = server.make_solid(alpha)
    assert solid.getpixel((48, 48)) == 255   # centre of solid rect stays solid


def test_make_solid_fills_interior_hole():
    # Ring-shaped mask (simulates an outline icon): outer circle filled, inner hole.
    alpha = Image.new("L", (96, 96), 0)
    draw = ImageDraw.Draw(alpha)
    draw.ellipse([5, 5, 91, 91], fill=255)   # outer ring
    draw.ellipse([28, 28, 68, 68], fill=0)   # interior hole (~40px wide)
    solid = server.make_solid(alpha)
    assert solid.getpixel((48, 48)) == 255   # centre hole should be filled


def test_make_solid_returns_binary():
    # All output pixels must be exactly 0 or 255 (binary after threshold).
    alpha = Image.new("L", (96, 96), 0)
    ImageDraw.Draw(alpha).ellipse([20, 20, 76, 76], fill=255)
    solid = server.make_solid(alpha)
    values = set(solid.getdata())
    assert values <= {0, 255}


def test_make_solid_mode_preserved():
    alpha = Image.new("L", (64, 64), 128)
    assert server.make_solid(alpha).mode == "L"


# ── resolve_placement ────────────────────────────────────────────────────────

def test_resolve_placement_uses_the_authored_glyph_box():
    assert server.resolve_placement({"shape": {"type": "square"}}, None) == \
        server.box_to_fit_anchor(server.glyph_box("square"))


def test_resolve_placement_differs_per_shape():
    # Placement is measured from the artwork, so two different shapes must not share a result.
    assert server.resolve_placement({"shape": {"type": "square"}}, None) != \
        server.resolve_placement({"shape": {"type": "right-triangle"}}, None)


def test_resolve_placement_follows_an_inset_shape():
    # A shape inset by its own `align` takes the glyph with it: the glyph shrinks by the same
    # factor, otherwise it would be sized against a shape that isn't there.
    plain = server.resolve_placement({"shape": {"type": "square"}}, None)
    inset = server.resolve_placement(
        {"shape": {"type": "square", "align": {"fit": 0.5, "anchor": [0.0, 0.0]}}}, None)
    assert inset[0] == pytest.approx(plain[0] * 0.5)
    assert inset[1][0] < plain[1][0] and inset[1][1] < plain[1][1]


def test_resolve_placement_no_background_fills_canvas():
    fit, anchor = server.resolve_placement({}, None)
    assert fit == server.NOBG_FIT
    assert tuple(anchor) == server.CENTER


def test_resolve_placement_no_background_is_full_canvas():
    # Glyph-only icons (no bg at all) render at 100% of the canvas.
    assert server.NOBG_FIT == 1.0


def test_resolve_placement_bg_icon_only_uses_bg_icon_fit():
    fit, anchor = server.resolve_placement({"icon": {"iconify_id": "mdi:star"}}, None)
    assert fit == server.BG_ICON_FIT
    assert tuple(anchor) == server.CENTER


def test_resolve_placement_bg_icon_fit_is_85_percent():
    assert server.BG_ICON_FIT == 0.85


def test_resolve_placement_override_wins():
    fit, anchor = server.resolve_placement(
        {"shape": {"type": "square"}}, {"fit": 0.5, "anchor": [0.1, 0.2]})
    assert fit == 0.5
    assert tuple(anchor) == (0.1, 0.2)


# ── resolve_layer_align ──────────────────────────────────────────────────────

def test_resolve_layer_align_defaults_to_full_bleed_centred():
    fit, anchor = server.resolve_layer_align(None)
    assert fit == 1.0
    assert anchor == server.CENTER


def test_resolve_layer_align_empty_spec_defaults_to_full_bleed_centred():
    fit, anchor = server.resolve_layer_align({"type": "circle"})
    assert fit == 1.0
    assert anchor == server.CENTER


def test_resolve_layer_align_reads_fit_and_anchor():
    fit, anchor = server.resolve_layer_align({"align": {"fit": 0.6, "anchor": [0.2, 0.8]}})
    assert fit == 0.6
    assert anchor == (0.2, 0.8)


def test_resolve_layer_align_partial_override_keeps_other_default():
    fit, anchor = server.resolve_layer_align({"align": {"fit": 0.5}})
    assert fit == 0.5
    assert anchor == server.CENTER


# ── build_background ─────────────────────────────────────────────────────────

def test_build_background_none_is_transparent():
    img = asyncio.run(server.build_background({}, 96))
    assert img.size == (96, 96)
    assert img.mode == "RGBA"
    assert img.getbbox() is None


def test_build_background_solid_shape_opaque():
    img = asyncio.run(server.build_background({"shape": {"type": "circle", "fill": "#2D6CDF"}}, 96))
    assert img.getbbox() is not None


def test_build_background_gradient_shape_opaque():
    bg = {"shape": {"type": "square", "gradient": {"from": "#000000", "to": "#FFFFFF", "angle": 135}}}
    img = asyncio.run(server.build_background(bg, 96))
    assert img.getbbox() is not None


def test_build_background_shape_align_moves_toward_anchor():
    bg_default = {"shape": {"type": "square", "fill": "#2D6CDF"}}
    bg_aligned = {"shape": {"type": "square", "fill": "#2D6CDF",
                            "align": {"fit": 0.5, "anchor": [1.0, 1.0]}}}
    default_bbox = asyncio.run(server.build_background(bg_default, 96)).getbbox()
    aligned_bbox = asyncio.run(server.build_background(bg_aligned, 96)).getbbox()
    default_cx = (default_bbox[0] + default_bbox[2]) / 2
    aligned_cx = (aligned_bbox[0] + aligned_bbox[2]) / 2
    assert aligned_cx > default_cx
    assert (aligned_bbox[2] - aligned_bbox[0]) < (default_bbox[2] - default_bbox[0])


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_build_background_with_bg_icon(mock_fetch):
    mock_fetch.return_value = SQUARE_SVG
    bg = {"shape": {"type": "square", "fill": "#000000"},
          "icon": {"iconify_id": "mdi:star", "color": "#FFFFFF"}}
    img = asyncio.run(server.build_background(bg, 64))
    assert img.getbbox() is not None


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_build_background_icon_align_moves_toward_anchor(mock_fetch):
    mock_fetch.return_value = SQUARE_SVG
    bg_default = {"icon": {"iconify_id": "mdi:square", "opacity": 1.0}}
    bg_aligned = {"icon": {"iconify_id": "mdi:square", "opacity": 1.0,
                          "align": {"fit": 0.4, "anchor": [1.0, 1.0]}}}
    default_bbox = asyncio.run(server.build_background(bg_default, 64)).getbbox()
    aligned_bbox = asyncio.run(server.build_background(bg_aligned, 64)).getbbox()
    default_cx = (default_bbox[0] + default_bbox[2]) / 2
    aligned_cx = (aligned_bbox[0] + aligned_bbox[2]) / 2
    default_cy = (default_bbox[1] + default_bbox[3]) / 2
    aligned_cy = (aligned_bbox[1] + aligned_bbox[3]) / 2
    assert aligned_cx > default_cx
    assert aligned_cy > default_cy
    assert (aligned_bbox[2] - aligned_bbox[0]) < (default_bbox[2] - default_bbox[0])


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_build_background_bg_icon_default_opacity_is_partial(mock_fetch):
    # Without an explicit opacity the bg.icon blends at BG_ICON_OPACITY < 1.0.
    # A pure-white icon over a pure-black shape must produce pixels lighter than
    # black but darker than white (i.e. partially blended).
    mock_fetch.return_value = SQUARE_SVG
    bg = {"shape": {"type": "square", "fill": "#000000"},
          "icon": {"iconify_id": "mdi:square"}}   # colour defaults to BG_ICON_COLOR (#FFFFFF)
    img = asyncio.run(server.build_background(bg, 64))
    pixels = list(img.getdata())
    opaque = [p for p in pixels if p[3] == 255]
    assert opaque, "expected opaque pixels from the solid shape"
    # At least one opaque pixel must be grey (blended icon over black shape)
    grey = [p for p in opaque if 0 < p[0] < 255]
    assert grey, "expected partially blended (grey) pixels — bg.icon must not be fully opaque"


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_build_background_bg_icon_explicit_opacity_respected(mock_fetch):
    mock_fetch.return_value = SQUARE_SVG
    # opacity: 1.0 → icon is fully opaque white over black → result pixels are white in icon area
    bg = {"shape": {"type": "square", "fill": "#000000"},
          "icon": {"iconify_id": "mdi:square", "color": "#FFFFFF", "opacity": 1.0}}
    img = asyncio.run(server.build_background(bg, 64))
    pixels = [p for p in img.getdata() if p[3] == 255]
    white = [p for p in pixels if p[0] > 200]
    assert white, "opacity:1.0 should produce fully-white icon pixels over black"


def test_bg_icon_color_default_is_white():
    assert server.BG_ICON_COLOR == "#FFFFFF"


def test_bg_icon_opacity_default_is_partial():
    assert 0 < server.BG_ICON_OPACITY < 1.0


# ── _render ──────────────────────────────────────────────────────────────────

@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_render_fg_only_size_and_mode(mock_fetch):
    mock_fetch.return_value = SQUARE_SVG
    img = asyncio.run(server._render("mdi:square", (255, 0, 0), {}, 24, None))
    assert img.size == (24, 24)
    assert img.mode == "RGBA"
    assert img.getbbox() is not None


@patch("server.fetch_icon_svg", new_callable=AsyncMock)
def test_render_plugin_size(mock_fetch):
    mock_fetch.return_value = SQUARE_SVG
    bg = {"shape": {"type": "rounded-square", "fill": "#2D6CDF"}}
    img = asyncio.run(server._render("mdi:square", (255, 255, 255), bg, 16, None))
    assert img.size == (16, 16)
