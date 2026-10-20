"""Perspektivvy i ögonhöjd ur Lantmäteriets data – underlag för AI-bilder och flygfilm.

Marken är markhöjdmodellen (1 m) med ortofotot draperat ovanpå. Skogen lyfts upp som
en massa (skogsmasken från utkast.klassa × trädhöjd), eftersom markmodellen saknar träd.
Bilden är alltså en grov "massmodell": allt ligger där det ligger i verkligheten
(green, bunkrar, dammar, skogskanter, backar), men ytorna är platta. AI:n får sedan
bara byta yta, som för hålbilderna.

Renderingen är en "voxel space"-strålgång: för varje bildkolumn stegas en stråle
framåt över höjdfältet och varje avstånd ritar en lodrät bit där den syns ovanför
det som redan ritats närmare kameran.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

from ..lantmateriet import read_window
from ..utkast import Fonster, klassa, matt, medel

TRADHOJD_M = 20.0   # svensk granskog på Glasriket: ~18–25 m
HIMMEL = ((196, 214, 226), (236, 238, 234))  # zenit → horisont


def _hojd_pa(dem: np.ndarray, d0: tuple[float, float, float], E: np.ndarray, N: np.ndarray) -> np.ndarray:
    e0, n0, r = d0
    x = np.clip((E - e0) / r, 0, dem.shape[1] - 1.001)
    y = np.clip((n0 - N) / r, 0, dem.shape[0] - 1.001)
    x0, y0 = x.astype(int), y.astype(int)
    fx, fy = x - x0, y - y0
    a, b = dem[y0, x0], dem[y0, x0 + 1]
    c, d = dem[y0 + 1, x0], dem[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def perspektiv(orto: Path, dem_fil: Path, kamera: tuple[float, float], mot: tuple[float, float],
               hojd_m: float = 1.6, bredd: int = 1536, hojd_px: int = 1024, fov_grader: float = 60.0,
               sikt_m: float = 420.0, ut: Path | None = None, fria: list | None = None,
               linjer: list | None = None, korridor_m: float = 24.0, fri_runt_kamera_m: float = 10.0) -> Image.Image:
    """fria: spelytor (polygoner) där inga träd står. linjer: hålens spellinjer – ett band
    korridor_m brett längs dem hålls öppet, som i hålbilderna (hålet är öppet från tee).
    Kameran står alltid på öppen mark (tee eller fairway)."""
    ce, cn = kamera
    bbox = (ce - sikt_m, cn - sikt_m, ce + sikt_m, cn + sikt_m)
    a, e0, n0, res = read_window(orto, bbox)
    f = Fonster(a.astype(np.float32), e0, n0, res)
    # halvera upplösningen (0,32 m) – räcker gott på de avstånd som syns
    rgb = f.rgbn[::2, ::2, :3]
    mt = matt(Fonster(f.rgbn[::2, ::2], e0, n0, res * 2))
    # träd = grov struktur och klorofyll. Mörka men släta ytor är skuggor på gräs, inte skog
    # (utkast.klassa räknar dem som skog, vilket är ofarligt i planvy men ger väggar i 3D).
    skog = (medel(mt["struktur"], 4) > 9) & (mt["ndvi"] > 0.1) & ~klassa(mt)["vatten"]
    if fria:  # spelytor ur hålfilerna: aldrig träd
        from .foto import _rastrera
        fr = _rastrera(fria, Fonster(rgb, e0, n0, res * 2), skog.shape)
        skog &= ~fr
    r = res * 2
    from ..utkast import _avstand_till_linje
    fh = Fonster(rgb, e0, n0, r)
    oppet = _avstand_till_linje(fh, [kamera, (kamera[0] + 0.01, kamera[1])], skog.shape) < fri_runt_kamera_m
    for lin in linjer or []:
        oppet |= _avstand_till_linje(fh, list(lin), skog.shape) < korridor_m / 2
    skog &= ~oppet
    dem, de0, dn0, dr = read_window(dem_fil, bbox)
    dem = dem.astype(np.float32).reshape(dem.shape[0], dem.shape[1])
    # markhöjd på ortofotots rutnät + skogen som massa (mjuk kant, lite ojämn topp)
    yy, xx = np.mgrid[: rgb.shape[0], : rgb.shape[1]]
    E = e0 + (xx + 0.5) * r
    N = n0 - (yy + 0.5) * r
    mark = _hojd_pa(dem, (de0, dn0, dr), E, N)
    kron = medel(skog.astype(np.float32), 3)
    ojamn = medel(mt["V"], 2) / 255.0  # ljusa kronor sticker upp lite
    H = mark + TRADHOJD_M * np.clip(kron * 1.4 - 0.2, 0, 1) * (0.85 + 0.3 * ojamn)

    kz = _hojd_pa(dem, (de0, dn0, dr), np.array([ce]), np.array([cn]))[0] + hojd_m
    phi = math.atan2(mot[1] - cn, mot[0] - ce)
    f_px = (bredd / 2) / math.tan(math.radians(fov_grader) / 2)
    horisont = hojd_px * 0.45
    kol = np.arange(bredd) - bredd / 2 + 0.5
    vink = phi - np.arctan(kol / f_px)          # strålens riktning per kolumn
    cosk = np.cos(np.arctan(kol / f_px))        # rätta fisheye-effekten
    dx, dy = np.cos(vink), np.sin(vink)

    bild = np.zeros((hojd_px, bredd, 3), np.float32)
    t = np.linspace(0, 1, hojd_px)[:, None]
    himmel = np.array(HIMMEL[0]) * (1 - t) + np.array(HIMMEL[1]) * t
    bild[:] = himmel[:, None, :]
    rad = np.arange(hojd_px, dtype=np.float32)
    ybuf = np.full(bredd, hojd_px, np.float32)  # lägsta y som redan är ritat per kolumn
    z, steg = 1.0, 0.08
    dis = np.array([236, 238, 234], np.float32)
    while z < sikt_m:
        we, wn = ce + dx * z, cn + dy * z
        px_ = np.clip(((we - e0) / r).astype(int), 0, rgb.shape[1] - 1)
        py_ = np.clip(((n0 - wn) / r).astype(int), 0, rgb.shape[0] - 1)
        h = H[py_, px_]
        zz = z * cosk
        y_skarm = horisont - (h - kz) / zz * f_px
        farg = rgb[py_, px_]
        dimma = min(1.0, (z / sikt_m) ** 1.6) * 0.55
        farg = farg * (1 - dimma) + dis * dimma
        syns = y_skarm < ybuf
        if syns.any():
            k = np.nonzero(syns)[0]
            m = (rad[:, None] >= y_skarm[k]) & (rad[:, None] < ybuf[k])
            yi, ki = np.nonzero(m)
            bild[yi, k[ki]] = farg[k[ki]]
        ybuf = np.minimum(ybuf, np.maximum(y_skarm, 0))
        z += steg
        steg *= 1.006
    im = Image.fromarray(np.clip(bild, 0, 255).astype(np.uint8))
    if ut:
        Path(ut).parent.mkdir(parents=True, exist_ok=True)
        im.save(ut, quality=92)
    return im
