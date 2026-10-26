"""Formkontroll och AI-underlag för flygfilmen (test 2026-10-23).

Samma regel som för hålbilderna: AI:n får byta yta, aldrig form. Här räknas den råa
filmens kamerabana om (samma kod och samma inställningar som `flygfilm`), så att
hålfilens konturer (green, fairway, bunkrar, vatten, mittlinje) kan ritas exakt där
de ska ligga i varje ruta – både i den råa filmen och i AI-filmen.

    python -m golfholes.render.flygfilm_kontroll kameror  klubbar/glasriket/hal-14.yaml --sek 13 --ut kam.json
    python -m golfholes.render.flygfilm_kontroll slutbild klubbar/glasriket/hal-14.yaml --kam kam.json --ut slut.png
    python -m golfholes.render.flygfilm_kontroll konturer klubbar/glasriket/hal-14.yaml --kam kam.json \
        --film ai.mp4 --rutor 0,100,200,311 --ut kontroll/   [--start 192 för ett klipp som börjar vid 8 s]

Översiktsfilmen (Eric 2026-10-24: ovanifrån → ner till tee 56 → green → upp igen):

    python -m golfholes.render.flygfilm_kontroll kameror  klubbar/glasriket/hal-14.yaml --forlopp oversikt --ut kam.json
    python -m golfholes.render.flygfilm_kontroll animatic klubbar/glasriket/hal-14.yaml --kam kam.json \
        --film hal-14-oversikt-flygfilm-ra.mp4 --ut animatic.mp4      (→ animatic.mp4 + animatic.jpg)

`animatic` gör hela filmen med bara kod: högt upp den målade hålbilden lagd på marken
(exakt, ruta för ruta), lågt ner filmen (rå nu, AI-filmen sen). Den skriver ut vilka rutor
AI:n måste göra om (hela sekunder, högst 6 s per klipp). Byt --film mot AI-klippen
hopsatta så blir det den färdiga filmen.

`tvatt` tar bort påhittad sand (och med --green en påhittad ljus green-yta) i ett område
nära horisonten i valda rutor, där formkontrollen visat att AI:n hittat på. Bara borttagning:
ytan fylls med gräset runt omkring, inget nytt ritas in (v2 480p: slutet av del 1 och del 2):

    python -m golfholes.render.flygfilm_kontroll tvatt klubbar/glasriket/hal-14.yaml --film del2.mp4 \
        --delar 85-150 --omrade 500,1010,280,355 --green --ut del2-tvattad.mp4

`rarutor` renderar om en bit av den råa filmen (samma kamerabana) med smala linjer suddade i
ortofotot, t.ex. körspåret i ruffen till höger om hål 14:s tee som AI:n gjorde till en grusgång.
Bara ytan ändras, ingen form (v3, Eric 2026-10-25: "ingen grusgång ... utan rough"):

    python -m golfholes.render.flygfilm_kontroll rarutor klubbar/glasriket/hal-14.yaml --kam kam.json \
        --delar 79-295 --sudda sudda.json --ut ra-79-295.mp4

`stig` tar bort en påhittad stig/grusgång ur en stillbild (AI-startbild) längs en handritad
mittlinje och fyller med ruffen bredvid (v3, Eric 2026-10-25: ingen grusgång längs högersidan):

    python -m golfholes.render.flygfilm_kontroll stig klubbar/glasriket/hal-14.yaml --film start.png \
        --linjer '[[34,-40,[[532,175],[548,725]]]]' --ut start-utan-stig.png

Översikten i början och slutet ligger på klubbens mörka färg (`--bakgrund klubb`, standard;
Glasriket #10202E som hålkorten) – `--bakgrund papper` ger den gamla ljusa. `hopklipp --tona 2`
ger korta skarvar utan spökträd.

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
from .flygfilm import (UTANFOR, Kamera, _avstand_till_linje, _bilinjar, bygg_scen, ffmpeg_bin, hal_bbox, kamerabana,
                       kamerabana_oversikt, korridor, standardtee)


def _scen(hole: Hole, data_dir: Path):
    orto = sorted((data_dir / "orto").glob("*.tif"))
    dem = sorted((data_dir / "hojd").glob("*.tif"))
    laz = sorted((data_dir / "laser").glob("*.laz"))
    scen = bygg_scen(orto[0], dem[0], laz[0] if laz else None, hal_bbox(hole, 450.0), 0.25)
    scen.korridor, scen.korridor_m = korridor(hole)
    return scen


def kameror(hole: Hole, data_dir: Path, sekunder: float, slut_s: float = 4.0, forlopp: str = "rak",
            tee: str | None = None, hojd_m: float = 5.0, blick_m: float = 60.0) -> dict:
    """Kamerabanan precis som i den råa filmen, plus markhöjd runt hålet (för projektion)."""
    scen = _scen(hole, data_dir)
    if forlopp == "oversikt":
        kams, info = kamerabana_oversikt(hole, scen, 24, standardtee(hole, tee), hojd_m, blick_m)
    else:
        kams, info = kamerabana(hole, scen, 24, sekunder, hojd_m, blick_m, slut_s)
    # markhöjd i 2 m-rutnät runt hålet (räcker för att lägga konturer på marken)
    e0, n0, e1, n1 = hal_bbox(hole, 60.0 if forlopp == "rak" else 450.0)
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


class MaladKarta:
    """Den godkända målade hålbilden som karta: SWEREF-punkt → färg (papper utanför)."""

    def __init__(self, hole: Hole, orto: Path, malad: Path, bakgrund=UTANFOR):
        from .foto import fotounderlag
        self.bakgrund = np.asarray(bakgrund, np.float32)
        m = Image.open(malad).convert("RGBA")
        _, px = fotounderlag(hole, orto, m.height)
        # px är affin (vridning + skala): räkna ut den ur tre punkter
        c = g_centroid(hole)
        self.e0, self.n0 = c
        p0, p1, p2 = px(c[0], c[1]), px(c[0] + 100, c[1]), px(c[0], c[1] + 100)
        self.p0 = np.array(p0, np.float64)
        self.ax = (np.array(p1) - p0) / 100
        self.ay = (np.array(p2) - p0) / 100
        self.a = np.asarray(m, np.float32)
        self.w, self.h = m.width, m.height

    def farg(self, e: np.ndarray, n: np.ndarray) -> np.ndarray:
        mx = self.p0[0] + (e - self.e0) * self.ax[0] + (n - self.n0) * self.ay[0]
        my = self.p0[1] + (e - self.e0) * self.ax[1] + (n - self.n0) * self.ay[1]
        farg = np.stack([_bilinjar(self.a[..., c], mx - 0.5, my - 0.5) for c in range(4)], -1)
        farg[(mx < 0) | (my < 0) | (mx > self.w - 1) | (my > self.h - 1)] = 0
        alfa = farg[..., 3:4] / 255
        return farg[..., :3] * alfa + self.bakgrund * (1 - alfa)


def hexfarg(text: str) -> np.ndarray:
    t = text.strip().lstrip("#")
    return np.array([int(t[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def klubbens_bakgrund(halfil: Path) -> np.ndarray:
    """Bakgrunden runt hålbilden i översikten: klubbens mörka färg (profil.farger.djup i
    klubb.yaml, Glasriket #10202E – samma som hålkortens mörka layout). Utan klubb.yaml: papper."""
    k = Path(halfil).parent / "klubb.yaml"
    if not k.exists():
        return UTANFOR
    from .klubbmaterial import Klubb
    return hexfarg(Klubb.from_dir(k.parent).farger["djup"])


def g_centroid(hole: Hole) -> tuple[float, float]:
    pts = hole.centerline
    return (float(np.mean([p[0] for p in pts])), float(np.mean([p[1] for p in pts])))


def malad_i_ruta(karta: MaladKarta, proj: Projektion, i: int) -> np.ndarray:
    """Den målade hålbilden som den syns från kameran i ruta i (lagd på marken)."""
    Y, X = np.mgrid[:proj.hojd_px, :proj.bredd].astype(np.float64)
    e, n = proj.mark_under(i, X, Y)
    return karta.farg(e, n)


def slutbild(hole: Hole, proj: Projektion, orto: Path, malad: Path, bredd: int = 1280, hojd_px: int = 720,
             bakgrund=UTANFOR) -> Image.Image:
    """Den målade hålbilden lagd exakt som den råa filmens sista ruta (rakt ovanifrån) på bakgrunden."""
    bild = malad_i_ruta(MaladKarta(hole, orto, malad, bakgrund), proj, len(proj.kams) - 1)
    return Image.fromarray(np.clip(bild, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- animatic och AI-delar
MALAD_HOJD = (90.0, 300.0)    # m över mark: under 90 syns filmen, över 300 bara hålbilden (övergång ~0,8 s)
PAPPER_HOJD = (50.0, 150.0)   # m över mark: utanför hålet tonas filmen till papper (som i hålbilden)


def _logvikt(h: float, lag: float, hog: float) -> float:
    u = (math.log(max(h, 0.1)) - math.log(lag)) / (math.log(hog) - math.log(lag))
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def vikter(hojd_over_mark: list[float]) -> tuple[np.ndarray, np.ndarray]:
    """Per ruta: (andel målad hålbild, andel papper utanför hålet)."""
    h = np.asarray(hojd_over_mark, np.float64)
    return (np.array([_logvikt(x, *MALAD_HOJD) for x in h]), np.array([_logvikt(x, *PAPPER_HOJD) for x in h]))


def ai_delar(hojd_over_mark: list[float], fps: int = 24, max_s: int = 6) -> list[tuple[int, int]]:
    """Rutorna där filmen syns (hålbilden inte täcker allt) delade i klipp på hela sekunder
    (OpenArt tar bara hela sekunder), högst max_s s var. Nästa klipp börjar på förra
    klippets sista ruta (samma startbild), så delarna hänger ihop."""
    mal, _ = vikter(hojd_over_mark)
    syns = np.nonzero(mal < 0.999)[0]
    if syns.size == 0:
        return []
    a, b = int(syns[0]), int(syns[-1])
    sek = max(1, math.ceil((b - a) / fps - 1e-6))
    antal = math.ceil(sek / max_s)
    langder = [sek // antal + (1 if j < sek % antal else 0) for j in range(antal)]
    ut, start = [], a
    for L in langder:
        ut.append((start, start + L * fps))
        start += L * fps
    return ut


def papper_utanfor(hole: Hole, proj: Projektion, i: int, skala: int = 4) -> np.ndarray:
    """0 → 1 utanför hålets korridor (samma mått som urklippet i den råa filmen), (h, w, 1)."""
    linje, halv = korridor(hole)
    Y, X = np.mgrid[:proj.hojd_px:skala, :proj.bredd:skala].astype(np.float64) + skala / 2
    e, n = proj.mark_under(i, X, Y)
    d = _avstand_till_linje(e, n, linje)
    m = np.clip((d - halv) / 18.0, 0, 1).astype(np.float32)
    m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((proj.bredd, proj.hojd_px), Image.BILINEAR),
                   np.float32) / 255
    return m[..., None]


def animatic(hole: Hole, proj: Projektion, hojd_over_mark: list[float], karta: MaladKarta, film: Path,
             ut: Path, fps: int = 24, etikett: bool = True) -> dict:
    """(Bakgrunden utanför hålet är kartans bakgrund: klubbens mörka färg eller papper.)"""
    """Bara kod: målade hålbilden där kameran är högt, filmen (rå eller AI) där den är lågt.
    Övergången: först tonas allt utanför hålet till papper, sedan tonas hålbilden in på plats."""
    ff = ffmpeg_bin()
    B, Hp = proj.bredd, proj.hojd_px
    mal, pap = vikter(hojd_over_mark)
    delar = ai_delar(hojd_over_mark, fps)
    las = subprocess.Popen([ff, "-loglevel", "error", "-i", str(film), "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-vf", f"scale={B}:{Hp}", "-"], stdout=subprocess.PIPE)
    skriv = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                              "-s", f"{B}x{Hp}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                              "-crf", "18", "-preset", "medium", "-movflags", "+faststart", str(ut)],
                             stdin=subprocess.PIPE)
    from PIL import ImageFont
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
        liten = ImageFont.truetype("DejaVuSans.ttf", 13)
    except OSError:
        font = liten = ImageFont.load_default()
    n = len(proj.kams)
    for i in range(n):
        buf = las.stdout.read(B * Hp * 3)
        if len(buf) < B * Hp * 3:
            break
        r = np.frombuffer(buf, np.uint8).reshape(Hp, B, 3).astype(np.float32)
        if pap[i] > 0.001 and mal[i] < 0.999:
            m = papper_utanfor(hole, proj, i) * pap[i]
            r = r * (1 - m) + karta.bakgrund * m
        if mal[i] > 0.001:
            r = r * (1 - mal[i]) + malad_i_ruta(karta, proj, i) * mal[i]
        im = Image.fromarray(np.clip(r, 0, 255).astype(np.uint8))
        if etikett:
            d = ImageDraw.Draw(im)
            ai = any(a <= i <= b for a, b in delar)
            delnr = next((j + 1 for j, (a, b) in enumerate(delar) if a <= i <= b), None)
            text = f"{i / fps:5.1f} s  " + (f"AI-del {delnr} (här: rå film)" if ai else "KOD: målade hålbilden")
            x1 = d.textbbox((14, 11), text, font=font)[2]
            d.rectangle([8, 8, x1 + 8, 36], fill=(0, 0, 0))
            d.text((14, 11), text, fill=(255, 220, 0) if ai else (255, 255, 255), font=font)
            d.text((10, Hp - 20), "Underlag: Ortofoto, Markhöjdmodell och Laserdata Skog ©Lantmäteriet, bearbetat, CC BY 4.0",
                   fill=(60, 60, 60), font=liten)
        skriv.stdin.write(im.tobytes())
    skriv.stdin.close()
    skriv.wait()
    las.stdout.close()
    las.wait()
    return {"delar": delar, "rutor": n}


def omprojicera(bild: Image.Image, proj: Projektion, k0: int, i: int, kant: float = 40.0):
    """En bild tagen från kameran i ruta k0 (t.ex. en AI-tvättad ruta ur den råa filmen) lagd på
    marken och sedd från kameran i ruta i. Exakt geometri så länge kameran tittar nästan rakt ner
    (marken räknas som platt yta, träden blir platta). Används för nedstigningen ur hålbilden.
    Ger (bild, täckning 0–1), där täckningen tonar ut `kant` px från bildens kant."""
    a = np.asarray(bild.convert("RGB").resize((proj.bredd, proj.hojd_px), Image.LANCZOS), np.float32)
    Y, X = np.mgrid[:proj.hojd_px, :proj.bredd].astype(np.float64)
    e, n = proj.mark_under(i, X, Y)
    x, y, _ = proj.px(k0, e, n)
    tack = np.clip(np.minimum.reduce([x, proj.bredd - x, y, proj.hojd_px - y]) / kant, 0, 1)
    x = np.clip(x - 0.5, 0, proj.bredd - 1)
    y = np.clip(y - 0.5, 0, proj.hojd_px - 1)
    return np.stack([_bilinjar(a[..., c], x, y) for c in range(3)], -1), tack[..., None]


def omproj_film(bilder: list[tuple[int, Path]], proj: Projektion, k0: int, k1: int, ut: Path, fps: int = 24) -> Path:
    """Rutorna k0..k1-1 gjorda av AI-tvättade stillbilder (var och en tagen i sin ruta) med
    kamerabanan. Med flera bilder tonas nästa bild in där den täcker, mot slutet av steget
    fram till dess ruta (den skarpare, närmare bilden tar över)."""
    skriv = subprocess.Popen([ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                              "-s", f"{proj.bredd}x{proj.hojd_px}", "-r", str(fps), "-i", "-", "-c:v", "libx264",
                              "-pix_fmt", "yuv420p", "-crf", "12", str(ut)], stdin=subprocess.PIPE)
    bilder = sorted(bilder)
    ims = [(k, Image.open(p)) for k, p in bilder]
    for i in range(k0, k1):
        ut_bild, _ = omprojicera(ims[0][1], proj, ims[0][0], i)
        for j in range(1, len(ims)):
            kf, kn = ims[j - 1][0], ims[j][0]
            u = min(1.0, max(0.0, (i - kf - 0.4 * (kn - kf)) / (0.6 * (kn - kf))))
            if u > 0:
                b, tack = omprojicera(ims[j][1], proj, kn, i)
                w = tack * (u * u * (3 - 2 * u))
                ut_bild = ut_bild * (1 - w) + b * w
        skriv.stdin.write(np.clip(ut_bild, 0, 255).astype(np.uint8).tobytes())
    skriv.stdin.close()
    skriv.wait()
    return ut


def _las_film(film: Path, B: int = 1280, Hp: int = 720, fps: int = 24) -> np.ndarray:
    """Hela filmen som (rutor, h, b, 3) uint8, omräknad till fps bilder/s."""
    r = subprocess.run([ffmpeg_bin(), "-loglevel", "error", "-i", str(film), "-vf", f"fps={fps},scale={B}:{Hp}",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, Hp, B, 3)


def _medel_std(bilder: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x = bilder[..., :3].reshape(-1, 3).astype(np.float32)[::7]
    return x.mean(0), x.std(0) + 1e-3


def fargmatcha(bilder: np.ndarray, kalla: tuple, mal: tuple, styrka: float = 1.0) -> np.ndarray:
    """Flyttar färgernas medel och spridning (per kanal) från kalla mot mal."""
    (m0, s0), (m1, s1) = kalla, mal
    m = m0 + (m1 - m0) * styrka
    s = s0 + (s1 - s0) * styrka
    return (bilder.astype(np.float32) - m0) * (s / s0) + m


def hopklipp(ra: Path, klipp: list[Path], delar: list[tuple[int, int]], ut: Path, fps: int = 24,
             tona: int = 6, B: int = 1280, Hp: int = 720) -> dict:
    """Sätter ihop AI-klippen till en film lika lång som den råa (samma rutnummer).

    Utanför AI-delarna används den råa filmen (där täcker hålbilden ändå allt). Varje klipp
    sträcks/kortas till exakt sin dels längd. Vid skarvarna mellan klippen jämnas färgen
    ut (medel och spridning glider från förra klippets slut till nästa klipps början) och
    bilderna tonas i varandra över `tona` rutor, så att man inte ser hoppet. Eftersom varje klipp
    börjar på förra klippets sista ruta räcker en kort toning (v3: 2 rutor); en lång toning
    blandar två bilder i rörelse och ger "spökträd" (v2). tona=0 är ett rent klipp."""
    film = _las_film(ra, B, Hp, fps).copy()
    bitar = []
    for (a, b), k in zip(delar, klipp):
        f = _las_film(k, B, Hp, fps)
        idx = np.round(np.linspace(0, len(f) - 1, b - a)).astype(int)   # exakt b - a rutor
        bitar.append(f[idx].copy())
        del f
    # färg: varje klipps början dras mot förra klippets slut, med avtagande styrka genom klippet
    for j in range(1, len(bitar)):
        slut = _medel_std(bitar[j - 1][-6:])
        borjan = _medel_std(bitar[j][:6])
        n = len(bitar[j])
        for t in range(n):
            w = max(0.0, 1 - t / (n * 0.6))
            if w > 0:
                bitar[j][t] = np.clip(fargmatcha(bitar[j][t], borjan, slut, w), 0, 255).astype(np.uint8)
    # tona över skarven: sista rutorna i förra klippet glider mot nästa klipps första ruta och tvärtom
    skillnad = []
    for j in range(1, len(bitar)):
        A, Bn = bitar[j - 1], bitar[j]
        a_slut, b_borjan = A[-1].astype(np.float32), Bn[0].astype(np.float32)
        skillnad.append(round(float(np.abs(a_slut - b_borjan).mean()), 1))
        h = min(tona, len(A) // 4, len(Bn) // 4)
        if h <= 0:
            continue
        for t in range(h):
            w = 0.5 * (t + 1) / (h + 1)          # 0 → 0,5 fram till skarven
            A[-h + t] = np.clip(A[-h + t] * (1 - w) + b_borjan * w, 0, 255).astype(np.uint8)
            Bn[h - 1 - t] = np.clip(Bn[h - 1 - t] * (1 - w) + a_slut * w, 0, 255).astype(np.uint8)
    for (a, b), bit in zip(delar, bitar):
        film[a:b] = bit
    skriv = subprocess.Popen([ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                              "-s", f"{B}x{Hp}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                              "-crf", "14", "-preset", "medium", str(ut)], stdin=subprocess.PIPE)
    skriv.stdin.write(film.tobytes())
    skriv.stdin.close()
    skriv.wait()
    return {"rutor": len(film), "skarv_skillnad": skillnad}


def _vidga(m: np.ndarray, n: int) -> np.ndarray:
    for _ in range(n):
        m2 = m.copy()
        m2[1:] |= m[:-1]; m2[:-1] |= m[1:]; m2[:, 1:] |= m[:, :-1]; m2[:, :-1] |= m[:, 1:]
        m = m2
    return m


def pahittad_yta(bild: np.ndarray, ruta: tuple[int, int, int, int], green: bool = False) -> np.ndarray:
    """Mask för sand (och med green=True: för ljus "green"-yta) inom ruta = (x0, x1, y0, y1).

    Används bara där formkontrollen har visat att AI:n har hittat på bunkrar eller en green
    som inte finns i hålfilen eller den råa filmen."""
    x0, x1, y0, y1 = ruta
    f = bild.astype(np.float32)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    mx, mn = f.max(-1), f.min(-1)
    sat = (mx - mn) / (mx + 1)
    m = (mx > 140) & (sat < 0.34) & (r > b + 4) & (r >= g - 12)          # ljus, blek, varm = sand
    if green:
        L = f.mean(-1)
        ref = np.median(L[y1:y1 + 50, x0:x1])                            # vanlig fairway strax under
        m |= (L > ref + 22) & (g >= r - 4)
    omr = np.zeros_like(m)
    omr[y0:y1, x0:x1] = True
    m &= omr
    e = m.copy()                                                          # bort med enstaka prickar
    e[1:-1, 1:-1] = m[1:-1, 1:-1] & m[:-2, 1:-1] & m[2:, 1:-1] & m[1:-1, :-2] & m[1:-1, 2:]
    m = e
    if green:                                                             # stäng hål ("dammar") i ytan
        for y in range(y0, y1):
            xs = np.nonzero(m[y])[0]
            for p, q in zip(xs[:-1], xs[1:]):
                if 1 < q - p < 45:
                    m[y, p:q] = True
    return _vidga(m, 6 if green else 7) & omr


def sand_lokal(bild: np.ndarray, kontrast: float = 22.0) -> np.ndarray:
    """Små ljusa, bleka fläckar (sand) som sticker ut mot gräset runt omkring. Hittar påhittade
    småbunkrar vid horisonten utan att ta solbelyst fairway eller ljusa stammar."""
    from PIL import ImageFilter
    f = bild.astype(np.float32)
    L = f.mean(-1)
    mx, mn = f.max(-1), f.min(-1)
    sat = (mx - mn) / (mx + 1)
    runt = np.asarray(Image.fromarray(np.clip(L, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(10)),
                      np.float32)
    m = (L > runt + kontrast) & (sat < 0.25) & (mx > 140) & (f[..., 0] >= f[..., 1] - 6)
    e = m.copy()
    e[1:-1, 1:-1] = m[1:-1, 1:-1] & (m[:-2, 1:-1] | m[2:, 1:-1]) & (m[1:-1, :-2] | m[1:-1, 2:])
    return e


def fyll_med_omgivning(bild: np.ndarray, m: np.ndarray, varv: int = 200) -> np.ndarray:
    """Fyller maskade pixlar inifrån kanten med medel av grannarna (gräset runt omkring)."""
    acc = bild.astype(np.float32).copy()
    w = (~m).astype(np.float32)
    acc[m] = 0

    def grannar(x):
        p = np.pad(x, ((1, 1), (1, 1)) + ((0, 0),) * (x.ndim - 2), mode="edge")
        return p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]
    for _ in range(varv):
        s, c = grannar(acc * w[..., None]), grannar(w)
        upd = m & (c > 0)
        acc[upd] = (s / np.maximum(c, 1e-6)[..., None])[upd]
        w = np.where(upd, 1.0, w)
    return acc


def tvatta_bild(bild: np.ndarray, ruta: tuple[int, int, int, int], green: bool = False,
                dampa: bool = False, skydd: np.ndarray | None = None) -> tuple[np.ndarray, int]:
    """Tar bort påhittad sand/green inom ruta. Bara borttagning: inget nytt ritas in.
    dampa=True (v3, horisonten): påhittad sand och ljus "green" fylls inte med en blandning
    (då blir det mörka fläckar av skogen), utan tonas till fairwayns färg strax under i samma
    kolumn; gräsets fina struktur behålls, vita prickar plattas ut. `skydd` (bool-mask) är
    hålfilens riktiga green och bunker i rutan (se `halfilens_ytor`): där rörs ingenting."""
    from PIL import ImageFilter
    if dampa:
        x0, x1, y0, y1 = ruta
        omr = np.zeros(bild.shape[:2], bool)
        omr[y0:y1, x0:x1] = True
        if skydd is not None:
            omr &= ~skydd
        hittad = sand_lokal(bild) & omr
        if green:
            hittad |= pahittad_yta(bild, ruta, True)
        m = _vidga(hittad, 9) & omr                              # med kanten (skuggan) runt
        if not m.any():
            return bild, 0
        f = bild.astype(np.float32)
        lag = np.asarray(Image.fromarray(bild).filter(ImageFilter.GaussianBlur(6)), np.float32)
        detalj = np.clip(f - lag, -4, 4)                         # lite av gräsets struktur, inga konturer kvar
        mal = lag.copy()
        h = m.shape[0]
        for x in np.nonzero(m.any(0))[0]:                        # färgen strax under fläcken, per kolumn
            ys = np.nonzero(m[:, x])[0]
            y1 = ys.max() + 1
            under = f[min(y1 + 3, h - 1):min(y1 + 23, h), x]
            if len(under):
                mal[ys, x] = under.mean(0)
        mal = np.asarray(Image.fromarray(np.clip(mal, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5)),
                         np.float32)
        w = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(7)),
                       np.float32)[..., None] / 255
        ut = f * (1 - w) + (mal + detalj) * w
        return np.clip(ut, 0, 255).astype(np.uint8), int(m.sum())
    m = pahittad_yta(bild, ruta, green)
    if not m.any():
        return bild, 0
    ys, xs = np.nonzero(m)
    Y0, Y1, X0, X1 = max(ys.min() - 14, 0), ys.max() + 15, max(xs.min() - 14, 0), xs.max() + 15
    sub, ms = bild[Y0:Y1, X0:X1], m[Y0:Y1, X0:X1]
    f = fyll_med_omgivning(sub, ms)
    f[ms] += np.random.default_rng(1).normal(0, 4, f[ms].shape)          # lite korn så det inte blir slätt
    w = np.array(Image.fromarray((ms * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), np.float32)[..., None] / 255
    ut = bild.copy()
    ut[Y0:Y1, X0:X1] = np.clip(sub * (1 - w) + f * w, 0, 255).astype(np.uint8)
    return ut, int(m.sum())


def halfilens_ytor(hole: Hole, proj: Projektion, i: int, marginal: int = 25, green: bool = False) -> np.ndarray:
    """Mask (h, b) över hålfilens bunkrar/vatten (och med green=True greenen) i ruta i, vidgad
    `marginal` px. Skyddar de riktiga ytorna när påhittad sand tvättas bort runt omkring."""
    mk = Image.new("L", (proj.bredd, proj.hojd_px), 0)
    d = ImageDraw.Draw(mk)
    for poly in ([hole.green] if green else []) + [h.polygon for h in hole.hazards]:
        x, y, fram = proj.px(i, [p[0] for p in poly], [p[1] for p in poly])
        if fram.all():
            d.polygon(list(zip(x.tolist(), y.tolist())), fill=255)
    return _vidga(np.asarray(mk) > 0, marginal)


def ta_bort_stig(bild: np.ndarray, linjer: list) -> np.ndarray:
    """Tar bort en påhittad stig/grusgång i en stillbild (t.ex. en AI-startbild). `linjer` är
    [[bredd_px, skift_px, [[x, y], ...]], ...]: stigens mittlinje i bilden, ritad för hand efter
    kontroll mot hålfilen och den råa filmen. Med skift ≠ 0 fylls stigen med ruffen bredvid
    (pixlarna skift px åt sidan, negativt = från vänster), annars med omgivningens medel.
    Bara borttagning: inget nytt ritas in (Eric 2026-10-25: ingen grusgång, det är ruff)."""
    from PIL import ImageFilter
    ut = bild.astype(np.float32).copy()
    for bredd, skift, pts in linjer:
        mk = Image.new("L", (bild.shape[1], bild.shape[0]), 0)
        d = ImageDraw.Draw(mk)
        d.line([tuple(p) for p in pts], fill=255, width=int(bredd))
        for x, y in pts:
            d.ellipse([x - bredd / 2, y - bredd / 2, x + bredd / 2, y + bredd / 2], fill=255)
        m = np.asarray(mk) > 0
        if skift:
            f = np.roll(ut, -int(skift), axis=1)
        else:
            f = fyll_med_omgivning(ut, m, 300)
            f[m] += np.random.default_rng(1).normal(0, 5, f[m].shape)
        w = np.asarray(mk.filter(ImageFilter.GaussianBlur(3)), np.float32)[..., None] / 255
        ut = ut * (1 - w) + f * w
    return np.clip(ut, 0, 255).astype(np.uint8)


def tvatta_film(film: Path, ut: Path, rutor: tuple[int, int], ruta: tuple[int, int, int, int], green: bool = False,
                fps: int | None = None, B: int = 1280, Hp: int = 720, dampa: bool = False, skydd=None) -> int:
    """tvatta_bild på rutorna a–b (filmens egna rutnummer) i en film; resten orört.
    skydd(i, fps) ger en mask med hålfilens riktiga ytor i klippets ruta i (eller None)."""
    r = subprocess.run([ffmpeg_bin(), "-loglevel", "error", "-i", str(film), "-vf", f"scale={B}:{Hp}",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, check=True)
    bilder = np.frombuffer(r.stdout, np.uint8).reshape(-1, Hp, B, 3).copy()
    if fps is None:
        p = subprocess.run([ffmpeg_bin().replace("ffmpeg", "ffprobe"), "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(film)],
                           stdout=subprocess.PIPE, text=True)
        try:
            t, n = p.stdout.strip().split("/")
            fps = round(int(t) / int(n))
        except ValueError:
            fps = 24
    antal = 0
    for i in range(rutor[0], min(rutor[1], len(bilder))):
        bilder[i], k = tvatta_bild(bilder[i], ruta, green, dampa, skydd(i, fps) if skydd else None)
        antal += k
    skriv = subprocess.Popen([ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                              "-s", f"{B}x{Hp}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                              "-crf", "14", "-preset", "medium", str(ut)], stdin=subprocess.PIPE)
    skriv.stdin.write(bilder.tobytes())
    skriv.stdin.close()
    skriv.wait()
    return antal


def nyckelark(film: Path, rutor: list[int], ut: Path, kolumner: int = 4, bredd: int = 480, fps: int = 24) -> Path:
    """Rutor ur en film på ett ark, med tid under varje bild."""
    from PIL import ImageFont
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="nyckelark-"))
    bilder = las_rutor(film, rutor, tmp)
    h = round(bredd * 9 / 16)
    rader = math.ceil(len(rutor) / kolumner)
    ark = Image.new("RGB", (kolumner * bredd, rader * (h + 26)), (255, 255, 255))
    d = ImageDraw.Draw(ark)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    for j, r in enumerate(rutor):
        x, y = (j % kolumner) * bredd, (j // kolumner) * (h + 26)
        ark.paste(Image.open(bilder[r]).convert("RGB").resize((bredd, h)), (x, y))
        d.text((x + 6, y + h + 4), f"{r / fps:.1f} s", fill=(0, 0, 0), font=font)
    ark.save(ut, quality=88)
    return ut


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


def _delar(text: str) -> list[tuple[int, int]]:
    return [tuple(int(x) for x in d.split("-")) for d in text.split(",") if d]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="flygfilm_kontroll")
    p.add_argument("steg", choices=["kameror", "slutbild", "konturer", "animatic", "hopklipp", "omproj", "tvatt", "stig", "rarutor"])
    p.add_argument("hal")
    p.add_argument("--data")
    p.add_argument("--sek", type=float, default=12.0)
    p.add_argument("--slut", type=float, default=4.0)
    p.add_argument("--kam")
    p.add_argument("--malad")
    p.add_argument("--film")
    p.add_argument("--rutor", default="")
    p.add_argument("--forlopp", choices=["rak", "oversikt"], default="rak")
    p.add_argument("--tee", default=None)
    p.add_argument("--hojd", type=float, default=5.0, help="kameror: höjd över marken (samma som flygfilm --hojd)")
    p.add_argument("--blick", type=float, default=60.0, help="kameror: blick framåt i m (samma som flygfilm --blick)")
    p.add_argument("--start", type=int, default=0, help="filmen börjar vid den här rutan i den råa filmen (klipp)")
    p.add_argument("--klipp", default="", help="hopklipp: AI-klippen i ordning, kommaseparerade")
    p.add_argument("--delar", default="", help="hopklipp/omproj: egna rutintervall, t.ex. 55-79,79-175")
    p.add_argument("--bild", help="omproj: AI-tvättade rutor som ruta:fil, t.ex. 55:a.png,79:b.png")
    p.add_argument("--ren", action="store_true", help="animatic utan text i bilden (färdig film)")
    p.add_argument("--omrade", default="420,1020,60,340", help="tvatt: x0,x1,y0,y1 där påhittad sand får tas bort")
    p.add_argument("--green", action="store_true", help="tvatt: ta också bort påhittad ljus green-yta")
    p.add_argument("--dampa", action="store_true", help="tvatt: tona ner påhittad sand/green till fairwayn under")
    p.add_argument("--skydda", type=int, default=0,
                   help="tvatt: rör inte hålfilens green/bunker (+ så många px); kräver --kam och --start")
    p.add_argument("--tona", type=int, default=6, help="hopklipp: rutor toning vid skarvarna (0 = rent klipp)")
    p.add_argument("--bakgrund", default="klubb",
                   help="animatic/slutbild: färg runt hålbilden, #rrggbb, 'klubb' (klubbens mörka) eller 'papper'")
    p.add_argument("--sudda", default="", help="rarutor: JSON-fil [[bredd_m, [[e,n],...]], ...] att sudda i ortofotot")
    p.add_argument("--linjer", default="", help="stig: JSON [[bredd, skift, [[x,y],...]], ...] i bildpunkter")
    p.add_argument("--ut", required=True)
    a = p.parse_args(argv)
    if a.steg == "stig":
        bild = np.asarray(Image.open(a.film).convert("RGB"))
        Image.fromarray(ta_bort_stig(bild, json.loads(a.linjer))).save(a.ut)
        return 0
    if a.steg == "tvatt":
        (r0, r1), = _delar(a.delar)
        omr = tuple(int(v) for v in a.omrade.split(","))
        skydd = None
        if a.skydda:
            hole, proj = Hole.from_yaml(a.hal), Projektion(json.loads(Path(a.kam).read_text()))
            sista = len(proj.kams) - 1
            skydd = lambda i, fps: halfilens_ytor(hole, proj, min(sista, a.start + round(i * 24 / fps)), a.skydda)  # noqa: E731
        print("tvättade pixlar:", tvatta_film(Path(a.film), Path(a.ut), (r0, r1), omr, a.green,
                                                    dampa=a.dampa, skydd=skydd))
        return 0
    hole = Hole.from_yaml(a.hal)
    hp = Path(a.hal)
    bakgrund = (klubbens_bakgrund(hp) if a.bakgrund == "klubb" else UTANFOR if a.bakgrund == "papper"
                else hexfarg(a.bakgrund))
    data_dir = Path(a.data) if a.data else Path("data") / hp.parent.name
    if a.steg == "kameror":
        Path(a.ut).write_text(json.dumps(kameror(hole, data_dir, a.sek, a.slut, a.forlopp, a.tee, a.hojd, a.blick)))
        return 0
    kd = json.loads(Path(a.kam).read_text())
    proj = Projektion(kd)
    if a.steg == "animatic":
        malad = Path(a.malad) if a.malad else hp.parent / "halbilder" / f"hal-{hole.number:02d}-malad.webp"
        orto = sorted((data_dir / "orto").glob("*.tif"))[0]
        r = animatic(hole, proj, kd["info"]["hojd_over_mark_m"], MaladKarta(hole, orto, malad, bakgrund), Path(a.film), Path(a.ut),
                     etikett=not a.ren)
        n = r["rutor"]
        nyckelark(Path(a.ut), [round(j * (n - 1) / 15) for j in range(16)], Path(a.ut).with_suffix(".jpg"))
        for j, (s0, s1) in enumerate(r["delar"], 1):
            print(f"AI-del {j}: ruta {s0}–{s1} ({s0 / 24:.2f}–{s1 / 24:.2f} s, {(s1 - s0) / 24:.2f} s)")
        return 0
    if a.steg == "hopklipp":
        klipp = [Path(k) for k in a.klipp.split(",") if k]
        delar = _delar(a.delar) or ai_delar(kd["info"]["hojd_over_mark_m"])
        if len(klipp) != len(delar):
            raise SystemExit(f"{len(delar)} AI-delar men {len(klipp)} klipp")
        print(hopklipp(Path(a.film), klipp, delar, Path(a.ut), tona=a.tona))
        return 0
    if a.steg == "rarutor":
        from .flygfilm import rendera_rutor, sudda_linjer
        scen = _scen(hole, data_dir)
        if a.sudda:
            print("suddade pixlar:", sudda_linjer(scen, json.loads(Path(a.sudda).read_text())))
        (r0, r1), = _delar(a.delar)
        rendera_rutor(scen, proj.kams, (r0, r1), Path(a.ut))
        return 0
    if a.steg == "omproj":
        (k0, k1), = _delar(a.delar)
        bilder = [(int(d.split(":", 1)[0]), Path(d.split(":", 1)[1])) for d in a.bild.split(",")]
        omproj_film(bilder, proj, k0, k1, Path(a.ut))
        return 0
    if a.steg == "slutbild":
        malad = Path(a.malad) if a.malad else hp.parent / "halbilder" / f"hal-{hole.number:02d}-malad.webp"
        orto = sorted((data_dir / "orto").glob("*.tif"))[0]
        slutbild(hole, proj, orto, malad, bakgrund=bakgrund).save(a.ut)
        return 0
    ut = Path(a.ut)
    rutor = [int(r) for r in a.rutor.split(",") if r] or [0, len(proj.kams) - 1]
    for r, f in las_rutor(Path(a.film), [r - a.start for r in rutor], ut / "rutor").items():
        i = min(r + a.start, len(proj.kams) - 1)
        rita_konturer(Image.open(f), proj, i, hole).save(ut / f"kontur-{i:04d}.jpg", quality=90)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
