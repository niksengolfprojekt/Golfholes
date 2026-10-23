"""Byt den gamla gula flaggan mot TACADA-flaggan på en färdig målad hålbild.

Hålbilder målade före TACADA-flaggan (2026-10-21) har kodens gula flagga inbränd. I stället för
att måla om hålet (krediter) tas den gamla flaggan bort – den ritades av koden, så vi vet exakt
var den ligger – ytan fylls från omgivande gräs och den nya flaggan ritas med samma kod som aibild.

    python verktyg/byt_flagga.py klubbar/glasriket/hal-07.yaml [fler hålfiler]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from golfholes.hole import Hole  # noqa: E402
from golfholes.render.foto import _flagga, _tyngdpunkt, fotounderlag, orto_for  # noqa: E402


def gammal_mask(size, x: float, y: float, s: float) -> np.ndarray:
    """Var kodens gamla flagga låg: stång, gul trekant och hålkopp, med lite marginal."""
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    stang = 30 * s
    d.line((x, y + 2 * s, x, y - stang - 1 * s), fill=255, width=max(3, int(4 * s)))
    d.polygon([(x - 1 * s, y - stang - 2 * s), (x + 19 * s, y - stang + 5 * s), (x - 1 * s, y - stang + 13 * s)], fill=255)
    d.ellipse((x - 4 * s, y - 3 * s, x + 4 * s, y + 3 * s), fill=255)
    return np.asarray(m.filter(ImageFilter.MaxFilter(5))) > 0


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


def byt(halfil: Path) -> Path:
    hole = Hole.from_yaml(halfil)
    klubb = halfil.parent
    bild = klubb / "halbilder" / f"hal-{hole.number:02d}-malad.webp"
    im = Image.open(bild).convert("RGBA")
    rot, px = fotounderlag(hole, orto_for(Path("data") / klubb.name), im.height)
    if rot.size != im.size:
        raise SystemExit(f"{bild.name} passar inte hålfilen ({im.size} mot {rot.size})")
    s = im.height / 1000
    x, y = px(*_tyngdpunkt(hole.green))
    # arbeta i ett utsnitt runt flaggan (snabbt och påverkar inget annat)
    r = int(60 * s)
    x0, y0 = max(0, int(x) - r), max(0, int(y) - r)
    bit = np.asarray(im.crop((x0, y0, x0 + 2 * r, y0 + 2 * r)))
    mask = gammal_mask((bit.shape[1], bit.shape[0]), x - x0, y - y0, s)
    rgb = fyll(bit[..., :3], mask)
    # samma korn som gräset runt omkring, så lagningen inte syns som en slät fläck
    brus = np.random.default_rng(hole.number).normal(0, 4.0, rgb.shape)
    rgb[mask] = np.clip(rgb[mask] + brus[mask], 0, 255)
    lagad = np.dstack([rgb.astype(np.uint8), bit[..., 3]])
    im.paste(Image.fromarray(lagad, "RGBA"), (x0, y0))
    _flagga(im, x, y, s)
    im.save(bild, quality=92)
    return bild


if __name__ == "__main__":
    for f in sys.argv[1:]:
        print(byt(Path(f)))
