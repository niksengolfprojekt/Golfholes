"""Färga om en hålbild i klubbens färger och rita spelinformationen ovanpå.

Stilen (teknik, penseldrag, linjer) behålls; färgerna byts mot klubbens tonskala.
Ljusheten styr vilken ton varje pixel får, så läsbarhetsregeln håller i alla
paletter: skog mörkast, ruff mörkare, fairway ljus, green ljusast.
Prickar och flagga ritas av koden, så de ser likadana ut i alla stilar och färger.

    python verktyg/klubbfarg.py in.png ut.png "#10202e,#1d4756,#3f7f86,#9cc9c3,#eef3ec" [--flagga "#e0a22a"]
"""
import argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# Spelinformation för Glasriket hål 14 i hålbildens ram (1192 x 2114 px).
MARKERS = {"rod": ((473, 536), (200, 44, 44)), "gul": ((317, 737), (240, 196, 40))}
FLAG = {"stang": ((915, 205), (915, 274)), "duk": [(916, 205), (952, 215), (916, 225)]}


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def sudda_spelinfo(a):
    """Ta bort AI:ns egna prickar och flagga (de hamnar några pixlar fel) innan koden ritar nya."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mattad = (a[..., :3].max(-1) - a[..., :3].min(-1)) > 80
    rod = mattad & (r > g + 60) & (r > b + 60)
    gul = mattad & (r > 150) & (g > 120) & (b < 110)
    platser = [xy for xy, _ in MARKERS.values()] + [(930, 225)]
    for x, y in platser:
        R = 60
        y0, y1, x0, x1 = max(0, y - R), y + R, max(0, x - R), x + R
        m = (rod | gul)[y0:y1, x0:x1].copy()
        # mörka prickar (t.ex. i screentrycket) nära markören
        lum = a[y0:y1, x0:x1, :3].mean(-1)
        yy, xx = np.mgrid[y0:y0 + lum.shape[0], x0:x0 + lum.shape[1]]
        nara = (yy - y) ** 2 + (xx - x) ** 2 < 40 ** 2
        mork = nara & (lum < np.median(lum) - 40)
        # bara kompakta prickar, inte gravyrens tunna linjer: erodera bort linjer, väx tillbaka
        mork = Image.fromarray((mork * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(9)).filter(ImageFilter.MaxFilter(13))
        m |= np.asarray(mork) > 0
        if not m.any():
            continue
        mm = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(11))) > 0
        fond = a[y0:y1, x0:x1][~mm]
        if len(fond):
            a[y0:y1, x0:x1][mm] = np.median(fond, 0)
    return a


def omfarga(im: Image.Image, ramp, flagga=(224, 162, 42)) -> Image.Image:
    im = im.convert("RGBA")
    a = sudda_spelinfo(np.asarray(im).astype(float).copy())
    alpha = a[..., 3]
    lum = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    inne = lum[alpha > 200]
    lo, hi = np.percentile(inne, 2), np.percentile(inne, 99)
    t = np.clip((lum - lo) / (hi - lo), 0, 1)
    stops = np.array([hexrgb(c) for c in ramp], float)
    pos = np.linspace(0, 1, len(stops))
    ut = np.stack([np.interp(t, pos, stops[:, k]) for k in range(3)], -1)
    res = Image.fromarray(np.dstack([ut, alpha]).astype(np.uint8), "RGBA")
    rita_spelinfo(res, flagga)
    return res


def rita_spelinfo(im, flagga):
    s = 4  # rita i fyrdubbel storlek för mjuka kanter
    lager = Image.new("RGBA", (im.width * s, im.height * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(lager)
    for (x, y), farg in MARKERS.values():
        r = 15
        d.ellipse([(x - r - 3) * s, (y - r - 3) * s, (x + r + 3) * s, (y + r + 3) * s], fill=(255, 255, 255, 235))
        d.ellipse([(x - r) * s, (y - r) * s, (x + r) * s, (y + r) * s], fill=farg + (255,))
    (x0, y0), (x1, y1) = FLAG["stang"]
    d.rectangle([(x0 - 2) * s, y0 * s, (x0 + 2) * s, y1 * s], fill=(30, 30, 30, 255))
    d.polygon([(x * s, y * s) for x, y in FLAG["duk"]], fill=tuple(flagga) + (255,))
    im.alpha_composite(lager.resize(im.size, Image.LANCZOS))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("inp"); p.add_argument("ut"); p.add_argument("ramp")
    p.add_argument("--flagga", default="#e0a22a")
    a = p.parse_args()
    omfarga(Image.open(a.inp), a.ramp.split(","), hexrgb(a.flagga)).save(a.ut)
