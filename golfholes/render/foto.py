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

from .. import geometry as g
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


def _mitt_i_fairway(linje, p, fairways, max_m: float = 40.0):
    """Flyttar en avståndspunkt i sidled (vinkelrätt mot spellinjen) till mitten av fairway där
    den ligger, så pricken hamnar mitt i fairway och inte vid kanten (Eric 2026-10-29).
    Avståndet längs linjen är detsamma. Ingen fairway inom `max_m` → punkten som den var."""
    if not fairways:
        return p
    bast = None
    for a, b in zip(linje, linje[1:]):
        L = math.dist(a, b) or 1.0
        t = max(0.0, min(1.0, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / (L * L)))
        q = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        if bast is None or math.dist(q, p) < bast[0]:
            bast = (math.dist(q, p), ((b[0] - a[0]) / L, (b[1] - a[1]) / L))
    nx, ny = -bast[1][1], bast[1][0]
    steg = [i * 0.5 for i in range(int(-max_m * 2), int(max_m * 2) + 1)]
    inne = [k for k in steg if any(g.contains(f, (p[0] + k * nx, p[1] + k * ny)) for f in fairways)]
    if not inne:
        return p
    # den sammanhängande biten av fairway som ligger närmast linjen
    bitar, bit = [], [inne[0]]
    for k in inne[1:]:
        if k - bit[-1] > 0.6:
            bitar.append(bit)
            bit = []
        bit.append(k)
    bitar.append(bit)
    bit = min(bitar, key=lambda b: 0 if b[0] <= 0 <= b[-1] else min(abs(b[0]), abs(b[-1])))
    k = (bit[0] + bit[-1]) / 2
    return (p[0] + k * nx, p[1] + k * ny)


def avstandspunkt(hole: Hole, mitt, meter: float):
    """Punkten `meter` före greenens mitt längs spellinjen, mitt i fairway."""
    p = _punkt_fore_green(hole.centerline, mitt, meter)
    return _mitt_i_fairway(hole.centerline, p, hole.fairways) if p else None


def _ramp(L: np.ndarray, stopp) -> np.ndarray:
    """Luminans 0–1 → färg längs en skala (mörk → ljus). Behåller fotots ljus och skugga."""
    xs = np.linspace(0, 1, len(stopp))
    return np.stack([np.interp(L, xs, [c[i] for c in stopp]) for i in range(3)], -1) / 255.0


LOV_GRANS = 1.8  # nära-IR/grönt; Glasriket: hål 3 ~25 % av skogen över, granhålet 14 ~15 %
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
    # fast gräns (inte andel per hål): ett granhål som 14 ska inte bli gult för att
    # hålet råkar sakna björk. Solbelysta lövkronor har högst kvot.
    sk = _mjuk(skog.astype(np.float32), 2)[..., None]
    lovtrad = np.clip(_mjuk((skog & (lov > LOV_GRANS)).astype(np.float32), 3) * 1.3, 0, 1)[..., None]
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


def _sand(rgb: np.ndarray, bunker: np.ndarray, res: float) -> np.ndarray:
    """Bunkrar ur hålfilen som ligger i skugga syns inte i ortofotot (hål 3 på Glasriket):
    ge dem sandens ljusa ton, mjukt i kanten. Formen kommer från hålfilen, aldrig från AI:n."""
    if not bunker.any():
        return rgb
    sand = np.array([214, 196, 160], dtype=np.float32)
    lum = rgb.mean(-1, keepdims=True)
    struktur = (lum - _mjuk(lum[..., 0], max(2, int(1 / res)))[..., None]) * 0.5
    m = _mjuk(bunker.astype(np.float32), max(1, int(0.4 / res)))[..., None]
    m *= np.clip((200 - lum) / 60, 0, 1)   # ljus sand i fotot lämnas orörd
    return np.clip(rgb * (1 - m) + (sand + struktur) * m, 0, 255)


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


def fotobild(hole: Hole, orto: Path, ut: Path, hojd_px: int = 2400, markeringar: bool = True,
             flagga: dict | None = None) -> Path:
    rot, px = fotounderlag(hole, orto, hojd_px)
    if markeringar:
        rita_spel(rot, hole, px, flagga)
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
    # dammar och bäckar som hålfilen tar med syns alltid (hål 5: dammen 45 m från linjen)
    vatten = _rastrera([h.polygon for h in hole.hazards if h.kind == "water"], f, shape)
    if vatten.sum() * res ** 2 >= 100:
        spel |= vatten
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
    # bildgräns åt sidan (grannhålets green ska inte med): mjuk övergång på 10 m
    sida = (N - bak.point[1]) * ax[0] - (E - bak.point[0]) * ax[1]  # > 0 = vänster om linjen
    if "vanster" in hole.bildgrans_m:
        alfa *= np.clip((hole.bildgrans_m["vanster"] + 5 - sida) / 10, 0, 1)
    if "hoger" in hole.bildgrans_m:
        alfa *= np.clip((hole.bildgrans_m["hoger"] + 5 + sida) / 10, 0, 1)
    alfa = _mjuk(alfa, int(4 / res))  # mjuk, organisk kant – inga raka snitt
    alfa = np.clip((alfa - 0.04) / 0.96, 0, 1)

    gras = ~kl["skog"] & ~kl["vatten"] & ~kl["bunker"]
    rgb = _utan_skugga(f.rgbn[..., :3], green, res)
    rgb = _utan_skugga(rgb, fairway & ~bunker, res)
    rgb = _sand(rgb, bunker, res)
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


def greenytans_mitt(hole: Hole, res: float = 0.1) -> tuple[float, float]:
    """Mitten av puttytan: medelpunkten av greenpolygonens yta (rastrerad, så att en polygon som
    korsar sig själv inte ger en tyngdpunkt ute i kanten – Glasriket hål 7 och 15) minus
    bunkrar som polygonen råkar täcka."""
    G = hole.green
    e0, n1 = min(p[0] for p in G), max(p[1] for p in G)
    W = int((max(p[0] for p in G) - e0) / res) + 2
    H = int((n1 - min(p[1] for p in G)) / res) + 2
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    d.polygon([((e - e0) / res, (n1 - n) / res) for e, n in G], fill=1)
    for h in hole.hazards:
        if h.kind == "bunker" and len(h.polygon) >= 3:
            d.polygon([((e - e0) / res, (n1 - n) / res) for e, n in h.polygon], fill=0)
    ys, xs = np.nonzero(np.asarray(m))
    if not len(xs):
        return _tyngdpunkt(G)
    return (e0 + (xs.mean() + 0.5) * res, n1 - (ys.mean() + 0.5) * res)


