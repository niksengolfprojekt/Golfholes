"""Hålbilden i klubbens valda stil, 1–4.

  1 Signatur  – fotorealistiskt ovanifrån (Lantmäteriets ortofoto), mörk träram
  2 Klassisk  – akvarell, ljus ekram
  3 Arv       – gravyr på pergament, valnötsram med guldlist
  4 Nordisk   – mjuk illustration med 3D-träd, smal svart ram

Alla fyra ritas från SAMMA vektorer, så bunkrar och vatten ligger exakt lika.
Bara utseendet skiljer. Ingen AI används här – inget kan flytta på hålet.
"""
from __future__ import annotations

import base64
import re
import math
import random
from dataclasses import dataclass
from pathlib import Path

from .. import geometry as g
from ..hole import Hole

STYLE_NAMES = {1: "Signatur", 2: "Klassisk", 3: "Arv", 4: "Nordisk"}


# ---------------------------------------------------------------- vy
@dataclass
class View:
    origin: g.Point
    angle: float
    xmin: float
    ymax: float
    scale: float  # px per meter
    w: float
    h: float

    def xy(self, p: g.Point) -> tuple[float, float]:
        x, y = g.rotate(p, self.origin, self.angle)
        return ((x - self.xmin) * self.scale, (self.ymax - y) * self.scale)

    def path(self, poly, closed: bool = True) -> str:
        pts = [self.xy(p) for p in poly]
        return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + ("Z" if closed else "")

    def smooth(self, poly) -> str:
        """Mjuk kurva genom punkterna (Catmull-Rom) – ser handritad ut men följer vektorerna."""
        pts = [self.xy(p) for p in poly]
        n = len(pts)
        if n < 3:
            return self.path(poly)
        d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
        for i in range(n):
            p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
            c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
            c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
            d += f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
        return d + "Z"


def make_view(hole: Hole, tee, width_px: float, margin_m: float = 30, green_zoom_m: float | None = None,
              min_aspect: float = 0.45) -> View:
    green_mid = g.centroid(hole.green)
    angle = g.bearing(tee.point, green_mid)
    if green_zoom_m:
        cx, cy = g.rotate(green_mid, tee.point, angle)
        xmin, xmax, ymin, ymax = cx - green_zoom_m, cx + green_zoom_m, cy - green_zoom_m, cy + green_zoom_m
    else:
        core = [t.point for t in hole.tees] + list(hole.green)
        for f in hole.fairways:
            core += f
        for hz in hole.hazards:
            core += hz.polygon
        rot = [g.rotate(p, tee.point, angle) for p in core]
        xs, ys = zip(*rot)
        xmin, xmax = min(xs) - margin_m, max(xs) + margin_m
        ymin, ymax = min(ys) - margin_m, max(ys) + margin_m
        w, h = xmax - xmin, ymax - ymin
        if w < min_aspect * h:
            pad = (min_aspect * h - w) / 2
            xmin, xmax = xmin - pad, xmax + pad
    scale = width_px / (xmax - xmin)
    return View(tee.point, angle, xmin, ymax, scale, width_px, (ymax - ymin) * scale)


def _tree_points(polys, step: float, seed: int):
    rnd = random.Random(seed)
    for poly in polys:
        xs, ys = zip(*poly)
        y, row = min(ys), 0
        while y <= max(ys):
            x = min(xs) + (step / 2 if row % 2 else 0)
            while x <= max(xs):
                p = (x + rnd.uniform(-step * 0.3, step * 0.3), y + rnd.uniform(-step * 0.3, step * 0.3))
                if g.contains(poly, p):
                    yield p, rnd
                x += step
            y += step * 0.87
            row += 1


def _water_and_bunkers(hole: Hole):
    water = [h for h in hole.hazards if h.kind in ("water", "creek")]
    bunkers = [h for h in hole.hazards if h.kind == "bunker"]
    return water, bunkers


