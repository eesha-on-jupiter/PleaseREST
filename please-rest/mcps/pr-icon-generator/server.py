"""
PleaseREST — pr-icon-generator MCP server
---------------------------------
Tools:
  generate_icon           — one 24x24 component icon, driven by icons.json
  generate_plugin_icon    — the 16x16 plugin/category icon for the GH ribbon; size/out_name
                            override it for the large README / listing logo
  list_background_shapes  — the background shapes available in backgrounds/
  preview_backgrounds     — render every shape x fill style to a contact sheet, so the
                            user can SEE the options before icons.json is authored
  add_to_resources        — inject a generated PNG into Resources.resx + Designer.cs

Rendering pipeline (all at 4x then downscaled with LANCZOS for clean edges):
  background layer  →  none | solid | gradient | icon (an Iconify glyph behind)
  foreground glyph  →  any Iconify icon, recoloured by silhouette+tint so ANY
                       colour works (white, light, even a gradient fill)

Background shapes come from the SVG files in backgrounds/ — there are no built-in
shapes. Drop an SVG in and it is available immediately under its filename slug.

Style is resolved per component: defaults < subcategory < component override.
Everything is specified in the plugin's icons.json (authored post-spec by the
pr-icons skill).

config_path is REQUIRED and names that icons.json. icons.template.json next to
this file is the starting point pr-icons copies; it is never rendered directly.
"""

import io
import json
import math
import base64
import platform
import re
import subprocess
from pathlib import Path

import httpx
import resvg_py
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pr-icon-generator")

# ── Config ───────────────────────────────────────────────────────────────────
# icons.template.json next to this file is a TEMPLATE, not a usable config — pr-icons copies it
# as the starting point for a plugin's icons.json. There is deliberately no default config: every
# call names the plugin's own icons.json, so a missing config_path fails loudly instead of
# silently rendering someone else's plugin's icons.
CONFIG_TEMPLATE = Path(__file__).parent / "icons.template.json"

def load_config(config_path: str | None = None) -> tuple[dict, Path]:
    """Load a plugin's icons.json. Returns (config, resolved path).

    `config_path` is required; see CONFIG_TEMPLATE above for why there is no default.
    Always re-read from disk — icons.json is small and this runs once per icon, so there's
    no benefit to caching it, only the risk of rendering against a stale copy after an edit
    (e.g. a "redo all icons" pass that rewrites icons.json mid-session).
    """
    if not config_path:
        raise ValueError(
            "config_path is required — pass the path to the plugin's icons.json. "
            f"(For a new plugin, start from the template at {CONFIG_TEMPLATE.name}.)")
    resolved = Path(config_path).resolve()
    with open(resolved, "r", encoding="utf-8") as f:
        return json.load(f), resolved

# ── Render constants ─────────────────────────────────────────────────────────
SCALE        = 4            # render at finalsize*SCALE, then downscale
COMPONENT_PX = 24           # component icon final size
PLUGIN_PX    = 16           # plugin / category icon final size

# Glyph placement:
#  - a background shape → read from the glyph box drawn in that shape's SVG (see glyph_box).
#  - background icon, no shape → the bg icon IS the background; the glyph sits at 85%, centred.
#  - no background at all → glyph fills the full canvas (100%), centred.
NOBG_FIT    = 1.0
BG_ICON_FIT = 0.85
CENTER      = (0.5, 0.5)

# Background icon — the optional Iconify glyph behind the foreground. Always rendered as a solid
# silhouette (interior holes of outline icons are filled in). Opacity is a separate control so the
# user can dial the lightness independently of the fill colour.
BG_ICON_COLOR   = "#FFFFFF"       # default fill colour for bg.icon
BG_ICON_OPACITY = 0.45            # default opacity for bg.icon overlay (0..1)

# ── Background shapes ────────────────────────────────────────────────────────
# Every shape is an SVG in backgrounds/, named bg-icon_<Name>.svg. There are no built-in
# shapes — the folder IS the shape set. Drop an SVG in and it becomes available under its
# filename slug (bg-icon_Arrow-Square.svg → "arrow-square") with no code change.
#
# Each file carries BOTH layers of the design:
#   - the background silhouette itself (unfilled geometry, rasterised and then tinted)
#   - a GLYPH BOX: a rect filled GLYPH_BOX_COLOR marking where the foreground icon goes
# The glyph box is stripped before the background is rasterised, so it never renders — it is
# purely a placement annotation authored in Illustrator alongside the artwork. This is why
# placement needs no per-shape table in code: the designer draws it, the renderer reads it.
#
# Authoring rules for a background SVG:
#   - square viewBox — the canvas is square, so a non-square viewBox renders letterboxed
#   - background geometry with NO fill attribute; it is rasterised to a silhouette and then
#     tinted with the configured colour/gradient, so any fill in the file is discarded anyway
#   - exactly one GLYPH_BOX_COLOR rect marking the foreground area (it may be non-square)
#   - vector only — an <image> element cannot be tinted and is rejected with a clear error
BACKGROUNDS_DIR = Path(__file__).parent / "backgrounds"
SHAPE_GLOB      = "bg-icon_*.svg"

# The glyph-box marker colour. Matched on the resolved fill, not on Illustrator's generated
# class name (`cls-1`), because that name is not stable across re-exports.
GLYPH_BOX_COLOR = "#ed1c24"

# Fallback when a background carries no glyph box at all — centred, inset. Only reached by a
# hand-written SVG; every shipped shape annotates its own box.
DEFAULT_GLYPH_BOX = (0.10, 0.10, 0.80, 0.80)   # (x, y, w, h), normalised 0..1

def hex_to_rgb(hex_color):
    hex_color = (hex_color or "#000000").lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

# ── Shape discovery ──────────────────────────────────────────────────────────

def shape_slug(path: Path) -> str:
    """bg-icon_Arrow-Square.svg → 'arrow-square'."""
    stem = path.stem
    name = stem.split("_", 1)[1] if "_" in stem else stem
    return name.lower()

def shape_index() -> dict[str, Path]:
    """Map every background SVG's slug to its path.

    Rescanned on each call rather than cached, so an SVG added to backgrounds/ while the
    server is running is picked up without a restart.
    """
    return {shape_slug(p): p for p in sorted(BACKGROUNDS_DIR.glob(SHAPE_GLOB))}

_SVG_OPEN_TAG = re.compile(r"<svg\b[^>]*?/?>", re.IGNORECASE | re.DOTALL)

def size_svg_root(svg_text: str, size: int) -> str:
    """Set width/height on the root <svg> element only.

    Deliberately not a blanket `width="..."` substitution: these background files are built from
    <rect>/<polygon> elements carrying their own width/height, so a global replace would resize
    the geometry instead of the canvas.
    """
    m = _SVG_OPEN_TAG.search(svg_text)
    if not m:
        raise ValueError("no <svg> root element")
    tag = m.group(0).rstrip()
    self_closing = tag.endswith("/>")
    inner = tag[:-2] if self_closing else tag[:-1]
    inner = re.sub(r'\s+(width|height)\s*=\s*"[^"]*"', "", inner, flags=re.IGNORECASE)
    rebuilt = f'{inner.rstrip()} width="{size}" height="{size}"' + ("/>" if self_closing else ">")
    return svg_text[:m.start()] + rebuilt + svg_text[m.end():]

