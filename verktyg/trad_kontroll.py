"""Kontroll: stämmer laserdatans träd (som flygfilmen bygger på) med ortofotot?

    python verktyg/trad_kontroll.py e0,n0,e1,n1 <ut.jpg>

Ritar trädkronornas kant ur Laserdata Skog (träd ≥ 2 m) i cyan på ortofotot. Där
fotot visar träd utan cyan kant saknas de i filmens underlag; cyan kant utan träd i
fotot = träd som fällts efter laserskanningen (eller byggnad)."""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verktyg.flygfilm_utsnitt as fu  # noqa: E402
import verktyg.orto_utsnitt as ou  # noqa: E402
from golfholes.laser import tradhojd  # noqa: E402


def main(bbox, ut):
    rgb, e0, n0, res = ou.read_window_jpg(ou.LM / "orto.jpg", bbox)
    rgb = Image.fromarray(np.ascontiguousarray(rgb[..., :3]))
    lr = 0.5
    b = (e0, n0 - rgb.height * res, e0 + rgb.width * res, n0)
    m, me0, mn0, ms = fu._hojd(b)
    lw, lh = int(round((b[2] - b[0]) / lr)), int(round((b[3] - b[1]) / lr))
    mark = np.asarray(Image.fromarray(m[..., 0]).resize((lw, lh), Image.BILINEAR), np.float32)
    laz = sorted((fu.DATA / "laser").glob("*.laz"))[0]
    th = tradhojd(laz, mark, b, res=lr)
    mask = Image.fromarray(((th > 0) * 255).astype(np.uint8)).resize(rgb.size, Image.NEAREST)
    kant = np.asarray(mask.filter(ImageFilter.MaxFilter(5))) ^ np.asarray(mask)
    a = np.asarray(rgb).copy()
    a[kant > 0] = (0, 230, 255)
    Image.fromarray(a).save(ut, quality=88)
    print(f"trädyta i laser: {(th > 0).mean() * 100:.1f} %")


if __name__ == "__main__":
    main(tuple(float(v) for v in sys.argv[1].split(",")), sys.argv[2])
