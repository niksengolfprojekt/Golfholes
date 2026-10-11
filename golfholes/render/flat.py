"""Hålbild i grafisk, platt stil (grunden för stilen "Nordisk").

Ritas helt från hålets vektorer – inget hittas på. Hålet roteras så att bakre
tee ligger nederst och green överst, oavsett väderstreck. En liten nordpil
visar verklig riktning.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .. import geometry as g
from ..hole import Hole

# Färger – Nordisk/platt. Ändras här, inte i koden nedan.
PALETTE = {
    "paper": "#f4f1e8",
    "rough": "#cdd9b4",
    "rough_edge": "#bccb9f",
    "fairway": "#a9c98b",
    "fairway_stripe": "#a1c283",
    "green": "#bfe0a0",
    "green_edge": "#86ad6c",
    "tee": "#bfe0a0",
    "bunker": "#efe5cc",
    "bunker_edge": "#d4c59f",
    "water": "#93b6c6",
    "water_edge": "#6f97aa",
    "tree": "#6e8f58",
    "tree_dark": "#5a7a47",
    "ink": "#3f4a3c",
    "marker_100": "#c0473b",
    "marker_150": "#f4f1e8",
    "marker_200": "#e2b93b",
}


@dataclass
class _Frame:
    origin: g.Point
    angle: float
    xmin: float
    ymax: float
    scale: float

    def xy(self, p: g.Point) -> tuple[float, float]:
        x, y = g.rotate(p, self.origin, self.angle)
        return ((x - self.xmin) * self.scale, (self.ymax - y) * self.scale)

    def path(self, poly) -> str:
        pts = [self.xy(p) for p in poly]
        return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z"


def _frame(hole: Hole, tee, width_px: float, margin_m: float) -> tuple[_Frame, float]:
    green_mid = g.centroid(hole.green)
    angle = g.bearing(tee.point, green_mid)
    core = [t.point for t in hole.tees] + list(hole.green)
    for f in hole.fairways:
        core += f
    for h in hole.hazards:
        core += h.polygon
    rot = [g.rotate(p, tee.point, angle) for p in core]
    xs, ys = zip(*rot)
    xmin, xmax = min(xs) - margin_m, max(xs) + margin_m
    ymin, ymax = min(ys) - margin_m, max(ys) + margin_m
    # Minst 45 % så bred som hög, så smala hål inte blir en tunn sträng.
    w, h = xmax - xmin, ymax - ymin
    if w < 0.45 * h:
        pad = (0.45 * h - w) / 2
        xmin, xmax = xmin - pad, xmax + pad
    scale = width_px / (xmax - xmin)
    return _Frame(tee.point, angle, xmin, ymax, scale), (ymax - ymin) * scale


def _trees(frame: _Frame, polygons, seed: int) -> str:
    """Träd som prickar inuti skogsytorna, placerade deterministiskt."""
    rnd = random.Random(seed)
    out = []
    step = 7.0  # meter mellan trädrader
    for poly in polygons:
        xs, ys = zip(*poly)
        y = min(ys)
        row = 0
        while y <= max(ys):
            x = min(xs) + (step / 2 if row % 2 else 0)
            while x <= max(xs):
                p = (x + rnd.uniform(-2, 2), y + rnd.uniform(-2, 2))
                if g.contains(poly, p):
                    cx, cy = frame.xy(p)
                    r = rnd.uniform(3.2, 4.6) * frame.scale
                    col = PALETTE["tree"] if rnd.random() > 0.35 else PALETTE["tree_dark"]
                    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{col}"/>')
                x += step
            y += step * 0.87
            row += 1
    return "".join(out)


def _stripes(frame: _Frame, poly, clip_id: str) -> str:
    """Klippta ränder på fairway, vinkelräta mot spelriktningen."""
    pts = [frame.xy(p) for p in poly]
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    band = 12 * frame.scale
    rects = []
    y = min(ys)
    i = 0
    while y < max(ys):
        if i % 2 == 0:
            rects.append(f'<rect x="{min(xs):.1f}" y="{y:.1f}" width="{max(xs) - min(xs):.1f}" height="{band:.1f}" fill="{PALETTE["fairway_stripe"]}"/>')
        y += band
        i += 1
    return f'<g clip-path="url(#{clip_id})">{"".join(rects)}</g>'


def render_flat(hole: Hole, tee_name: str | None = None, width_px: float = 600, margin_m: float = 30,
                markers: tuple[int, ...] = (100, 150, 200), north_arrow: bool = True, fit: bool = False,
                fade: bool = False) -> str:
    """Returnerar en SVG-sträng av hålet.

    fit=True: utan fasta mått, så att bilden skalar till sin behållare (skylt, webb).
    fade=True: kanterna tonar mjukt ut i papperet (skyltens stil).
    """
    tee = hole.tee(tee_name)
    fr, height_px = _frame(hole, tee, width_px, margin_m)
    P = PALETTE
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_px:.0f} {height_px:.0f}" '
        + ('preserveAspectRatio="xMidYMid meet" ' if fit else f'width="{width_px:.0f}" height="{height_px:.0f}" ')
        + 'font-family="Inter, Helvetica, Arial, sans-serif">',
        "<defs>",
    ]
    for i, f in enumerate(hole.fairways):
        parts.append(f'<clipPath id="fw{i}"><path d="{fr.path(f)}"/></clipPath>')
    if fade:
        blur = 0.04 * width_px
        parts.append(f'<filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="{blur:.1f}"/></filter>'
                     f'<mask id="fade"><rect x="{2 * blur:.1f}" y="{2 * blur:.1f}" width="{width_px - 4 * blur:.1f}" '
                     f'height="{height_px - 4 * blur:.1f}" rx="{4 * blur:.1f}" fill="#fff" filter="url(#soft)"/></mask>')
    parts.append("</defs>")
    parts.append('<g mask="url(#fade)">' if fade else "<g>")
    parts.append(f'<rect width="100%" height="100%" fill="{P["rough"]}"/>')
    parts.append(_trees(fr, hole.trees, seed=hole.number))

    for h in hole.hazards:
        if h.kind in ("water", "creek"):
            parts.append(f'<path d="{fr.path(h.polygon)}" fill="{P["water"]}" stroke="{P["water_edge"]}" stroke-width="1.2"/>')
    for i, f in enumerate(hole.fairways):
        parts.append(f'<path d="{fr.path(f)}" fill="{P["fairway"]}"/>')
        parts.append(_stripes(fr, f, f"fw{i}"))
    # Tees som små rundade rutor kring tee-punkterna
    for t in hole.tees:
        x, y = fr.xy(t.point)
        w, hgt = 12 * fr.scale, 8 * fr.scale
        parts.append(f'<rect x="{x - w / 2:.1f}" y="{y - hgt / 2:.1f}" width="{w:.1f}" height="{hgt:.1f}" rx="{2 * fr.scale:.1f}" fill="{P["tee"]}" stroke="{P["green_edge"]}" stroke-width="1"/>')
    parts.append(f'<path d="{fr.path(hole.green)}" fill="{P["green"]}" stroke="{P["green_edge"]}" stroke-width="1.5"/>')
    for h in hole.hazards:
        if h.kind == "bunker":
            parts.append(f'<path d="{fr.path(h.polygon)}" fill="{P["bunker"]}" stroke="{P["bunker_edge"]}" stroke-width="1.2"/>')

    # Avståndsmarkeringar till greenens mitt (svensk standard: rött 100, vitt 150, gult 200)
    green_mid = g.centroid(hole.green)
    s_mid = g.project(hole.centerline, green_mid)[0]
    s_tee = g.project(hole.centerline, tee.point)[0]
    colors = {100: P["marker_100"], 150: P["marker_150"], 200: P["marker_200"]}
    for m in markers:
        if s_mid - m <= s_tee + 20:
            continue
        x, y = fr.xy(g.point_along(hole.centerline, s_mid - m))
        r = 4.2 * fr.scale
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{colors.get(m, P["paper"])}" stroke="{P["ink"]}" stroke-width="0.8"/>')
        parts.append(f'<text x="{x + r + 4:.1f}" y="{y + 4:.1f}" font-size="{max(10, 9 * fr.scale):.1f}" fill="{P["ink"]}" font-weight="600">{m}</text>')

    # Flagga på greenens mitt
    gx, gy = fr.xy(green_mid)
    pole = 16 * fr.scale
    parts.append(f'<line x1="{gx:.1f}" y1="{gy:.1f}" x2="{gx:.1f}" y2="{gy - pole:.1f}" stroke="{P["ink"]}" stroke-width="1.5"/>')
    parts.append(f'<path d="M{gx:.1f},{gy - pole:.1f}l{8 * fr.scale:.1f},{3 * fr.scale:.1f}l{-8 * fr.scale:.1f},{3 * fr.scale:.1f}Z" fill="{P["marker_100"]}"/>')
    parts.append(f'<circle cx="{gx:.1f}" cy="{gy:.1f}" r="1.8" fill="{P["ink"]}"/>')

    parts.append("</g>")
    if north_arrow:
        # Nordpil: verklig norr efter rotationen
        inset = 0.1 * width_px if fade else 0
        cx, cy, L = width_px - 28 - inset, 34 + inset, 16
        a = math.radians(fr.angle)
        dx, dy = -math.sin(a) * L, -math.cos(a) * L
        parts.append(f'<g stroke="{P["ink"]}" fill="{P["ink"]}"><circle cx="{cx}" cy="{cy}" r="18" fill="{P["paper"]}" fill-opacity="0.85" stroke-width="0.8"/>'
                     f'<line x1="{cx - dx * 0.6:.1f}" y1="{cy - dy * 0.6:.1f}" x2="{cx + dx * 0.6:.1f}" y2="{cy + dy * 0.6:.1f}" stroke-width="1.4"/>'
                     f'<circle cx="{cx + dx * 0.6:.1f}" cy="{cy + dy * 0.6:.1f}" r="2.4"/></g>'
                     f'<text x="{cx + dx * 0.95:.1f}" y="{cy + dy * 0.95 + 3:.1f}" font-size="9" text-anchor="middle" fill="{P["ink"]}" font-weight="700">N</text>')
    parts.append("</svg>")
    return "".join(parts)