def _fade_mask(v: View, frac: float = 0.05) -> tuple[str, str]:
    blur = frac * v.w
    defs = (f'<filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="{blur:.1f}"/></filter>'
            f'<mask id="fade"><rect x="{2 * blur:.1f}" y="{2 * blur:.1f}" width="{v.w - 4 * blur:.1f}" height="{v.h - 4 * blur:.1f}" '
            f'rx="{5 * blur:.1f}" fill="#fff" filter="url(#soft)"/></mask>')
    return defs, 'mask="url(#fade)"'


# ---------------------------------------------------------------- 4 Nordisk
def _nordisk(hole: Hole, v: View, tee, zoom: bool) -> tuple[str, str]:
    defs = ('<radialGradient id="tree" cx="35%" cy="30%" r="75%"><stop offset="0" stop-color="#9cbf7c"/>'
            '<stop offset=".55" stop-color="#5f8a4a"/><stop offset="1" stop-color="#3f6634"/></radialGradient>'
            '<filter id="shadow" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="2" dy="3" stdDeviation="2.5" flood-color="#2d3b26" flood-opacity=".35"/></filter>'
            '<linearGradient id="fw" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#a9c97e"/><stop offset="1" stop-color="#c3db8f"/></linearGradient>'
            '<linearGradient id="wat" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#9cc3d6"/><stop offset="1" stop-color="#6e9fb8"/></linearGradient>'
            '<pattern id="check" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            '<rect width="5" height="5" fill="#000" opacity=".05"/><rect x="5" y="5" width="5" height="5" fill="#000" opacity=".05"/></pattern>')
    water, bunkers = _water_and_bunkers(hole)
    out = [f'<rect width="100%" height="100%" fill="#dfe6c8"/>']
    for f in hole.fairways:  # ruff-zon runt fairway
        out.append(f'<path d="{v.smooth(f)}" fill="none" stroke="#cddcae" stroke-width="{30 * v.scale:.1f}" stroke-linejoin="round" opacity=".9"/>')
    for w in water:
        out.append(f'<path d="{v.smooth(w.polygon) if w.kind == "water" else v.path(w.polygon)}" fill="url(#wat)" stroke="#5f8ea6" stroke-width="1"/>')
    for f in hole.fairways:
        out.append(f'<path d="{v.smooth(f)}" fill="url(#fw)" stroke="#97b86f" stroke-width="1"/>')
    for t in hole.tees:
        x, y = v.xy(t.point)
        out.append(f'<rect x="{x - 6 * v.scale:.1f}" y="{y - 4 * v.scale:.1f}" width="{12 * v.scale:.1f}" height="{8 * v.scale:.1f}" rx="{2 * v.scale:.1f}" fill="#c9e09a" stroke="#97b86f" filter="url(#shadow)"/>')
    out.append(f'<path d="{v.smooth(hole.green)}" fill="#c9e3a0" stroke="#8fb36c" stroke-width="1.5" filter="url(#shadow)"/>')
    out.append(f'<path d="{v.smooth(hole.green)}" fill="url(#check)"/>')
    for b in bunkers:
        out.append(f'<path d="{v.smooth(b.polygon)}" fill="#fbf6ea" stroke="#d9cdb0" stroke-width="1.2" filter="url(#shadow)"/>')
    trees = []
    for p, rnd in _tree_points(hole.trees, 9.0, hole.number):
        x, y = v.xy(p)
        r = rnd.uniform(4.2, 6.0) * v.scale
        trees.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="url(#tree)"/>')
    out.append(f'<g filter="url(#shadow)">{"".join(trees)}</g>')
    return defs, "".join(out)


# ---------------------------------------------------------------- 2 Klassisk (akvarell)
def _akvarell(hole: Hole, v: View, tee, zoom: bool) -> tuple[str, str]:
    defs = ('<filter id="wc" x="-10%" y="-10%" width="120%" height="120%">'
            '<feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="3" seed="4" result="n"/>'
            '<feDisplacementMap in="SourceGraphic" in2="n" scale="7" xChannelSelector="R" yChannelSelector="G" result="d"/>'
            '<feGaussianBlur in="d" stdDeviation="0.7"/></filter>'
            '<filter id="bleed" x="-20%" y="-20%" width="140%" height="140%">'
            '<feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="2" seed="9" result="n"/>'
            '<feDisplacementMap in="SourceGraphic" in2="n" scale="5" result="d"/><feGaussianBlur in="d" stdDeviation="1.6"/></filter>'
            '<filter id="grain"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="1" seed="2"/>'
            '<feColorMatrix values="0 0 0 0 0.45  0 0 0 0 0.42  0 0 0 0 0.38  0 0 0 .07 0"/></filter>')
    water, bunkers = _water_and_bunkers(hole)
    tree_cols = ["#2f5a3a", "#3d6b45", "#4d7b4e", "#5b6f8e", "#6a5f8f", "#7b8f5a", "#2c4d4f"]
    out = ['<rect width="100%" height="100%" fill="#fbfaf6"/>']
    for f in hole.fairways:  # ruff i tunna lager
        out.append(f'<path d="{v.smooth(f)}" fill="none" stroke="#c9d6a6" stroke-width="{34 * v.scale:.1f}" stroke-linejoin="round" opacity=".55" filter="url(#bleed)"/>')
    trees = []
    for p, rnd in _tree_points(hole.trees, 6.5, hole.number + 7):
        x, y = v.xy(p)
        r = rnd.uniform(3.5, 6.5) * v.scale
        trees.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{rnd.choice(tree_cols)}" opacity="{rnd.uniform(.35, .7):.2f}"/>')
    out.append(f'<g filter="url(#bleed)">{"".join(trees)}</g>')
    for w in water:
        d = v.smooth(w.polygon) if w.kind == "water" else v.path(w.polygon)
        out.append(f'<path d="{d}" fill="#4fa6d8" opacity=".75" filter="url(#wc)"/>')
        out.append(f'<path d="{d}" fill="none" stroke="#2f7fb3" stroke-width="2" opacity=".5" filter="url(#wc)"/>')
    for f in hole.fairways:
        out.append(f'<path d="{v.smooth(f)}" fill="#b5cd8a" opacity=".85" filter="url(#wc)"/>')
        out.append(f'<path d="{v.smooth(f)}" fill="none" stroke="#7f8a7a" stroke-width=".6" opacity=".5"/>')  # blyerts
    for t in hole.tees:
        x, y = v.xy(t.point)
        out.append(f'<rect x="{x - 6 * v.scale:.1f}" y="{y - 4 * v.scale:.1f}" width="{12 * v.scale:.1f}" height="{8 * v.scale:.1f}" fill="#d7e6b2" opacity=".9" filter="url(#wc)"/>')
    out.append(f'<path d="{v.smooth(hole.green)}" fill="#e9ef9e" filter="url(#wc)"/>')
    for b in bunkers:
        out.append(f'<path d="{v.smooth(b.polygon)}" fill="#f4d7b0" filter="url(#wc)"/>')
    out.append('<rect width="100%" height="100%" filter="url(#grain)"/>')
    return defs, "".join(out)


# ---------------------------------------------------------------- 3 Arv (gravyr)
INK = "#4a3426"


def _gravyr(hole: Hole, v: View, tee, zoom: bool) -> tuple[str, str]:
    defs = (f'<pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(35)">'
            f'<line x1="0" y1="0" x2="0" y2="5" stroke="{INK}" stroke-width=".5" opacity=".45"/></pattern>'
            f'<pattern id="waves" width="12" height="4" patternUnits="userSpaceOnUse">'
            f'<path d="M0 2 Q3 0.8 6 2 T12 2" fill="none" stroke="{INK}" stroke-width=".45" opacity=".5"/></pattern>'
            f'<pattern id="stipple" width="4" height="4" patternUnits="userSpaceOnUse">'
            f'<circle cx="1" cy="1" r=".45" fill="{INK}" opacity=".55"/><circle cx="3" cy="3" r=".35" fill="{INK}" opacity=".4"/></pattern>'
            '<filter id="paper"><feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="3" seed="3"/>'
            '<feColorMatrix values="0 0 0 0 0.55  0 0 0 0 0.42  0 0 0 0 0.25  0 0 0 .12 0"/></filter>')
    water, bunkers = _water_and_bunkers(hole)
    out = ['<rect width="100%" height="100%" fill="#f1e5c9"/>', '<rect width="100%" height="100%" filter="url(#paper)"/>']
    for w in water:
        d = v.smooth(w.polygon) if w.kind == "water" else v.path(w.polygon)
        out.append(f'<path d="{d}" fill="#c6cfcc"/><path d="{d}" fill="url(#waves)" stroke="{INK}" stroke-width="1.1"/>')
    for f in hole.fairways:
        out.append(f'<path d="{v.smooth(f)}" fill="#ece0c2"/><path d="{v.smooth(f)}" fill="url(#hatch)" stroke="{INK}" stroke-width="1"/>')
    for t in hole.tees:
        x, y = v.xy(t.point)
        w, h = 13 * v.scale, 9 * v.scale
        out.append(f'<rect x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="2" fill="#cfdca8" stroke="{INK}" stroke-width=".9"/>')
        if not zoom:
            out.append(f'<text x="{x:.1f}" y="{y + 3.5 * v.scale:.1f}" text-anchor="middle" font-size="{max(8, 6.5 * v.scale):.1f}" fill="{INK}" font-family="Georgia, serif">{t.name}</text>')
    out.append(f'<path d="{v.smooth(hole.green)}" fill="#cfdca8" stroke="{INK}" stroke-width="1.3"/>')
    for b in bunkers:
        out.append(f'<path d="{v.smooth(b.polygon)}" fill="#ecc99c"/><path d="{v.smooth(b.polygon)}" fill="url(#stipple)" stroke="{INK}" stroke-width="1"/>')
    trees = []
    for p, rnd in _tree_points(hole.trees, 8.0, hole.number + 3):
        x, y = v.xy(p)
        r = rnd.uniform(3.6, 5.2) * v.scale
        trees.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#f1e5c9" stroke="{INK}" stroke-width=".9"/>'
                     f'<path d="M{x - r * .2:.1f},{y + r * .85:.1f} A{r:.1f},{r:.1f} 0 0 0 {x + r * .85:.1f},{y - r * .2:.1f}" fill="none" stroke="{INK}" stroke-width="{max(1.2, r * .28):.1f}" opacity=".7"/>')
    out.append("".join(trees))
    if not zoom:
        # Ram, kompassros och skalstock
        m = 10
        out.append(f'<rect x="{m}" y="{m}" width="{v.w - 2 * m:.1f}" height="{v.h - 2 * m:.1f}" fill="none" stroke="{INK}" stroke-width="1.6"/>'
                   f'<rect x="{m + 4}" y="{m + 4}" width="{v.w - 2 * m - 8:.1f}" height="{v.h - 2 * m - 8:.1f}" fill="none" stroke="{INK}" stroke-width=".6"/>')
        out.append(_compass(46, 62, 26, v.angle))
        out.append(_scale_bar(v, 30, v.h - 34))
    return defs, "".join(out)


