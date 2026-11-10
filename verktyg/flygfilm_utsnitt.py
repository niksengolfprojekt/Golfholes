"""Kör flygfilmen på det sparade utsnittet (orto.jpg + jgw, hojd.tif, laser) i molnet.

    import verktyg.flygfilm_utsnitt  # före golfholes.render.flygfilm
    → data/<klubb>-utsnitt/{orto,hojd,laser}/ som flygfilm() hittar
"""
from pathlib import Path

import verktyg.orto_utsnitt as ou
from golfholes.render import flygfilm as _ff

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "glasriket-utsnitt"
for kat, src in (("orto", None), ("hojd", ou.LM / "hojd.tif"), ("laser", None)):
    (DATA / kat).mkdir(parents=True, exist_ok=True)
(DATA / "orto" / "orto.tif").touch()
for p, src in ((DATA / "hojd" / "hojd.tif", ou.LM / "hojd.tif"),
               (DATA / "laser" / "y26a023-63050_4900_25.copc.laz", ou.LM / "laser" / "y26a023-63050_4900_25.copc.laz")):
    if not p.exists():
        p.symlink_to(src)


def _hojd(bbox):
    import numpy as np
    from PIL import Image
    s, _, _, _, e0, n0 = (float(v) for v in (ou.LM / "hojd.tfw").read_text().split())
    a = np.asarray(Image.open(ou.LM / "hojd.tif"), np.float32)
    E0, N0 = e0 - s / 2, n0 + s / 2
    x0, y0 = max(0, int((bbox[0] - E0) / s)), max(0, int((N0 - bbox[3]) / s))
    x1 = min(a.shape[1], int(np.ceil((bbox[2] - E0) / s)))
    y1 = min(a.shape[0], int(np.ceil((N0 - bbox[1]) / s)))
    return a[y0:y1, x0:x1, None], E0 + x0 * s, N0 - y0 * s, s


def _rw(path, bbox):
    if Path(path).parent.name == "orto":
        return ou.read_window_jpg(ou.LM / "orto.jpg", bbox)
    if Path(path).parent.name == "hojd":
        return _hojd(bbox)
    return ou._riktig(path, bbox)


_ff.read_window = _rw


from golfholes.render import foto as _foto  # noqa: E402

_foto.read_window = lambda path, bbox: (ou.read_window_jpg(ou.LM / "orto.jpg", bbox) if Path(path).parent == DATA / "orto"
                                        else ou.read_window_jpg(path, bbox))
