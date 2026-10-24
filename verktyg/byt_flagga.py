"""Byt flaggan på en färdig målad hålbild utan att måla om hålet (inga krediter).

Hålbilden `halbilder/hal-NN-malad.webp` har en flagga inbränd. Flaggan ritades av koden, så vi
vet exakt hur den ser ut och var den står. Verktyget
1. hittar den gamla flaggan (TACADA-flaggan med T, eller den äldre gula) i bilden – letar runt
   den beräknade punkten efter flaggdukens färg, så att en flagga som står lite fel också hittas,
2. tar bort duk, stång, hålkopp och slagskugga. Finns AI-målningen kvar (`--malningar`) tas ytan
   under flaggan ur den – exakt som den målades. Annars lagas ytan med små rutor ur gräset runt
   omkring (samma ränder och korn) och färgen jämnas mot kanten,
3. sparar den lagade bilden som `hal-NN-malad-utan-flagga.webp` (målningen med prickar, utan
   flagga och outlinje) – nästa flaggbyte börjar därifrån och behöver inte sudda något,
4. ritar outlinjer (hålfilens `ob`) och klubbens flagga (`flagga:` i klubb.yaml) på
   `flagga_punkt` / greenens mitt med samma kod som `aibild`.

    python verktyg/byt_flagga.py klubbar/glasriket/hal-07.yaml [fler hålfiler]
    python verktyg/byt_flagga.py klubbar/glasriket/hal-07.yaml --malningar data/glasriket/ai/h07/*.png
    python verktyg/byt_flagga.py --gul klubbar/glasriket/hal-07.yaml   # den gamla gula flaggan
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from golfholes.hole import Hole  # noqa: E402
from golfholes.render.foto import (  # noqa: E402
    _flagga, _tyngdpunkt, flaggstil, fotounderlag, orto_for, pa_formen, rita_flagga_och_ob, utan_flagga,
)


def gammal_mask(size, x: float, y: float, s: float) -> np.ndarray:
    """Var kodens gamla gula flagga låg: stång, gul trekant och hålkopp, med lite marginal."""
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    stang = 30 * s
    d.line((x, y + 2 * s, x, y - stang - 1 * s), fill=255, width=max(3, int(4 * s)))
    d.polygon([(x - 1 * s, y - stang - 2 * s), (x + 19 * s, y - stang + 5 * s), (x - 1 * s, y - stang + 13 * s)], fill=255)
    d.ellipse((x - 4 * s, y - 3 * s, x + 4 * s, y + 3 * s), fill=255)
    return np.asarray(m.filter(ImageFilter.MaxFilter(5))) > 0


def t_flagga(size, x: float, y: float, s: float) -> tuple[np.ndarray, np.ndarray]:
    """T-flaggan ritad på tom bakgrund: (allt den täcker inkl. skugga, bara duken)."""
    lag = Image.new("RGBA", size, (0, 0, 0, 0))
    _flagga(lag, x, y, s)
    a = np.asarray(lag)
    allt = a[..., 3] > 2
    duk = (a[..., 3] > 200) & (a[..., 0] > a[..., 1] + 20)
    return allt, duk


def t_skugga(size, x: float, y: float, s: float) -> np.ndarray:
    """T-flaggans mjuka slagskugga som täckning 0–1 (samma geometri som _flagga utan stil)."""
    k = 4
    w, h = int(70 * s), int(56 * s)
    ox, oy = 14 * s * k, (h - 8 * s) * k
    S = s * k
    stang, fl, fh = 27 * S, 19 * S, 13 * S
    sk = Image.new("L", (w * k, h * k), 0)
    ds = ImageDraw.Draw(sk)
    dx, dy = 1.05, -0.38
    topp = (ox + stang * dx, oy + stang * dy)
    ds.line((ox, oy, *topp), fill=185, width=int(1.3 * S))
    ds.polygon([topp, (topp[0] - fl * 0.22, topp[1] - fl * 0.66 + 2 * S),
                (ox + (stang - fh * 0.7) * dx, oy + (stang - fh * 0.7) * dy)], fill=160)
    sk = sk.filter(ImageFilter.GaussianBlur(1.1 * S)).resize((w, h), Image.LANCZOS)
    ut = Image.new("L", size, 0)
    ut.paste(sk, (int(x - ox / k), int(y - oy / k)))
    return np.asarray(ut, np.float64) / 255


SKUGGFARG = np.array([10, 30, 10], np.float64)


def ta_bort_skugga(rgb: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Skuggan lades som (10, 30, 10) med täckning a: ursprunget = (bild − a·färg) / (1 − a)."""
    a3 = np.clip(a, 0, 0.85)[..., None]
    ut = (rgb.astype(np.float64) - a3 * SKUGGFARG) / (1 - a3)
    return np.clip(ut, 0, 255)