def _compass(cx, cy, r, angle_deg) -> str:
    """Kompassros vriden så att N pekar mot verklig norr i den roterade bilden."""
    a = -angle_deg
    star = []
    for k in range(8):
        L = r if k % 2 == 0 else r * 0.55
        ang = math.radians(k * 45)
        tip = (cx + L * math.sin(ang), cy - L * math.cos(ang))
        l1 = (cx + r * .14 * math.sin(ang - math.pi / 2), cy - r * .14 * math.cos(ang - math.pi / 2))
        l2 = (cx + r * .14 * math.sin(ang + math.pi / 2), cy - r * .14 * math.cos(ang + math.pi / 2))
        star.append(f'<path d="M{l1[0]:.1f},{l1[1]:.1f}L{tip[0]:.1f},{tip[1]:.1f}L{cx},{cy}Z" fill="{INK}"/>'
                    f'<path d="M{l2[0]:.1f},{l2[1]:.1f}L{tip[0]:.1f},{tip[1]:.1f}L{cx},{cy}Z" fill="#f1e5c9" stroke="{INK}" stroke-width=".6"/>')
    return (f'<g transform="rotate({a:.1f} {cx} {cy})"><circle cx="{cx}" cy="{cy}" r="{r * .7:.1f}" fill="none" stroke="{INK}" stroke-width=".7"/>'
            f'{"".join(star)}<text x="{cx}" y="{cy - r - 4:.1f}" text-anchor="middle" font-size="10" font-family="Georgia, serif" fill="{INK}">N</text></g>')


