"""Tvätta bort AI-ränder i bildkanten (där ortofotots utsnitt tar slut och AI:n drar ut vågräta streck).

    python verktyg/kant_tvatt.py klubbar/glasriket/halbilder/hal-08-a5.webp [fler...]

Ränderna letas i hålets lyft-underlag (hal-NN-lyft.webp), där utsnittets kant syns som vågräta streck
(jämnt i sidled, hackigt i höjdled), inte i målningen: där skulle mörk skog också slå ut. De ytorna
(med marginal) tonas till bildens egen bakgrundsfärg med mjuk kant. `--i-bilden` letar även ränder i själva målningen (bara på hål där
de syns: mörk skog kan annars slå ut); -utan-flagga-versionen tvättas med samma mask. Bilder utan ränder lämnas orörda.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def _std(a, r, ax):
    k = 2 * r + 1

    def box(x):
        p = np.pad(x, [(r + 1, r) if i == ax else (0, 0) for i in range(2)], mode="edge").cumsum(ax)
        n = p.shape[ax]
        return (np.take(p, range(k, n), ax) - np.take(p, range(0, n - k), ax)) / k

    m = box(a)
    return np.sqrt(np.clip(box(a * a) - m * m, 0, None))


def randmask(im):
    g = np.asarray(im.convert("L"), dtype=np.float32)
    m = Image.fromarray((((_std(g, 20, 1) < 3) & (_std(g, 20, 0) > 10)) * 255).astype(np.uint8))
    m = m.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.MinFilter(31))  # bara sammanhängande ränder
    if not np.asarray(m).any():
        return None
    m = m.filter(ImageFilter.MaxFilter(81))  # täck hela randen och lite till
    return np.asarray(m.filter(ImageFilter.GaussianBlur(25)), dtype=np.float32)[..., None] / 255


def tvatta(fil):
    fil = Path(fil)
    im = Image.open(fil)
    lyft = Image.open(fil.with_name(fil.name.split("-a")[0] + "-lyft.webp")).convert("RGB").resize(im.size)
    m = [x for x in (randmask(lyft), randmask(im) if "--i-bilden" in sys.argv else None) if x is not None]
    m = np.maximum.reduce(m) if m else None
    if m is None:
        print(fil, "inga ränder")
        return
    for f in (fil, fil.with_name(fil.stem + "-utan-flagga.webp")):
        if f.exists():
            a = np.asarray(Image.open(f).convert("RGB"), dtype=np.float32)
            bg = np.median(a[:40, :40].reshape(-1, 3), axis=0)
            Image.fromarray((a * (1 - m) + bg * m).astype(np.uint8)).save(f, quality=92)
            print(f, f"{(m > 0.5).mean():.1%} tvättat")


if __name__ == "__main__":
    for f in [a for a in sys.argv[1:] if not a.startswith("--")]:
        tvatta(f)