def _glyph_box_classes(svg_text: str) -> set[str]:
    """CSS class names whose rule fills with GLYPH_BOX_COLOR.

    Illustrator emits the box as `class="cls-1"` plus a `<style>` rule `.cls-1 { fill: #ed1c24 }`.
    The generated class name changes between exports, so resolve it by colour instead.
    """
    out = set()
    for block in re.findall(r"<style[^>]*>(.*?)</style>", svg_text, re.DOTALL | re.IGNORECASE):
        for selectors, body in re.findall(r"([^{}]+)\{([^}]*)\}", block):
            if re.search(rf"fill:\s*{GLYPH_BOX_COLOR}\b", body, re.IGNORECASE):
                out.update(re.findall(r"\.([A-Za-z0-9_-]+)", selectors))
    return out

def _is_glyph_box(element: str, classes: set[str]) -> bool:
    """True if this SVG element is the glyph-box marker (by class or by inline fill)."""
    if re.search(rf'fill\s*=\s*"{GLYPH_BOX_COLOR}"', element, re.IGNORECASE):
        return True
    m = re.search(r'class\s*=\s*"([^"]*)"', element)
    return bool(m) and bool(set(m.group(1).split()) & classes)

_ELEMENT = re.compile(r"<(rect|path|circle|ellipse|polygon)\b[^>]*/?>", re.IGNORECASE)

def split_glyph_box(svg_text: str) -> tuple[str, tuple[float, float, float, float] | None]:
    """Separate a background SVG into (artwork without the glyph box, the box's viewBox rect).

    Returns the box as (x, y, w, h) in the file's own viewBox units, or None if unannotated.
    """
    classes = _glyph_box_classes(svg_text)
    box = None
    for m in list(_ELEMENT.finditer(svg_text)):
        el = m.group(0)
        if not _is_glyph_box(el, classes):
            continue
        attrs = {k: float(v) for k, v in re.findall(r'\b(x|y|width|height)\s*=\s*"([-\d.]+)"', el)}
        if "width" in attrs and "height" in attrs:
            box = (attrs.get("x", 0.0), attrs.get("y", 0.0), attrs["width"], attrs["height"])
        svg_text = svg_text.replace(el, "", 1)
    return svg_text, box

def _viewbox_size(svg_text: str) -> tuple[float, float]:
    m = re.search(r'viewBox\s*=\s*"([-\d.\s]+)"', svg_text)
    if not m:
        return 360.0, 360.0
    parts = [float(v) for v in m.group(1).split()]
    return (parts[2], parts[3]) if len(parts) == 4 else (360.0, 360.0)

_mask_cache: dict[tuple, Image.Image] = {}
_box_cache: dict[tuple, tuple] = {}

def _read_shape(shape_name: str) -> tuple[Path, str]:
    index = shape_index()
    path = index.get(shape_name)
    if path is None:
        available = ", ".join(sorted(index)) or "(backgrounds/ is empty)"
        raise ValueError(f"Unknown background shape '{shape_name}'. Available: {available}")
    text = path.read_text(encoding="utf-8")
    if re.search(r"<image\b", text, re.IGNORECASE):
        raise ValueError(
            f"Background '{shape_name}' ({path.name}) embeds a raster <image>. Background "
            f"shapes are tinted silhouettes, so they must be vector — re-export it with the "
            f"artwork as paths.")
    return path, text

def load_shape_mask(shape_name: str, size: int) -> Image.Image:
    """An L-mode mask for a background shape: 255 inside the shape, 0 outside.

    Renders backgrounds/bg-icon_<Name>.svg to a silhouette with the glyph-box marker stripped,
    so the box never appears in output. Cached per (shape, size, mtime) so editing an SVG
    invalidates its cached mask.
    """
    path, text = _read_shape(shape_name)
    key = (shape_name, size, path.stat().st_mtime_ns)
    if key not in _mask_cache:
        artwork, _ = split_glyph_box(text)
        alpha = svg_to_alpha(size_svg_root(artwork, size).encode("utf-8"))
        if alpha.size != (size, size):
            alpha = alpha.resize((size, size), Image.LANCZOS)
        if alpha.getextrema()[1] == 0:
            raise ValueError(
                f"Background '{shape_name}' ({path.name}) renders empty — it has no filled "
                f"geometry outside its glyph box.")
        _mask_cache[key] = alpha
    return _mask_cache[key]

def glyph_box(shape_name: str) -> tuple[float, float, float, float]:
    """The authored foreground area for a shape as (x, y, w, h), normalised to 0..1.

    Read from the GLYPH_BOX_COLOR rect in the shape's SVG — the designer positions the glyph in
    Illustrator and the renderer honours it exactly. Falls back to DEFAULT_GLYPH_BOX only for a
    background that carries no box.
    """
    path, text = _read_shape(shape_name)
    key = (shape_name, path.stat().st_mtime_ns)
    if key not in _box_cache:
        _, box = split_glyph_box(text)
        if box is None:
            _box_cache[key] = DEFAULT_GLYPH_BOX
        else:
            vw, vh = _viewbox_size(text)
            x, y, w, h = box
            _box_cache[key] = (x / vw, y / vh, w / vw, h / vh)
    return _box_cache[key]

# ── Glyph placement, authored in the artwork ─────────────────────────────────
# There is no placement algorithm and no per-shape table: the glyph box drawn in each SVG IS
# the placement. `glyph_box()` reads it; the helpers below convert between that box and the
# (fit, anchor) form that icons.json exposes for overrides.

def box_to_fit_anchor(box) -> tuple[float, tuple[float, float]]:
    """Convert a normalised (x, y, w, h) box to place_glyph's (fit, anchor).

    A square glyph fits the box's shorter side; the anchor then centres it in the box. `anchor`
    is a position within the LEFTOVER space, not a centre, hence the division by (1 - fit).
    """
    x, y, w, h = box
    fit = min(w, h)
    def anchor_for(lo, span):
        centre = lo + span / 2
        free = 1.0 - fit
        return 0.5 if free <= 1e-6 else min(1.0, max(0.0, (centre - fit / 2) / free))
    return fit, (anchor_for(x, w), anchor_for(y, h))

def fit_anchor_to_box(fit: float, anchor) -> tuple[float, float, float, float]:
    """Inverse of box_to_fit_anchor — the box a given (fit, anchor) describes."""
    free = 1.0 - fit
    return (anchor[0] * free, anchor[1] * free, fit, fit)

# ── Gradient ─────────────────────────────────────────────────────────────────

_gradient_cache: dict[tuple, Image.Image] = {}