def _scale_bar(v: View, x, y) -> str:
    length_m = 50
    L = length_m * v.scale
    return (f'<g font-family="Georgia, serif" font-size="10" fill="{INK}">'
            f'<rect x="{x}" y="{y}" width="{L / 2:.1f}" height="4" fill="{INK}"/><rect x="{x + L / 2:.1f}" y="{y}" width="{L / 2:.1f}" height="4" fill="none" stroke="{INK}" stroke-width=".8"/>'
            f'<text x="{x}" y="{y - 4}">0</text><text x="{x + L:.1f}" y="{y - 4}" text-anchor="middle">{length_m} m</text></g>')


# ---------------------------------------------------------------- 1 Signatur (foto)
def _read_worldfile(img: Path):
    for ext in (".jgw", ".pgw", ".wld"):
        wf = img.with_suffix(ext)
        if wf.exists():
            a, d, b, e, c, f = (float(x) for x in wf.read_text().split()[:6])
            return a, d, b, e, c, f
    raise FileNotFoundError(f"World-fil saknas för {img.name}")


def _foto(hole: Hole, v: View, tee, zoom: bool) -> tuple[str, str]:
    defs = ('<filter id="grade"><feColorMatrix type="saturate" values="1.18"/>'
            '<feComponentTransfer><feFuncR type="linear" slope="1.06"/><feFuncG type="linear" slope="1.08"/><feFuncB type="linear" slope="0.96"/></feComponentTransfer></filter>')
    if not hole.ortho or not Path(hole.ortho).exists():
        msg = '<rect width="100%" height="100%" fill="#e4e8dc"/>' + ('' if zoom else
               f'<text x="{v.w / 2:.0f}" y="{v.h / 2 - 10:.0f}" text-anchor="middle" font-family="Inter, Arial" font-size="15" fill="#6b7565">Fotostil</text>'
               f'<text x="{v.w / 2:.0f}" y="{v.h / 2 + 12:.0f}" text-anchor="middle" font-family="Inter, Arial" font-size="11" fill="#6b7565">ortofoto från Lantmäteriet läggs in här</text>')
        # Visa ändå konturerna så att man ser att geometrin stämmer
        outline = "".join(f'<path d="{v.smooth(p)}" fill="none" stroke="#9aa58f" stroke-width="1" stroke-dasharray="4 3"/>'
                          for p in [hole.green] + hole.fairways + [h.polygon for h in hole.hazards])
        return defs, msg + outline
    a, d, b, e, c, f = _read_worldfile(Path(hole.ortho))
    from PIL import Image

    with Image.open(hole.ortho) as im:
        W, H = im.size
    data = base64.b64encode(Path(hole.ortho).read_bytes()).decode()
    # Pixel (col,row) → SWEREF: E = a*col + b*row + c ; N = d*col + e*row + f (pixelmitt)
    # SWEREF → vy: rotera kring v.origin med v.angle, flytta, skala, spegla N.
    r = math.radians(v.angle)
    cos, sin, s = math.cos(r), math.sin(r), v.scale
    ox, oy = v.origin
    # x_vy = s*((E-ox)cos - (N-oy)sin - xmin) ; y_vy = s*(ymax - ((E-ox)sin + (N-oy)cos))
    c0, f0 = c - a / 2 - b / 2 - ox, f - d / 2 - e / 2 - oy  # hörnet på pixel (0,0)
    A = s * (a * cos - d * sin)
    C = s * (b * cos - e * sin)
    E_ = s * (c0 * cos - f0 * sin - v.xmin)
    B = -s * (a * sin + d * cos)
    D = -s * (b * sin + e * cos)
    F = s * (v.ymax - (c0 * sin + f0 * cos))
    img = (f'<image href="data:image/jpeg;base64,{data}" width="{W}" height="{H}" '
           f'transform="matrix({A:.6f} {B:.6f} {C:.6f} {D:.6f} {E_:.3f} {F:.3f})" filter="url(#grade)" preserveAspectRatio="none"/>')
    return defs, img


