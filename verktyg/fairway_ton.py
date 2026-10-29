"""Ny fairwaybit i en redan målad hålbild (Eric 2026-10-29, hål 1: fairway är sammanhängande).
När en fairwaypolygon läggs till i hålfilen efter målningen ligger den nya biten kvar i ruffens
färg. Det här tonar biten mot resten av fairwayns färg och ljus (medel och spridning per kanal),
så gräset och dess detaljer blir kvar men ytan läses som fairway. Inga krediter, ingen ny form.

    python verktyg/fairway_ton.py klubbar/glasriket/hal-01.yaml 2 [--namn a5]

2 = fairwaypolygonens nummer i hålfilen (räknat från 0). Kör före fairway_frisk.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verktyg.orto_utsnitt  # noqa: E402,F401
from golfholes.hole import Hole  # noqa: E402
from golfholes.render.foto import fotounderlag, orto_for  # noqa: E402
from verktyg.fairway_frisk import _blur, prickmask  # noqa: E402
from verktyg.skuggskydd import _mask  # noqa: E402


def tona(im: Image.Image, hole: Hole, px, nr: int) -> float:
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    rgb = a[..., :3]
    ovriga = [f for i, f in enumerate(hole.fairways) if i != nr]
    gammal = np.asarray(_mask(im, ovriga, px, 0), np.float32) / 255
    ny = np.asarray(_mask(im, [hole.fairways[nr]], px, 0), np.float32) / 255
    bort = [h.polygon for h in hole.hazards]
    if bort:
        ny *= 1 - np.asarray(_mask(im, bort, px, 0), np.float32) / 255
    w = np.clip(_blur(ny * (1 - gammal), 3), 0, 1) * ~prickmask(rgb)
    kalla, mal = w > 0.5, (gammal > 0.5) & ~prickmask(rgb)
    if kalla.sum() < 50 or mal.sum() < 50:
        return 0.0
    mk, sk = rgb[kalla].mean(0), rgb[kalla].std(0) + 1
    mm, sm = rgb[mal].mean(0), rgb[mal].std(0) + 1
    ut = np.clip((rgb - mk) / sk * sm + mm, 0, 255)
    a[..., :3] = rgb * (1 - w[..., None]) + ut * w[..., None]
    im.paste(Image.fromarray(a.astype(np.uint8), "RGBA"))
    return float(kalla.sum())


def kor(hf: Path, nr: int, namn: str = "a5") -> None:
    hole = Hole.from_yaml(hf)
    club = hf.parent
    for f in (club / "halbilder" / f"hal-{hole.number:02d}-{namn}.webp",
              club / "halbilder" / f"hal-{hole.number:02d}-{namn}-utan-flagga.webp"):
        if not f.exists():
            continue
        im = Image.open(f).convert("RGBA")
        _, px = fotounderlag(hole, orto_for(Path("data") / club.name), im.height)
        n = tona(im, hole, px, nr)
        im.save(f, quality=92)
        print(f, f"{n:.0f} bildpunkter tonade")


if __name__ == "__main__":
    namn = sys.argv[sys.argv.index("--namn") + 1] if "--namn" in sys.argv else "a5"
    kor(Path(sys.argv[1]), int(sys.argv[2]), namn)