def flaggpunkt(hole: Hole) -> tuple[float, float]:
    """Där flaggan står: hålfilens `flagga_punkt` om den finns (kontrollerad mot ortofotot),
    annars mitten av puttytan (greenytans_mitt)."""
    return hole.flagga_punkt or greenytans_mitt(hole)


def flaggstil(klubbmapp: Path | None) -> dict | None:
    """Klubbens egen flagga ur klubb.yaml: `flagga: {logga: profil/sigill-vit.png, farg: "#1D4756"}`.
    Loggan ska vara i en färg (ljus) med genomskinlig bakgrund. Saknas fältet: None (T-flaggan)."""
    if klubbmapp is None:
        return None
    f = Path(klubbmapp) / "klubb.yaml"
    if not f.exists():
        return None
    import yaml

    d = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("flagga") or {}
    if not d.get("logga") or not d.get("farg"):
        return None
    logga = Path(klubbmapp) / d["logga"]
    if not logga.exists():
        raise FileNotFoundError(f"Flaggans logga finns inte: {logga}")
    farg = d["farg"].lstrip("#")
    return {"logga": logga, "farg": tuple(int(farg[i:i + 2], 16) for i in (0, 2, 4))}


def rita_prickar(rot: Image.Image, hole: Hole, px) -> None:
    """Prickar 100/150 m kvar till greenens mitt (par 3: inga)."""
    d = ImageDraw.Draw(rot)
    s = rot.height / 1000  # storlek på symboler oberoende av upplösning
    mitt = _tyngdpunkt(hole.green)
    for meter, farg in ([] if hole.par == 3 else PRICKAR):  # par 3: slås mot green, inga prickar
        p = avstandspunkt(hole, mitt, meter)
        if p:
            x, y = px(*p)
            r = 9 * s
            d.ellipse((x - r, y - r, x + r, y + r), fill=farg + (255,), outline=(255, 255, 255, 230), width=max(1, int(1.6 * s)))


def rita_flagga_och_ob(rot: Image.Image, hole: Hole, px, flagga: dict | None = None) -> None:
    """Outlinjer (om hålfilen har `ob`) och flaggan på `flaggpunkt`. Ritas sist, ovanpå en
    bild utan flagga – så kan flaggan bytas utan att hålet målas om."""
    rita_ob(rot, hole, px)
    _flagga(rot, *px(*flaggpunkt(hole)), rot.height / 1000, flagga)


def rita_spel(rot: Image.Image, hole: Hole, px, flagga: dict | None = None) -> None:
    """Prickar (100/150 m kvar till greenens mitt), outlinjer och flagga – alltid ritade av koden."""
    rita_prickar(rot, hole, px)
    rita_flagga_och_ob(rot, hole, px, flagga)


# ---------- out of bounds ----------
OB_STEG_M = 2.0       # punkt var 2:a meter längs spellinjen
OB_MAX_M = 70.0       # längre än så från spellinjen letas ingen trädlinje
OB_IN_I_SKOG_M = 1.0  # linjen ligger strax innanför trädlinjen, som outpinnarna
OB_MIN_PUNKTER = 15   # kortare än 30 m sammanhängande trädlinje (enstaka dungar) ritas inte


def _langs(linje, station: float):
    """Punkt och enhetsvektor framåt på `station` meter längs linjen."""
    gick = 0.0
    for a, b in zip(linje, linje[1:]):
        L = math.dist(a, b)
        if L and gick + L >= station:
            t = (station - gick) / L
            return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])), ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        gick += L
    return None, None


def ob_linjer(hole: Hole, res: float = 0.5) -> list[list[tuple[float, float]]]:
    """Outlinjerna i SWEREF: för varje `ob`-sträcka går en stråle från spellinjen rakt ut åt
    sidan och linjen läggs där strålen först når hålfilens skog (`trees`, ur ortofotot) –
    trädlinjen. Där ingen skog finns inom OB_MAX_M blir det ett glapp; inga påhittade lägen."""
    if not hole.ob or not hole.trees:
        return []
    from .. import geometry as g

    bak = max(hole.tees, key=lambda t: t.length_m or 0)
    s0 = g.project(hole.centerline, bak.point)[0]
    alla = [p for t in hole.trees for p in t] + hole.centerline
    e0, n1 = min(p[0] for p in alla) - OB_MAX_M, max(p[1] for p in alla) + OB_MAX_M
    e1, n0 = max(p[0] for p in alla) + OB_MAX_M, min(p[1] for p in alla) - OB_MAX_M
    W, H = int((e1 - e0) / res) + 1, int((n1 - n0) / res) + 1
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    for t in hole.trees:
        if len(t) >= 3:
            d.polygon([((e - e0) / res, (n1 - n) / res) for e, n in t], fill=255)
    skog = np.asarray(m) > 0
    spelytor = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(spelytor)
    for poly in hole.fairways + [hole.green]:
        if len(poly) >= 3:
            d.polygon([((e - e0) / res, (n1 - n) / res) for e, n in poly], fill=255)
    spel = np.asarray(spelytor) > 0

    def i_skog(e, n):
        x, y = int((e - e0) / res), int((n1 - n) / res)
        return 0 <= x < W and 0 <= y < H and skog[y, x]

    def i_spel(e, n):
        x, y = int((e - e0) / res), int((n1 - n) / res)
        return 0 <= x < W and 0 <= y < H and spel[y, x]

    linjer = []
    for ob in hole.ob:
        tecken = 1 if ob["sida"] == "vanster" else -1
        run: list = []
        st = float(ob.get("fran_m", 0))
        till = float(ob.get("till_m", 1e9))
        while st <= till:
            p, fram = _langs(hole.centerline, s0 + st)
            if p is None:
                break
            nx, ny = -fram[1] * tecken, fram[0] * tecken  # vänster = framåt vridet 90° moturs
            hit = None
            dd = 4.0
            while dd <= OB_MAX_M:
                q = (p[0] + nx * dd, p[1] + ny * dd)
                if i_skog(*q) and not i_spel(*q):
                    hit = dd + OB_IN_I_SKOG_M
                    break
                dd += res
            if hit is None:
                if len(run) >= OB_MIN_PUNKTER:
                    linjer.append(run)
                run = []
            else:
                run.append((p[0] + nx * hit, p[1] + ny * hit))
            st += OB_STEG_M
        if len(run) >= OB_MIN_PUNKTER:
            linjer.append(run)
    # mjuka till: glidande medel över fem punkter (trädlinjen är taggig i fotot)
    ut = []
    for run in linjer:
        k = 3
        sm = []
        for i in range(len(run)):
            bit = run[max(0, i - k): i + k + 1]
            sm.append((sum(p[0] for p in bit) / len(bit), sum(p[1] for p in bit) / len(bit)))
        ut.append(sm)
    return ut