def _rod(rgb: np.ndarray) -> np.ndarray:
    r, g, b = (rgb[..., i].astype(np.int16) for i in range(3))
    return (r > g + 25) & (r > b + 5) & (r < 200)


def hitta_t(bit: np.ndarray, x: float, y: float, s: float, sok: int = 60) -> tuple[float, float, float]:
    """Flyttar mallen runt (x, y) och ger läget där flest av dukens pixlar är vinröda."""
    rod = _rod(bit[..., :3])
    _, duk = t_flagga((bit.shape[1], bit.shape[0]), x, y, s)
    ys, xs = np.nonzero(duk)
    bast = (-1.0, 0, 0)
    for dy in range(-sok, sok + 1, 2):
        for dx in range(-sok, sok + 1, 2):
            yy, xx = ys + dy, xs + dx
            ok = (yy >= 0) & (yy < rod.shape[0]) & (xx >= 0) & (xx < rod.shape[1])
            andel = rod[yy[ok], xx[ok]].sum() / len(ys)
            if andel > bast[0]:
                bast = (andel, dx, dy)
    # finjustera på pixelnivå
    a0, dx0, dy0 = bast
    for dy in range(dy0 - 2, dy0 + 3):
        for dx in range(dx0 - 2, dx0 + 3):
            yy, xx = ys + dy, xs + dx
            ok = (yy >= 0) & (yy < rod.shape[0]) & (xx >= 0) & (xx < rod.shape[1])
            andel = rod[yy[ok], xx[ok]].sum() / len(ys)
            if andel > bast[0]:
                bast = (andel, dx, dy)
    return x + bast[1], y + bast[2], bast[0]


