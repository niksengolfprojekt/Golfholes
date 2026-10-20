"""Halvautomatiskt utkast av ett hål ur Lantmäteriets ortofoto (RGB + NIR).

Koden hittar själv skog, vatten och bunkrar inom hålets korridor. Green och
fairway tas fram med en "trollstav": en punkt mitt i ytan, sedan växer koden ut
ytan så långt färg och struktur är lika och gör den till en polygon. Det enda en
människa (eller Claude) anger är därför tees, spellinje och en punkt per green och
fairway – allt i klubbar/<klubb>/utkast/hal-NN.yaml, kontrollerat mot klubbens
hålkarta. Resultatet är ett utkast som granskas och vid behov rättas i
ritverktyget innan det godkänns. Inget hittas på: varje form kommer ur fotot.

    python -m golfholes utkast klubbar/glasriket/utkast/hal-03.yaml
    → klubbar/glasriket/hal-03.yaml + data/glasriket/utkast/hal-03_kontroll.jpg
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .lantmateriet import read_window

STEG = 2  # 0,16 m → 0,32 m per pixel räcker för hålbilder och går fyra gånger fortare


# ---------- Bild och mått ----------

@dataclass
class Fonster:
    rgbn: np.ndarray  # (h, w, 4) float32: R, G, B, NIR
    e0: float         # övre vänstra pixelkantens E
    n0: float         # övre vänstra pixelkantens N
    res: float        # meter per pixel

    def pix(self, e: float, n: float) -> tuple[int, int]:
        """(rad, kolumn) för en SWEREF-punkt."""
        return int((self.n0 - n) / self.res), int((e - self.e0) / self.res)

    def geo(self, x: float, y: float) -> tuple[float, float]:
        """SWEREF för pixelhörn (x = kolumn, y = rad)."""
        return self.e0 + x * self.res, self.n0 - y * self.res


def las_fonster(orto: str | Path, bbox: tuple[float, float, float, float], steg: int = STEG) -> Fonster:
    a, e0, n0, res = read_window(orto, bbox)
    a = a.astype(np.float32)
    h, w = a.shape[0] // steg * steg, a.shape[1] // steg * steg
    a = a[:h, :w].reshape(h // steg, steg, w // steg, steg, a.shape[2]).mean((1, 3))
    if a.shape[2] < 4:
        raise ValueError("Ortofotot saknar NIR-band – utkast kräver Lantmäteriets 4-bandsfoto.")
    return Fonster(a, e0, n0, res * steg)


def medel(x: np.ndarray, r: int) -> np.ndarray:
    """Medelvärde i en ruta (2r+1)² med summerad area-tabell."""
    k = 2 * r + 1
    p = np.pad(x, r + 1, mode="edge")
    c = p.cumsum(0).cumsum(1)
    s = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return s[: x.shape[0], : x.shape[1]] / (k * k)


def matt(f: Fonster) -> dict[str, np.ndarray]:
    R, G, B, N = (f.rgbn[..., i] for i in range(4))
    m = medel(G, 3)
    sd = np.sqrt(np.maximum(medel(G * G, 3) - m * m, 0))
    return {"R": R, "G": G, "B": B, "N": N, "V": (R + G + B) / 3,
            "ndvi": (N - R) / (N + R + 1e-3), "struktur": sd}


def klassa(mt: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Skog, vatten och bunker per pixel. Trösklarna är satta på Glasriket juli 2025
    och kontrolleras visuellt per bana (kontrollbilden)."""
    sd4 = medel(mt["struktur"], 4)
    vatten = (medel(mt["ndvi"], 3) < -0.15) & (medel(mt["N"], 3) < 40)
    # sand är ljus och saknar klorofyll; torrt gräs (hål 5, juli) har V ~150 och ndvi ~0
    bunker = (mt["R"] > 150) & (mt["R"] >= mt["G"] - 5) & (mt["R"] - mt["B"] > 15) & (mt["ndvi"] < -0.04) \
        & (mt["V"] > 172)
    skog = ((medel(mt["V"], 4) < 72) | (sd4 > 11)) & ~vatten
    return {"skog": skog, "vatten": vatten, "bunker": bunker}


# ---------- Morfologi och trollstav ----------

def _skift(m: np.ndarray, dy: int, dx: int) -> np.ndarray:
    out = np.zeros_like(m)
    h, w = m.shape
    out[max(dy, 0):h + min(dy, 0), max(dx, 0):w + min(dx, 0)] = m[max(-dy, 0):h - max(dy, 0), max(-dx, 0):w - max(dx, 0)]
    return out


