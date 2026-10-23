"""Formkontroll och AI-underlag för flygfilmen (test 2026-10-23).

Samma regel som för hålbilderna: AI:n får byta yta, aldrig form. Här räknas den råa
filmens kamerabana om (samma kod och samma inställningar som `flygfilm`), så att
hålfilens konturer (green, fairway, bunkrar, vatten, mittlinje) kan ritas exakt där
de ska ligga i varje ruta – både i den råa filmen och i AI-filmen.

    python -m golfholes.render.flygfilm_kontroll kameror  klubbar/glasriket/hal-14.yaml --sek 13 --ut kam.json
    python -m golfholes.render.flygfilm_kontroll slutbild klubbar/glasriket/hal-14.yaml --kam kam.json --ut slut.png
    python -m golfholes.render.flygfilm_kontroll konturer klubbar/glasriket/hal-14.yaml --kam kam.json \
        --film ai.mp4 --rutor 0,100,200,311 --ut kontroll/   [--start 192 för ett klipp som börjar vid 8 s]

`slutbild` lägger den godkända målade hålbilden (hal-NN-malad.webp) i exakt samma
läge som den råa filmens sista ruta (vy rakt ovanifrån på papper). Den används som
slutbild till AI:n, så att filmen landar i hålbilden.

Konturerna ritas utan skymning: bakom ett träd syns linjen ändå. Jämför därför
linjerna mot det som syns i öppna partier (green, bunker, fairwaykant).
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from dataclasses import asdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from ..hole import Hole
from .flygfilm import UTANFOR, Kamera, _bilinjar, bygg_scen, hal_bbox, kamerabana, korridor, ffmpeg_bin


def _scen(hole: Hole, data_dir: Path):
    orto = sorted((data_dir / "orto").glob("*.tif"))
    dem = sorted((data_dir / "hojd").glob("*.tif"))
    laz = sorted((data_dir / "laser").glob("*.laz"))
    scen = bygg_scen(orto[0], dem[0], laz[0] if laz else None, hal_bbox(hole, 450.0), 0.25)
    scen.korridor, scen.korridor_m = korridor(hole)
    return scen


def kameror(hole: Hole, data_dir: Path, sekunder: float, slut_s: float = 4.0) -> dict:
    """Kamerabanan precis som i den råa filmen, plus markhöjd runt hålet (för projektion)."""
    scen = _scen(hole, data_dir)
    kams, info = kamerabana(hole, scen, 24, sekunder, 5.0, 60.0, slut_s)
    # markhöjd i 2 m-rutnät runt hålet (räcker för att lägga konturer på marken)
    e0, n0, e1, n1 = hal_bbox(hole, 60.0)
    E = np.arange(e0, e1, 2.0)
    N = np.arange(n1, n0, -2.0)
    x = (E[None, :] - scen.e0) / scen.res - 0.5
    y = (scen.n0 - N[:, None]) / scen.res - 0.5
    mark = _bilinjar(scen.mark, np.broadcast_to(x, (len(N), len(E))), np.broadcast_to(y, (len(N), len(E))))
    return {"kameror": [asdict(k) for k in kams], "info": info,
            "mark": {"e0": e0, "n1": n1, "res": 2.0, "z": np.round(mark, 2).tolist()}}


class Projektion:
    def __init__(self, data: dict, bredd: int = 1280, hojd_px: int = 720, fov_grader: float = 60.0):
        self.kams = [Kamera(**k) for k in data["kameror"]]
        m = data["mark"]
        self.me0, self.mn1, self.mres = m["e0"], m["n1"], m["res"]
        self.mz = np.array(m["z"], np.float32)
        self.bredd, self.hojd_px = bredd, hojd_px
        self.f = (bredd / 2) / math.tan(math.radians(fov_grader) / 2)

    def markhojd(self, e, n):
        x = (np.asarray(e, np.float64) - self.me0) / self.mres
        y = (self.mn1 - np.asarray(n, np.float64)) / self.mres
        return _bilinjar(self.mz, x, y)

    def axlar(self, k: Kamera):
        cy, sy = math.cos(k.yaw), math.sin(k.yaw)
        cp, sp = math.cos(k.pitch), math.sin(k.pitch)
        F = np.array([cp * cy, cp * sy, sp])
        R = np.array([sy, -cy, 0.0])
        U = np.cross(R, F)
        return F, R, U

    def px(self, i: int, e, n, z=None):
        """Världspunkter → bildpunkter i ruta i (samma kamera som rendera). None bakom kameran."""
        k = self.kams[i]
        e, n = np.asarray(e, np.float64), np.asarray(n, np.float64)
        z = self.markhojd(e, n) if z is None else np.asarray(z)
        F, R, U = self.axlar(k)
        V = np.stack([e - k.e, n - k.n, z - k.z], -1)
        df, dr, du = V @ F, V @ R, V @ U
        x = self.bredd / 2 + self.f * dr / np.maximum(df, 1e-6)
        y = self.hojd_px / 2 - self.f * du / np.maximum(df, 1e-6)
        return x, y, df > 8.0

    def mark_under(self, i: int, X: np.ndarray, Y: np.ndarray):
        """Bildpunkter → markpunkter (e, n) för ruta i. Strålen skärs med marken (3 iterationer)."""
        k = self.kams[i]
        F, R, U = self.axlar(k)
        xs = (X - self.bredd / 2 + 0.5) / self.f
        ys = (Y - self.hojd_px / 2 + 0.5) / self.f
        D = F + xs[..., None] * R + (-ys)[..., None] * U
        D /= np.linalg.norm(D, axis=-1, keepdims=True)
        dz = np.minimum(D[..., 2], -1e-3)
        z = np.full(X.shape, float(np.median(self.mz)))
        for _ in range(3):
            t = (k.z - z) / -dz
            e, n = k.e + t * D[..., 0], k.n + t * D[..., 1]
            z = self.markhojd(e, n)
        return e, n


def _tata(poly, steg=1.0):
    ut = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        d = math.dist(a, b)
        m = max(1, int(d / steg))
        ut += [(a[0] + (b[0] - a[0]) * j / m, a[1] + (b[1] - a[1]) * j / m) for j in range(m)]
    return ut


def lager(hole: Hole):
    ut = [(fw, (255, 0, 200), True) for fw in hole.fairways] + [(hole.green, (0, 170, 255), True)]
    ut += [(h.polygon, (255, 255, 255) if h.kind == "bunker" else (0, 60, 255), True) for h in hole.hazards]
    ut.append((hole.centerline, (255, 200, 0), False))
    return ut


def rita_konturer(im: Image.Image, proj: Projektion, i: int, hole: Hole) -> Image.Image:
    ut = im.convert("RGB").copy()
    d = ImageDraw.Draw(ut)
    for poly, farg, sluten in lager(hole):
        pts = _tata(poly) if sluten else [p for a, b in zip(poly, poly[1:]) for p in _tata([a, b])[:-1]] + [poly[-1]]
        if sluten:
            pts.append(pts[0])
        x, y, fram = proj.px(i, [p[0] for p in pts], [p[1] for p in pts])
        seg = []
        for xx, yy, ok in zip(x, y, fram):
            if ok and -2000 < xx < 4000 and -2000 < yy < 3000:
                seg.append((float(xx), float(yy)))
            elif len(seg) > 1:
                d.line(seg, fill=farg, width=2)
                seg = []
            else:
                seg = []
        if len(seg) > 1:
            d.line(seg, fill=farg, width=2)
    d.text((8, 6), f"ruta {i}  ({i / 24:.1f} s)", fill=(255, 255, 0))
    return ut


def slutbild(hole: Hole, proj: Projektion, orto: Path, malad: Path, bredd: int = 1280, hojd_px: int = 720) -> Image.Image:
    """Den målade hålbilden lagd exakt som den råa filmens sista ruta (rakt ovanifrån) på papper."""
    from .foto import fotounderlag
    m = Image.open(malad).convert("RGBA")
    _, px = fotounderlag(hole, orto, m.height)
    i = len(proj.kams) - 1
    Y, X = np.mgrid[:hojd_px, :bredd].astype(np.float64)
    e, n = proj.mark_under(i, X, Y)
    # e, n → målningens bildpunkter. px är affin (vridning + skala): räkna ut den ur tre punkter
    e0, n0 = float(np.mean(e)), float(np.mean(n))
    p0, p1, p2 = px(e0, n0), px(e0 + 100, n0), px(e0, n0 + 100)
    ax = (np.array(p1) - p0) / 100
    ay = (np.array(p2) - p0) / 100
    mx = p0[0] + (e - e0) * ax[0] + (n - n0) * ay[0]
    my = p0[1] + (e - e0) * ax[1] + (n - n0) * ay[1]
    a = np.asarray(m, np.float32)
    farg = np.stack([_bilinjar(a[..., c], mx - 0.5, my - 0.5) for c in range(4)], -1)
    ute = (mx < 0) | (my < 0) | (mx > m.width - 1) | (my > m.height - 1)
    farg[ute] = 0
    alfa = farg[..., 3:4] / 255
    bild = farg[..., :3] * alfa + UTANFOR * (1 - alfa)
    return Image.fromarray(np.clip(bild, 0, 255).astype(np.uint8))


def las_rutor(film: Path, rutor: list[int], ut: Path) -> dict[int, Path]:
    """Plockar ut rutor ur en film (bildnummer räknas i 24 bilder/s, som den råa filmen)."""
    ut.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg_bin()
    res = {}
    for r in rutor:
        p = ut / f"ruta-{r:04d}.png"
        subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{r / 24:.4f}", "-i", str(film),
                        "-frames:v", "1", "-vf", "scale=1280:720", str(p)], check=True)
        res[r] = p
    return res


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="flygfilm_kontroll")
    p.add_argument("steg", choices=["kameror", "slutbild", "konturer"])
    p.add_argument("hal")
    p.add_argument("--data")
    p.add_argument("--sek", type=float, default=12.0)
    p.add_argument("--slut", type=float, default=4.0)
    p.add_argument("--kam")
    p.add_argument("--malad")
    p.add_argument("--film")
    p.add_argument("--rutor", default="")
    p.add_argument("--start", type=int, default=0, help="filmen börjar vid den här rutan i den råa filmen (klipp)")
    p.add_argument("--ut", required=True)
    a = p.parse_args(argv)
    hole = Hole.from_yaml(a.hal)
    hp = Path(a.hal)
    data_dir = Path(a.data) if a.data else Path("data") / hp.parent.name
    if a.steg == "kameror":
        Path(a.ut).write_text(json.dumps(kameror(hole, data_dir, a.sek, a.slut)))
        return 0
    proj = Projektion(json.loads(Path(a.kam).read_text()))
    if a.steg == "slutbild":
        malad = Path(a.malad) if a.malad else hp.parent / "halbilder" / f"hal-{hole.number:02d}-malad.webp"
        orto = sorted((data_dir / "orto").glob("*.tif"))[0]
        slutbild(hole, proj, orto, malad).save(a.ut)
        return 0
    ut = Path(a.ut)
    rutor = [int(r) for r in a.rutor.split(",") if r] or [0, len(proj.kams) - 1]
    for r, f in las_rutor(Path(a.film), [r - a.start for r in rutor], ut / "rutor").items():
        i = min(r + a.start, len(proj.kams) - 1)
        rita_konturer(Image.open(f), proj, i, hole).save(ut / f"kontur-{i:04d}.jpg", quality=90)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
