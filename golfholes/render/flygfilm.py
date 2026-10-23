"""Flygfilm (rå) längs ett hål ur Lantmäteriets data – underlag för AI:ns video-till-video.

Allt som syns ligger där det ligger i verkligheten: marken är markhöjdmodellen (1 m),
träden är Laserdata Skog (riktig höjd och form) och ytan är ortofotot draperat ovanpå.
Inget gissas och ingen AI används här. Filmen är "rå": platta ytor, ortofotots färger.
AI:n får sedan bara byta yta på den (samma regel som för hålbilderna).

Kameran (Erics beslut 2026-10-11):
  - följer hålets mittlinje (`centerline`) från bakre tee till green, 5 m över marken,
    blicken ~60 m framåt, mjukt utjämnad kurva,
  - sist stiger kameran och tippar ner tills den ser rakt ner: filmen slutar i hålbilden
    ovanifrån (tee nederst, green överst – samma riktning som hålbilden).

Renderingen är strålgång per bildpunkt över ett höjdfält (mark + träd). En
max-pyramid av höjdfältet låter strålarna ta långa steg över öppen mark, så en ruta i
1280 × 720 tar några sekunder i numpy. Rutorna renderas parallellt och sätts ihop till
MP4 med ffmpeg.

    python -m golfholes flygfilm klubbar/glasriket/hal-14.yaml [--data data/glasriket]
    → output/<klubb>/flygfilm/hal-14-ra.mp4 + nyckelbilder
"""
from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from .. import geometry as g
from ..hole import Hole
from ..lantmateriet import read_window

ATTRIBUTION = "Underlag: Ortofoto, Markhöjdmodell och Laserdata Skog ©Lantmäteriet, bearbetat, CC BY 4.0"
DIS = np.array([226, 230, 228], np.float32)        # dis mot horisonten
HIMMEL = (np.array([150, 186, 222], np.float32),   # zenit
          np.array([222, 232, 238], np.float32))   # horisont
UTANFOR = np.array([239, 233, 220], np.float32)    # utanför Lantmäteriets ruta (papper)


# ---------------------------------------------------------------- scen
@dataclass
class Scen:
    rgb: np.ndarray    # (h, w, 3) uint8, ortofoto i full upplösning (rgb_res)
    H: np.ndarray      # (h, w) float32, mark + träd (m ö.h.)
    mark: np.ndarray   # (h, w) float32, markhöjd
    e0: float
    n0: float
    res: float
    pyr: list          # [(blockstorlek i celler, dilaterad blockmax)]
    rgb_res: float = 0.16
    korridor: np.ndarray | None = None   # hålets mittlinje (tee → green) för urklippet i slutet
    korridor_m: float = 40.0             # halva bredden på urklippet

    @property
    def hmin(self) -> float:
        return float(self.mark.min())

    @property
    def hmax(self) -> float:
        return float(self.H.max())


def _bilinjar(a: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0, a.shape[1] - 1.001)
    y = np.clip(y, 0, a.shape[0] - 1.001)
    x0, y0 = x.astype(np.int32), y.astype(np.int32)
    fx, fy = x - x0, y - y0
    if a.ndim == 3:
        fx, fy = fx[..., None], fy[..., None]
    a00, a01 = a[y0, x0], a[y0, x0 + 1]
    a10, a11 = a[y0 + 1, x0], a[y0 + 1, x0 + 1]
    return (a00 * (1 - fx) + a01 * fx) * (1 - fy) + (a10 * (1 - fx) + a11 * fx) * fy


