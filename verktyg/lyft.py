"""Lyft: gör den målade hålbilden levande med riktigt ljus – 0 AI-krediter.

Det AI-målningen saknar är djup. Det tar vi ur Lantmäteriets mätdata, så ljuset blir
lika sant som formen:

1. Trädskuggor: varje träd ur Laserdata Skog kastar sin skugga i låg eftermiddagssol
   (sydväst, 30°). Riktig höjd ger riktig skugglängd – 20 m gran ger 35 m skugga.
2. Relief: markhöjdmodellen (1 m) ger mjuka sluttningar, svackor och kullar.
3. Skogskant: fairway mörknar en aning in mot trädväggen (som i verkligheten).
4. Färg: kvällsljus (varma högdagrar, svala skuggor), björkarnas neongula dämpas
   till guld, vattnet blir djupt och klart.
5. Fokus: spelytan i full färg, omgivningen sjunker undan mot klubbens mörka botten.

Ingen form ändras: allt läggs ovanpå målningen och följer hålfilens koordinater.

    python verktyg/lyft.py klubbar/glasriket/hal-14.yaml → halbilder/hal-14-lyft.webp
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verktyg.orto_utsnitt as utsnitt  # noqa: E402,F401  (före golfholes.render)
from golfholes.hole import Hole  # noqa: E402
from golfholes.laser import ytor  # noqa: E402
from golfholes.render.foto import _mjuk, fotounderlag, orto_for  # noqa: E402

SOL_AZIMUT = 235.0   # grader från norr medurs: sydväst, sen eftermiddag
SOL_HOJD = 30.0      # grader över horisonten
RES = 0.5            # m per ruta för laser och skuggor
LAZ = utsnitt.LM / "laser" / "y26a023-63050_4900_25.copc.laz"
DEM = utsnitt.LM / "hojd.tif"
BOTTEN = np.array([17, 30, 48], np.float32)  # klubbens mörka marinblå (layout 3)


def _affin(px):
    """Bildpixel → SWEREF (e, n) ur px (som är affin: vridning + skala + flytt)."""
    pts = [(0.0, 0.0), (100.0, 0.0), (0.0, 100.0)]
    src = np.array([[*px(*p), 1.0] for p in pts])
    dst = np.array(pts)
    return np.linalg.solve(src, dst)  # [x, y, 1] @ M = [e, n]  (relativt e0, n0)


def _dem(bbox):
    s, _, _, _, e0, n0 = (float(v) for v in DEM.with_suffix(".tfw").read_text().split())
    a = np.asarray(Image.open(DEM), np.float32)
    E0, N0 = e0 - s / 2, n0 + s / 2
    x0, y0 = max(0, int((bbox[0] - E0) / s)), max(0, int((N0 - bbox[3]) / s))
    x1 = min(a.shape[1], int(np.ceil((bbox[2] - E0) / s)))
    y1 = min(a.shape[0], int(np.ceil((N0 - bbox[1]) / s)))  # utsnittet slutar vid banans kant
    return a[y0:y1, x0:x1], E0 + x0 * s, N0 - y0 * s, s


def _skift(a: np.ndarray, dy: int, dx: int, fyll: float = 0.0) -> np.ndarray:
    out = np.full_like(a, fyll)
    h, w = a.shape
    ys, yd = (slice(dy, h), slice(0, h - dy)) if dy >= 0 else (slice(0, h + dy), slice(-dy, h))
    xs, xd = (slice(dx, w), slice(0, w - dx)) if dx >= 0 else (slice(0, w + dx), slice(-dx, w))
    out[yd, xd] = a[ys, xs]
    return out


def skuggor(yta: np.ndarray, res: float) -> np.ndarray:
    """1 där solen skyms av något högre i solens riktning (höjdfält, strålgång)."""
    az = math.radians(SOL_AZIMUT)
    ue, un = math.sin(az), math.cos(az)            # mot solen i världen
    tan = math.tan(math.radians(SOL_HOJD))
    skugga = np.zeros_like(yta)
    for steg in range(1, int(45 / res)):
        d = steg * res
        dx, dy = round(ue * d / res), round(-un * d / res)  # rader växer söderut
        hinder = _skift(yta, dy, dx, fyll=-1e9) - d * tan
        skugga = np.maximum(skugga, np.clip((hinder - yta) / 1.5, 0, 1))
    return skugga


def _blur(a: np.ndarray, r: float) -> np.ndarray:
    """≈ gaussisk oskärpa (tre boxfilter); r i rutor."""
    return _mjuk(a.astype(np.float32), max(1, round(r)))


def _sampla(grid, g_e0, g_n0, g_res, E, N):
    """Bilinjärt – rutnätet är mycket grövre än bilden, så inga trappsteg."""
    x = np.clip((E - g_e0) / g_res - 0.5, 0, grid.shape[1] - 1.001)
    y = np.clip((g_n0 - N) / g_res - 0.5, 0, grid.shape[0] - 1.001)
    x0, y0 = x.astype(int), y.astype(int)
    fx, fy = x - x0, y - y0
    a, b = grid[y0, x0], grid[y0, x0 + 1]
    c, d = grid[y0 + 1, x0], grid[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def _hsv_bjork(rgb: np.ndarray, vikt: np.ndarray) -> np.ndarray:
    """Neongula björkar → djupt guld; bara mättat gult, bara utanför spelytan."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    s = (mx - mn) / (mx + 1e-3)
    gul = (r > b * 1.6) & (g > b * 1.4) & (r >= g * 0.85) & (s > 0.5) & (mx > 120)
    m = _blur(gul.astype(np.float32), 2.0) * vikt
    guld = np.stack([mx * 0.86, mx * 0.62, mx * 0.30], -1)  # varm bärnsten, lägre ljus
    ut = rgb * (1 - 0.55 * m[..., None]) + guld * (0.55 * m[..., None])
    return ut


