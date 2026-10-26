"""Tar bort en grusväg som AI:n målat in men som inte finns (kontrollerat mot ortofotot eller
klubbens besked). Grusfärgade pixlar i varje ruta fylls med omgivande gräs och får tillbaka
gräsets struktur från en granne vid sidan om. Bara borttagning – inget ritas till.

    python verktyg/ta_bort_grus.py <bild.webp> --ruta y0,y1,x0,x1[,minljus] [--ruta ...] [--skift -70]

minljus (standard 120) = hur ljus en pixel minst ska vara för att räknas som grus; sänk den för
ljusa fläckar som blivit kvar. Bilden skrivs över (originalet finns i git).
Glasriket hål 2 (Eric 2026-10-26: grusvägen slutar före tee 44, sedan fairway):
    --ruta 600,2835,300,600 --ruta 2350,2850,560,780 --ruta 1990,2140,300,430,95 --ruta 2000,2140,320,420,150
"""
from __future__ import annotations

import argparse

import cv2
import numpy as np
from PIL import Image


def ta_bort(im: np.ndarray, y0: int, y1: int, x0: int, x1: int, minljus: int = 120, skift: int = -70,
            bred: int = 13) -> np.ndarray:
    rgb, a = im[..., :3].astype(float), im[..., 3]
    mx, mn = rgb.max(-1), rgb.min(-1)
    grus = (a > 240) & (mn > minljus) & ((mx - mn) < 55)
    if minljus >= 150:  # ljus fläck: färgen spelar ingen roll, bara ljusheten
        grus = (a > 240) & (mn > minljus)
        bred = 21
    yy, xx = np.mgrid[:im.shape[0], :im.shape[1]]
    m = (grus & (yy > y0) & (yy < y1) & (xx > x0) & (xx < x1)).astype(np.uint8) * 255
    m = cv2.dilate(m, np.ones((bred, bred), np.uint8))
    fyll = cv2.inpaint(np.ascontiguousarray(rgb.astype(np.uint8)[..., ::-1]), m, 12, cv2.INPAINT_TELEA)[..., ::-1]
    detalj = np.roll(rgb - cv2.GaussianBlur(rgb, (0, 0), 3), skift, axis=1)
    mjuk = cv2.GaussianBlur(m.astype(float) / 255, (0, 0), 3)[..., None]
    ny = rgb * (1 - mjuk) + (fyll + detalj * 0.9) * mjuk
    return np.dstack([np.clip(ny, 0, 255).astype(np.uint8), a])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bild")
    ap.add_argument("--ruta", action="append", required=True)
    ap.add_argument("--skift", type=int, default=-70, help="var gräsets struktur hämtas, px i sidled")
    ar = ap.parse_args()
    im = np.asarray(Image.open(ar.bild).convert("RGBA"))
    for r in ar.ruta:
        v = [int(x) for x in r.split(",")]
        im = ta_bort(im, *v[:4], minljus=v[4] if len(v) > 4 else 120, skift=ar.skift)
    Image.fromarray(im, "RGBA").save(ar.bild, quality=95)
    print(f"{ar.bild}: {len(ar.ruta)} rutor tvättade")


if __name__ == "__main__":
    main()
