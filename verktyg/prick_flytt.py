"""Flyttar avståndsprickarna (100/150 m) i en färdig hålbild till sina nya lägen mitt i fairway
(Eric 2026-10-29). Prickarna finns ofta också inmålade i AI-målningen på de gamla lägena längs
spellinjen, så de gamla lägena lagas först (med bilden en bit bort, där gräs och dammkant fortsätter) och sedan ritar koden
prickarna på nytt. Ingen kredit, formen rörs inte.

    python verktyg/prick_flytt.py klubbar/glasriket/hal-01.yaml [fler...] [--namn a5]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verktyg.orto_utsnitt  # noqa: E402,F401
from golfholes.hole import Hole  # noqa: E402
from golfholes.render.foto import (PRICKAR, _punkt_fore_green, _tyngdpunkt, avstandspunkt,  # noqa: E402
                                   fotounderlag, orto_for, rita_prickar)


def flytta(im: Image.Image, hole: Hole, px) -> float:
    """Lagar de gamla prickarna med bilden en bit bort (den riktning som liknar omgivningen mest),
    och ritar sedan prickarna på nytt."""
    if hole.par == 3:
        return 0.0
    s = im.height / 1000
    r = 9 * s
    mitt = _tyngdpunkt(hole.green)
    a = np.asarray(im.convert("RGBA")).copy()
    rgb = a[..., :3]
    yy, xx = np.mgrid[0:im.height, 0:im.width]
    flytt = 0.0
    for meter, _ in PRICKAR:
        gammal, ny = _punkt_fore_green(hole.centerline, mitt, meter), avstandspunkt(hole, mitt, meter)
        if not gammal:
            continue
        flytt = max(flytt, float(np.hypot(ny[0] - gammal[0], ny[1] - gammal[1])))
        gx, gy = px(*gammal)
        nx, ny_ = px(*ny)
        # den målade prickens yta med vit ring (samma storlek som kodens prick) och lite marginal
        m = (((xx - gx) ** 2 + (yy - gy) ** 2 < (1.45 * r) ** 2) * 255).astype(np.uint8)
        m = np.where((xx - nx) ** 2 + (yy - ny_) ** 2 < (r - 2) ** 2, 0, m)  # nya pricken täcker sig själv
        if not m.any():
            continue
        # lagningen hämtas 3,5 prickradier bort, längs spellinjen framåt eller bakåt eller åt sidan:
        # den riktning vars bit liknar gräset runt pricken mest (annars kan ett träd följa med)
        bak = _punkt_fore_green(hole.centerline, mitt, meter + 2)
        vx, vy = np.subtract(px(*bak), (gx, gy)) if bak else (0.0, 1.0)
        n = float(np.hypot(vx, vy)) or 1.0
        vx, vy = vx / n, vy / n
        ring = ((xx - gx) ** 2 + (yy - gy) ** 2 < (2.6 * r) ** 2) & (m == 0)
        ref = rgb[ring].astype(np.float32)
        pm = np.zeros(rgb.shape[:2], bool)  # prickarnas lägen (gamla och nya) får aldrig bli lagning
        for mm, _ in PRICKAR:
            for q in (_punkt_fore_green(hole.centerline, mitt, mm), avstandspunkt(hole, mitt, mm)):
                if q:
                    qx, qy = px(*q)
                    pm |= (xx - qx) ** 2 + (yy - qy) ** 2 < (1.6 * r) ** 2
        bast = None
        for ux, uy in ((vx, vy), (-vx, -vy), (-vy, vx), (vy, -vx)):
            dx, dy = int(round(ux * 3.5 * r)), int(round(uy * 3.5 * r))
            k = np.roll(np.roll(rgb, -dy, axis=0), -dx, axis=1)
            bit = k[m > 0].astype(np.float32)
            fel = float(np.abs(bit.mean(0) - ref.mean(0)).sum() + np.abs(bit.std(0) - ref.std(0)).sum())
            fel += 1e6 * float(np.roll(np.roll(pm, -dy, axis=0), -dx, axis=1)[m > 0].mean())  # aldrig en prick som lagning
            if bast is None or fel < bast[0]:
                bast = (fel, k)
        kalla = bast[1]
        w = np.asarray(Image.fromarray(m).filter(ImageFilter.GaussianBlur(2)), np.float32)[..., None] / 255
        rgb = (rgb * (1 - w) + kalla * w).astype(np.uint8)
    a[..., :3] = rgb
    ut = Image.fromarray(a, "RGBA")
    rita_prickar(ut, hole, px)
    im.paste(ut)
    return flytt


def kor(hf: Path, namn: str = "a5") -> None:
    hole = Hole.from_yaml(hf)
    club = hf.parent
    for f in (club / "halbilder" / f"hal-{hole.number:02d}-{namn}.webp",
              club / "halbilder" / f"hal-{hole.number:02d}-{namn}-utan-flagga.webp"):
        if not f.exists():
            continue
        im = Image.open(f).convert("RGBA")
        _, px = fotounderlag(hole, orto_for(Path("data") / club.name), im.height)
        n = flytta(im, hole, px)
        im.save(f, quality=92)
        print(f, f"prickar flyttade upp till {n:.1f} m")


if __name__ == "__main__":
    namn = sys.argv[sys.argv.index("--namn") + 1] if "--namn" in sys.argv else "a5"
    for a in sys.argv[1:]:
        if a.endswith(".yaml"):
            kor(Path(a), namn)