def rita_ob(rot: Image.Image, hole: Hole, px) -> None:
    """Outlinjen som tunn vit streckad linje (som i klubbarnas banguider), bara där bilden syns."""
    linjer = ob_linjer(hole)
    if not linjer:
        return
    s = rot.height / 1000
    k = 2  # ritas dubbelt så stort och skalas ner för mjuka kanter
    lag = Image.new("RGBA", (rot.width * k, rot.height * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(lag)
    streck, glapp, bredd = 9 * s * k, 6 * s * k, max(2, round(1.5 * s * k))
    for linje in linjer:
        pts = [tuple(c * k for c in px(*p)) for p in linje]
        # dela linjen i streck med jämn rytm längs hela linjen
        pos, rita, kvar = 0.0, True, streck
        for a, b in zip(pts, pts[1:]):
            L = math.dist(a, b)
            t = 0.0
            while t < L:
                steg = min(kvar, L - t)
                if rita:
                    p0 = (a[0] + (b[0] - a[0]) * t / L, a[1] + (b[1] - a[1]) * t / L)
                    p1 = (a[0] + (b[0] - a[0]) * (t + steg) / L, a[1] + (b[1] - a[1]) * (t + steg) / L)
                    d.line((p0, p1), fill=(255, 255, 255, 215), width=bredd)
                t += steg
                kvar -= steg
                if kvar <= 1e-6:
                    rita = not rita
                    kvar = streck if rita else glapp
    lag = lag.resize(rot.size, Image.LANCZOS)
    # bara där målningen syns fullt: ingen linje ut i den tonade kanten
    alfa = np.asarray(rot.getchannel("A"), dtype=np.float32) / 255.0
    vis = np.clip((alfa - 0.45) / 0.35, 0, 1)
    a = np.asarray(lag.getchannel("A"), dtype=np.float32) * vis
    lag.putalpha(Image.fromarray(a.astype(np.uint8), "L"))
    # svag mörk kant under, så linjen syns även mot ljust gräs
    skugga = Image.new("RGBA", rot.size, (12, 28, 14, 0))
    skugga.putalpha(lag.getchannel("A").filter(ImageFilter.GaussianBlur(1.2 * s)).point(lambda v: v * 45 // 100))
    rot.alpha_composite(skugga)
    rot.alpha_composite(lag)


FLAGGFARG = (87, 31, 48)        # TACADA Vinröd #571F30: tydlig mot allt grönt
FLAGGMARKE = (243, 237, 226)    # TACADA Elfenben #F3EDE2
TYPSNITT_TACADA = Path(__file__).resolve().parent.parent.parent / "assets" / "typsnitt" / "Marcellus-Regular.ttf"


def _vag(i: float) -> float:
    """Dukens våg: 0–1 längs duken → förskjutning i enheter av 1,4 × s."""
    return math.sin(i * math.pi * 1.6)


def _duk_med_logga(fl: float, fh: float, S: float, farg: tuple, logga: Path) -> Image.Image:
    """Tygflaggan i klubbens färg med loggan (en färg, ljus) mitt på, vajande: varje kolumn
    flyttas upp/ned med vågen och får ljus och skugga – loggan följer tyget."""
    W, H = max(2, round(fl)), max(2, round(fh))
    duk = Image.new("RGBA", (W, H), farg + (255,))
    lg = Image.open(logga).convert("RGBA")
    lg = lg.crop(lg.getchannel("A").getbbox())
    d = round(H * 0.9)
    lg = lg.resize((d, round(d * lg.height / lg.width)), Image.LANCZOS)
    duk.alpha_composite(lg, ((W - lg.width) // 2, (H - lg.height) // 2))
    a = np.asarray(duk, dtype=np.float32)
    amp = 1.4 * S
    ut = np.zeros((H + int(2 * amp) + 4, W, 4), np.float32)
    for x in range(W):
        u = x / W
        dy = amp + amp * _vag(u)
        ljus = 1 + 0.28 * math.cos(u * math.pi * 1.6)
        y0 = int(dy)
        f = dy - y0
        kol = a[:, x].copy()
        kol[:, :3] = np.clip(kol[:, :3] * ljus, 0, 255)
        # delpixelförskjutning: blanda två heltalslägen
        ut[y0:y0 + H, x] += kol * (1 - f)
        ut[y0 + 1:y0 + 1 + H, x] += kol * f
    return Image.fromarray(np.clip(ut, 0, 255).astype(np.uint8), "RGBA")


def _flagga(rot: Image.Image, x: float, y: float, s: float, stil: dict | None = None) -> None:
    """Flaggan som i målningen: ljus stång, vajande tygflagga med ljus och skugga, hålkopp
    och en mjuk slagskugga åt höger–uppåt (solen står lågt nere till vänster, som i målningen).
    `stil` = flaggstil(klubbmapp): klubbens logga på duk i klubbens färg (lite större duk,
    så att sigillet syns). Utan stil: TACADA-flaggan med T. Ritas 4 ggr större och skalas ner."""
    k = 4
    w, h = int(70 * s), int(56 * s)
    lag = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    ox, oy = 14 * s * k, (h - 8 * s) * k  # stångens fot i lagret
    S = s * k
    stang = (30 if stil else 27) * S
    fl, fh = ((24 * S, 18 * S) if stil else (19 * S, 13 * S))
    # slagskugga: stång och flagga lagda snett bakåt på greenen
    sk = Image.new("L", lag.size, 0)
    ds = ImageDraw.Draw(sk)
    dx, dy = 1.05, -0.38  # skuggans riktning per meter stång
    topp = (ox + stang * dx, oy + stang * dy)
    ds.line((ox, oy, *topp), fill=185, width=int(1.3 * S))
    ds.polygon([topp, (topp[0] - fl * 0.22, topp[1] - fl * 0.66 + 2 * S),
                (ox + (stang - fh * 0.7) * dx, oy + (stang - fh * 0.7) * dy)], fill=160)
    sk = sk.filter(ImageFilter.GaussianBlur(1.1 * S))
    lag.paste((10, 30, 10, 255), mask=sk)
    d = ImageDraw.Draw(lag)
    # hålkoppen
    d.ellipse((ox - 2.4 * S, oy - 1.4 * S, ox + 2.4 * S, oy + 1.4 * S), fill=(235, 240, 225, 200))
    d.ellipse((ox - 1.8 * S, oy - 1.0 * S, ox + 1.8 * S, oy + 1.0 * S), fill=(30, 40, 28, 255))
    # stången: ljus med skuggsida
    d.line((ox, oy, ox, oy - stang), fill=(240, 238, 230, 255), width=int(1.3 * S))
    d.line((ox + 0.6 * S, oy, ox + 0.6 * S, oy - stang), fill=(170, 168, 160, 255), width=max(1, int(0.6 * S)))
    t0 = oy - stang
    if stil:
        duk = _duk_med_logga(fl, fh, S, stil["farg"], stil["logga"])
        lag.alpha_composite(duk, (int(ox), int(t0 - 1.4 * S)))
        upp = [(ox + fl * i / 12, t0 + 1.4 * S * _vag(i / 12)) for i in range(13)]
        d.line([(px_, py_ + 0.5 * S) for px_, py_ in upp], fill=(255, 255, 255, 60), width=max(1, int(0.6 * S)))
        lag = lag.resize((w, h), Image.LANCZOS)
        rot.alpha_composite(lag, (int(x - ox / k), int(y - oy / k)))
        return
    # tygflaggan: vajande kant (två bågar), ljusare överkant, mörkare veck
    upp = [(ox + fl * i / 12, t0 + 1.4 * S * math.sin(i / 12 * math.pi * 1.6)) for i in range(13)]
    ned = [(ox + fl * i / 12, t0 + fh - 1.0 * S * i / 12 + 1.4 * S * math.sin(i / 12 * math.pi * 1.6)) for i in range(12, -1, -1)]
    d.polygon(upp + ned, fill=FLAGGFARG + (255,))
    for i in range(12):  # ljus och skugga i vågorna
        a = math.cos(i / 12 * math.pi * 1.6)
        ton = tuple(int(c * (1 + 0.45 * a)) for c in FLAGGFARG)
        x0 = ox + fl * i / 12
        x1 = ox + fl * (i + 1) / 12
        y0u, y1u = upp[i][1], upp[i + 1][1]
        y0n = t0 + fh - 1.0 * S * i / 12 + 1.4 * S * math.sin(i / 12 * math.pi * 1.6)
        y1n = t0 + fh - 1.0 * S * (i + 1) / 12 + 1.4 * S * math.sin((i + 1) / 12 * math.pi * 1.6)
        d.polygon([(x0, y0u), (x1, y1u), (x1, y1n), (x0, y0n)], fill=tuple(min(255, c) for c in ton) + (255,))
    d.line([(px_, py_ + 0.6 * S) for px_, py_ in upp], fill=(255, 255, 255, 70), width=max(1, int(0.7 * S)))
    # TACADA-T:et mitt på duken, i profilens Marcellus med samma halvfeta kontur
    from PIL import ImageFont
    f = ImageFont.truetype(str(TYPSNITT_TACADA), int(fh * 0.78))
    tx, ty = ox + fl * 0.5, t0 + fh * 0.5 + 0.3 * S
    d.text((tx, ty), "T", font=f, anchor="mm", fill=FLAGGMARKE + (255,),
           stroke_width=max(1, round(fh * 0.78 * 0.022)), stroke_fill=FLAGGMARKE + (255,))
    lag = lag.resize((w, h), Image.LANCZOS)
    rot.alpha_composite(lag, (int(x - ox / k), int(y - oy / k)))


TYPSNITT_MARK = Path(__file__).resolve().parent.parent.parent / "assets" / "typsnitt" / "HankenGrotesk-SemiBold.ttf"


def _tee_grupper(hole: Hole) -> list[tuple[str, tuple[float, float]]]:
    """Tees på samma plats delar namn ("52 · 49"), längsta först."""
    platser: dict[tuple[int, int], list] = {}
    for t in sorted(hole.tees, key=lambda t: -(t.length_m or 0)):
        platser.setdefault((round(t.point[0]), round(t.point[1])), []).append(t)
    return [(" · ".join(t.name.replace("/", " · ") for t in ts), ts[0].point) for ts in platser.values()]


def hinderlinjer(hole: Hole) -> list[dict]:
    """Hinder i spelzonen med fågelvägsavstånd från varje tee: fram till hindret och över
    det (carry), som en laserkikare mäter. Bara spelzonen: från 100 m från bakre tee till
    30 m före green. Greenbunkrar, hinder vid tee och par 3 (slås mot green) tas inte med.
    Hinder som börjar inom 20 m från varandra (bakre tee) slås ihop till en båge."""
    from .. import geometry as g

    if hole.par == 3:
        return []
    bak = max(hole.tees, key=lambda t: t.length_m or 0)
    gmitt = _tyngdpunkt(hole.green)
    grupper = _tee_grupper(hole)
    rader = []
    for h in hole.hazards:
        tat = [p for i, p in enumerate(h.polygon) for p in [p, ((p[0] + h.polygon[i - 1][0]) / 2, (p[1] + h.polygon[i - 1][1]) / 2)]]
        if min(g.dist(p, gmitt) for p in tat) < 30:  # greenbunker / damm vid green: inspelet, inte utslaget
            continue
        fram = min(g.dist(bak.point, p) for p in tat)
        over = max(g.dist(bak.point, p) for p in tat)
        if fram < 100 or fram > g.dist(bak.point, gmitt) - 30:
            continue
        rader.append({"hinder": [h], "fram": fram, "over": over})
    rader.sort(key=lambda r: r["fram"])
    ihop: list[dict] = []
    for r in rader:
        if ihop and r["fram"] - ihop[-1]["fram"] < 20:
            ihop[-1]["hinder"] += r["hinder"]
            ihop[-1]["over"] = max(ihop[-1]["over"], r["over"])
        else:
            ihop.append(r)
    for r in ihop:
        tat = [p for h in r["hinder"] for p in h.polygon]
        r["tees"] = [(namn, round(min(g.dist(pt, p) for p in tat)), round(max(g.dist(pt, p) for p in tat)))
                     for namn, pt in grupper]
        r["tees"] = [t for t in r["tees"] if t[2] >= 20]
    return [r for r in ihop if r["tees"]]


def _font(storlek: float, vikt: str = "SemiBold"):
    from PIL import ImageFont

    return ImageFont.truetype(str(TYPSNITT_MARK.with_name(f"HankenGrotesk-{vikt}.ttf")), max(8, round(storlek)))


def _tabell(d: ImageDraw.ImageDraw, x: float, y: float, rader: list[tuple[str, int, int]], s: float, at: str,
            upptagna: list):
    """Avståndstabell: tee | fram–över m, mörk ruta. at = 'v' betyder att x är högerkanten."""
    f, fb = _font(13 * s, "Medium"), _font(13 * s)
    rh, pad = 19 * s, 6 * s
    texter = [(n, f"{a}–{b}" if b - a >= 6 else f"{a}") for n, a, b in rader]
    w1 = max(d.textlength(n, font=fb) for n, _ in texter)
    w2 = max(d.textlength(t + " m", font=f) for _, t in texter)
    W, H = w1 + w2 + 4 * pad, rh * len(texter) + pad
    x0 = x - W if at == "v" else x
    x0 = min(max(x0, 2 * s), d.im.size[0] - W - 2 * s)
    y0 = min(max(y - H / 2, 2 * s), d.im.size[1] - H - 2 * s)
    for b in upptagna:  # aldrig ovanpå en tidigare tabell: flytta ner under den
        if y0 < b[3] + 4 * s and y0 + H > b[1] - 4 * s and x0 < b[2] and x0 + W > b[0]:
            y0 = b[3] + 4 * s
    upptagna.append((x0, y0, x0 + W, y0 + H))
    d.rounded_rectangle((x0, y0, x0 + W, y0 + H), radius=3 * s, fill=(22, 30, 25, 225))
    d.line((x0 + w1 + 2 * pad, y0 + pad, x0 + w1 + 2 * pad, y0 + H - pad), fill=(255, 255, 255, 70), width=max(1, round(s)))
    for i, (n, t) in enumerate(texter):
        yy = y0 + pad / 2 + rh * i + rh / 2
        d.text((x0 + pad + w1, yy), n, font=fb, fill=(255, 255, 255, 255), anchor="rm")
        d.text((x0 + 3 * pad + w1, yy), t + " m", font=f, fill=(236, 230, 214, 255), anchor="lm")
    return (x0, y0, x0 + W, y0 + H)


def _tata(poly, steg: float = 1.5) -> list:
    """Polygonens kant med en punkt var steg:e meter."""
    ut = []
    for i, b in enumerate(poly):
        a = poly[i - 1]
        n = max(1, int(math.dist(a, b) / steg))
        ut += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]
    return ut


def greenbagar(hole: Hole) -> list[float]:
    """Avstånd kvar till greenens mitt där en båge ritas, som i Bro Hofs banguide: var
    50:e meter från 100 m och vid varje hinders bortre kant sett från green (läggupp-
    punkten framför hindret). Bågar närmare än 12 m varandra slås ihop, hindret vinner."""
    from .. import geometry as g

    if hole.par == 3:
        return []
    gm = _tyngdpunkt(hole.green)
    bak = max(hole.tees, key=lambda t: t.length_m or 0)
    langst = g.dist(bak.point, gm) - 40
    hinder = sorted(round(max(g.dist(gm, p) for p in h.polygon)) for h in hole.hazards)
    fram = min(g.dist(t.point, gm) for t in hole.tees) - 30  # hinder vid tee: inte en läggupp-punkt
    hinder = [r for r in hinder if 50 <= r <= min(langst, fram)]
    jamna = [r for r in range(100, int(langst) + 1, 50) if all(abs(r - h) >= 12 for h in hinder)]
    ut: list[float] = []
    for r in sorted(hinder + jamna):
        if not ut or r - ut[-1] >= 12:
            ut.append(r)
    return ut


def rita_tees_och_hinder(rot: Image.Image, hole: Hole, px, marg: float = 0, bagar: bool = False) -> str:
    """Yardage-book-markeringar: tees som vita romber med namn, och för varje hinder i
    spelzonen en tunn båge tvärs över hålet på hindrets framkant (avstånd från bakre tee)
    med en tabell: varje tee, meter fram till hindret – över det. Fågelväg, som laser.
    marg = tom kant i px på båda sidor där tabellerna får plats. Returnerar förklaringen."""
    import math

    d = ImageDraw.Draw(rot)
    s = rot.height / 1000
    bak = max(hole.tees, key=lambda t: t.length_m or 0)
    W = rot.size[0]
    from .. import geometry as g

    # bågar från greenens mitt med meter kvar, siffran vid bågens högra ände
    # (av tills vidare: Eric 2026-10-21 "ta bort alla strecken, läggs in sen")
    gm = _tyngdpunkt(hole.green)
    fb = _font(15 * s)
    tata = [_tata(f) for f in hole.fairways]
    for R in (greenbagar(hole) if bagar else []):
        mitt = min((g.point_along(hole.centerline, st) for st in range(0, int(g.polyline_length(hole.centerline)), 2)),
                   key=lambda p: abs(math.dist(gm, p) - R))
        # fairwaykanten där bågen skär den, nära spellinjen (inte andra sidan en dogleg)
        fw = [p for f in tata for p in f if abs(math.dist(gm, p) - R) < 2 and math.dist(p, mitt) < 45] or [mitt]
        v = [math.atan2(p[1] - gm[1], p[0] - gm[0]) for p in fw]
        mid = v[0]
        v = [(a - mid + math.pi) % (2 * math.pi) - math.pi + mid for a in v]  # ingen vinkel-skarv
        lo, hi = min(v) - 10 / R, max(v) + 10 / R
        bage = [px(gm[0] + R * math.cos(a), gm[1] + R * math.sin(a)) for a in [lo + (hi - lo) * i / 40 for i in range(41)]]
        d.line(bage, fill=(255, 255, 255, 60), width=max(2, round(3 * s)), joint="curve")
        d.line(bage, fill=(22, 30, 25, 200), width=max(1, round(1.3 * s)), joint="curve")
        ande = max(bage, key=lambda q: q[0])
        d.text((ande[0] + 5 * s, ande[1]), str(round(R)), font=fb, fill=(22, 30, 25, 255), anchor="lm",
               stroke_width=max(1, round(2.4 * s)), stroke_fill=(250, 244, 236, 235))
    upptagna: list = []
    for r in (hinderlinjer(hole) if bagar else []):
        R = r["fram"]
        # bågen: konstant avstånd från bakre tee, över hindren och fairway
        hpts = [p for h in r["hinder"] for p in h.polygon]
        vinklar = [math.atan2(p[1] - bak.point[1], p[0] - bak.point[0]) for p in hpts]
        fw = [p for f in hole.fairways for p in f if abs(math.dist(bak.point, p) - R) < 6]
        vinklar += [math.atan2(p[1] - bak.point[1], p[0] - bak.point[0]) for p in fw]
        lo, hi = min(vinklar) - 12 / R, max(vinklar) + 12 / R
        bage = [px(bak.point[0] + R * math.cos(a), bak.point[1] + R * math.sin(a))
                for a in [lo + (hi - lo) * i / 40 for i in range(41)]]
        d.line(bage, fill=(0, 0, 0, 70), width=max(2, round(3.2 * s)), joint="curve")
        d.line(bage, fill=(255, 255, 255, 235), width=max(1, round(1.6 * s)), joint="curve")
        # tabellen på hindrets sida, i den tomma kanten; tunn linje från bågens ände
        vanster = True  # tabellerna till vänster, greenens siffror till höger (som Bro Hof)
        ande = min(bage, key=lambda q: q[0]) if vanster else max(bage, key=lambda q: q[0])
        tx = ande[0] - 14 * s if vanster else ande[0] + 14 * s
        box = _tabell(d, tx, ande[1], r["tees"], s, "v" if vanster else "h", upptagna)
        kx = box[2] if vanster else box[0]
        d.line((ande[0], ande[1], kx, (box[1] + box[3]) / 2), fill=(255, 255, 255, 200), width=max(1, round(1.2 * s)))
    _rita_tees(d, hole, px, s)
    if not bagar:
        return ""
    delar = (["Mörka bågar: meter kvar till greenens mitt"] if greenbagar(hole) else []) + \
        (["tabeller: meter från varje tee fram till hindret – över"] if hinderlinjer(hole) else [])
    return ", ".join(delar)


def _rita_tees(d: ImageDraw.ImageDraw, hole: Hole, px, s: float) -> None:
    """Tees: vit romb med mörk kant och namnet bredvid."""
    f = _font(13 * s)
    for namn, (e, n) in _tee_grupper(hole):
        x, y = px(e, n)
        r = 6 * s
        d.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], fill=(255, 255, 255, 255), outline=(22, 30, 25, 255),
                  width=max(1, round(1.4 * s)))
        tw = d.textlength(namn, font=f)
        d.rounded_rectangle((x + 9 * s, y - 9 * s, x + 17 * s + tw, y + 9 * s), radius=3 * s, fill=(255, 255, 255, 230))
        d.text((x + 13 * s, y), namn, font=f, fill=(22, 30, 25, 255), anchor="lm")


def markera_halbild(hole: Hole, orto: Path, bild: Path, ut: Path, bagar: bool = False) -> tuple[Path, str]:
    """Färdig hålbild (målad eller foto) + tees och hinderavstånd, för hålkortet.
    Placeringen räknas om ur fotounderlaget i bildens höjd, samma som när bilden gjordes."""
    im = Image.open(bild).convert("RGBA")
    rot, px = fotounderlag(hole, orto, im.height)
    if rot.size != im.size:  # bilden gjord på en äldre hålfil: rita inget hellre än fel
        print(f"VARNING: {bild.name} passar inte hålfilen ({im.size} mot {rot.size}) – inga tees/hinder ritade")
        return bild, ""
    marg = round(im.height * 0.16) if bagar and (hinderlinjer(hole) or greenbagar(hole)) else 0  # plats för tabellerna, beskärs sedan
    if marg:
        stor = Image.new("RGBA", (im.width + 2 * marg, im.height), (0, 0, 0, 0))
        stor.paste(im, (marg, 0))
        im, px0 = stor, px
        px = lambda e, n: (px0(e, n)[0] + marg, px0(e, n)[1])
    forklaring = rita_tees_och_hinder(im, hole, px, marg, bagar)
    if marg:  # bara så mycket kant som tabellerna behöver
        x0, _, x1, _ = im.getchannel("A").point(lambda v: 255 if v > 6 else 0).getbbox()
        im = im.crop((max(0, x0 - 4), 0, min(im.width, x1 + 4), im.height))
    ut.parent.mkdir(parents=True, exist_ok=True)
    im.save(ut)
    return ut, forklaring


def _matt_green(hole: Hole) -> dict:
    """Greenens djup längs inspelslinjen och bredd tvärs den, i meter, plus riktningen."""
    mitt = _tyngdpunkt(hole.green)
    a = hole.centerline[-3] if len(hole.centerline) >= 3 else hole.centerline[0]
    L = math.dist(a, mitt)
    u = ((mitt[0] - a[0]) / L, (mitt[1] - a[1]) / L)
    v = (-u[1], u[0])
    langs = [(p[0] - mitt[0]) * u[0] + (p[1] - mitt[1]) * u[1] for p in hole.green]
    tvars = [(p[0] - mitt[0]) * v[0] + (p[1] - mitt[1]) * v[1] for p in hole.green]
    return {"mitt": mitt, "u": u, "v": v, "fram": min(langs), "bak": max(langs),
            "vanster": max(tvars), "hoger": min(tvars),
            "djup": round(max(langs) - min(langs)), "bredd": round(max(tvars) - min(tvars))}


def _etikett(d: ImageDraw.ImageDraw, x: float, y: float, text: str, s: float, at: str = "h") -> None:
    """Siffra i en liten mörk ruta bredvid en punkt (at = 'h' höger, 'v' vänster om punkten)."""
    f = _font(15 * s)
    tw = d.textlength(text, font=f)
    x0 = x + 14 * s if at == "h" else x - 14 * s - tw - 12 * s
    d.rounded_rectangle((x0, y - 11 * s, x0 + tw + 12 * s, y + 11 * s), radius=3 * s, fill=(22, 30, 25, 225))
    d.text((x0 + 6 * s, y), text, font=f, fill=(255, 255, 255, 255), anchor="lm")


def spelarvy(hole: Hole, orto: Path, bild: Path, ut: Path) -> dict:
    """Spelarversionen av hålbilden (webb/mobil): tees, siffror vid prickarna och vid
    200 m kvar, och en förstorad green med djup och bredd. Bara mått ur hålfilen –
    inga lutningspilar (höjdmodellen är för grov för greener).
    Returnerar filerna och siffrorna som layouten skriver ut."""
    from .. import geometry as g

    im = Image.open(bild).convert("RGBA")
    rot, px = fotounderlag(hole, orto, im.height)
    if rot.size != im.size:
        raise ValueError(f"{bild.name} passar inte hålfilen ({im.size} mot {rot.size})")
    d = ImageDraw.Draw(im)
    s = im.height / 1000
    gm = _matt_green(hole)
    linje_x = sum(px(*p)[0] for p in hole.centerline) / len(hole.centerline)
    if hole.par != 3:
        for meter in (200, 150, 100):
            p = avstandspunkt(hole, gm["mitt"], meter)
            if not p:
                continue
            x, y = px(*p)
            if meter == 200:  # 100 och 150 har redan sina prickar i bilden
                r = 6 * s
                d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 255), outline=(22, 30, 25, 255),
                          width=max(1, round(1.4 * s)))
            _etikett(d, x, y, str(meter), s, "v" if x > linje_x else "h")
    _rita_tees(d, hole, px, s)

    # förstorad green, vriden så att inspelet kommer nerifrån: djup uppåt, bredd tvärs
    M, u, v = gm["mitt"], gm["u"], gm["v"]
    pt = lambda a, b: (M[0] + a * u[0] + b * v[0], M[1] + a * u[1] + b * v[1])
    (fx, fy), (bx, by) = px(*pt(gm["fram"], 0)), px(*pt(gm["bak"], 0))
    vinkel = 90 - math.degrees(math.atan2(-(by - fy), bx - fx))  # moturs så att fram→bak pekar uppåt
    cx, cy = px(*pt((gm["fram"] + gm["bak"]) / 2, (gm["hoger"] + gm["vanster"]) / 2))
    m = 16.0
    halv_m = max(gm["bak"] - gm["fram"], gm["vanster"] - gm["hoger"]) / 2 + m
    half = halv_m * math.dist((fx, fy), (bx, by)) / (gm["bak"] - gm["fram"])
    utan = Image.open(bild).convert("RGBA")  # utan siffror, bara målningen med flaggan
    R = half * 1.5
    stor = utan.crop((round(cx - R), round(cy - R), round(cx + R), round(cy + R)))
    stor = stor.rotate(vinkel, resample=Image.BICUBIC, center=(R, R))
    krop = stor.crop((round(R - half), round(R - half), round(R + half), round(R + half))).resize((1200, 1200), Image.LANCZOS)
    k = 1200 / (2 * half)
    a_ = math.radians(vinkel)

    def gp(e, n):
        x, y = px(e, n)
        x, y = x - cx, y - cy
        # PIL roterar moturs i bilden (y nedåt)
        return (x * math.cos(a_) + y * math.sin(a_)) * k + 600, (-x * math.sin(a_) + y * math.cos(a_)) * k + 600

    dg = ImageDraw.Draw(krop)
    f = _font(44)
    vit, mork = (255, 255, 255, 240), (22, 30, 25, 225)

    def matt(p0, p1, text, sida):
        (x0, y0), (x1, y1) = gp(*p0), gp(*p1)
        dg.line((x0, y0, x1, y1), fill=(0, 0, 0, 80), width=8)
        dg.line((x0, y0, x1, y1), fill=vit, width=4)
        for x, y in ((x0, y0), (x1, y1)):
            dg.ellipse((x - 8, y - 8, x + 8, y + 8), fill=vit)
        tx, ty = (x1 + sida[0], y1 + sida[1])  # vid linjens bortre ände
        tw = dg.textlength(text, font=f)
        tx = min(max(tx, tw / 2 + 40), 1160 - tw / 2)
        dg.rounded_rectangle((tx - tw / 2 - 16, ty - 32, tx + tw / 2 + 16, ty + 32), radius=8, fill=mork)
        dg.text((tx, ty), text, font=f, fill=(255, 255, 255, 255), anchor="mm")

    xm = (gm["hoger"] + gm["vanster"]) / 2
    am = (gm["fram"] + gm["bak"]) / 2
    matt(pt(gm["fram"], xm), pt(gm["bak"], xm), f"{gm['djup']} m", (0, -52))
    matt(pt(am, gm["hoger"]), pt(am, gm["vanster"]), f"{gm['bredd']} m", (0, 58))
    # rund förstoring med mjuk kant
    mask = Image.new("L", krop.size, 0)
    ImageDraw.Draw(mask).ellipse((6, 6, 1194, 1194), fill=255)
    krop.putalpha(Image.fromarray(np.minimum(np.array(krop.getchannel("A")), np.array(mask))))

    ut = Path(ut)
    ut.parent.mkdir(parents=True, exist_ok=True)
    im.save(ut)
    green_ut = ut.with_name(ut.stem + "-green.png")
    krop.save(green_ut)
    grupper = _tee_grupper(hole)
    fagel = [(namn, round(g.dist(pt_, gm["mitt"]))) for namn, pt_ in grupper]
    bunkrar = []
    for h in hole.hazards:
        if h.kind != "bunker" or min(g.dist(p, gm["mitt"]) for p in h.polygon) > 30:
            continue
        langs = [(p[0] - M[0]) * u[0] + (p[1] - M[1]) * u[1] for p in h.polygon]
        tvars = sum((p[0] - M[0]) * v[0] + (p[1] - M[1]) * v[1] for p in h.polygon) / len(h.polygon)
        kort = round(gm["fram"] - min(langs))
        sida = "höger" if tvars < 0 else "vänster"
        bunkrar.append(f"Bunker {sida}, börjar {kort} m kort om greenen" if kort > 2 else f"Bunker {sida} om greenen")
    return {"bild": ut, "green": green_ut, "djup": gm["djup"], "bredd": gm["bredd"], "fagelvag": fagel,
            "bunkrar": bunkrar}


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
    if rot.width > bredd * AI_SKALA:  # brett hål (korta par 3): bredden styr i stället
        rot, _ = fotounderlag(hole, orto, round(hojd_px * AI_SKALA * bredd * AI_SKALA / rot.width))
    duk = Image.new("RGB", (bredd, hojd_px), (250, 244, 236))
    duk.paste(rot, ((bredd - rot.width) // 2, (hojd_px - rot.height) // 2), rot)
    return _spara(duk, ut)


AI_SKALA = 0.95


def _lum(im: Image.Image, r: int) -> np.ndarray:
    a = np.asarray(im.convert("RGB"), dtype=np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    return _mjuk(a, r)


def formpoang(underlag: Image.Image, malad: Image.Image, hole: Hole, px) -> dict:
    """Hur väl målningen ligger på hålets form, 0–1 (högre är bättre).
    likhet: korrelation mellan fotots och målningens ljusbild (grovt, ~3 m), inom hålet.
    kant: hur tydligt fairway och green är ljusare än ytan strax utanför i målningen
    (hålfilens polygoner, alltså formen ur fotot)."""
    r = max(2, underlag.height // 300)
    a, b = _lum(underlag, r), _lum(malad, r)
    m = np.asarray(underlag.getchannel("A")) > 200
    x, y = a[m] - a[m].mean(), b[m] - b[m].mean()
    likhet = float((x * y).sum() / (np.sqrt((x * x).sum() * (y * y).sum()) + 1e-6))
    yta = Image.new("L", underlag.size, 0)
    d = ImageDraw.Draw(yta)
    for poly in hole.fairways + [hole.green]:
        if len(poly) > 2:
            d.polygon([px(*p) for p in poly], fill=255)
    inne = np.asarray(yta) > 0
    ring_px = max(3, underlag.height // 250)
    ute = (_mjuk(inne.astype(np.float32), ring_px) > 0.02) & ~inne & m
    inne_k = (_mjuk(inne.astype(np.float32), ring_px // 2) > 0.98) & m
    l = _lum(malad, 1)
    kant = float(np.clip((l[inne_k].mean() - l[ute].mean()) / 40, 0, 1)) if ute.any() and inne_k.any() else 0.0
    return {"likhet": round(likhet, 3), "kant": round(kant, 3), "poang": round(0.6 * likhet + 0.4 * kant, 3)}


def pa_formen(rot: Image.Image, fil: Path) -> Image.Image:
    """AI-målningen (9:16-duken från ai_underlag) skalad tillbaka och utklippt med
    fotounderlagets siluett `rot` – samma placering som ai_tillbaka."""
    hojd_px = rot.height
    ai = Image.open(fil).convert("RGB")
    # AI:n lämnar inte exakt 9:16 (4K: 3072 × 5504); duken räknas som underlagets 9:16
    duk_w = round(hojd_px * 9 / 16)
    ai = ai.resize((duk_w, hojd_px), Image.LANCZOS)
    inre_h = round(hojd_px * AI_SKALA)
    inre_w = round(rot.width * AI_SKALA)
    if inre_w > duk_w * AI_SKALA:  # brett hål: som i ai_underlag styr bredden
        inre_w = round(duk_w * AI_SKALA)
        inre_h = round(inre_w * rot.height / rot.width)
    x0, y0 = (duk_w - inre_w) // 2, (hojd_px - inre_h) // 2
    malad = ai.crop((x0, y0, x0 + inre_w, y0 + inre_h)).resize(rot.size, Image.LANCZOS).convert("RGBA")
    malad.putalpha(rot.getchannel("A"))
    return malad


def ai_tillbaka(hole: Hole, orto: Path, ai_bilder: list[Path], ut: Path, kontroll: Path | None = None,
                hojd_px: int = 4000, flagga: dict | None = None) -> tuple[Path, list[dict]]:
    """Lägger AI-målningen på hålets exakta form: duken skalas tillbaka, hålet klipps
    ut med fotounderlagets egen siluett (alfa) och prickar och flagga ritas av koden
    på hålfilens koordinater. Får den flera målningar väljs den med högst formpoäng.
    Kontrollbilden visar hålfilens konturer ovanpå målningen – ligger de inte på
    målningens kanter har AI:n flyttat något och bilden får inte användas."""
    rot, px = fotounderlag(hole, orto, hojd_px)
    resultat = []
    for fil in ai_bilder:
        malad = pa_formen(rot, fil)
        resultat.append((formpoang(rot, malad, hole, px) | {"fil": str(fil)}, malad))
    resultat.sort(key=lambda t: -t[0]["poang"])
    malad = resultat[0][1]
    if kontroll:
        _spara(rita_konturer(malad, hole, px), kontroll)
    rita_prickar(malad, hole, px)
    # utan flagga och outlinje: så kan flaggan bytas senare utan att något suddas bort
    _spara(malad, utan_flagga(ut))
    rita_flagga_och_ob(malad, hole, px, flagga)
    return _spara(malad, ut), [r[0] for r in resultat]


def utan_flagga(bild: Path) -> Path:
    """hal-NN-malad.webp → hal-NN-malad-utan-flagga.webp (målningen med prickar, utan flagga och outlinje)."""
    bild = Path(bild)
    return bild.with_name(f"{bild.stem}-utan-flagga{bild.suffix}")