def _blockmax(H: np.ndarray, b: int) -> np.ndarray:
    h, w = -(-H.shape[0] // b), -(-H.shape[1] // b)
    p = np.full((h * b, w * b), -1e9, np.float32)
    p[: H.shape[0], : H.shape[1]] = H
    m = p.reshape(h, b, w, b).max((1, 3))
    q = np.pad(m, 1, mode="edge")  # 3 × 3 block: säkert avstånd ≥ b celler åt alla håll
    return np.max(np.stack([q[i:i + h, j:j + w] for i in range(3) for j in range(3)]), axis=0)


def hal_bbox(hole: Hole, marginal_m: float) -> tuple[float, float, float, float]:
    pts = hole.centerline + hole.green + [t.point for t in hole.tees]
    es, ns = [p[0] for p in pts], [p[1] for p in pts]
    return (min(es) - marginal_m, min(ns) - marginal_m, max(es) + marginal_m, max(ns) + marginal_m)


def _avstand_till_linje(e: np.ndarray, n: np.ndarray, linje: np.ndarray) -> np.ndarray:
    d = np.full(e.shape, np.inf, np.float32)
    for (ax, ay), (bx, by) in zip(linje[:-1], linje[1:]):
        vx, vy = bx - ax, by - ay
        u = np.clip(((e - ax) * vx + (n - ay) * vy) / max(vx * vx + vy * vy, 1e-9), 0, 1)
        d = np.minimum(d, np.hypot(e - ax - u * vx, n - ay - u * vy))
    return d


def korridor(hole: Hole) -> tuple[np.ndarray, float]:
    """Hålets spelyta som linje + halv bredd: bakre tee → mittlinjen → green, bred nog
    för fairway, green och alla tees (som urklippet i hålbilden)."""
    tee = hole.tee()
    s0 = g.project(hole.centerline, tee.point)[0]
    s1 = g.project(hole.centerline, g.centroid(hole.green))[0]
    steg = np.linspace(s0, s1, 40)
    linje = np.array([g.point_along(hole.centerline, s) for s in steg])
    pts = [p for f in hole.fairways for p in f] + hole.green + [t.point for t in hole.tees]
    if not pts:
        return linje, 40.0
    d = _avstand_till_linje(np.array([p[0] for p in pts]), np.array([p[1] for p in pts]), linje)
    return linje, float(max(30.0, d.max() + 14.0))


def bygg_scen(orto: Path, dem_fil: Path, laz: Path | None, bbox, res: float = 0.25) -> Scen:
    """Ortofoto, markhöjd och träd på ett gemensamt rutnät (res m)."""
    a, e0, n0, r0 = read_window(orto, bbox)
    rgb = a[..., :3].astype(np.uint8) if a.dtype == np.uint8 else np.clip(a[..., :3], 0, 255).astype(np.uint8)
    del a
    k = res / r0
    w, h = int(rgb.shape[1] / k), int(rgb.shape[0] / k)
    yy, xx = np.mgrid[:h, :w].astype(np.float32)
    E = e0 + (xx + 0.5) * res
    N = n0 - (yy + 0.5) * res
    dem, de0, dn0, dr = read_window(dem_fil, (e0, n0 - h * res, e0 + w * res, n0))
    dem = dem.astype(np.float32).reshape(dem.shape[0], dem.shape[1])
    mark = _bilinjar(dem, (E - de0) / dr - 0.5, (dn0 - N) / dr - 0.5).astype(np.float32)
    H = mark.copy()
    if laz:
        from ..laser import tradhojd
        lr = 0.5  # laserpunkterna är för glesa för 0,25 m; 0,5 m fylls och läggs ut på rutnätet
        lw, lh = int(math.ceil(w * res / lr)), int(math.ceil(h * res / lr))
        lE = e0 + (np.arange(lw) + 0.5) * lr
        lN = n0 - (np.arange(lh) + 0.5) * lr
        lm = _bilinjar(dem, (lE[None, :] - de0) / dr - 0.5, (dn0 - lN[:, None]) / dr - 0.5).astype(np.float32)
        th = tradhojd(laz, lm, (e0, n0 - lh * lr, e0 + lw * lr, n0), res=lr)
        H = mark + _bilinjar(th, (xx + 0.5) * res / lr - 0.5, (yy + 0.5) * res / lr - 0.5).astype(np.float32)
    pyr = [(b, _blockmax(H, b)) for b in (4, 16, 64)]
    return Scen(rgb, H.astype(np.float32), mark, e0, n0, res, pyr, r0)


# ---------------------------------------------------------------- kamera
@dataclass
class Kamera:
    e: float
    n: float
    z: float
    yaw: float     # radianer, 0 = öster, moturs
    pitch: float   # radianer, negativ = nedåt
    dimma: float = 1.0
    urklipp: float = 0.0   # 0 → 1: allt utanför hålets korridor tonas till papper (som hålbilden)


def _utjamna(x: np.ndarray, sigma: float) -> np.ndarray:
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    return np.convolve(np.pad(x, r, mode="edge"), k, mode="valid")


def _smoothstep(u):
    u = np.clip(u, 0, 1)
    return u * u * (3 - 2 * u)


def _vinkel_lerp(a: float, b: float, u: float) -> float:
    d = (b - a + math.pi) % (2 * math.pi) - math.pi
    return a + d * u


def kamerabana(hole: Hole, scen: Scen, fps: int = 24, sekunder: float = 12.0, hojd_m: float = 5.0,
               blick_m: float = 60.0, slut_s: float = 4.0, bredd: int = 1280, hojd_px: int = 720,
               fov_grader: float = 60.0) -> tuple[list[Kamera], dict]:
    """Kamerans läge per ruta. Flygning tee → strax före green, sedan stigning och tippning
    ner till vy rakt ovanifrån med hela hålet i bild."""
    tee = hole.tee()
    cl = hole.centerline
    s_tee = g.project(cl, tee.point)[0]
    gm = g.centroid(hole.green)
    s_green = g.project(cl, gm)[0]
    langd = g.polyline_length(cl)

    def punkt(s):
        if s <= langd:
            return g.point_along(cl, max(0.0, s))
        a, b = cl[-2], cl[-1]
        d = g.dist(a, b)
        return (b[0] + (b[0] - a[0]) / d * (s - langd), b[1] + (b[1] - a[1]) / d * (s - langd))

    # mittlinjen var 1 m, utjämnad (σ 12 m) = mjuk kurva utan knyckar vid brytpunkterna
    ss = np.arange(s_tee - 20, s_green + blick_m + 40, 1.0)
    P = np.array([punkt(s) for s in ss])
    P = np.stack([_utjamna(P[:, 0], 12), _utjamna(P[:, 1], 12)], 1)

    def mark_pa(e, n):
        x = (np.asarray(e) - scen.e0) / scen.res - 0.5
        y = (scen.n0 - np.asarray(n)) / scen.res - 0.5
        return _bilinjar(scen.mark, x, y)

    def H_pa(e, n):
        x = (np.asarray(e) - scen.e0) / scen.res - 0.5
        y = (scen.n0 - np.asarray(n)) / scen.res - 0.5
        return _bilinjar(scen.H, x, y)

    mark_P = _utjamna(mark_pa(P[:, 0], P[:, 1]), 8)

    def vid(s):
        i = np.clip(s - ss[0], 0, len(ss) - 1.001)
        i0 = int(i)
        f = i - i0
        p = P[i0] * (1 - f) + P[i0 + 1] * f
        return p, mark_P[i0] * (1 - f) + mark_P[i0 + 1] * f

    n = int(round(fps * sekunder))
    n_slut = int(round(fps * slut_s))
    n_flyg = n - n_slut
    s_slut = s_green - (30 if hole.par > 3 else 20)
    # fart: mjuk start, jämn mitt, ingen inbromsning (stigningen tar över)
    u = np.linspace(0, 1, n_flyg)
    v = np.where(u < 0.15, (u / 0.15) ** 2 * 0.15 / 2 / 0.925, (u - 0.075) / 0.925)
    s_lista = s_tee + (s_slut - s_tee) * v / v[-1]

    vfov = 2 * math.atan(math.tan(math.radians(fov_grader) / 2) * hojd_px / bredd)
    kams: list[Kamera] = []
    varning = []
    for s in s_lista:
        p, m = vid(s)
        z = m + hojd_m
        hinder = float(H_pa(p[0], p[1]))
        if hinder + 1.0 > z:  # träd mitt i spellinjen: lyft hellre än att flyga in i det
            varning.append(round(float(s - s_tee)))
            z = hinder + 1.0
        q, mq = vid(s + blick_m)
        yaw = math.atan2(q[1] - p[1], q[0] - p[0])
        pitch = math.atan2(mq - z, blick_m)
        kams.append(Kamera(p[0], p[1], z, yaw, pitch))

    # slutläge: rakt ner, tee nederst och green överst, hela hålet i bild
    yaw_t = math.atan2(gm[1] - tee.point[1], gm[0] - tee.point[0])
    pts = cl + hole.green + [t.point for t in hole.tees]
    ca, sa = math.cos(yaw_t), math.sin(yaw_t)
    lang = [(p[0] - tee.point[0]) * ca + (p[1] - tee.point[1]) * sa for p in pts]
    tvar = [-(p[0] - tee.point[0]) * sa + (p[1] - tee.point[1]) * ca for p in pts]
    ml, mt = (min(lang) + max(lang)) / 2, (min(tvar) + max(tvar)) / 2
    ce, cn = tee.point[0] + ml * ca - mt * sa, tee.point[1] + ml * sa + mt * ca
    mark_mitt = float(np.median(mark_pa(np.array([p[0] for p in pts]), np.array([p[1] for p in pts]))))
    ut_l = (max(lang) - min(lang)) * 1.12 + 24
    ut_t = (max(tvar) - min(tvar)) * 1.12 + 24
    alt = max(ut_l / 2 / math.tan(vfov / 2), ut_t / 2 / math.tan(math.radians(fov_grader) / 2))
    sist = kams[-1]
    for i in range(1, n_slut + 1):
        u = i / n_slut
        uxy = float(_smoothstep(u))
        uz = float(_smoothstep(u) ** 1.3)
        up = float(_smoothstep(min(1.0, u * 1.08)))
        kams.append(Kamera(
            sist.e + (ce - sist.e) * uxy, sist.n + (cn - sist.n) * uxy,
            sist.z + (mark_mitt + alt - sist.z) * uz,
            _vinkel_lerp(sist.yaw, yaw_t, uxy),
            sist.pitch + (-math.pi / 2 + 1e-3 - sist.pitch) * up,
            dimma=1.0 - uxy, urklipp=float(_smoothstep((u - 0.7) / 0.3))))
    info = {"ruta_slut_flygning": n_flyg, "rutor": len(kams), "hojd_slut_m": round(alt),
            "flygstracka_m": round(s_slut - s_tee), "lyft_for_trad_vid_m": sorted(set(varning))}
    return kams, info


# ---------------------------------------------------------------- rendering
def rendera(scen: Scen, k: Kamera, bredd: int = 1280, hojd_px: int = 720, fov_grader: float = 60.0,
            sikt_m: float = 650.0) -> np.ndarray:
    """En ruta: strålgång per bildpunkt över höjdfältet."""
    f = (bredd / 2) / math.tan(math.radians(fov_grader) / 2)
    cy, sy = math.cos(k.yaw), math.sin(k.yaw)
    cp, sp = math.cos(k.pitch), math.sin(k.pitch)
    F = np.array([cp * cy, cp * sy, sp])
    R = np.array([sy, -cy, 0.0])
    U = np.cross(R, F)
    xs = (np.arange(bredd) - bredd / 2 + 0.5) / f
    ys = (np.arange(hojd_px) - hojd_px / 2 + 0.5) / f
    D = F[None, None, :] + xs[None, :, None] * R + (-ys)[:, None, None] * U
    D = (D / np.linalg.norm(D, axis=2, keepdims=True)).reshape(-1, 3).astype(np.float32)
    n = D.shape[0]
    C = np.array([k.e, k.n, k.z], np.float32)
    res, Hs = scen.res, scen.H
    hmax, hmin = scen.hmax, scen.hmin
    dz = D[:, 2]
    dxy = np.maximum(np.hypot(D[:, 0], D[:, 1]), 1e-4)
    # närgräns 4 m: löv alldeles intill kameran ritas inte (annars stora block i bild)
    t0 = np.where((dz < 0) & (k.z > hmax), (k.z - hmax) / np.maximum(-dz, 1e-6), 0.0)
    t0 = np.maximum(t0, 4.0)
    t1 = np.where(dz < 0, np.minimum(sikt_m / dxy, (k.z - hmin) / np.maximum(-dz, 1e-6)), sikt_m / dxy)
    t1 = np.minimum(t1, 4000.0)
    traff = np.full(n, np.inf, np.float32)
    aktiv = np.nonzero(t0 < t1)[0]
    t = t0[aktiv].astype(np.float32)
    tforr = t.copy()
    bas = (0.6 * res / np.maximum(dxy, np.abs(dz))).astype(np.float32)
    H_h, H_w = Hs.shape

    def hojd(e, nn):
        xf = (e - scen.e0) / res
        yf = (scen.n0 - nn) / res
        x, y = xf.astype(np.int32), yf.astype(np.int32)
        ute = (xf < 0) | (yf < 0) | (x >= H_w) | (y >= H_h)
        # bilinjärt: mjuk mark och mjuka trädkronor i stället för trappsteg per ruta
        return _bilinjar(Hs, xf - 0.5, yf - 0.5), x, y, ute

    for _ in range(4000):
        if aktiv.size == 0:
            break
        d = D[aktiv]
        z = C[2] + t * d[:, 2]
        e = C[0] + t * d[:, 0]
        nn = C[1] + t * d[:, 1]
        h, x, y, ute = hojd(e, nn)
        h = np.where(ute, hmin - 50, h)
        tr = z <= h
        if tr.any():
            # finjustera mellan förra (ovanför) och nuvarande (under) läget
            a, b = tforr[tr], t[tr]
            dd = d[tr]
            for _ in range(5):
                m = (a + b) / 2
                hm = hojd(C[0] + m * dd[:, 0], C[1] + m * dd[:, 1])[0]
                under = C[2] + m * dd[:, 2] <= hm
                b = np.where(under, m, b)
                a = np.where(under, a, m)
            traff[aktiv[tr]] = b
        # säkert steg: över blockmax kan strålen gå till blockets kant eller ner till maxhöjden
        steg = np.maximum(bas[aktiv], t * 0.0025)
        for blk, M in scen.pyr:
            bx = np.clip(x // blk, 0, M.shape[1] - 1)
            by = np.clip(y // blk, 0, M.shape[0] - 1)
            mm = np.where(ute, hmin - 50, M[by, bx])
            fri = z - mm
            rad = blk * res / dxy[aktiv]
            ned = np.where(d[:, 2] < -1e-6, fri / np.maximum(-d[:, 2], 1e-6), np.inf)
            s = np.where(fri > 0, np.minimum(rad, ned), 0.0)
            steg = np.maximum(steg, s)
        tforr = t
        t = t + steg
        kvar = (~tr) & (t < t1[aktiv])
        aktiv, t, tforr = aktiv[kvar], t[kvar], tforr[kvar]

    bild = np.empty((n, 3), np.float32)
    elev = np.clip(D[:, 2], 0, 1)[:, None] ** 0.6
    bild[:] = HIMMEL[1] * (1 - elev) + HIMMEL[0] * elev
    tr = np.isfinite(traff)
    bild[~tr & (D[:, 2] < -0.05) & (k.z > hmax)] = UTANFOR  # brant stråle utan träff = utanför rutan
    if tr.any():
        i = np.nonzero(tr)[0]
        tt = traff[i]
        e = C[0] + tt * D[i, 0]
        nn = C[1] + tt * D[i, 1]
        z = C[2] + tt * D[i, 2]
        farg = _bilinjar(scen.rgb, (e - scen.e0) / scen.rgb_res - 0.5,
                         (scen.n0 - nn) / scen.rgb_res - 0.5).astype(np.float32)
        x = (e - scen.e0) / res - 0.5
        y = (scen.n0 - nn) / res - 0.5
        # trädens sidor: mörkare längre ner mot stammen (djupkänsla, ingen påhittad form)
        top, mk = _bilinjar(Hs, x, y), _bilinjar(scen.mark, x, y)
        sida = np.where(top - mk > 2.0, np.clip((top - z) / np.maximum(top - mk, 0.5), 0, 1), 0.0)
        farg *= (1 - 0.38 * sida)[:, None]
        ute = (x < 0) | (y < 0) | (x > H_w - 1) | (y > H_h - 1)
        farg[ute] = UTANFOR
        if k.urklipp > 0 and scen.korridor is not None:
            dist = _avstand_till_linje(e, nn, scen.korridor)
            utanfor = np.clip((dist - scen.korridor_m) / 18.0, 0, 1)[:, None] * k.urklipp
            farg = farg * (1 - utanfor) + UTANFOR * utanfor
        avst = tt * dxy[i]
        dis = (np.clip(avst / sikt_m, 0, 1) ** 1.5 * 0.6 * k.dimma)[:, None]
        bild[i] = farg * (1 - dis) + DIS * dis
    return np.clip(bild.reshape(hojd_px, bredd, 3), 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- film
_SCEN: Scen | None = None


def _rendera_ruta(arg):
    i, k, bredd, hojd_px, mapp, ss = arg
    im = Image.fromarray(rendera(_SCEN, k, int(bredd * ss), int(hojd_px * ss)))
    if ss != 1:  # översampling: mjukare trädkanter och mindre flimmer i fjärran
        im = im.resize((bredd, hojd_px), Image.LANCZOS)
    p = Path(mapp) / f"r{i:04d}.png"
    im.save(p, compress_level=1)
    return str(p)


def ffmpeg_bin() -> str | None:
    b = shutil.which("ffmpeg")
    if b:
        return b
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return None


def flygfilm(hole: Hole, data_dir: Path, ut_dir: Path, fps: int = 24, sekunder: float = 12.0,
             bredd: int = 1280, hojd_px: int = 720, hojd_m: float = 5.0, blick_m: float = 60.0,
             slut_s: float = 4.0, nyckelbilder: int = 6, processer: int | None = None,
             res: float = 0.25, ss: float = 1.5) -> dict:
    """Renderar hela flygningen. Returnerar filvägar och fakta om banan."""
    global _SCEN
    orto = sorted((data_dir / "orto").glob("*.tif"))
    dem = sorted((data_dir / "hojd").glob("*.tif"))
    laz = sorted((data_dir / "laser").glob("*.laz"))
    if not orto or not dem:
        raise SystemExit(f"Saknar ortofoto eller höjdmodell under {data_dir} (orto/*.tif, hojd/*.tif).")
    bbox = hal_bbox(hole, 450.0)
    _SCEN = bygg_scen(orto[0], dem[0], laz[0] if laz else None, bbox, res)
    _SCEN.korridor, _SCEN.korridor_m = korridor(hole)
    kams, info = kamerabana(hole, _SCEN, fps, sekunder, hojd_m, blick_m, slut_s, bredd, hojd_px)
    ut_dir.mkdir(parents=True, exist_ok=True)
    namn = f"hal-{hole.number:02d}"
    tmp = Path(tempfile.mkdtemp(prefix=f"flygfilm-{namn}-"))
    jobb = [(i, k, bredd, hojd_px, str(tmp), ss) for i, k in enumerate(kams)]
    import multiprocessing as mp
    with mp.get_context("fork").Pool(processer or os.cpu_count() or 2) as pool:
        rutor = pool.map(_rendera_ruta, jobb, chunksize=2)
    filer = {}
    # nyckelbilder jämnt utspridda, sista = vy ovanifrån
    idx = [round(j * (len(rutor) - 1) / (nyckelbilder - 1)) for j in range(nyckelbilder)]
    for j, i in enumerate(idx, 1):
        p = ut_dir / f"{namn}-nyckelbild-{j}.jpg"
        Image.open(rutor[i]).convert("RGB").save(p, quality=90)
        filer[f"nyckelbild {j} ({i / fps:.1f} s)"] = p
    ff = ffmpeg_bin()
    if ff:
        mp4 = ut_dir / f"{namn}-flygfilm-ra.mp4"
        subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(tmp / "r%04d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
                        "-movflags", "+faststart", str(mp4)], check=True)
        filer["film"] = mp4
    else:
        filer["rutor"] = tmp
    if ff:
        shutil.rmtree(tmp, ignore_errors=True)
    info.update({"tee": hole.tee().name, "sekunder": round(len(kams) / fps, 1), "fps": fps,
                 "upplosning": f"{bredd}x{hojd_px}", "laser": bool(laz)})
    return {"filer": filer, "info": info}