def linear_gradient(size, c_from, c_to, angle_deg) -> Image.Image:
    """RGB linear gradient across `size`x`size` at `angle_deg` (0 = left→right).

    Memoised on (size, from, to, angle): this is a per-pixel Python loop, and a contact sheet
    re-renders the same gradient once per shape (30+ times). Callers only ever read or resize
    the result, but a copy is returned anyway so a mutating caller can't poison the cache.
    """
    key = (size, tuple(c_from), tuple(c_to), angle_deg)
    if key in _gradient_cache:
        return _gradient_cache[key].copy()
    img = Image.new("RGB", (size, size))
    px  = img.load()
    a   = math.radians(angle_deg)
    dx, dy = math.cos(a), math.sin(a)
    projs = [x * dx + y * dy for x in (0, size - 1) for y in (0, size - 1)]
    pmin, span = min(projs), (max(projs) - min(projs)) or 1.0
    for y in range(size):
        for x in range(size):
            t = ((x * dx + y * dy) - pmin) / span
            px[x, y] = (
                round(c_from[0] + (c_to[0] - c_from[0]) * t),
                round(c_from[1] + (c_to[1] - c_from[1]) * t),
                round(c_from[2] + (c_to[2] - c_from[2]) * t),
            )
    _gradient_cache[key] = img
    return img.copy()

# ── Iconify fetch + silhouette ───────────────────────────────────────────────

_ICONIFY_CACHE: dict[str, str] = {}   # iconify_id → raw SVG text, per process

def parse_iconify_id(iconify_id: str) -> tuple[str, str]:
    """Split 'prefix:name' with a clear error for malformed ids (e.g. 'mdiplus', 'mdi:')."""
    if not isinstance(iconify_id, str) or iconify_id.count(":") != 1:
        raise ValueError(f"Bad Iconify id {iconify_id!r} — expected 'prefix:name' (e.g. 'mdi:plus')")
    prefix, name = (x.strip() for x in iconify_id.split(":"))
    if not prefix or not name:
        raise ValueError(f"Bad Iconify id {iconify_id!r} — expected 'prefix:name' (e.g. 'mdi:plus')")
    return prefix, name

async def fetch_icon_svg(iconify_id: str, render_size: int) -> bytes:
    prefix, name = parse_iconify_id(iconify_id)
    svg = _ICONIFY_CACHE.get(iconify_id)
    if svg is None:
        url = f"https://api.iconify.design/{prefix}/{name}.svg"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            svg = resp.text
        if not svg.lstrip().startswith("<"):
            raise ValueError(f"Iconify returned no SVG for {iconify_id!r} — check the id exists")
        _ICONIFY_CACHE[iconify_id] = svg   # one fetch per id per process (fg + bg + re-renders)
    # force a solid black silhouette regardless of the icon's own colours
    svg = svg.replace("currentColor", "#000000")
    return size_svg_root(svg, render_size).encode("utf-8")

def svg_to_alpha(svg_bytes: bytes) -> Image.Image:
    """Render the (black) glyph on white, return an L-mode alpha mask (255 = glyph).

    Uses resvg (via resvg_py) rather than svglib/reportlab: reportlab's only raster
    backend on this platform is rlPyCairo, which dlopen()s a native libcairo-2.dll that
    isn't installed here. resvg_py ships a self-contained compiled extension with no
    external native dependency, and the root <svg> already carries explicit pixel
    width/height (see size_svg_root), so it rasterises at exactly render_size.
    """
    png = resvg_py.svg_to_bytes(svg_string=svg_bytes.decode("utf-8"), background="#FFFFFF")
    lum = Image.open(io.BytesIO(bytes(png))).convert("L")
    return lum.point(lambda p: 255 - p)   # white bg → 0 alpha, dark glyph → opaque

def fill_from_alpha(alpha: Image.Image, fill) -> Image.Image:
    """Apply `fill` (an (r,g,b) tuple OR an RGB Image) through the alpha mask → RGBA."""
    size = alpha.size
    rgb  = Image.new("RGB", size, fill) if isinstance(fill, tuple) else fill.resize(size, Image.LANCZOS)
    rgba = rgb.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba

def scale_alpha(rgba: Image.Image, factor: float) -> Image.Image:
    """Return a copy of an RGBA image with its alpha channel multiplied by `factor` (0..1)."""
    r, g, b, a = rgba.split()
    a = a.point(lambda p: round(p * factor))
    return Image.merge("RGBA", (r, g, b, a))

GLYPH_INK_THRESHOLD = 8    # alpha above this counts as ink, ignoring anti-aliasing haze

def trim_alpha(alpha: Image.Image) -> Image.Image:
    """Crop an L-mode glyph mask down to its visible ink.

    Iconify glyphs carry padding inside their own viewBox — mdi:plus only draws in ~58% of it,
    mdi:magnify ~75%. Scaling the raw viewBox to the canvas therefore leaves the glyph visibly
    smaller than asked for. Trimming first makes "fill the canvas" mean the glyph's own bounds,
    which is what a fit of 1.0 is supposed to give.
    """
    bbox = alpha.point(lambda p: 255 if p > GLYPH_INK_THRESHOLD else 0).getbbox()
    return alpha.crop(bbox) if bbox else alpha