def vidga(m: np.ndarray, r: int) -> np.ndarray:
    return medel(m.astype(np.float32), r) > 1e-6


def krymp(m: np.ndarray, r: int) -> np.ndarray:
    return medel(m.astype(np.float32), r) > 1 - 1e-6


def oppna(m, r):
    return vidga(krymp(m, r), r)


def stang(m, r):
    return krymp(vidga(m, r), r)


def etiketter(m: np.ndarray) -> tuple[np.ndarray, int]:
    """Numrerar sammanhängande ytor (4-grannar) via rader av löpande pixlar + union-find."""
    d = np.diff(np.pad(m, ((0, 0), (1, 1))).astype(np.int8), axis=1)
    rs, ss = np.nonzero(d == 1)
    _, es = np.nonzero(d == -1)
    n = len(rs)
    far = list(range(n))

    def rot(i):
        while far[i] != i:
            far[i] = far[far[i]]
            i = far[i]
        return i

    radstart = np.searchsorted(rs, np.arange(m.shape[0] + 1))
    for r in range(m.shape[0] - 1):
        a, a1 = radstart[r], radstart[r + 1]
        b, b1 = radstart[r + 1], radstart[r + 2]
        while a < a1 and b < b1:
            if ss[a] < es[b] and ss[b] < es[a]:
                ra, rb = rot(a), rot(b)
                if ra != rb:
                    far[max(ra, rb)] = min(ra, rb)
            if es[a] < es[b]:
                a += 1
            else:
                b += 1
    lab = np.zeros(m.shape, dtype=np.int32)
    nummer: dict[int, int] = {}
    for i in range(n):
        k = nummer.setdefault(rot(i), len(nummer) + 1)
        lab[rs[i], ss[i]:es[i]] = k
    return lab, len(nummer)


def fyll_hal(m: np.ndarray) -> np.ndarray:
    """Fyller hål i en yta (t.ex. flaggstång eller skugga mitt på green)."""
    lab, _ = etiketter(np.pad(~m, 1, constant_values=True))
    return lab[1:-1, 1:-1] != lab[0, 0]


def komponent(m: np.ndarray, rad: int, kol: int) -> np.ndarray:
    """Den sammanhängande delen av m som innehåller (rad, kol)."""
    if not m[rad, kol]:
        return np.zeros_like(m)
    lab, _ = etiketter(m)
    return lab == lab[rad, kol]


def trollstav(mt: dict[str, np.ndarray], rad: int, kol: int, tol: float = 1.0,
              max_radie_px: int | None = None, utom: np.ndarray | None = None) -> np.ndarray:
    """Växer ut en yta från en punkt: pixlar vars utjämnade färg, NIR och struktur ligger
    nära punktens omgivning och som hänger ihop med den."""
    kanaler = [medel(mt[k], 2) for k in ("R", "G", "B", "N")] + [medel(mt["struktur"], 4)]
    vikt = [1.0, 1.0, 1.0, 0.6, 2.0]  # struktur skiljer kortklippt från ruff
    r0, r1 = max(rad - 4, 0), rad + 5
    k0, k1 = max(kol - 4, 0), kol + 5
    ref = [float(np.median(c[r0:r1, k0:k1])) for c in kanaler]
    skala = [6.0, 6.0, 6.0, 9.0, 1.5]
    d = sum(v * ((c - m) / s) ** 2 for c, m, s, v in zip(kanaler, ref, skala, vikt))
    kand = d < (tol * 3.0) ** 2
    if utom is not None:
        kand &= ~utom
    if max_radie_px:
        yy, xx = np.ogrid[: kand.shape[0], : kand.shape[1]]
        kand &= (yy - rad) ** 2 + (xx - kol) ** 2 <= max_radie_px ** 2
    kand = oppna(kand, 1)  # klipper smala bryggor mot grannytor
    yta = komponent(kand, rad, kol)
    # Strukturmåttet suddar ut kanten några pixlar; ta tillbaka kantbandet med bara färgen
    farg = sum(v * ((c - m) / s) ** 2 for c, m, s, v in zip(kanaler[:4], ref[:4], skala[:4], vikt[:4]))
    kant = vidga(yta, 7) & (farg < (tol * 2.5) ** 2)
    if utom is not None:
        kant &= ~utom
    return fyll_hal(stang(yta | kant, 2))


# ---------- Polygoner ----------