def fyll(rgb: np.ndarray, mask: np.ndarray, varv: int = 400) -> np.ndarray:
    """Fyll maskade pixlar inifrån kanten med medelvärdet av fyllda grannar (enkel diffusion)."""
    ut = rgb.astype(np.float32).copy()
    kvar = mask.copy()
    for _ in range(varv):
        if not kvar.any():
            break
        kant_sum = np.zeros_like(ut)
        kant_n = np.zeros(kvar.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            ok = np.roll(~kvar, (dy, dx), axis=(0, 1))
            kant_sum += np.roll(ut, (dy, dx), axis=(0, 1)) * ok[..., None]
            kant_n += ok
        ny = kvar & (kant_n > 0)
        ut[ny] = kant_sum[ny] / kant_n[ny][:, None]
        kvar &= ~ny
    return ut


RUTA, OMGIVNING, LAGFARG = 2.5, 5.0, 5.0  # i enheter av s (bildhöjd/1000)


def _oskarp(a: np.ndarray, r: float) -> np.ndarray:
    """Tre boxfilter i rad (≈ gaussisk oskärpa) med kantvärdena utdragna."""
    k = max(1, int(round(r)))
    for ax in (0, 1):
        for _ in range(3):
            pad = [(0, 0), (0, 0)]
            pad[ax] = (k + 1, k)
            c = np.cumsum(np.pad(a, pad, mode="edge"), axis=ax)
            a = (np.take(c, range(2 * k + 1, c.shape[ax]), axis=ax) - np.take(c, range(0, c.shape[ax] - 2 * k - 1), axis=ax)) / (2 * k + 1)
    return a


def _korr(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Korskorrelation via FFT: C[dy, dx] = sum_u A[u + d] * B[u] för alla förskjutningar d
    där B (litet fönster) ligger helt inne i A."""
    H, W = A.shape
    h, w = B.shape
    F = np.fft.irfft2(np.fft.rfft2(A) * np.conj(np.fft.rfft2(B, s=(H, W))), s=(H, W))
    return F[: H - h + 1, : W - w + 1]


def laga(bit: np.ndarray, mask: np.ndarray, s: float) -> np.ndarray:
    """Lagar `mask` bit för bit med rutor ur gräset runt omkring (exempelbaserad ifyllnad):
    för varje liten ruta letas den plats i närheten vars omgivning stämmer bäst med det som
    redan är känt runt rutan (ränder, skugga, korn), och rutans saknade pixlar kopieras därifrån.
    Rutorna fylls utifrån och in, så att ränder och skuggkanter fortsätter genom lagningen."""
    rgb = bit[..., :3].astype(np.float64)
    H, W = mask.shape
    kand = ~(np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))) > 0)
    kand &= bit[..., 3] > 250  # källor: bara synlig, orörd yta
    kand_f = kand.astype(np.float64)
    kvar = mask.copy()
    b = max(4, int(RUTA * s))   # rutans sida
    m = max(4, int(OMGIVNING * s))  # omgivning som jämförs
    R = int(60 * s)             # hur långt bort källan får ligga
    ys, xs = np.nonzero(mask)
    rutor = {(y // b * b, x // b * b) for y, x in zip(ys, xs)}
    while rutor:
        # rutan med mest känd omgivning först (utifrån och in)
        def kant(r):
            y0, x0 = r
            f = kvar[max(0, y0 - m): y0 + b + m, max(0, x0 - m): x0 + b + m]
            return (~f).mean()
        r = max(rutor, key=kant)
        rutor.discard(r)
        y0, x0 = r
        wy0, wx0 = max(0, y0 - m), max(0, x0 - m)
        wy1, wx1 = min(H, y0 + b + m), min(W, x0 + b + m)
        T = rgb[wy0:wy1, wx0:wx1]
        K = (~kvar[wy0:wy1, wx0:wx1]).astype(np.float64)
        h, w = K.shape
        sy0, sx0 = max(0, wy0 - R), max(0, wx0 - R)
        sy1, sx1 = min(H, wy1 + R), min(W, wx1 + R)
        S = rgb[sy0:sy1, sx0:sx1]
        Kd = kand_f[sy0:sy1, sx0:sx1]
        kost = _korr((S ** 2).sum(-1), K)
        for c in range(3):
            kost -= 2 * _korr(S[..., c], K * T[..., c])
        giltig = _korr(Kd, np.ones((h, w))) > h * w - 0.5  # hela källfönstret orört
        if not giltig.any():
            continue
        kost[~giltig] = np.inf
        dy, dx = np.unravel_index(np.argmin(kost), kost.shape)
        src = rgb[sy0 + dy: sy0 + dy + h, sx0 + dx: sx0 + dx + w]
        fyll_har = kvar[wy0:wy1, wx0:wx1] & np.zeros_like(K, bool)
        fyll_har[(y0 - wy0):(y0 - wy0 + b), (x0 - wx0):(x0 - wx0 + b)] = True
        fyll_har &= kvar[wy0:wy1, wx0:wx1]
        T[fyll_har] = src[fyll_har]
        kvar[wy0:wy1, wx0:wx1] &= ~fyll_har
    if kvar.any():  # något kvar (ingen källa): diffusion
        rgb = fyll(rgb, kvar)
    # färg och ljus i stort från en jämn utfyllnad från kanten (följer rundade band och
    # skuggkanter), struktur och korn från rutorna: lagningen = rutor + utjämnad skillnad
    jamn = fyll(bit[..., :3].astype(np.float64), mask)
    skillnad = (jamn - rgb) * mask[..., None]
    r = max(1.0, LAGFARG * s)
    vikt = _oskarp(mask.astype(np.float64), r)
    sk = np.stack([_oskarp(skillnad[..., c], r) for c in range(3)], -1)
    ut = rgb.copy()
    ut[mask] += (sk / np.maximum(vikt, 1e-3)[..., None])[mask]
    return ut


def _ur_malningen(rot, malningar, bit, mask, hörn):
    """Finns AI-målningen kvar (utan flagga) tas ytan under flaggan direkt ur den: den målning
    som efter samma placering som aibild stämmer med bilden runt flaggan (medianfel < 3 av 255)."""
    x0, y0 = hörn
    h, w = mask.shape
    ring = (np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(41))) > 0) & ~mask
    bast = (1e9, None, None)
    for fil in malningar:
        m = np.asarray(pa_formen(rot, fil).crop((x0, y0, x0 + w, y0 + h)), np.float64)[..., :3]
        fel = float(np.median(np.abs(m[ring] - bit[..., :3][ring].astype(np.float64))))
        if fel < bast[0]:
            bast = (fel, fil, m)
    if bast[1] is not None:
        print(f"  bästa målning {bast[1]}: medianfel {bast[0]:.1f}")
    return bast[2] if bast[0] < 3 else None


def byt(halfil: Path, gul: bool = False, malningar: list[Path] | None = None) -> Path:
    hole = Hole.from_yaml(halfil)
    klubb = halfil.parent
    bild = klubb / "halbilder" / f"hal-{hole.number:02d}-malad.webp"
    ren = utan_flagga(bild)
    rot, px = fotounderlag(hole, orto_for(Path("data") / klubb.name), Image.open(bild).height)
    if ren.exists():
        im = Image.open(ren).convert("RGBA")
        print(f"  {ren.name} finns – börjar från den, inget att sudda")
    else:
        im = Image.open(bild).convert("RGBA")
        if rot.size != im.size:
            raise SystemExit(f"{bild.name} passar inte hålfilen ({im.size} mot {rot.size})")
        s = im.height / 1000
        x, y = px(*_tyngdpunkt(hole.green))  # där flaggan ritades förut
        r = int(110 * s)
        x0, y0 = max(0, int(x) - r), max(0, int(y) - r)
        bit = np.asarray(im.crop((x0, y0, x0 + 2 * r, y0 + 2 * r))).copy()
        if gul:
            mask = gammal_mask((bit.shape[1], bit.shape[0]), x - x0, y - y0, s)
        else:
            fx, fy, andel = hitta_t(bit, x - x0, y - y0, s)
            if andel < 0.6:
                raise SystemExit(f"Hål {hole.number}: hittar ingen T-flagga nära greenens mitt (bäst {andel:.0%}).")
            print(f"  T-flaggan hittad {fx - (x - x0):+.0f}, {fy - (y - y0):+.0f} px från greenens mitt ({andel:.0%} av duken)")
            mask, _ = t_flagga((bit.shape[1], bit.shape[0]), fx, fy, s)
            skugga = t_skugga((bit.shape[1], bit.shape[0]), fx, fy, s)
            if not malningar:
                # skuggan räknas bort exakt (vi vet färg och täckning); bara stång, duk och kopp lagas
                bit[..., :3] = np.where((skugga > 0.004)[..., None], ta_bort_skugga(bit[..., :3], skugga), bit[..., :3]).astype(np.uint8)
                lag_ = Image.new("RGBA", (bit.shape[1], bit.shape[0]), (0, 0, 0, 0))
                _flagga(lag_, fx, fy, s)
                tackt = np.asarray(lag_)[..., 3] / 255.0
                mask = ((tackt - skugga) > 0.02) | (skugga > 0.8)
            mask = np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(2 * int(2 * s) + 1))) > 0
        kalla = _ur_malningen(rot, malningar or [], bit, mask, (x0, y0))
        if kalla is not None:
            rgb = bit[..., :3].astype(np.float64)
            rgb[mask] = kalla[mask]
        else:
            rgb = laga(bit, mask, s)
            brus = np.random.default_rng(hole.number).normal(0, 1.0, rgb.shape)
            rgb[mask] = np.clip(rgb[mask] + brus[mask], 0, 255)
        bit[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
        im.paste(Image.fromarray(bit, "RGBA"), (x0, y0))
        im.save(ren, quality=92)
    rita_flagga_och_ob(im, hole, px, flaggstil(klubb))
    im.save(bild, quality=92)
    return bild


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("halfiler", nargs="+")
    ap.add_argument("--gul", action="store_true", help="den gamla gula flaggan i stället för T-flaggan")
    ap.add_argument("--malningar", nargs="*", default=[],
                    help="AI-målningarna (utan flagga) om de finns kvar: ytan under flaggan tas då ur rätt målning")
    a = ap.parse_args()
    for f in a.halfiler:
        print(byt(Path(f), gul=a.gul, malningar=[Path(m) for m in a.malningar]))
