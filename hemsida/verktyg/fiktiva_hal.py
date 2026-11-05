"""Klipper ut hål ur den påhittade banbilden till hålrullen på startsidan.

Varje hål roteras så att tee hamnar nederst och greenen överst, och kanten tonas ut
som en mjuk kapsel runt hålet (genomskinlig bakgrund, som de tidigare hålbilderna).
Punkterna är i en 1360 px bred version av banbilden.

Kör:  python hemsida/verktyg/fiktiva_hal.py <banbild.png>
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

UT = Path(__file__).resolve().parents[1] / "public" / "img" / "hal"
# hål: (tee, green, halv bredd), allt i 1360-skalan
HAL = {
    "hal-04": ((850, 925), (497, 622), 120),
    "hal-07": ((257, 1700), (238, 1240), 82),
    "hal-10": ((300, 1135), (575, 1585), 105),
    "hal-12": ((1150, 1100), (1112, 1815), 85),
}
HOJD = 1100


def klipp(im, tee, green, halv):
    s = im.width / 1360
    tx, ty, gx, gy = tee[0] * s, tee[1] * s, green[0] * s, green[1] * s
    vinkel = math.degrees(math.atan2(gx - tx, -(gy - ty)))  # 0 = greenen rakt upp
    cx, cy = (tx + gx) / 2, (ty + gy) / 2
    langd = math.hypot(gx - tx, gy - ty)
    m = 70 * s
    bw, bh = int(2 * halv * s + 2 * m), int(langd + 2 * halv * s + 2 * m)
    stor = int(math.hypot(bw, bh)) + 4
    ut = im.crop((int(cx - stor / 2), int(cy - stor / 2), int(cx + stor / 2), int(cy + stor / 2)))
    ut = ut.rotate(vinkel, resample=Image.BICUBIC)
    ut = ut.crop(((stor - bw) // 2, (stor - bh) // 2, (stor - bw) // 2 + bw, (stor - bh) // 2 + bh))
    # Mjuk kapsel som mask, lite ojämn kant så att den inte ser stansad ut.
    yy, xx = np.mgrid[0:bh, 0:bw].astype(np.float32)
    y0, y1 = m + halv * s, bh - m - halv * s
    dy = np.clip(yy, y0, y1)
    d = np.hypot(xx - bw / 2, yy - dy)
    rng = np.random.default_rng(3)
    brus = np.asarray(Image.fromarray((rng.random((bh // 24 + 2, bw // 24 + 2)) * 255).astype(np.uint8))
                      .resize((bw, bh), Image.BICUBIC), dtype=np.float32) / 255
    r = halv * s * (1 + .12 * (brus - .5))
    alfa = np.clip((r + m * .55 - d) / (m * .55), 0, 1)
    mask = Image.fromarray((alfa * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4 * s))
    ut = ut.convert("RGBA"); ut.putalpha(mask)
    bb = ut.getbbox(); ut = ut.crop(bb)
    return ut.resize((round(ut.width * HOJD / ut.height), HOJD), Image.LANCZOS)


def main(kalla):
    im = Image.open(kalla).convert("RGB")
    for namn, (tee, green, halv) in HAL.items():
        b = klipp(im, tee, green, halv)
        b.save(UT / f"{namn}.webp", quality=84, method=6)
        print(namn, b.size)


if __name__ == "__main__":
    main(sys.argv[1])
