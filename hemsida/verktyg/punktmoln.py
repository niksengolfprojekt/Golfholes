"""Gör ett punktmoln av ett riktigt hål till startsidan.

Läser Lantmäteriets laserdata (COPC/LAZ) och ortofoto, klipper ut hålet med marginal,
färgar varje punkt från ortofotot och sparar en kompakt binärfil för webben:
uint32 antal, sedan antal × (3 × int16 position i dm kring hålets mitt, 3 × uint8 färg).
Kräver laspy + lazrs och numpy (körs lokalt, inte i sajtbygget).
"""
import struct
import sys
from pathlib import Path

import laspy
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def las_jgw(fil):
    a, _, _, e, x0, y0 = [float(v) for v in Path(fil).read_text().split()]
    return a, e, x0, y0


def main(laz, orto, jgw, ut, xmin, ymin, xmax, ymax, max_punkter=160000):
    las = laspy.read(laz)
    x, y, z = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)
    klass = np.asarray(las.classification)
    m = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax) & np.isin(klass, [1, 2])
    x, y, z, klass = x[m], y[m], z[m], klass[m]
    rng = np.random.default_rng(14)
    # Marken bär formen, träden ramar in: behåll mer mark än vegetation.
    mark = np.flatnonzero(klass == 2)
    veg = np.flatnonzero(klass == 1)
    n_mark = min(len(mark), int(max_punkter * 0.62))
    n_veg = min(len(veg), max_punkter - n_mark)
    val = np.concatenate([rng.choice(mark, n_mark, replace=False), rng.choice(veg, n_veg, replace=False)])
    x, y, z = x[val], y[val], z[val]

    a, e, x0, y0 = las_jgw(jgw)
    bild = Image.open(orto)
    k0, r0 = int((xmin - x0) / a), int((ymax - y0) / e)
    k1, r1 = int((xmax - x0) / a) + 1, int((ymin - y0) / e) + 1
    utsnitt = np.asarray(bild.crop((k0, r0, k1, r1)).convert("RGB"))
    kol = np.clip(((x - x0) / a - k0).astype(int), 0, utsnitt.shape[1] - 1)
    rad = np.clip(((y - y0) / e - r0).astype(int), 0, utsnitt.shape[0] - 1)
    farg = utsnitt[rad, kol]

    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    cz = np.percentile(z, 5)
    pos = np.stack([(x - cx) * 10, (y - cy) * 10, (z - cz) * 10], axis=1).round().astype("<i2")
    with open(ut, "wb") as f:
        f.write(struct.pack("<I", len(pos)))
        f.write(pos.tobytes())
        f.write(farg.astype(np.uint8).tobytes())
    print(f"{len(pos)} punkter -> {ut} ({Path(ut).stat().st_size // 1024} kB)")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[2], a[3], *map(float, a[4:8]))