def ringar(m: np.ndarray) -> list[np.ndarray]:
    """Gränslinjer (i pixelhörn, x/y) runt varje yta i en mask. Ytterkanter går medurs
    (positiv area i bildkoordinater), hål moturs."""
    p = np.pad(m, 1)
    kanter: dict[tuple[int, int], list[tuple[int, int]]] = {}

    def lagg(maske, a, b):
        ys, xs = np.nonzero(maske)
        for y, x in zip(ys.tolist(), xs.tolist()):
            kanter.setdefault((x + a[0], y + a[1]), []).append((x + b[0], y + b[1]))

    inne = p[1:-1, 1:-1]
    # pixel (r, c) = ruta [c, c+1] × [r, r+1]; insidan till höger om kanten
    lagg(inne & ~p[:-2, 1:-1], (0, 0), (1, 0))   # ovankant
    lagg(inne & ~p[1:-1, 2:], (1, 0), (1, 1))    # högerkant
    lagg(inne & ~p[2:, 1:-1], (1, 1), (0, 1))    # underkant
    lagg(inne & ~p[1:-1, :-2], (0, 1), (0, 0))   # vänsterkant
    ut = []
    while kanter:
        start = next(iter(kanter))
        ring = [start]
        cur, prev_d = start, None
        while True:
            nasta = kanter[cur]
            if len(nasta) > 1 and prev_d is not None:  # hörn där två ytor möts: sväng höger
                nasta.sort(key=lambda q: ((prev_d[0] * (q[1] - cur[1]) - prev_d[1] * (q[0] - cur[0])) <= 0))
            nx = nasta.pop(0)
            if not nasta:
                del kanter[cur]
            prev_d = (nx[0] - cur[0], nx[1] - cur[1])
            cur = nx
            if cur == start:
                break
            ring.append(cur)
        ut.append(np.array(ring, dtype=float))
    return ut