RENDERERS = {1: _foto, 2: _akvarell, 3: _gravyr, 4: _nordisk}


def render_hole(hole: Hole, style: int, width_px: float = 600, tee_name: str | None = None,
                fade: bool = True, fit: bool = True) -> str:
    """Hålbild i stil 1–4 som SVG."""
    tee = hole.tee(tee_name)
    v = make_view(hole, tee, width_px)
    defs, body = RENDERERS[style](hole, v, tee, False)
    mdefs, mask = _fade_mask(v) if fade and style != 3 else ("", "")
    size = 'preserveAspectRatio="xMidYMid meet"' if fit else f'width="{v.w:.0f}" height="{v.h:.0f}"'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {v.w:.0f} {v.h:.0f}" {size}>'
            f'<defs>{defs}{mdefs}</defs><g {mask}>{body}</g></svg>')


def render_green(hole: Hole, style: int, size_px: float = 300, radius_m: float = 28) -> str:
    """Rund förstoring av green i samma stil."""
    tee = hole.tee()
    v = make_view(hole, tee, size_px, green_zoom_m=radius_m)
    defs, body = RENDERERS[style](hole, v, tee, True)
    r = size_px / 2
    ring = {1: "#ffffff", 2: "none", 3: INK, 4: "#b7a68a"}[style]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size_px:.0f} {size_px:.0f}" preserveAspectRatio="xMidYMid meet">'
            f'<defs>{defs}<clipPath id="gc"><circle cx="{r}" cy="{r}" r="{r - 3}"/></clipPath></defs>'
            f'<g clip-path="url(#gc)">{body}</g>'
            f'<circle cx="{r}" cy="{r}" r="{r - 3}" fill="none" stroke="{ring}" stroke-width="{3 if style != 3 else 2}"/></svg>')


def parse_style(value) -> int:
    """Klubbens val: 1–4 eller namnet ("signatur", "klassisk", "arv", "nordisk")."""
    if value is None:
        return 4
    if isinstance(value, int) or str(value).strip().isdigit():
        n = int(value)
        if n in STYLE_NAMES:
            return n
    else:
        for n, name in STYLE_NAMES.items():
            if str(value).strip().lower() == name.lower():
                return n
    raise ValueError(f"Okänd stil {value!r} – välj 1–4: " + ", ".join(f"{n} {s}" for n, s in STYLE_NAMES.items()))


def scope_ids(svg: str, prefix: str) -> str:
    """Gör id:n unika när flera SVG:er ligger på samma sida (annars krockar filter och masker)."""
    ids = set(re.findall(r'id="([^"]+)"', svg))
    for i in ids:
        svg = svg.replace(f'id="{i}"', f'id="{prefix}-{i}"').replace(f"url(#{i})", f"url(#{prefix}-{i})")
    return svg