def make_solid(alpha: Image.Image) -> Image.Image:
    """Fill interior holes in an L-mode alpha mask to produce a solid silhouette.

    Applies a gaussian blur (radius ≈ 1/8 the image width) to bleed strokes together,
    then re-thresholds to binary. Outline icons become solid blobs; solid icons are
    unchanged. Used for background icons.
    """
    r = max(4, alpha.width // 8)
    return alpha.filter(ImageFilter.GaussianBlur(r)).point(lambda p: 255 if p > 15 else 0)

# ── Background layer ─────────────────────────────────────────────────────────

def _fill_for(spec: dict, size: int):
    """A solid (r,g,b) or a gradient RGB image, depending on what `spec` provides."""
    grad = spec.get("gradient")
    if grad:
        return linear_gradient(size, hex_to_rgb(grad.get("from", "#2D2D2D")),
                               hex_to_rgb(grad.get("to", "#000000")), grad.get("angle", 135))
    return hex_to_rgb(spec.get("fill") or spec.get("color") or "#444444")

async def build_background(bg: dict, size: int) -> Image.Image:
    """
    Compose the background from independent OPTIONAL layers:
      - bg["shape"] : a background SVG filled solid or with a gradient  (optional)
      - bg["icon"]  : an Iconify glyph behind the foreground            (optional)
    Provide either, both, or neither. Neither (or no `bg`) → fully transparent (no background).

    Each layer accepts its own optional `align: {fit, anchor}` (same shape as the foreground's
    `glyph` override) to size/position it within the canvas — e.g. a shape inset off-centre, or
    a background icon pushed into a corner. Omitting `align` keeps the full-bleed, centred default.
    """
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if not bg:
        return canvas

    # Layer 1 — optional shape, rendered from its SVG in backgrounds/ (solid or gradient)
    shape = bg.get("shape")
    if shape and shape.get("type"):
        mask = load_shape_mask(shape["type"], size)
        layer = fill_from_alpha(mask, _fill_for(shape, size))
        fit, anchor = resolve_layer_align(shape)
        canvas = place_glyph(canvas, layer, size, fit, anchor)

    # Layer 2 — optional background icon (an Iconify glyph), on top of the shape if present.
    # Always rendered as a solid silhouette (make_solid fills interior holes so outline icons
    # become filled blobs). Opacity is applied separately so lightness is independent of colour.
    icon = bg.get("icon")
    if icon and icon.get("iconify_id"):
        alpha     = make_solid(svg_to_alpha(await fetch_icon_svg(icon["iconify_id"], size)))
        fill      = _fill_for(icon, size) if icon.get("gradient") else hex_to_rgb(icon.get("color", BG_ICON_COLOR))
        icon_rgba = fill_from_alpha(alpha, fill)
        opacity   = icon.get("opacity", BG_ICON_OPACITY)
        if opacity < 1.0:
            icon_rgba = scale_alpha(icon_rgba, opacity)
        fit, anchor = resolve_layer_align(icon)
        canvas = place_glyph(canvas, icon_rgba, size, fit, anchor)

    return canvas

# ── Composite glyph onto background ──────────────────────────────────────────

def resolve_placement(background: dict, override: dict | None):
    """Return (fit, anchor) for the glyph, from the background shape's authored glyph box.

    fit    = glyph's longest side as a fraction of the canvas
    anchor = (ax, ay) in [0,1]; 0.5,0.5 = centred, larger = toward right/bottom
    """
    background = background or {}
    shape = background.get("shape")
    stype = shape.get("type") if shape else None
    if stype:
        fit, anchor = box_to_fit_anchor(glyph_box(stype))
        # The shape layer may itself be inset via `align`; the glyph has to follow it into that
        # sub-rect, otherwise it would be positioned against a shape that isn't there.
        sfit, sanchor = resolve_layer_align(shape)
        if sfit < 1.0:
            fit, anchor = _nest_placement(fit, anchor, sfit, sanchor)
    elif background.get("icon"):
        fit, anchor = BG_ICON_FIT, CENTER
    else:
        fit, anchor = NOBG_FIT, CENTER
    if override:
        fit = override.get("fit", fit)
        anchor = tuple(override.get("anchor", anchor))
    return fit, anchor

def _nest_placement(fit, anchor, outer_fit, outer_anchor):
    """Re-express a placement measured inside a shape as a placement on the whole canvas.

    Used when the background shape is itself inset by its own `align`: the glyph's (fit, anchor)
    was measured against the shape's artwork, so it has to be scaled and shifted into wherever
    that shape actually landed.
    """
    new_fit = fit * outer_fit
    free_out = 1.0 - outer_fit
    free_in  = 1.0 - fit
    free_new = 1.0 - new_fit
    out = []
    for i in range(2):
        origin = outer_anchor[i] * free_out                  # shape box's origin on the canvas
        centre_local = anchor[i] * free_in + fit / 2         # glyph centre within the shape box
        centre = origin + outer_fit * centre_local           # glyph centre on the canvas
        a = 0.5 if free_new <= 1e-6 else (centre - new_fit / 2) / free_new
        out.append(min(1.0, max(0.0, a)))
    return new_fit, tuple(out)

def place_glyph(bg: Image.Image, glyph: Image.Image, size: int, fit: float, anchor) -> Image.Image:
    """Composite `glyph` onto `bg`, scaled to `fit` of `size` and positioned by `anchor`.

    Generic layer compositor — used for the foreground glyph AND for the background
    shape/icon layers (see `resolve_layer_align`), so every layer aligns the same way.
    """
    target = fit * size
    gw, gh = glyph.size
    scale  = min(target / gw, target / gh)
    nw, nh = round(gw * scale), round(gh * scale)
    scaled = glyph.resize((nw, nh), Image.LANCZOS)
    x = round(anchor[0] * (size - nw))
    y = round(anchor[1] * (size - nh))
    bg.alpha_composite(scaled, (x, y))
    return bg

def resolve_layer_align(spec: dict | None) -> tuple[float, tuple[float, float]]:
    """fit/anchor for a background layer (shape or icon), from its optional `align` block.

    Defaults to fit=1.0, anchor=centred — full-bleed, edge to edge — which matches the
    layer's behaviour before alignment was configurable, so omitting `align` is a no-op.
    """
    align = (spec or {}).get("align") or {}
    fit = align.get("fit", 1.0)
    anchor = tuple(align.get("anchor", CENTER))
    return fit, anchor

# ── Style resolution: defaults < subcategory < component ─────────────────────

BACKGROUND_LAYERS = ("shape", "icon")

def _merge(*dicts):
    """Merge background blocks, lowest precedence first.

    `None` (key absent) inherits; an explicit `{}` at any level means "nothing here" — so a
    component with `"background": {}` gets NO background even when its subcategory has one,
    and `"background": {"shape": {...}, "icon": {}}` keeps its own shape but drops the
    inherited bg icon. Within a level, `shape`/`icon` sub-blocks replace (not deep-merge) so
    a component's own shape isn't polluted by the subcategory's gradient/fill.
    """
    out: dict = {}
    for d in dicts:
        if d is None:
            continue
        if not isinstance(d, dict):
            continue
        if d == {}:
            out = {}          # explicit empty: wipe everything inherited so far
            continue
        for k, v in d.items():
            if k in BACKGROUND_LAYERS and v == {}:
                out.pop(k, None)   # explicit empty layer: drop the inherited one
            else:
                out[k] = v
    return out

def resolve_style(config, component_name, subcategory=None, iconify_id=None):
    """Resolve (fg_iconify_id, fg color/gradient, background dict, size, glyph_override).

    Precedence is per level: a component's own `fg_color` beats an inherited `fg` gradient;
    only when BOTH `fg` and `fg_color` are set at the same level does the gradient win.
    """
    defaults = config.get("defaults", {})
    comp = next((c for c in config.get("components", []) if c.get("name") == component_name), {})
    sub_name = subcategory or comp.get("subcategory")
    sub = config.get("subcategories", {}).get(sub_name, {}) if sub_name else {}

    fg_id = iconify_id or comp.get("fg_iconify_id")
    background = _merge(defaults.get("background"), sub.get("background"), comp.get("background"))
    fg = None
    for level in (comp, sub, defaults):          # highest precedence first
        if level.get("fg"):
            fg = level["fg"]; break
        if level.get("fg_color"):
            fg = hex_to_rgb(level["fg_color"]); break
    if fg is None:
        fg = hex_to_rgb("#FFFFFF")
    size = comp.get("size") or defaults.get("size") or COMPONENT_PX
    glyph_override = comp.get("glyph") or sub.get("glyph") or defaults.get("glyph")  # optional fit/anchor
    return (fg_id, fg, background, size, glyph_override)

def is_custom_icon(config, component_name) -> bool:
    """True if the component's icons.json entry says `"custom": true` — a hand-made PNG that
    generate_icon must never overwrite."""
    comp = next((c for c in config.get("components", []) if c.get("name") == component_name), {})
    return bool(comp.get("custom"))

def has_background(background: dict | None) -> bool:
    """True if anything will actually be drawn behind the glyph."""
    background = background or {}
    shape = background.get("shape")
    icon = background.get("icon")
    return bool((shape and shape.get("type")) or (icon and icon.get("iconify_id")))

async def _render(fg_id, fg, background, final_size, glyph_override=None) -> Image.Image:
    render_size = final_size * SCALE
    bg = await build_background(background, render_size)
    if fg_id:
        alpha = svg_to_alpha(await fetch_icon_svg(fg_id, render_size))
        # Iconify glyphs carry their own internal padding (mdi:plus only draws in ~58% of its
        # viewBox), so scaling the raw viewBox to `fit` leaves visible ink well short of the
        # target area — the box authored in the background artwork, or the full canvas when
        # there's no background. Trimming to the glyph's own ink first makes `fit` describe
        # what's actually drawn, so the glyph reaches ~95-100% of its target area either way.
        alpha = trim_alpha(alpha)
        if isinstance(fg, dict):  # foreground gradient
            fill = linear_gradient(render_size, hex_to_rgb(fg.get("from", "#FFFFFF")),
                                   hex_to_rgb(fg.get("to", "#CCCCCC")), fg.get("angle", 135))
        else:
            fill = fg
        fit, anchor = resolve_placement(background, glyph_override)
        glyph = fill_from_alpha(alpha, fill)
        bg = place_glyph(bg, glyph, render_size, fit, anchor)
    return bg.resize((final_size, final_size), Image.LANCZOS)

# ── Tool: list_background_shapes ─────────────────────────────────────────────

@mcp.tool()
def list_background_shapes() -> str:
    """
    List the background shapes available for `background.shape.type` in icons.json.

    Shapes are the SVG files in this server's backgrounds/ folder — add or remove an SVG there
    to change the set. Use this to show the user their real options before authoring icons.json.
    """
    index = shape_index()
    if not index:
        return f"No background shapes found in {BACKGROUNDS_DIR} (expected files named {SHAPE_GLOB})."
    lines = [f"{len(index)} background shapes in {BACKGROUNDS_DIR}:"]
    lines += [f"  {slug:<24} {path.name}" for slug, path in sorted(index.items())]
    return "\n".join(lines)

# ── Tool: preview_backgrounds ────────────────────────────────────────────────
# There are three ways to fill the space behind a glyph, and before this tool existed none of
# them was visible without authoring an icons.json and rendering for real. The template's own
# default (a shape + gradient) therefore became everyone's house style by accident. This renders
# the real options through the real pipeline so the user picks deliberately.

PREVIEW_STYLES = ("gradient", "solid", "none")

# Contact-sheet palette. Tiles sit on white cells over a light sheet so a coloured shape reads
# cleanly; only the transparent 'none' tile gets a checkerboard, because that is the one tile
# whose whole point is that there is nothing behind the glyph.
SHEET_BG        = (245, 245, 245)
SHEET_CELL_BG   = (255, 255, 255)
SHEET_CELL_EDGE = (219, 219, 219)
SHEET_INK       = (32, 32, 32)
SHEET_INK_SOFT  = (112, 112, 112)
CHECKER_LIGHT   = (255, 255, 255)
CHECKER_DARK    = (214, 214, 214)

SHEET_COLS   = 6
SHEET_GAP    = 14
SHEET_MARGIN = 24

def _sheet_font(px: int):
    """PIL's built-in bitmap font, sized if this Pillow supports it.

    Deliberately no font file: the sheet has to render on a headless box with no system fonts.
    """
    try:
        return ImageFont.load_default(size=px)     # Pillow >= 10.1
    except TypeError:                              # older Pillow: fixed-size bitmap font
        return ImageFont.load_default()

def _text_w(draw, text, font) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left

def parse_preview_styles(styles: str) -> list[str]:
    """Comma-separated style names → canonical order, de-duped. Raises on an unknown name."""
    names = [s.strip().lower() for s in (styles or "").split(",") if s.strip()]
    if not names:
        raise ValueError(f"No styles given — valid styles: {', '.join(PREVIEW_STYLES)}")
    unknown = [n for n in names if n not in PREVIEW_STYLES]
    if unknown:
        raise ValueError(f"Unknown style(s): {', '.join(unknown)}. "
                         f"Valid styles: {', '.join(PREVIEW_STYLES)}")
    return [s for s in PREVIEW_STYLES if s in names]

def parse_preview_shapes(shapes: str, index: dict) -> list[str]:
    """Comma-separated shape slugs → list. Empty means every shape. Raises on an unknown slug."""
    raw = [s.strip().lower() for s in (shapes or "").split(",") if s.strip()]
    if not raw:
        return sorted(index)
    unknown = [n for n in raw if n not in index]
    if unknown:
        raise ValueError(f"Unknown background shape(s): {', '.join(unknown)}. "
                         f"Available: {', '.join(sorted(index))}")
    seen: set[str] = set()
    return [n for n in raw if not (n in seen or seen.add(n))]

def preview_background_spec(style, slug, fill, grad_from, grad_to, grad_angle, bg_icon_id) -> dict:
    """The icons.json `background` block a given preview tile stands for.

    This is the literal block the catalog tells the user to paste, so the preview and the paste
    can never drift apart.
    """
    if style == "none":
        return {}
    shape = ({"type": slug, "gradient": {"from": grad_from, "to": grad_to, "angle": grad_angle}}
             if style == "gradient" else {"type": slug, "fill": fill})
    bg = {"shape": shape}
    if bg_icon_id:
        bg["icon"] = {"iconify_id": bg_icon_id, "color": BG_ICON_COLOR, "opacity": BG_ICON_OPACITY}
    return bg

def _checkerboard(size: int, square: int = 8) -> Image.Image:
    """A light checkerboard, the conventional "this is transparent" ground."""
    img = Image.new("RGB", (size, size), CHECKER_LIGHT)
    draw = ImageDraw.Draw(img)
    for y in range(0, size, square):
        for x in range(0, size, square):
            if (x // square + y // square) % 2:
                draw.rectangle([x, y, x + square - 1, y + square - 1], fill=CHECKER_DARK)
    return img

def _contact_sheet(groups, tile_px: int, title: str, subtitle: str) -> Image.Image:
    """Compose the labelled grid.

    `groups` is [(header, [(caption, RGBA tile, checker?), ...]), ...] — one group per style, so
    all the gradients sit together and can be compared without scanning past the solids.
    """
    ttl_font, hdr_font, cap_font = _sheet_font(20), _sheet_font(15), _sheet_font(12)
    cap_line, cap_pad = 14, 6
    cap_h  = cap_line * 2 + cap_pad
    cell_h = tile_px + cap_h
    widest = max((len(tiles) for _, tiles in groups), default=1)
    cols   = max(1, min(SHEET_COLS, widest))

    sheet_w = SHEET_MARGIN * 2 + cols * tile_px + (cols - 1) * SHEET_GAP
    head_h  = SHEET_MARGIN + 26 + 20
    body_h  = 0
    for _, tiles in groups:
        rows = (len(tiles) + cols - 1) // cols
        body_h += 28 + rows * (cell_h + SHEET_GAP)
    sheet_h = head_h + body_h + SHEET_MARGIN

    sheet = Image.new("RGB", (sheet_w, sheet_h), SHEET_BG)
    draw  = ImageDraw.Draw(sheet)
    draw.text((SHEET_MARGIN, SHEET_MARGIN), title, font=ttl_font, fill=SHEET_INK)
    draw.text((SHEET_MARGIN, SHEET_MARGIN + 26), subtitle, font=cap_font, fill=SHEET_INK_SOFT)

    y = head_h
    for header, tiles in groups:
        draw.text((SHEET_MARGIN, y), header, font=hdr_font, fill=SHEET_INK)
        y += 28
        for i, (caption, img, checker) in enumerate(tiles):
            col, row = i % cols, i // cols
            x = SHEET_MARGIN + col * (tile_px + SHEET_GAP)
            ty = y + row * (cell_h + SHEET_GAP)
            ground = _checkerboard(tile_px) if checker else Image.new(
                "RGB", (tile_px, tile_px), SHEET_CELL_BG)
            sheet.paste(ground, (x, ty))
            sheet.paste(img, (x, ty), img)
            draw.rectangle([x, ty, x + tile_px - 1, ty + tile_px - 1], outline=SHEET_CELL_EDGE)
            for line_no, line in enumerate(caption):
                lx = x + max(0, (tile_px - _text_w(draw, line, cap_font)) // 2)
                draw.text((lx, ty + tile_px + 2 + line_no * cap_line), line, font=cap_font,
                          fill=SHEET_INK if line_no == 0 else SHEET_INK_SOFT)
        rows = (len(tiles) + cols - 1) // cols
        y += rows * (cell_h + SHEET_GAP)
    return sheet

def _snippet(background: dict) -> str:
    """A `background` block as a paste-ready icons.json fragment."""
    body = json.dumps({"background": background}, indent=2)
    return "\n".join("    " + line for line in body.splitlines()[1:-1])

@mcp.tool()
async def preview_backgrounds(output_dir: str,
                              fg_iconify_id: str = "mdi:star",
                              styles: str = "gradient,solid,none",
                              shapes: str = "",
                              size: int = 128,
                              fill: str = "#2D6CDF",
                              gradient_from: str = "#2D6CDF",
                              gradient_to: str = "#1B3A8B",
                              gradient_angle: int = 135,
                              fg_color: str = "#FFFFFF",
                              bg_icon_iconify_id: str = "") -> str:
    """
    Render every background option to PNGs plus one labelled contact sheet, so the user can SEE
    the choices and pick before icons.json is written. Reads no config — run it first.

    There are three fill styles behind a glyph:
      gradient — a shape filled with a linear gradient
      solid    — a shape filled with one flat colour
      none     — NO background at all: the glyph alone, filling the canvas

    The shapes are the SVG files in this server's backgrounds/ folder, not a fixed list in code —
    drop a new SVG in and it appears here under its filename slug with no code change.

    Every tile goes through the same renderer as generate_icon, so a preview is exactly what
    you would get. Output: <output_dir>/preview_<slug>_<style>.png per shape+style, one
    <output_dir>/preview_none.png for the no-background option, and contact-sheet.png.

    Args:
        output_dir:         where the PNGs and contact-sheet.png are written (created if needed)
        fg_iconify_id:      the sample foreground glyph, 'prefix:name'
        styles:             comma-separated subset of gradient,solid,none
        shapes:             comma-separated shape slugs; empty = every shape in backgrounds/
        size:               tile size in px (previews are bigger than the real 24px icons)
        fill:               colour for the 'solid' style
        gradient_from/to/angle: the 'gradient' style's ramp
        fg_color:           the sample glyph's colour
        bg_icon_iconify_id: optional watermark glyph behind the foreground, shown on every shape
    """
    try:
        index = shape_index()
        if not index:
            return (f"No background shapes found in {BACKGROUNDS_DIR} "
                    f"(expected files named {SHAPE_GLOB}).")
        style_list = parse_preview_styles(styles)
        shape_list = parse_preview_shapes(shapes, index)

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        fg = hex_to_rgb(fg_color)

        groups, written = [], []
        for style in style_list:
            tiles = []
            if style == "none":
                # One tile, not one per shape: with no shape there is nothing to vary.
                img  = await _render(fg_iconify_id, fg, {}, size)
                path = out_dir / "preview_none.png"
                img.save(path, "PNG")
                written.append(path)
                tiles.append((["(no background)", "none"], img, True))
                header = "none - no shape, no fill; the glyph alone fills the canvas"
            else:
                for slug in shape_list:
                    bg   = preview_background_spec(style, slug, fill, gradient_from,
                                                   gradient_to, gradient_angle, bg_icon_iconify_id)
                    img  = await _render(fg_iconify_id, fg, bg, size)
                    path = out_dir / f"preview_{slug}_{style}.png"
                    img.save(path, "PNG")
                    written.append(path)
                    tiles.append(([slug, style], img, False))
                header = (f"gradient - shape filled {gradient_from} to {gradient_to} at {gradient_angle} deg"
                          if style == "gradient" else f"solid - shape filled {fill}")
            groups.append((header, tiles))

        watermark = f" + watermark {bg_icon_iconify_id}" if bg_icon_iconify_id else ""
        sheet = _contact_sheet(
            groups, size,
            "Background options - pick a style, then a shape",
            f"glyph {fg_iconify_id} in {fg_color}{watermark} | "
            f"{len(shape_list)} shapes | {len(written)} tiles | slug goes in shape.type")
        sheet_path = out_dir / "contact-sheet.png"
        sheet.save(sheet_path, "PNG")

        # ── the catalog ──────────────────────────────────────────────────────
        out = [
            f"Rendered {len(written)} previews to {out_dir}",
            f"Contact sheet: {sheet_path}",
            "  ^ open this first - compare, pick ONE style + ONE shape, then paste below.",
            "",
            f"Sample glyph: {fg_iconify_id} in {fg_color} (each component sets its own "
            f"fg_iconify_id later; only the background is being chosen here).",
            "",
        ]
        for n, style in enumerate(style_list, 1):
            example = shape_list[0]
            bg = preview_background_spec(style, example, fill, gradient_from, gradient_to,
                                         gradient_angle, bg_icon_iconify_id)
            count = 1 if style == "none" else len(shape_list)
            files = ("preview_none.png" if style == "none"
                     else f"preview_<slug>_{style}.png ({count} files)")
            out.append(f"STYLE {n}/{len(style_list)} - {style.upper()}   [{files}]")
            out.append('  Paste into icons.json under "defaults" (or one subcategory, or one component):')
            out.append(_snippet(bg))
            if style == "none":
                out.append("  Nothing is drawn behind the glyph, so the glyph must contrast with the")
                out.append("  Grasshopper canvas - a white fg_color disappears. Use a dark one.")
            else:
                out.append(f'  Swap "{example}" for any slug listed below.')
            out.append("")

        if not bg_icon_iconify_id:
            out += [
                "Optional extra layer - a watermark glyph behind the foreground, on top of any",
                "shape above. Re-run with bg_icon_iconify_id=<prefix:name> to preview it:",
                _snippet({"shape": {"type": shape_list[0], "fill": fill},
                          "icon": {"iconify_id": "mdi:cloud", "color": BG_ICON_COLOR,
                                   "opacity": BG_ICON_OPACITY}}),
                "",
            ]

        out.append(f"{len(shape_list)} background shapes - the value for shape.type:")
        for i in range(0, len(shape_list), 4):
            out.append("  " + "  ".join(f"{s:<24}" for s in shape_list[i:i + 4]).rstrip())
        out += ["",
                "Shapes come from backgrounds/ next to this server - drop an SVG in to add one.",
                "Some shapes (trapezoid, saddle-shape, database, l-border, quarter-circle-right,",
                "right-triangle, half-circle) place the glyph partly outside the artwork by design;",
                "those need a DARK fg_color or the glyph vanishes where it leaves the shape."]
        return "\n".join(out)
    except httpx.HTTPStatusError as e:
        return f"Failed to fetch icon: HTTP {e.response.status_code}"
    except Exception as e:
        return f"Error: {e}"

# ── Tool: generate_icon ──────────────────────────────────────────────────────

@mcp.tool()
async def generate_icon(component_name: str, config_path: str | None = None,
                        subcategory: str | None = None, iconify_id: str | None = None) -> str:
    """
    Generate a component icon (default 24x24 PNG) from the plugin's icons.json.

    Style resolves defaults < subcategory < per-component override. The component's
    foreground icon and background (none|solid|gradient|icon) come from icons.json;
    pass subcategory/iconify_id only to override or for a legacy config.

    A component marked `"custom": true` in icons.json is a hand-made icon: this tool skips it
    (returns a "skipped" message) and never overwrites the PNG in the Icons/ folder.

    Args:
        component_name: name without prefix, e.g. 'FindBoard'
        config_path:    path to the plugin's icons.json (required)
        subcategory:    optional override / legacy lookup
        iconify_id:     optional foreground icon override, e.g. 'mdi:magnify'
    """
    try:
        config, cfg_file = load_config(config_path)
        prefix     = config["plugin_prefix"]
        resources  = config["resources_path"]
        out_dir    = Path(resources) if Path(resources).is_absolute() else cfg_file.parent / resources
        out_dir.mkdir(parents=True, exist_ok=True)

        if is_custom_icon(config, component_name):
            return (f"Skipped '{component_name}' — marked \"custom\": true in icons.json; the hand-made "
                    f"{out_dir / f'{prefix}_{component_name}.png'} is kept. Run add_to_resources to embed it.")

        fg_id, fg, background, size, glyph_override = resolve_style(
            config, component_name, subcategory, iconify_id)
        if not fg_id:
            return (f"No foreground icon for '{component_name}'. Add an 'fg_iconify_id' to its entry "
                    f"in icons.json, or pass iconify_id.")

        img = await _render(fg_id, fg, background, size, glyph_override)
        out_path = out_dir / f"{prefix}_{component_name}.png"
        img.save(out_path, "PNG")
        return f"Icon saved: {out_path}"
    except httpx.HTTPStatusError as e:
        return f"Failed to fetch icon: HTTP {e.response.status_code}"
    except Exception as e:
        return f"Error: {e}"

# ── Tool: generate_plugin_icon ───────────────────────────────────────────────

@mcp.tool()
async def generate_plugin_icon(
    config_path: str | None = None,
    size: int | None = None,
    out_name: str | None = None,
) -> str:
    """
    Generate the plugin / category icon from the `plugin_icon` block in icons.json.

    Default (no size, no out_name): the 16x16 ribbon-strip icon, saved to
    resources_path as <prefix>_<PluginName>Logo.png, so pr-assembly can wire it via
    GH_AssemblyPriority.AddCategoryIcon (resource <prefix>_<PluginName>Logo).

    size / out_name override that pair for the large marketing logo the README and the
    Food4Rhino listing use -- same artwork, rendered big and written outside Icons/:
      generate_plugin_icon(cfg, size=1024, out_name="<prefix>_Plugin_Icon.png")
    out_name is resolved relative to the icons.json folder (the plugin root); it may
    include subfolders. It never touches Resources.resx -- the large logo is a repo
    asset, not an embedded resource, so do not pass it to add_to_resources.
    """
    try:
        config, cfg_file = load_config(config_path)
        prefix    = config["plugin_prefix"]
        plugin    = config.get("plugin_name", "Plugin")
        resources = config["resources_path"]
        out_dir   = Path(resources) if Path(resources).is_absolute() else cfg_file.parent / resources

        pi = config.get("plugin_icon", {})
        fg_id = pi.get("fg_iconify_id")
        if not fg_id:
            return "No plugin_icon.fg_iconify_id in icons.json — specify the plugin icon."
        fg   = pi.get("fg") or pi.get("fg_color") or "#FFFFFF"
        fg   = fg if isinstance(fg, dict) else hex_to_rgb(fg)
        px   = size if size is not None else pi.get("size", PLUGIN_PX)
        if not isinstance(px, int) or px < 1:
            return f"size must be a positive integer, got {px!r}"

        if out_name:
            out_path = (cfg_file.parent / out_name).resolve()
            if cfg_file.parent.resolve() not in out_path.parents:
                return f"out_name must stay inside the plugin folder, got {out_name!r}"
        else:
            out_path = out_dir / f"{prefix}_{plugin}Logo.png"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        img = await _render(fg_id, fg, pi.get("background", {}), px, pi.get("glyph"))
        img.save(out_path, "PNG")
        return f"Plugin icon saved ({px}x{px}): {out_path}"
    except httpx.HTTPStatusError as e:
        return f"Failed to fetch icon: HTTP {e.response.status_code}"
    except Exception as e:
        return f"Error: {e}"

# ── Resources.resx / Designer.cs writers ─────────────────────────────────────

RESX_SKELETON = """<?xml version="1.0" encoding="utf-8"?>
<root>
  <resheader name="resmimetype">
    <value>text/microsoft-resx</value>
  </resheader>
  <resheader name="version">
    <value>2.0</value>
  </resheader>
  <resheader name="reader">
    <value>System.Resources.ResXResourceReader, System.Windows.Forms, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089</value>
  </resheader>
  <resheader name="writer">
    <value>System.Resources.ResXResourceWriter, System.Windows.Forms, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089</value>
  </resheader>
</root>
"""

RESX_BITMAP_TYPE = "System.Drawing.Bitmap, System.Drawing"
RESX_BYTEARRAY_MIME = "application/x-microsoft.net.object.bytearray.base64"


def write_resx_bitmap(resx_path: Path, resource_name: str, png_bytes: bytes) -> None:
    """
    Add or replace one Bitmap resource in a .resx without .NET — the macOS/Linux path of
    add_to_resources. Writes the node ResXResourceWriter.AddResource(name, Bitmap) writes:
    type System.Drawing.Bitmap, the PNG bytes base64-encoded under the bytearray mimetype.
    Every other node in the file is left byte-for-byte as it was. A resx with no <resheader>
    (an empty `<root/>` scaffold) gets the standard headers, without which MSBuild's
    GenerateResource rejects the file.
    """
    text = resx_path.read_text(encoding="utf-8-sig") if resx_path.exists() else ""
    if "<resheader" not in text:
        inner = re.search(r"<root[^>]*>(.*)</root>", text, re.S)
        kept = inner.group(1).strip("\n") if inner else ""
        text = RESX_SKELETON.replace("</root>", (kept + "\n" if kept.strip() else "") + "</root>")

    b64 = base64.b64encode(png_bytes).decode("ascii")
    lines = "\n".join("        " + b64[i:i + 80] for i in range(0, len(b64), 80))
    node = (f'  <data name="{resource_name}" type="{RESX_BITMAP_TYPE}" '
            f'mimetype="{RESX_BYTEARRAY_MIME}">\n'
            f"    <value>\n{lines}\n</value>\n"
            f"  </data>\n")

    existing = re.compile(
        rf'[ \t]*<data\s+name="{re.escape(resource_name)}"[^>]*?(?:/>|>.*?</data>)[ \t]*\r?\n?', re.S)
    text = existing.sub("", text)
    close = text.rfind("</root>")
    if close < 0:
        raise ValueError(f"{resx_path} has no closing </root> — not a .resx file")
    head = text[:close]
    if head and not head.endswith("\n"):
        head += "\n"
    resx_path.write_text(head + node + text[close:], encoding="utf-8")


def _add_designer_property(resx_path: Path, resource_name: str) -> str:
    """Add the strongly-typed Bitmap property to Resources.Designer.cs (idempotent)."""
    designer_path = resx_path.parent / "Resources.Designer.cs"
    if not designer_path.exists():
        return f"Added '{resource_name}' to Resources.resx (Resources.Designer.cs not found — skipped)"

    designer_text = designer_path.read_text(encoding="utf-8")
    property_block = (
        f"\n"
        f"        /// <summary>\n"
        f"        ///   Looks up a localized resource of type System.Drawing.Bitmap.\n"
        f"        /// </summary>\n"
        f"        internal static System.Drawing.Bitmap {resource_name} {{\n"
        f"            get {{\n"
        f"                object obj = ResourceManager.GetObject(\"{resource_name}\", resourceCulture);\n"
        f"                return ((System.Drawing.Bitmap)(obj));\n"
        f"            }}\n"
        f"        }}"
    )

    # Already declared (any comment/whitespace style)? Then the resx is updated and the
    # Designer needs nothing — appending again would be a duplicate member (CS0102).
    existing = re.compile(
        rf"internal\s+static\s+(?:System\.Drawing\.)?Bitmap\s+{re.escape(resource_name)}\b")
    if existing.search(designer_text):
        return (f"Added '{resource_name}' to Resources.resx "
                f"(Resources.Designer.cs already declares it — unchanged)")

    stripped = designer_text.rstrip()
    # Insert before the class's closing brace (indented) followed by the namespace's brace.
    m = None
    for cand in re.finditer(r"\n([ \t]*)\}\s*\n[ \t]*\}\s*$", stripped):
        m = cand
    if m is None:
        return (f"Added '{resource_name}' to Resources.resx, but Resources.Designer.cs has no "
                f"recognisable class/namespace closing braces — add the property by hand:\n"
                f"{property_block.strip()}")
    insert_at = m.start()
    designer_text = stripped[:insert_at] + "\n" + property_block + stripped[insert_at:] + "\n"
    designer_path.write_text(designer_text, encoding="utf-8")

    return f"Added '{resource_name}' to Resources.resx and Resources.Designer.cs"


# ── Tool: add_to_resources ───────────────────────────────────────────────────

@mcp.tool()
def add_to_resources(component_name: str, config_path: str | None = None) -> str:
    """
    Embed a generated PNG into Properties/Resources.resx and add the strongly-typed
    property to Resources.Designer.cs. Use the component name (e.g. 'FindBoard') or the
    plugin icon's base name (e.g. 'AcmeConnectLogo'). Idempotent.

    On Windows the .resx write shells out to PowerShell + System.Windows.Forms
    (ResXResourceWriter). On macOS/Linux, where neither exists, the same <data> node is
    written directly (write_resx_bitmap) — the Bitmap is stored as PNG bytes in the
    bytearray.base64 form ResXResourceWriter itself emits.
    """
    try:
        is_windows = platform.system() == "Windows"
        config, cfg_file = load_config(config_path)
        prefix    = config["plugin_prefix"]
        icons_dir = (Path(config["resources_path"]) if Path(config["resources_path"]).is_absolute()
                     else cfg_file.parent / config["resources_path"])
        resx_path = (Path(config["resx_path"]) if Path(config["resx_path"]).is_absolute()
                     else cfg_file.parent / config["resx_path"])

        resource_name = f"{prefix}_{component_name}"
        png_path      = icons_dir / f"{resource_name}.png"

        if not png_path.exists():
            return f"Icon not found: {png_path} — run generate_icon first."
        if not resx_path.exists():
            return f"Resources.resx not found: {resx_path}"

        if not is_windows:
            write_resx_bitmap(resx_path, resource_name, png_path.read_bytes())
            return _add_designer_property(resx_path, resource_name)

        ps_png  = str(png_path).replace("'", "''")
        ps_resx = str(resx_path).replace("'", "''")
        ps_name = resource_name.replace("'", "''")

        ps_script = f"""
Add-Type -AssemblyName 'System.Drawing'
Add-Type -AssemblyName 'System.Windows.Forms'

$pngPath  = '{ps_png}'
$resxPath = '{ps_resx}'
$resName  = '{ps_name}'

$nodes  = [System.Collections.Generic.List[System.Resources.ResXDataNode]]::new()
$reader = New-Object System.Resources.ResXResourceReader($resxPath)
$reader.UseResXDataNodes = $true
$enum   = $reader.GetEnumerator()
while ($enum.MoveNext()) {{
    if ($enum.Key -ne $resName) {{ $nodes.Add($enum.Value) }}
}}
$reader.Close()

$bmp    = New-Object System.Drawing.Bitmap($pngPath)
$writer = New-Object System.Resources.ResXResourceWriter($resxPath)
foreach ($node in $nodes) {{ $writer.AddResource($node) }}
$writer.AddResource($resName, $bmp)
$writer.Generate()
$writer.Close()
$bmp.Dispose()
Write-Output 'OK'
"""

        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 or "OK" not in result.stdout:
            return f"PowerShell error:\n{result.stderr.strip() or result.stdout.strip()}"

        return _add_designer_property(resx_path, resource_name)
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