def _prickar(a: np.ndarray) -> np.ndarray:
    """Kodens 100/150 m-prickar (röd, gul, vit kant) ska inte färgas om."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    rod = (r > 170) & (g < 90) & (b < 100)
    gul = (r > 200) & (g > 160) & (b < 80)
    m = (rod | gul).astype(np.float32)
    return _mjuk(m, 6) > 0.02


def lyft(halfil: Path, bild: Path, ut: Path) -> Path:
    hole = Hole.from_yaml(halfil)
    im = Image.open(bild).convert("RGBA")
    rot, px = fotounderlag(hole, orto_for(Path("data") / halfil.parent.name), im.height)
    if rot.size != im.size:
        im = im.resize(rot.size, Image.LANCZOS)
    W, H = im.size
    M = _affin(px)
    yy, xx = np.mgrid[:H, :W].astype(np.float32)
    E = xx * M[0, 0] + yy * M[1, 0] + M[2, 0]
    N = xx * M[0, 1] + yy * M[1, 1] + M[2, 1]
    bbox = (float(E.min()) - 50, float(N.min()) - 50, float(E.max()) + 50, float(N.max()) + 50)
    m_per_px = math.dist(px(0, 0), px(10, 0)) / 10
    m_per_px = 1 / m_per_px

    # --- höjder: mark ur höjdmodellen, träd ur laser
    dem, de0, dn0, dres = _dem(bbox)
    yta, le0, ln0, _ = ytor(LAZ, bbox, RES)
    yta = np.where(np.isfinite(yta), yta, np.nan)
    gy, gx = np.mgrid[: yta.shape[0], : yta.shape[1]]
    mark = _sampla(dem, de0, dn0, dres, le0 + (gx + 0.5) * RES, ln0 - (gy + 0.5) * RES)
    trad = np.nan_to_num(yta - mark, nan=0.0)
    trad = np.where(trad >= 2.0, trad, 0.0)
    trad = np.maximum(trad, _blur(trad, 1.0) * 0.9)  # hela kronor, inga hål
    hoj = mark + trad
    sk = skuggor(hoj.astype(np.float32), RES)
    sk = np.clip(_blur(sk, 2.0) * 1.1, 0, 1)  # halvskugga ~1 m
    # relief: lambert med samma sol, bara markens lutning
    mjuk = _blur(mark, 4.0 / RES)  # 4 m: bara terrängens former, inget brus
    dz_e = np.gradient(mjuk, axis=1) / RES
    dz_n = -np.gradient(mjuk, axis=0) / RES
    az, alt = math.radians(SOL_AZIMUT), math.radians(SOL_HOJD)
    l = np.array([math.sin(az) * math.cos(alt), math.cos(az) * math.cos(alt), math.sin(alt)])
    nlen = np.sqrt(dz_e ** 2 + dz_n ** 2 + 1)
    lam = (-dz_e * l[0] - dz_n * l[1] + l[2]) / nlen
    rel = lam / math.sin(alt)  # 1 = plan mark
    # skogskant: närhet till träd (ambient occlusion)
    ao = np.clip(_blur((trad > 3).astype(np.float32), 6.0 / RES) * 1.6, 0, 1)

    S = _sampla(sk, le0, ln0, RES, E, N)
    R = _sampla(rel, le0, ln0, RES, E, N)
    A = _sampla(ao, le0, ln0, RES, E, N)
    T = _sampla(trad, le0, ln0, RES, E, N)

    # --- spelytan i bildens pixlar
    spel = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(spel)
    for poly in hole.fairways + [hole.green]:
        if len(poly) > 2:
            d.polygon([px(*p) for p in poly], fill=255)
    d.line([px(*p) for p in hole.centerline], fill=255, width=max(2, int(14 / m_per_px)))
    for t in hole.tees:
        x, y = px(*t.point)
        r = 9 / m_per_px
        d.ellipse((x - r, y - r, x + r, y + r), fill=255)
    vatten = Image.new("L", (W, H), 0)
    dv = ImageDraw.Draw(vatten)
    for h in hole.hazards:
        if h.kind == "water" and len(h.polygon) > 2:
            dv.polygon([px(*p) for p in h.polygon], fill=255)
    vat = np.asarray(vatten.filter(ImageFilter.GaussianBlur(1.5 / m_per_px)), np.float32) / 255
    nara = np.asarray(spel.filter(ImageFilter.GaussianBlur(22 / m_per_px)), np.float32) / 255
    fokus = np.clip(nara * 3.0, 0, 1)
    fokus = np.maximum(fokus, vat)  # dammar i hålet hör till spelet

    a = np.asarray(im, np.float32)
    skydd = _prickar(a)
    rgb, alfa = a[..., :3], a[..., 3]

    # 1 björkar
    rgb = _hsv_bjork(rgb, np.clip(1.0 - vat, 0, 1))
    # 2 relief (mest på gräs) och skogskant
    gras = (T < 1.0).astype(np.float32)
    relf = 1 + (np.clip(R, 0.7, 1.25) - 1) * (0.35 * gras + 0.1)
    rgb *= relf[..., None]
    rgb *= (1 - 0.16 * A * gras)[..., None]
    # 3 skuggor: blåaktiga, genomskinliga (aldrig svarta), mjukare i vatten
    s = (S * (1 - 0.35 * vat) * (1 - 0.75 * np.clip(T / 6, 0, 1)) * (1 + 0.35 * gras))[..., None]  # mest på gräset
    skuggfarg = np.array([0.55, 0.64, 0.80], np.float32)
    rgb = rgb * (1 - s * (1 - skuggfarg))
    # 4 vatten: djupare, klarare, ljusare mot solsidan
    v = vat[..., None]
    djup = rgb * np.array([0.55, 0.72, 0.95]) + np.array([4, 14, 30])
    rgb = rgb * (1 - 0.6 * v) + djup * (0.6 * v)
    # 5 kvällsljus: varma högdagrar, svala skuggor, mer kontrast i mitten
    L = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    t = np.clip(L / 255, 0, 1)[..., None]
    varm = np.array([1.04, 1.02, 0.95], np.float32)
    sval = np.array([0.96, 0.99, 1.05], np.float32)
    rgb = rgb * (sval * (1 - t) + varm * t)
    kurva = lambda x: 255 * (0.5 + 0.5 * np.tanh((x / 255 - 0.47) * 2.3) / np.tanh(0.53 * 2.3))
    rgb = rgb * 0.7 + kurva(rgb) * 0.3
    # lokal kontrast (klarhet) + skärpa
    bas = np.stack([_blur(rgb[..., i], 24) for i in range(3)], -1)
    rgb = rgb + (rgb - bas) * 0.18
    fin = np.stack([_blur(rgb[..., i], 1.2) for i in range(3)], -1)
    rgb = rgb + (rgb - fin) * 0.35
    # 6 fokus: omgivningen avfärgas och sjunker mot den mörka botten
    grå = (rgb @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
    ute = (1 - fokus)[..., None]
    rgb = rgb * (1 - 0.35 * ute) + grå * (0.35 * ute)
    rgb = rgb * (1 - 0.25 * ute) + BOTTEN * (0.25 * ute)
    rgb = np.where(skydd[..., None], a[..., :3], rgb)  # prickarna orörda

    # 7 kanten: ingen ljus dimma ut mot botten – kanten bränns mörk och blir skarpare,
    # så hålet ligger som en upplyst ö på klubbens mörka färg
    a01 = alfa / 255
    bränn = np.clip((0.85 - a01) / 0.85, 0, 1)[..., None] ** 1.2
    rgb = rgb * (1 - 0.75 * bränn) + BOTTEN * (0.75 * bränn)
    alfa = 255 * np.clip((a01 - 0.10) / 0.75, 0, 1) ** 0.9
    out = np.dstack([np.clip(rgb, 0, 255), alfa]).astype(np.uint8)
    ut.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out, "RGBA").save(ut, quality=92, method=6)
    return ut


if __name__ == "__main__":
    hf = Path(sys.argv[1])
    n = Hole.from_yaml(hf).number
    bild = Path(sys.argv[2]) if len(sys.argv) > 2 else hf.parent / "halbilder" / f"hal-{n:02d}-malad-utan-flagga.webp"
    ut = Path(sys.argv[3]) if len(sys.argv) > 3 else hf.parent / "halbilder" / f"hal-{n:02d}-lyft.webp"
    print(lyft(hf, bild, ut))
