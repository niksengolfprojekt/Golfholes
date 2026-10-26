"""Kör kodens ortofoto-steg på det sparade utsnittet (orto.jpg + orto.jgw) i stället
för Lantmäteriets 1 GB-ruta, som inte följer med mellan molnsessionerna.

    import verktyg.orto_utsnitt  # före golfholes.render.*

Utsnittet har bara RGB; fjärde bandet (nära IR) uppskattas ur grönt, så det duger
för läget (px) och siluetten men inte för en ny skogsklassning.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
# GOLF_KLUBB = klubbens mapp (standard glasriket). GOLF_LM = mappen med orto.jpg/.jgw, hojd.tif,
# lantmateriet.json och laser/*.copc.laz (standard: Glasrikets utsnitt i projektmappen).
KLUBB = os.environ.get("GOLF_KLUBB", "glasriket")
LM = Path(os.environ.get("GOLF_LM", "/mnt/project-files/glasriket/lantmateriet"))
ROOT = Path(__file__).resolve().parents[1]
_bild = None


def _orto():
    global _bild
    if _bild is None:
        _bild = np.asarray(Image.open(LM / "orto.jpg").convert("RGB"))
    return _bild


def read_window_jpg(path, bbox):
    if not str(path).endswith(".jpg"):
        return _riktig(path, bbox)
    s, _, _, s2, e0, n0 = (float(v) for v in (LM / "orto.jgw").read_text().split())
    res = s
    E0, N0 = e0 - res / 2, n0 + res / 2  # övre vänstra pixelkanten
    a = _orto()
    x0, y0 = max(0, int((bbox[0] - E0) / res)), max(0, int((N0 - bbox[3]) / res))
    x1, y1 = min(a.shape[1], int(np.ceil((bbox[2] - E0) / res))), min(a.shape[0], int(np.ceil((N0 - bbox[1]) / res)))
    rgb = a[y0:y1, x0:x1]
    g = rgb[..., 1].astype(np.float32)
    nir = np.clip(g * 1.35 - rgb[..., 0] * 0.2, 0, 255).astype(np.uint8)
    return np.dstack([rgb, nir]), E0 + x0 * res, N0 - y0 * res, res


_d = ROOT / "data" / KLUBB
if not list((_d / "orto").glob("*.tif")):  # bara utsnittet finns; är rutan nyss hämtad används den direkt
    from golfholes import lantmateriet as _lm  # noqa: E402
    from golfholes.render import foto as _foto  # noqa: E402

    _riktig = _lm.read_window
    _foto.read_window = read_window_jpg

    # orto_for läser data/<klubb>/lantmateriet.json – peka den på utsnittet
    _d.mkdir(parents=True, exist_ok=True)
    _logg = json.loads((LM / "lantmateriet.json").read_text(encoding="utf-8"))
    for f in _logg["filer"]:
        if f["katalog"] == "orto":
            f["fil"] = str(LM / "orto.jpg")
    (_d / "lantmateriet.json").write_text(json.dumps(_logg, ensure_ascii=False, indent=1), encoding="utf-8")