def area(r: np.ndarray) -> float:
    x, y = r[:, 0], r[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def forenkla(pts: np.ndarray, tol: float) -> np.ndarray:
    """Douglas–Peucker för en sluten ring."""
    if len(pts) < 5:
        return pts
    i = int(np.argmax(((pts - pts[0]) ** 2).sum(1)))

    def dp(p):
        if len(p) < 3:
            return p
        a, b = p[0], p[-1]
        ab = b - a
        n = math.hypot(*ab) or 1e-9
        d = np.abs(ab[0] * (p[:, 1] - a[1]) - ab[1] * (p[:, 0] - a[0])) / n
        j = int(np.argmax(d))
        if d[j] <= tol:
            return np.array([a, b])
        return np.vstack([dp(p[: j + 1])[:-1], dp(p[j:])])

    halva1 = dp(pts[: i + 1])
    halva2 = dp(np.vstack([pts[i:], pts[:1]]))
    return np.vstack([halva1[:-1], halva2[:-1]])


def mjuka(pts: np.ndarray, varv: int = 2) -> np.ndarray:
    """Chaikin: rundar av trappstegen från pixelkanterna."""
    for _ in range(varv):
        q = np.roll(pts, -1, axis=0)
        pts = np.stack([0.75 * pts + 0.25 * q, 0.25 * pts + 0.75 * q], 1).reshape(-1, 2)
    return pts


def polygoner(m: np.ndarray, f: Fonster, min_m2: float = 4.0, tol_m: float = 0.5,
              max_m2: float | None = None) -> list[list[tuple[float, float]]]:
    """Mask → polygoner i SWEREF 99 TM (ytterkanter, hål hoppas över)."""
    ut = []
    for r in ringar(m):
        a = area(r) * f.res ** 2
        if a < min_m2 or (max_m2 and a > max_m2):
            continue
        r = mjuka(forenkla(r, tol_m / f.res), 2)
        r = forenkla(r, 0.15 / f.res)
        ut.append([tuple(round(float(v), 1) for v in f.geo(x, y)) for x, y in r])
    return ut


def kompakthet(m: np.ndarray) -> float:
    """4πA/P² (1 = cirkel) – skiljer bunkrar från gångvägar."""
    rs = ringar(m)
    if not rs:
        return 0.0
    r = max(rs, key=area)
    omkrets = float(np.hypot(*np.diff(np.vstack([r, r[:1]]), axis=0).T).sum())
    return 4 * math.pi * area(r) / (omkrets ** 2 or 1)


# ---------- Ett hål ----------

def _avstand_till_linje(f: Fonster, linje: list[tuple[float, float]], shape) -> np.ndarray:
    """Avstånd i meter från varje pixel till spellinjen."""
    yy, xx = np.mgrid[: shape[0], : shape[1]]
    E = f.e0 + (xx + 0.5) * f.res
    N = f.n0 - (yy + 0.5) * f.res
    d = np.full(shape, np.inf, dtype=np.float32)
    for (ea, na), (eb, nb) in zip(linje, linje[1:]):
        vx, vy = eb - ea, nb - na
        t = np.clip(((E - ea) * vx + (N - na) * vy) / (vx * vx + vy * vy), 0, 1)
        d = np.minimum(d, np.hypot(E - ea - t * vx, N - na - t * vy))
    return d


def spelfri(f: Fonster, linje: list, tees: list, shape, bredd_m: float = 12.0) -> np.ndarray:
    """Spelkorridoren: bandet längs spellinjen och från varje tee fram till linjen.
    Där ritas aldrig skog – hålet är öppet från tee. Mörkt gräs och skuggor som
    klassats som skog försvinner; ett verkligt träd i spellinjen läggs in för hand
    (eller med spelfri_m: 0 i fröfilen)."""
    if bredd_m <= 0:
        return np.zeros(shape, dtype=bool)
    d = _avstand_till_linje(f, linje, shape)
    for t in tees:
        d = np.minimum(d, _avstand_till_linje(f, [tuple(t["point"]), tuple(linje[1])], shape))
    return d < bredd_m / 2


def _bitar(m: np.ndarray):
    """Varje sammanhängande del av m för sig, som (mask, ruta) – rutan ger ett litet
    utsnitt så att formmåtten går fort."""
    lab, n = etiketter(m)
    if not n:
        return
    ys, xs = np.nonzero(lab)
    ordn = np.argsort(lab[ys, xs], kind="stable")
    ys, xs = ys[ordn], xs[ordn]
    grans = np.searchsorted(lab[ys, xs], np.arange(1, n + 2))
    for i in range(n):
        y, x = ys[grans[i]:grans[i + 1]], xs[grans[i]:grans[i + 1]]
        k = np.zeros(m.shape, dtype=bool)
        k[y, x] = True
        yield k, (y.min(), y.max() + 1, x.min(), x.max() + 1)


def _tyngdpunkt(m: np.ndarray, f: Fonster) -> tuple[float, float]:
    ys, xs = np.nonzero(m)
    return f.geo(xs.mean() + 0.5, ys.mean() + 0.5)


def spellinje(tee, green_punkt, fairway: np.ndarray, green: np.ndarray, f: Fonster, par: int) -> list:
    """Spellinje utan handpåläggning: bakre tee → fairwayns tyngdpunkt (par 4–5) →
    greenens mitt → greenens bakkant. Klubbarnas längder mäts längs en sådan linje
    mitt i fairway; avviker längdkontrollen ska linjen ritas om för hand."""
    mitt = _tyngdpunkt(green, f) if green.any() else tuple(green_punkt)
    linje = [tuple(tee)]
    if par >= 4 and fairway.any():
        linje.append(tuple(round(float(v), 1) for v in _tyngdpunkt(fairway, f)))
    linje.append(tuple(round(float(v), 1) for v in mitt))
    # förläng förbi mitten till greenens bakkant så att "bak"-avståndet går att mäta
    (ea, na), (eb, nb) = linje[-2], linje[-1]
    L = math.hypot(eb - ea, nb - na) or 1
    ys, xs = np.nonzero(green)
    djup = 0.0
    if len(xs):
        E = f.e0 + (xs + 0.5) * f.res
        N = f.n0 - (ys + 0.5) * f.res
        djup = float((((E - eb) * (eb - ea) + (N - nb) * (nb - na)) / L).max())
    linje.append((round(eb + (eb - ea) / L * djup, 1), round(nb + (nb - na) / L * djup, 1)))
    return linje


def utkast_hal(fro: dict, orto: str | Path, marginal: float = 70.0) -> tuple[dict, Fonster, dict]:
    """Bygger hålfilens innehåll ur fröpunkterna. Returnerar (hål, fönster, masker)."""
    bak = max(fro["tees"], key=lambda t: t.get("length_m") or 0)["point"]
    auto = fro.get("centerline", "auto") == "auto"
    linje = [tuple(bak), tuple(fro["green"])] if auto else [tuple(p) for p in fro["centerline"]]
    alla = linje + [tuple(t["point"]) for t in fro["tees"]] + [tuple(fro["green"])]
    es, ns = [p[0] for p in alla], [p[1] for p in alla]
    bbox = (min(es) - marginal, min(ns) - marginal, max(es) + marginal, max(ns) + marginal)
    f = las_fonster(orto, bbox)
    mt = matt(f)
    kl = klassa(mt)
    if fro.get("laser"):  # Laserdata Skog: vatten och träd ur punkterna i stället för ur färgen
        from .laser import till_fonster, vatten_och_trad
        lv, lt = vatten_och_trad(fro["laser"], fro["hojd"], bbox)
        kl["skog"] = till_fonster(lt > 0, bbox, 1.0, f)
        # dammar med näckrosor/alger ger laserekon men syns på färgen; tak och trädskuggor
        # som färgen tar för vatten har laserhöjd eller ligger under kronor och faller bort
        kl["vatten"] = oppna(till_fonster(lv, bbox, 1.0, f), 2) | (kl["vatten"] & ~vidga(kl["skog"], 3))
        kl["bunker"] &= ~kl["vatten"] & ~kl["skog"]
    korridor = _avstand_till_linje(f, linje, kl["skog"].shape)
    per_m = 1 / f.res

    gr, gk = f.pix(*fro["green"])
    if fro.get("green_polygon"):  # inritad för hand ur fotot, när skuggor gör trollstaven osäker
        green = rastrera(fro["green_polygon"], f, kl["skog"].shape)
    else:
        green = trollstav(mt, gr, gk, tol=fro.get("green_tol", 1.2), max_radie_px=int(fro.get("green_radie", 20) * per_m),
                          utom=kl["bunker"] | kl["vatten"])
    fairway = np.zeros_like(green)
    for p in fro.get("fairway", []):
        r, k = f.pix(*p)
        fairway |= trollstav(mt, r, k, tol=fro.get("fairway_tol", 1.0), utom=kl["bunker"] | kl["vatten"] | kl["skog"])
    fairway &= ~vidga(green, 2)
    if auto:
        linje = spellinje(bak, fro["green"], fairway, green, f, fro["par"])
        korridor = _avstand_till_linje(f, linje, kl["skog"].shape)

    nara_tee = np.zeros_like(green)  # grus, mattor och skyltar vid tee är inga bunkrar
    for t in fro["tees"]:
        r, k = f.pix(*t["point"])
        nara_tee[max(r - int(8 * per_m), 0):r + int(8 * per_m), max(k - int(8 * per_m), 0):k + int(8 * per_m)] = True
    bunkrar = []
    for b, (y0, y1, x0, x1) in _bitar(oppna(kl["bunker"], 1)):
        a = b[y0:y1, x0:x1].sum() * f.res ** 2
        if 4 <= a <= 700 and korridor[b].min() < fro.get("bunker_avstand", 45) \
                and not (b & nara_tee).any() and kompakthet(b[y0:y1, x0:x1]) > 0.25:
            bunkrar += polygoner(b, f, min_m2=4, tol_m=0.3)
    vatten = []
    for v, (y0, y1, x0, x1) in _bitar(oppna(kl["vatten"], 2)):
        a = v[y0:y1, x0:x1].sum() * f.res ** 2
        # stora dammar har flikig strandkant (hål 5: 0,19), små mörka fläckar måste vara runda
        # med laserdata är vattnet uppmätt (inga ekon/LAS 9), så smala ringar runt en green får vara med
        krav = 0.02 if fro.get("laser") else (0.12 if a >= 300 else 0.3)
        if a >= 25 and korridor[v].min() < marginal and kompakthet(v[y0:y1, x0:x1]) > krav \
                and not (a < 100 and (v & nara_tee).any()):  # skuggfläck vid tee
            vatten += polygoner(v, f, min_m2=25, tol_m=0.6)
    skog = oppna(stang(kl["skog"], 2), 3) & (korridor < fro.get("skog_avstand", 55)) & ~vidga(fairway | green, 1)
    skog &= ~spelfri(f, linje, fro["tees"], skog.shape, fro.get("spelfri_m", 12))
    # Skogen delas i rutor om 40 m så att gläntor (andra håls fairways) inte fylls igen –
    # hålfilens polygoner har inga hål, och träden ritas som punkter i ytorna.
    trad = []
    ruta = int(40 / f.res)
    for y in range(0, skog.shape[0], ruta):
        for x in range(0, skog.shape[1], ruta):
            del_ = np.zeros_like(skog)
            del_[y:y + ruta, x:x + ruta] = skog[y:y + ruta, x:x + ruta]
            if del_.any():
                trad += polygoner(del_, f, min_m2=40, tol_m=1.0)

    hal = {
        "club": fro["club"], "hole": fro["hole"], "par": fro["par"], "index": fro.get("index"),
        "source": (f"Ortofoto ©Lantmäteriet ({Path(orto).name}), utkast med trollstav "
                   "(golfholes/utkast.py) från fröpunkter i " + fro.get("_fil", "?") + ". Granskas mot klubbens hålkarta."),
        "origin": [0.0, 0.0],
        "centerline": [list(p) for p in linje],
        "tees": fro["tees"],
        "green": ([list(p) for p in fro["green_polygon"]] if fro.get("green_polygon") else
                  [list(p) for p in max(polygoner(green, f, min_m2=50, tol_m=0.3), key=len, default=[])]),
        "hazards": [{"kind": "bunker", "name": "", "polygon": [list(p) for p in b]} for b in bunkrar]
                   + [{"kind": "water", "name": "", "polygon": [list(p) for p in v]} for v in vatten],
        "fairways": [[list(p) for p in fw] for fw in polygoner(fairway, f, min_m2=150, tol_m=0.6)],
        "trees": [[list(p) for p in t] for t in trad],
        "strategy": fro.get("strategy") or {},
    }
    return hal, f, {"green": green, "fairway": fairway, "skog": skog, **kl}


def rastrera(poly, f: Fonster, shape) -> np.ndarray:
    im = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(im).polygon([((e - f.e0) / f.res, (f.n0 - n) / f.res) for e, n in poly], fill=255)
    return np.array(im) > 0


def kontrollbild(hal: dict, f: Fonster, ut: str | Path, bredd: int = 1400) -> Path:
    """Ortofotot med utkastets former ovanpå – för granskning mot klubbens hålkarta."""
    rgb = np.clip(f.rgbn[..., :3], 0, 255).astype(np.uint8)
    im = Image.fromarray(rgb).convert("RGBA")
    lager = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lager)

    def px(p):
        return ((p[0] - f.e0) / f.res, (f.n0 - p[1]) / f.res)

    def poly(pts, fyll, kant):
        if len(pts) >= 3:
            d.polygon([px(p) for p in pts], fill=fyll, outline=kant, width=2)

    for t in hal["trees"]:
        poly(t, (20, 70, 30, 70), (20, 70, 30, 255))
    for fw in hal["fairways"]:
        poly(fw, (180, 230, 110, 90), (230, 255, 150, 255))
    poly(hal["green"], (90, 220, 90, 120), (255, 255, 255, 255))
    for h in hal["hazards"]:
        poly(h["polygon"], (250, 240, 200, 150) if h["kind"] == "bunker" else (60, 140, 230, 150), (255, 200, 0, 255))
    d.line([px(p) for p in hal["centerline"]], fill=(255, 210, 60, 255), width=3)
    for t in hal["tees"]:
        x, y = px(t["point"])
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
        d.text((x + 9, y - 6), str(t["name"]), fill=(255, 255, 255, 255))
    im = Image.alpha_composite(im, lager).convert("RGB")
    if im.width > bredd:
        im = im.resize((bredd, round(im.height * bredd / im.width)), Image.LANCZOS)
    ut = Path(ut)
    ut.parent.mkdir(parents=True, exist_ok=True)
    im.save(ut, quality=88)
    return ut


def ritverktyg_json(hal: dict, ut: str | Path) -> Path:
    """Utkastet i ritverktygets format, så att det kan rättas i stället för att ritas om."""
    import json

    feats = [{"layer": "tee", "name": str(t["name"]), "pts": [t["point"]]} for t in hal["tees"]]
    feats.append({"layer": "centerline", "name": "", "pts": hal["centerline"]})
    if hal["green"]:
        feats.append({"layer": "green", "name": "", "pts": hal["green"]})
    feats += [{"layer": "fairway", "name": "", "pts": p} for p in hal["fairways"]]
    feats += [{"layer": h["kind"], "name": h.get("name", ""), "pts": h["polygon"]} for h in hal["hazards"]]
    feats += [{"layer": "trees", "name": "", "pts": p} for p in hal["trees"]]
    scorecard = ", ".join(f"{t['name']}={t['length_m']}" for t in hal["tees"] if t.get("length_m"))
    data = {"club": hal["club"], "hole": hal["hole"], "par": hal["par"], "index": hal.get("index"),
            "scorecard": scorecard, "feats": feats}
    ut = Path(ut)
    ut.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return ut
