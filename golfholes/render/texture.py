"""Texturrendering: exakt geometri från kartan + yta och penseldrag från ett texturkit.

Idén: AI (eller en målare) får bara bestämma HUR gräs, vatten, sand och träd ser ut.
VAR de ligger kommer alltid från hålfilen. Varje yta klipps med en mask som ritas
direkt från vektorerna – därför ligger bunkrar och vatten exakt rätt, i alla stilar.

Texturkit ligger i assets/texturer/<stil>/ (fairway.png, green.png, vatten.png …).
Demo-kiten är utklipp ur AI-skisserna; för tryck byts de mot högupplösta texturer.

Kräver numpy (finns i molnet; `pip install numpy` på Macen).
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..hole import Hole
from .styles import _tree_points, make_view

KITS = Path(__file__).resolve().parents[2] / "assets" / "texturer"


# ---------------------------------------------------------------- grundverktyg
def smooth_pts(pts, per_seg: int = 10):
    """Catmull-Rom genom punkterna (sluten) – samma mjuka form som i SVG-stilarna."""
    n = len(pts)
    if n < 3:
        return pts
    out = []
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        for k in range(per_seg):
            t = k / per_seg
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    return out


class Canvas:
    def __init__(self, hole: Hole, width_px: int, margin_m: float = 45, tee=None):
        self.hole = hole
        self.tee = tee or hole.tee()
        self.v = make_view(hole, self.tee, width_px, margin_m=margin_m)
        self.W, self.H = int(round(self.v.w)), int(round(self.v.h))
        self.s = self.v.scale  # px per meter

    def px(self, meters: float) -> float:
        return meters * self.s

    def mask(self, polys, smooth: bool = True, ss: int = 3) -> np.ndarray:
        """Polygoner → mask 0..1 med mjuk (kantutjämnad) kant."""
        im = Image.new("L", (self.W * ss, self.H * ss), 0)
        d = ImageDraw.Draw(im)
        for poly in polys:
            pts = [self.v.xy(p) for p in poly]
            if smooth:
                pts = smooth_pts(pts)
            d.polygon([(x * ss, y * ss) for x, y in pts], fill=255)
        return np.asarray(im.resize((self.W, self.H), Image.LANCZOS), dtype=np.float32) / 255

    def rect_mask(self, centers, w_m: float, h_m: float, radius_m: float = 1.5) -> np.ndarray:
        im = Image.new("L", (self.W * 3, self.H * 3), 0)
        d = ImageDraw.Draw(im)
        for p in centers:
            x, y = self.v.xy(p)
            w, h, r = self.px(w_m) * 3, self.px(h_m) * 3, self.px(radius_m) * 3
            d.rounded_rectangle((x * 3 - w / 2, y * 3 - h / 2, x * 3 + w / 2, y * 3 + h / 2), radius=r, fill=255)
        return np.asarray(im.resize((self.W, self.H), Image.LANCZOS), dtype=np.float32) / 255


def blur(m: np.ndarray, r: float) -> np.ndarray:
    if r <= 0:
        return m
    im = Image.fromarray(np.clip(m * 255, 0, 255).astype("uint8"))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), dtype=np.float32) / 255


def grow(m: np.ndarray, r: float) -> np.ndarray:
    """Utvidga en mask med ungefär r pixlar (mjuk kant)."""
    b = blur((m > 0.5).astype(np.float32), r)
    return np.clip((b - 0.02) / 0.1, 0, 1)


def shrink(m: np.ndarray, r: float) -> np.ndarray:
    b = blur((m > 0.5).astype(np.float32), r)
    return np.clip((b - 0.88) / 0.1, 0, 1)


def noise(h: int, w: int, seed: int, cell: float = 40, octaves: int = 4) -> np.ndarray:
    """Mjukt brus 0..1 (för penseldrag, ojämna kanter, variation i ytor)."""
    rnd = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        c = max(2.0, cell / (2 ** o))
        gh, gw = int(h / c) + 2, int(w / c) + 2
        grid = (rnd.random((gh, gw)) * 255).astype("uint8")
        layer = np.asarray(Image.fromarray(grid).resize((int(gw * c), int(gh * c)), Image.BICUBIC), np.float32)[:h, :w] / 255
        out += amp * layer
        tot += amp
        amp *= 0.5
    return out / tot


def tile(tex: Image.Image, w: int, h: int, scale: float = 1.0, angle: float = 0.0) -> np.ndarray:
    """Täck en yta med texturen (speglad upprepning, så skarvarna inte syns)."""
    t = tex.convert("RGB")
    if scale != 1.0:
        t = t.resize((max(4, int(t.width * scale)), max(4, int(t.height * scale))), Image.LANCZOS)
    a = np.asarray(t, np.float32)
    a = np.concatenate([a, a[:, ::-1]], axis=1)
    a = np.concatenate([a, a[::-1]], axis=0)
    big = max(w, h) * 1.5 if angle else max(w, h)
    reps_y, reps_x = int(math.ceil(big / a.shape[0])) + 1, int(math.ceil(big / a.shape[1])) + 1
    full = np.tile(a, (reps_y, reps_x, 1))
    if angle:
        im = Image.fromarray(full.astype("uint8")).rotate(angle, resample=Image.BICUBIC)
        cx, cy = im.width // 2, im.height // 2
        im = im.crop((cx - w // 2, cy - h // 2, cx - w // 2 + w, cy - h // 2 + h))
        return np.asarray(im, np.float32)
    return full[:h, :w]


def synth(tex: Image.Image, w: int, h: int, scale: float = 1.0, seed: int = 0, turn: str = "fri",
          patch: float = 0.85) -> np.ndarray:
    """Bygg en stor yta av texturen genom att lägga ut slumpade bitar med mjuka kanter.

    Ingen synlig upprepning och inga spegelmönster. `turn`: "fri" (vrid 90°, spegla),
    "180" (bara halvt varv – för klippränder som ska behålla riktning), "ingen".
    """
    t = tex.convert("RGB")
    if scale != 1.0:
        t = t.resize((max(8, int(t.width * scale)), max(8, int(t.height * scale))), Image.LANCZOS)
    src = np.asarray(t, np.float32)
    th, tw = src.shape[:2]
    P = max(8, int(min(th, tw) * patch))
    rnd = np.random.default_rng(seed)
    out = np.zeros((h, w, 3), np.float32) + src.reshape(-1, 3).mean(0)
    win1 = np.sin(np.linspace(0, np.pi, P)) ** 0.8
    win = np.minimum(1, 2.2 * np.outer(win1, win1))[..., None]
    step = max(4, int(P * 0.55))
    for gy in range(-P // 2, h + step, step):
        for gx in range(-P // 2, w + step, step):
            y0, x0 = int(rnd.integers(0, th - P + 1)), int(rnd.integers(0, tw - P + 1))
            pt = src[y0:y0 + P, x0:x0 + P]
            if turn == "fri":
                pt = np.rot90(pt, int(rnd.integers(0, 4)))
                if rnd.random() < .5:
                    pt = pt[:, ::-1]
            elif turn == "180" and rnd.random() < .5:
                pt = pt[::-1, ::-1]
            y, x = gy + int(rnd.integers(-step // 4, step // 4 + 1)), gx + int(rnd.integers(-step // 4, step // 4 + 1))
            ys, xs = max(0, y), max(0, x)
            ye, xe = min(h, y + P), min(w, x + P)
            if ys >= ye or xs >= xe:
                continue
            a = win[ys - y:ye - y, xs - x:xe - x]
            out[ys:ye, xs:xe] = out[ys:ye, xs:xe] * (1 - a) + pt[ys - y:ye - y, xs - x:xe - x] * a
    return out


def flatten(rgb: np.ndarray, r: float) -> np.ndarray:
    """Ta bort skissens stora ljus/skugga-fläckar men behåll strukturen (högpass)."""
    low = np.stack([blur(rgb[..., i] / 255, r) * 255 for i in range(3)], -1)
    return np.clip(rgb - low + rgb.reshape(-1, 3).mean(0), 0, 255)


def stripes(c: "Canvas", width_m: float = 9, angle: float = 35, amount: float = 0.05) -> np.ndarray:
    """Klippränder: faktor runt 1.0 i diagonala band."""
    yy, xx = np.mgrid[0:c.H, 0:c.W].astype(np.float32)
    a = math.radians(angle)
    u = (xx * math.cos(a) + yy * math.sin(a)) / c.px(width_m)
    band = np.clip(np.sin(u * math.pi) * 3, -1, 1)
    return 1 + amount * band


def over(base: np.ndarray, color, alpha: np.ndarray) -> np.ndarray:
    c = np.asarray(color, np.float32)
    a = alpha[..., None]
    return base * (1 - a) + c * a


def multiply(base: np.ndarray, color, alpha: np.ndarray) -> np.ndarray:
    c = np.asarray(color, np.float32)
    a = alpha[..., None]
    return base * (1 - a) + (base * c / 255) * a


def shade(rgb: np.ndarray, factor) -> np.ndarray:
    f = factor[..., None] if isinstance(factor, np.ndarray) else factor
    return np.clip(rgb * f, 0, 255)


def load_kit(style: str) -> dict[str, Image.Image]:
    d = KITS / style
    if not d.exists():
        raise FileNotFoundError(f"Texturkit saknas: {d} – kör verktyg/texturkit.py")
    return {p.stem: Image.open(p).convert("RGB") for p in d.glob("*.png")}


def _layers(c: Canvas):
    h = c.hole
    L = {
        "fairway": c.mask(h.fairways),
        "green": c.mask([h.green]),
        "tee": c.rect_mask([t.point for t in h.tees], 11, 7),
        "bunker": c.mask([z.polygon for z in h.hazards if z.kind == "bunker"]),
        "vatten": c.mask([z.polygon for z in h.hazards if z.kind == "water"]),
        "back": c.mask([z.polygon for z in h.hazards if z.kind == "creek"], smooth=False),
        "skog": c.mask(h.trees),
    }
    L["spel"] = np.maximum.reduce([L["fairway"], L["green"], L["tee"]])
    return L


# ---------------------------------------------------------------- 4 Nordisk
def _tree_sprite(R: int, foliage: Image.Image, rnd: random.Random):
    """En mjuk 3D-trädkrona: ojämn rund form, lövtextur, ljus uppe till vänster."""
    S = 2 * R + 4
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) - (R + 2)
    ang = np.arctan2(yy, xx)
    rad = np.hypot(xx, yy)
    edge = np.full_like(ang, R * 0.86)
    for k, amp in ((5, .05), (9, .04), (17, .03), (31, .025)):
        edge += R * amp * np.sin(k * ang + rnd.uniform(0, 6.28))
    alpha = np.clip((edge - rad) / 1.6, 0, 1)
    tex = foliage.rotate(rnd.uniform(0, 360), resample=Image.BICUBIC, expand=False).resize((S, S), Image.LANCZOS)
    rgb = np.asarray(tex, np.float32)
    light = 1.18 - 0.42 * np.clip(((xx + yy) / (1.6 * R) + 0.6) / 1.6, 0, 1)   # ljus från nordväst
    rim = 1 - 0.25 * np.clip((rad / edge - 0.75) / 0.25, 0, 1)                  # mörkare kant
    rgb = shade(rgb, light * rim)
    return rgb, alpha


def render_nordisk(hole: Hole, width_px: int = 1400) -> Image.Image:
    kit = load_kit("nordisk")
    c = Canvas(hole, width_px)
    W, H, px = c.W, c.H, c.px
    L = _layers(c)
    n = noise(H, W, hole.number, cell=px(25))

    img = np.zeros((H, W, 3), np.float32) + np.array([247, 245, 239], np.float32)
    # Ruffen runt spelytan, tonar ut mot papperet
    ruff = blur(grow(L["spel"], px(16)), px(10))
    img = over(img, (214, 221, 190), ruff * (0.82 + 0.18 * n))
    semi = blur(grow(L["spel"], px(4)), px(2))
    img = over(img, (196, 210, 160), semi * 0.9)

    # Vatten och bäck
    water = np.maximum(L["vatten"], L["back"])
    k = c.s / 4.5   # skissen har ca 4,5 px per meter
    wtex = flatten(synth(kit["vatten"], W, H, k, 1), px(4))
    wtex = shade(wtex, 0.92 + 0.12 * n)
    img = over(img, (226, 230, 214), grow(water, px(1.2)))                    # strandkant
    img = img * (1 - water[..., None]) + wtex * water[..., None]
    inner = np.clip(water - shrink(water, px(2.5)), 0, 1)
    img = multiply(img, (120, 150, 170), blur(inner, px(1)) * 0.5)

    # Fairway, tee och green med textur, skugga och tunn kantlinje
    def raised(img, m, tex, line=(120, 140, 80)):
        sh = blur(np.roll(np.roll(m, int(px(1.2)), 0), int(px(0.8)), 1), px(1.5))
        img = multiply(img, (150, 160, 130), np.clip(sh - m, 0, 1) * 0.7)
        img = img * (1 - m[..., None]) + tex * m[..., None]
        edge = np.clip(m - shrink(m, px(0.6)), 0, 1)
        return over(img, line, edge * 0.55)

    ftex = flatten(synth(kit["fairway"], W, H, k, 2, turn="180", patch=0.95), px(3))
    ftex = shade(ftex, (0.94 + 0.12 * n) * stripes(c, 8, 35, 0.045))
    img = raised(img, L["fairway"], ftex)
    img = raised(img, L["tee"], shade(ftex, 1.04))
    collar = np.clip(grow(L["green"], px(2.2)) - L["green"], 0, 1)
    img = over(img, (186, 205, 128), collar)
    gtex = synth(kit["green"], W, H, k, 3, turn="ingen", patch=0.95)
    img = raised(img, L["green"], gtex)

    # Bunkrar: ljus sand med skugga i överkanten (ser nedsänkta ut)
    b = L["bunker"]
    img = over(img, (240, 234, 220), b)
    lip = np.clip(b - np.roll(np.roll(b, int(px(1.0)), 0), int(px(0.6)), 1), 0, 1)
    img = multiply(img, (200, 190, 170), blur(lip, px(0.6)) * b)
    img = over(img, (150, 160, 120), np.clip(grow(b, px(0.5)) - b, 0, 1) * 0.6)

    # Träd: skugga först, sedan kronorna uppifrån och ner
    rnd = random.Random(hole.number)
    trees = [(c.v.xy(p), r) for p, r in _tree_points(hole.trees, 12.5, hole.number + 11)]
    trees.sort(key=lambda t: t[0][1])
    shadow = np.zeros((H, W), np.float32)
    crowns = []
    for (x, y), r in trees:
        R = int(px(r.uniform(7.5, 10.5)))
        if R < 4:
            continue
        rgb, a = _tree_sprite(R, kit["lov"], rnd)
        crowns.append((int(x) - R - 2, int(y) - R - 2, rgb, a))
        ox, oy = int(x - R - 2 + R * 0.35), int(y - R - 2 + R * 0.45)
        _paste(shadow, a, ox, oy, mode="max")
    img = multiply(img, (120, 128, 100), blur(shadow, R * 0.35 if trees else 1) * 0.75)
    for x0, y0, rgb, a in crowns:
        _paste_rgb(img, rgb, a, x0, y0)

    # Oval vinjett – bilden tonar ut i papperet
    alla = np.maximum.reduce([L["spel"], L["skog"], L["vatten"], L["bunker"]])
    vig = blur(grow(alla, px(8)), px(9))
    img = img * vig[..., None] + np.array([247, 245, 239], np.float32) * (1 - vig[..., None])
    return Image.fromarray(np.clip(img, 0, 255).astype("uint8"))


def _paste(dst, a, x0, y0, mode="max"):
    h, w = a.shape
    H, W = dst.shape[:2]
    xs, ys = max(0, x0), max(0, y0)
    xe, ye = min(W, x0 + w), min(H, y0 + h)
    if xs >= xe or ys >= ye:
        return
    sub = a[ys - y0:ye - y0, xs - x0:xe - x0]
    dst[ys:ye, xs:xe] = np.maximum(dst[ys:ye, xs:xe], sub)


def _paste_rgb(dst, rgb, a, x0, y0):
    h, w = a.shape
    H, W = dst.shape[:2]
    xs, ys = max(0, x0), max(0, y0)
    xe, ye = min(W, x0 + w), min(H, y0 + h)
    if xs >= xe or ys >= ye:
        return
    sa = a[ys - y0:ye - y0, xs - x0:xe - x0, None]
    dst[ys:ye, xs:xe] = dst[ys:ye, xs:xe] * (1 - sa) + rgb[ys - y0:ye - y0, xs - x0:xe - x0] * sa


# ---------------------------------------------------------------- 2 Klassisk (akvarell)
def _dab(R: int, rnd: random.Random):
    """Ett penseldrag: ojämn rund fläck, mörkare kant (färgen torkar i kanten)."""
    S = 2 * R + 4
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) - (R + 2)
    ang, rad = np.arctan2(yy, xx), np.hypot(xx, yy)
    edge = np.full_like(ang, R * 0.8)
    for kk, amp in ((2, .12), (3, .1), (7, .06), (13, .04)):
        edge += R * amp * np.sin(kk * ang + rnd.uniform(0, 6.28))
    a = np.clip((edge - rad) / 1.2, 0, 1)
    rim = np.clip(1 - (edge - rad) / (R * 0.35), 0, 1)
    return a * (0.55 + 0.45 * rim)


def render_klassisk(hole: Hole, width_px: int = 1400) -> Image.Image:
    kit = load_kit("klassisk")
    c = Canvas(hole, width_px)
    W, H, px = c.W, c.H, c.px
    L = _layers(c)
    n1 = noise(H, W, hole.number + 1, cell=px(18))
    n2 = noise(H, W, hole.number + 2, cell=px(6))
    paper = np.array([251, 250, 246], np.float32)
    img = np.zeros((H, W, 3), np.float32) + paper

    def ragged(m, r_m, cut=0.5, soft=0.08):
        """Akvarellkant: suddig, ojämn och lite utflytande."""
        b = blur(m, px(r_m)) + (n1 - 0.5) * 0.35 + (n2 - 0.5) * 0.2
        return np.clip((b - cut) / soft + 0.5, 0, 1)

    def wash(img, m, color, var=0.10, pool=0.22, factor=None):
        """En lavering: färg som lasyr (multiplicera), variation i tonen, mörkare kant."""
        col = np.asarray(color, np.float32)[None, None, :] * (1 - var / 2 + var * n1[..., None])
        if factor is not None:
            col = col * factor[..., None]
        img = img * (1 - m[..., None]) + (img * np.clip(col, 0, 255) / 255) * m[..., None]
        edge = np.clip(m - shrink(m, px(1.0)), 0, 1)
        return multiply(img, (200, 205, 195), blur(edge, px(0.4)) * pool)

    # Ljus grönska och rosa/violett undervegetation mot skogen
    ruff = ragged(grow(L["spel"], px(10)), 2.5)
    img = wash(img, ruff * 0.75, (205, 222, 182), pool=0.04)
    band = np.clip(grow(L["skog"], px(3)) - shrink(L["skog"], px(8)), 0, 1)
    patchy = np.clip((noise(H, W, 31, cell=px(14)) - 0.5) * 4 + 0.5, 0, 1)
    under = ragged(band, 1.5, cut=0.55) * patchy
    img = wash(img, under * 0.5, (232, 190, 222), var=0.3, pool=0.0)

    # Skogen: hundratals penseldrag i färger hämtade ur skissens skog
    # Mellantoner ur skissens skog; flera lager på varandra blir djupt mörka, som riktig akvarell
    pal = np.array([(96, 140, 104), (120, 160, 112), (150, 178, 120), (110, 120, 170), (140, 120, 180),
                    (86, 128, 128), (170, 190, 140), (100, 150, 96)], np.float32)
    rnd = random.Random(hole.number + 5)
    layer = np.ones((H, W, 3), np.float32) * 255
    pts = [(c.v.xy(p), r) for p, r in _tree_points(hole.trees, 6.0, hole.number + 9)]
    for (x, y), r in pts:
        R = int(px(r.uniform(3.5, 7.0)))
        if R < 3:
            continue
        a = _dab(R, rnd) * rnd.uniform(.55, .9)
        col = pal[rnd.randrange(len(pal))]
        x0, y0 = int(x) - R - 2, int(y) - R - 2
        hh, ww = a.shape
        ys, xs, ye, xe = max(0, y0), max(0, x0), min(H, y0 + hh), min(W, x0 + ww)
        if ys >= ye or xs >= xe:
            continue
        sa = a[ys - y0:ye - y0, xs - x0:xe - x0, None]
        layer[ys:ye, xs:xe] = layer[ys:ye, xs:xe] * (1 - sa + sa * col / 255)
    layer = np.stack([blur(layer[..., i] / 255, px(0.5)) * 255 for i in range(3)], -1)   # vått i vått
    skog = ragged(L["skog"], 1.8, cut=0.45, soft=0.3)
    # Grundlavering i skogen: grönt med violetta partier, sedan penseldragen ovanpå
    vio = np.clip((noise(H, W, 41, cell=px(22)) - 0.45) * 3, 0, 1)[..., None]
    base = np.array([150, 182, 140], np.float32) * (1 - vio) + np.array([150, 140, 196], np.float32) * vio
    img = img * (1 - skog[..., None]) + (img * base / 255) * skog[..., None]
    img = img * (1 - skog[..., None]) + (img * layer / 255) * skog[..., None]

    # Spelytorna – lasyrer i skissens färger, ränder i fairway
    img = wash(img, ragged(L["fairway"], 0.5), (194, 216, 162), factor=stripes(c, 9, 35, 0.035))
    img = wash(img, ragged(L["tee"], 0.4), (190, 212, 150))
    img = wash(img, ragged(L["green"], 0.5), (232, 238, 158))
    img = wash(img, ragged(L["bunker"], 0.35), (240, 212, 172), pool=0.3)
    water = np.maximum(L["vatten"], L["back"])
    wt = flatten(synth(kit["vatten"], W, H, c.s / 5, 4), px(5))
    wm = ragged(water, 0.4)
    img = img * (1 - wm[..., None]) + (img * wt / 255 * 1.12) * wm[..., None]
    img = multiply(img, (90, 130, 170), blur(np.clip(wm - shrink(wm, px(1.2)), 0, 1), px(.5)) * 0.35)

    # Blyertslinjer
    for m in (L["fairway"], L["green"]):
        line = np.clip(grow(m, 1.0) - m, 0, 1)
        img = multiply(img, (150, 150, 145), line * 0.35)
    grain = noise(H, W, 7, cell=3, octaves=2)
    img = shade(img, 0.975 + 0.04 * grain)
    alla = np.maximum.reduce([L["spel"], L["skog"], L["vatten"], L["bunker"]])
    vig = ragged(grow(alla, px(4)), 6, cut=0.4, soft=0.3)
    img = img * vig[..., None] + paper * (1 - vig[..., None])
    return Image.fromarray(np.clip(img, 0, 255).astype("uint8"))


RENDERERS = {2: render_klassisk, 4: render_nordisk}


def as_svg(img: Image.Image) -> str:
    """Rasterbilden inbäddad i en SVG – så att skylt och webb kan använda den som vilken hålbild som helst."""
    import base64
    import io

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    data = base64.b64encode(buf.getvalue()).decode()
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {img.width} {img.height}" preserveAspectRatio="xMidYMid meet">'
            f'<image href="data:image/jpeg;base64,{data}" width="{img.width}" height="{img.height}"/></svg>')
