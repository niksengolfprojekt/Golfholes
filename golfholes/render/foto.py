"""Fotostil: hålet ur Lantmäteriets ortofoto, utklippt längs spelkorridoren.

Allt som syns är det riktiga fotot – formen ändras aldrig. Det som görs är bara
stil: kanten tonas ut mot papperet, skuggorna lyfts, lövträden får höstfärg,
golfare och vagnar på fairway och green retuscheras bort, och koden ritar flagga
och avståndsprickar ovanpå. Hålet vrids så att tee hamnar nederst.

    python -m golfholes fotobild klubbar/glasriket/hal-03.yaml
    → klubbar/glasriket/halbilder/hal-03-foto.webp  (RGBA, genomskinlig bakgrund)
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..hole import Hole
from ..lantmateriet import read_window
from ..utkast import Fonster, klassa, matt, medel

KANT_FULL_M = 24.0   # så här långt från spelytan syns fotot fullt
KANT_TONA_M = 26.0   # ... och tonas sedan ut över så här många meter
PRICKAR = ((100, (214, 40, 57)), (150, (247, 197, 24)))  # röd 100 m, gul 150 m till greenens mitt


def orto_for(club_data: Path) -> Path:
    logg = json.loads((club_data / "lantmateriet.json").read_text(encoding="utf-8"))
    return Path(next(f["fil"] for f in logg["filer"] if f["katalog"] == "orto"))


def _rastrera(polys, f: Fonster, shape, bredd: int = 0) -> np.ndarray:
    im = Image.new("L", (shape[1], shape[0]), 0)
    d = ImageDraw.Draw(im)
    for p in polys:
        xy = [((e - f.e0) / f.res, (f.n0 - n) / f.res) for e, n in p]
        if bredd:
            d.line(xy, fill=255, width=bredd, joint="curve")
            for x, y in (xy[0], xy[-1]):
                d.ellipse((x - bredd / 2, y - bredd / 2, x + bredd / 2, y + bredd / 2), fill=255)
        elif len(xy) >= 3:
            d.polygon(xy, fill=255)
    return np.array(im) > 0


def _mjuk(x: np.ndarray, r: int) -> np.ndarray:
    """Tre boxfilter i rad ≈ gaussisk oskärpa."""
    for _ in range(3):
        x = medel(x, r)
    return x


def _tyngdpunkt(poly) -> tuple[float, float]:
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        c = x0 * y1 - x1 * y0
        a += c
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    return (cx / (3 * a), cy / (3 * a)) if a else poly[0]


def _punkt_fore_green(linje, mitt, meter: float):
    """Punkten på spellinjen som ligger `meter` före greenens mitt (räknat bakåt längs linjen)."""
    # projicera greenens mitt på linjen
    bast, lang, gick = (1e18, 0.0), 0.0, 0.0
    for a, b in zip(linje, linje[1:]):
        L = math.dist(a, b)
        t = max(0.0, min(1.0, ((mitt[0] - a[0]) * (b[0] - a[0]) + (mitt[1] - a[1]) * (b[1] - a[1])) / (L * L or 1)))
        q = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        if math.dist(q, mitt) < bast[0]:
            bast = (math.dist(q, mitt), gick + t * L)
        gick += L
    mal = bast[1] - meter
    if mal <= 0:
        return None
    gick = 0.0
    for a, b in zip(linje, linje[1:]):
        L = math.dist(a, b)
        if gick + L >= mal:
            t = (mal - gick) / L
            return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        gick += L
    return None


def _ramp(L: np.ndarray, stopp) -> np.ndarray:
    """Luminans 0–1 → färg längs en skala (mörk → ljus). Behåller fotots ljus och skugga."""
    xs = np.linspace(0, 1, len(stopp))
    return np.stack([np.interp(L, xs, [c[i] for c in stopp]) for i in range(3)], -1) / 255.0


GRAN = [(22, 38, 26), (44, 72, 40), (86, 112, 58), (150, 160, 96)]
LOV = [(70, 64, 24), (168, 146, 44), (232, 204, 84), (250, 238, 168)]


def _host(rgb: np.ndarray, mt: dict, skog: np.ndarray, gras: np.ndarray, klippt: np.ndarray) -> np.ndarray:
    """Färgsättning: lyfta skuggor, lövträd i guld, granar i djup grönt, friskt gräs
    där klippta ytor är ljusast. Bara färg – varje träd står där det står på fotot."""
    x = np.clip(rgb / 255.0, 0, 1)
    lum = x @ np.array([0.299, 0.587, 0.114])
    # skuggorna i ett julifoto är hårda – lyft dem utan att platta till högdagrarna
    lyft = np.clip(1 - lum / 0.4, 0, 1)[..., None] * 0.22
    x = x + lyft * (1 - x)
    # löv eller barr: lövträd reflekterar mer nära-IR i förhållande till grönt
    lov = medel(mt["N"] / (mt["G"] + 1), 4)
    grans = np.percentile(lov[skog], 40) if skog.any() else 0
    sk = _mjuk(skog.astype(np.float32), 2)[..., None]
    lovtrad = np.clip(_mjuk((skog & (lov > grans)).astype(np.float32), 6) * 1.3, 0, 1)[..., None]
    L = np.clip((lum - 0.04) / 0.40, 0, 1) ** 0.7
    trad = _ramp(L, GRAN) * (1 - 0.92 * lovtrad) + _ramp(L, LOV) * 0.92 * lovtrad
    x = x * (1 - 0.92 * sk) + trad * 0.92 * sk
    # gräs: mer mättat och friskt, klippt gräs ljusast så att fairway läses direkt
    g = _mjuk(gras.astype(np.float32), 2)[..., None]
    k = _mjuk(klippt.astype(np.float32), 3)[..., None]
    lg = x.mean(-1, keepdims=True)
    frisk = np.clip(lg + (x - lg) * 1.6, 0, 1) * np.array([0.93, 1.07, 0.80])
    frisk = frisk * (0.90 + 0.20 * k)
    x = x * (1 - 0.8 * g) + np.clip(frisk, 0, 1) * 0.8 * g
    # lätt S-kurva och varm ton
    x = np.clip(x, 0, 1)
    x = x + 0.12 * (x - x ** 2) * (2 * x - 1) * -1
    x = x * np.array([1.03, 1.01, 0.93])
    return np.clip(x * 255, 0, 255)


def _skarp(rgb: np.ndarray, yta: np.ndarray, res: float) -> np.ndarray:
    """Lyfter klippmönstret (ränderna) på fairway och green."""
    slat = np.stack([_mjuk(rgb[..., i], max(2, int(1.5 / res))) for i in range(3)], -1)
    m = _mjuk(yta.astype(np.float32), 2)[..., None]
    return np.clip(rgb + (rgb - slat) * 0.7 * m, 0, 255)


def _utan_skugga(rgb: np.ndarray, yta: np.ndarray, res: float) -> np.ndarray:
    """Trädskuggor över fairway och green: jämna ut ljuset inom ytan (skuggan är ljus, inte form)."""
    if not yta.any():
        return rgb
    lum = rgb.mean(-1)
    r = max(3, int(2.5 / res))
    vikt = _mjuk(yta.astype(np.float32), r) + 1e-3
    lokal = _mjuk(lum * yta, r) / vikt
    mal = float(np.median(lum[yta]))
    skala = np.clip(mal / np.maximum(lokal, 1), 1.0, 2.6)
    m = _mjuk(yta.astype(np.float32), 2)
    return np.clip(rgb * (1 + (skala - 1) * m)[..., None], 0, 255)


def _retusch(rgb: np.ndarray, yta: np.ndarray, res: float) -> np.ndarray:
    """Tar bort små mörka eller ljusa prickar (golfare, vagnar, deras skuggor) på klippta ytor."""
    r = max(3, int(1.2 / res))
    slat = np.stack([_mjuk(rgb[..., i], r) for i in range(3)], -1)
    avvik = np.abs(rgb - slat).sum(-1)
    inne = medel(yta.astype(np.float32), int(2 / res)) > 0.999   # inte kanten mot ruffen
    flack = (avvik > 45) & inne
    flack = medel(flack.astype(np.float32), r) > 0.02   # ta med kanten runt pricken
    flack &= inne
    ut = rgb.copy()
    ut[flack] = slat[flack]
    return ut


def fotobild(hole: Hole, orto: Path, ut: Path, hojd_px: int = 2400, markeringar: bool = True) -> Path:
    rot, px = fotounderlag(hole, orto, hojd_px)
    if markeringar:
        rita_spel(rot, hole, px)
    return _spara(rot, ut)


def fotounderlag(hole: Hole, orto: Path, hojd_px: int = 2400):
    """Hålet ur ortofotot, vridet så att bakre tee är nederst. Returnerar (RGBA-bild,
    px) där px(e, n) ger bildkoordinaten för en SWEREF-punkt."""
    if not hole.green:
        raise ValueError("Hålfilen saknar green – kör utkast först.")
    bak = max(hole.tees, key=lambda t: t.length_m or 0)
    alla = [p for p in hole.centerline] + hole.green + [t.point for t in hole.tees]
    for fw in hole.fairways:
        alla += fw
    m = KANT_FULL_M + KANT_TONA_M * 1.5 + 10
    bbox = (min(p[0] for p in alla) - m, min(p[1] for p in alla) - m,
            max(p[0] for p in alla) + m, max(p[1] for p in alla) + m)
    a, e0, n0, res = read_window(orto, bbox)
    f = Fonster(a.astype(np.float32), e0, n0, res)
    shape = a.shape[:2]
    mt = matt(f)
    kl = klassa(mt)

    fairway = _rastrera(hole.fairways, f, shape)
    green = _rastrera([hole.green], f, shape)
    bunker = _rastrera([h.polygon for h in hole.hazards if h.kind == "bunker"], f, shape)
    spel = fairway | green | bunker
    spel |= _rastrera([hole.centerline], f, shape, bredd=int(12 / res))
    for t in hole.tees:
        spel |= _rastrera([[t.point, t.point]], f, shape, bredd=int(14 / res))

    # synlighet: fullt nära spelytan, tonar ut längre bort
    rf = int(KANT_FULL_M / res / 3)
    nara = _mjuk(spel.astype(np.float32), rf) > 0.01
    alfa = _mjuk(nara.astype(np.float32), int(KANT_TONA_M / res / 3))
    alfa = np.clip((alfa - 0.08) / 0.62, 0, 1) ** 1.3
    # aldrig ända ut till fönstrets kant, så att inga raka snitt syns
    yy, xx = np.mgrid[: shape[0], : shape[1]]
    kant = np.minimum.reduce([yy, xx, shape[0] - 1 - yy, shape[1] - 1 - xx]) * res
    alfa *= np.clip(kant / 8.0, 0, 1)
    # bara det här hålet: tona bort det som ligger bakom bakre tee och bortom greenen
    mitt0 = _tyngdpunkt(hole.green)
    ax = np.array([mitt0[0] - bak.point[0], mitt0[1] - bak.point[1]])
    L = float(np.hypot(*ax))
    ax /= L
    E = f.e0 + (xx + 0.5) * res
    N = f.n0 - (yy + 0.5) * res
    langs = (E - bak.point[0]) * ax[0] + (N - bak.point[1]) * ax[1]
    alfa *= np.clip((langs + 22) / 26, 0, 1) * np.clip((L + 34 - langs) / 22, 0, 1)
    alfa = _mjuk(alfa, int(4 / res))  # mjuk, organisk kant – inga raka snitt
    alfa = np.clip((alfa - 0.04) / 0.96, 0, 1)

    gras = ~kl["skog"] & ~kl["vatten"] & ~kl["bunker"]
    rgb = _utan_skugga(f.rgbn[..., :3], green, res)
    rgb = _utan_skugga(rgb, fairway & ~bunker, res)
    rgb = _retusch(rgb, (fairway | green) & ~bunker, res)
    rgb = _skarp(rgb, fairway | green, res)
    rgb = _host(rgb, mt, kl["skog"], gras, fairway | green)
    rgba = np.dstack([rgb, alfa * 255]).astype(np.uint8)
    im = Image.fromarray(rgba, "RGBA")

    # vrid så att bakre tee hamnar nederst och greenen överst
    mitt = _tyngdpunkt(hole.green)
    phi = math.degrees(math.atan2(mitt[1] - bak.point[1], mitt[0] - bak.point[0]))
    vinkel = 90 - phi
    W, H = im.size
    rot = im.rotate(vinkel, resample=Image.BICUBIC, expand=True)
    W2, H2 = rot.size

    def till_rot(e, n):
        x, y = (e - f.e0) / res - W / 2, (f.n0 - n) / res - H / 2
        # moturs vridning i bilden (y nedåt)
        v = math.radians(vinkel)
        return (x * math.cos(v) + y * math.sin(v) + W2 / 2, -x * math.sin(v) + y * math.cos(v) + H2 / 2)

    box = rot.getchannel("A").point(lambda v: 255 if v > 6 else 0).getbbox()
    rot = rot.crop(box)
    k = hojd_px / rot.height
    rot = rot.resize((round(rot.width * k), hojd_px), Image.LANCZOS)

    def px(e, n):
        x, y = till_rot(e, n)
        return ((x - box[0]) * k, (y - box[1]) * k)

    return rot, px


def rita_spel(rot: Image.Image, hole: Hole, px) -> None:
    """Prickar (100/150 m kvar till greenens mitt) och flagga – alltid ritade av koden."""
    d = ImageDraw.Draw(rot)
    s = rot.height / 1000  # storlek på symboler oberoende av upplösning
    mitt = _tyngdpunkt(hole.green)
    for meter, farg in PRICKAR:
        p = _punkt_fore_green(hole.centerline, mitt, meter)
        if p:
            x, y = px(*p)
            r = 9 * s
            d.ellipse((x - r, y - r, x + r, y + r), fill=farg + (255,), outline=(255, 255, 255, 230), width=max(1, int(1.6 * s)))
    # flagga i greenens mitt
    x, y = px(*mitt)
    stang = 30 * s
    d.line((x, y, x, y - stang), fill=(30, 30, 30, 255), width=max(2, int(2 * s)))
    d.polygon([(x, y - stang), (x + 17 * s, y - stang + 5 * s), (x, y - stang + 11 * s)], fill=(247, 197, 24, 255))
    d.ellipse((x - 2.5 * s, y - 1.5 * s, x + 2.5 * s, y + 1.5 * s), fill=(30, 30, 30, 255))


def rita_konturer(rot: Image.Image, hole: Hole, px) -> Image.Image:
    """Kontrollbild: hålfilens fairway, green, bunkrar och vatten som tunna linjer ovanpå
    bilden. Används för att se att en AI-målning inte har flyttat något."""
    ut = rot.convert("RGBA").copy()
    d = ImageDraw.Draw(ut)
    w = max(2, rot.height // 600)
    lager = [(fw, (255, 0, 200)) for fw in hole.fairways] + [(hole.green, (0, 160, 255))]
    lager += [(h.polygon, (255, 255, 255) if h.kind == "bunker" else (0, 60, 255)) for h in hole.hazards]
    for poly, farg in lager:
        pts = [px(*p) for p in poly]
        if len(pts) > 2:
            d.line(pts + [pts[0]], fill=farg + (255,), width=w)
    linje = [px(*p) for p in hole.centerline]
    d.line(linje, fill=(255, 200, 0, 255), width=w)
    return ut


def _spara(rot: Image.Image, ut: Path) -> Path:
    ut = Path(ut)
    ut.parent.mkdir(parents=True, exist_ok=True)
    if ut.suffix.lower() == ".webp":
        rot.save(ut, quality=90, method=6)
    elif ut.suffix.lower() in (".jpg", ".jpeg"):
        bg = Image.new("RGB", rot.size, (250, 244, 236))
        bg.paste(rot, mask=rot.getchannel("A") if rot.mode == "RGBA" else None)
        bg.save(ut, quality=92)
    else:
        rot.save(ut)
    return ut


def ai_underlag(hole: Hole, orto: Path, ut: Path, hojd_px: int = 2400, bredd: int = 1350) -> Path:
    """Fotounderlaget utan prickar och flagga, centrerat på krämfärgad duk i 9:16
    (1350 × 2400) – det AI:n får måla om. Placeringen följer AI_SKALA så att
    AI-bilden kan läggas tillbaka exakt med ai_tillbaka."""
    rot, _ = fotounderlag(hole, orto, round(hojd_px * AI_SKALA))
    duk = Image.new("RGB", (bredd, hojd_px), (250, 244, 236))
    duk.paste(rot, ((bredd - rot.width) // 2, (hojd_px - rot.height) // 2), rot)
    return _spara(duk, ut)


AI_SKALA = 0.95


def ai_tillbaka(hole: Hole, orto: Path, ai_bild: Path, ut: Path, kontroll: Path | None = None,
                hojd_px: int = 2400) -> Path:
    """Lägger AI-målningen på hålets exakta form: duken skalas tillbaka, hålet klipps
    ut med fotounderlagets egen siluett (alfa) och prickar och flagga ritas av koden
    på hålfilens koordinater. Kontrollbilden visar hålfilens konturer ovanpå målningen
    – ligger de inte på målningens kanter har AI:n flyttat något och bilden får inte
    användas."""
    rot, px = fotounderlag(hole, orto, hojd_px)
    inre_h = round(hojd_px * AI_SKALA)
    inre_w = round(rot.width * AI_SKALA)
    ai = Image.open(ai_bild).convert("RGB")
    duk_w = round(ai.height and hojd_px * ai.width / ai.height)
    ai = ai.resize((duk_w, hojd_px), Image.LANCZOS)
    x0, y0 = (duk_w - inre_w) // 2, (hojd_px - inre_h) // 2
    malad = ai.crop((x0, y0, x0 + inre_w, y0 + inre_h)).resize(rot.size, Image.LANCZOS).convert("RGBA")
    malad.putalpha(rot.getchannel("A"))
    if kontroll:
        _spara(rita_konturer(malad, hole, px), kontroll)
    rita_spel(malad, hole, px)
    return _spara(malad, ut)
