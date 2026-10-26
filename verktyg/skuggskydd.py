"""Skuggskydd (Eric 2026-10-26): skuggorna ska förhöja bilden men aldrig dölja green,
bunkrar eller vatten. Inom green (+ en kant) och bunkrar tonas skuggade partier mot ytans egen solbelysta
färg, så ytan syns tydligt men skuggan finns kvar som ton.

Används av verktyg/ai_tillbaka_test.py före prickar och flagga ritas.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

STYRKA = 0.7    # hur stor del av skuggan inom ytan som tas bort
FAIRWAY = 0.55  # fairway: skuggan dämpas, men en del får vara kvar för djupet
KANT_M = 3.0    # skyddet går så här långt utanför greenkanten


def _mask(im, polys, px, kant_px):
    m = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(m)
    for poly in polys:
        d.polygon([tuple(float(v) for v in px(*p)) for p in poly], fill=255)
    if kant_px >= 1:
        m = m.filter(ImageFilter.MaxFilter(int(kant_px) * 2 + 1))
    elif kant_px <= -1:
        m = m.filter(ImageFilter.MinFilter(int(-kant_px) * 2 + 1))
    return m.filter(ImageFilter.GaussianBlur(max(2, kant_px / 2)))


def skuggskydd(im: Image.Image, hole, px) -> dict:
    """Skuggade bildpunkter inom ytan tonas mot ytans egen solbelysta färg (samma kulör,
    detaljen behålls), så ingen neonfärg och ingen gloria uppstår."""
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    px_per_m = float(math.dist([float(v) for v in px(0, 0)], [float(v) for v in px(10, 0)])) / 10
    bunkrar = [h.polygon for h in hole.hazards if h.kind == "bunker"]
    rapport = {}
    for namn, polys, kant, styrka in (("fairway", hole.fairways, 0.0, FAIRWAY), ("green", [hole.green], KANT_M, STYRKA),
                                      ("bunkrar", bunkrar, -0.5, STYRKA)):
        if not polys:
            continue
        M = np.asarray(_mask(im, polys, px, kant * px_per_m), np.float32) / 255
        rgb = a[..., :3]
        L = rgb.mean(axis=2)
        inne = M > 0.5
        if inne.sum() < 50:
            continue
        ljus = np.percentile(L[inne], 85)
        sol = inne & (L > np.percentile(L[inne], 65))
        if sol.sum() < 20:
            continue
        ref = np.median(rgb[sol], axis=0)                       # ytans solbelysta färg
        fore = float((L[inne] < ljus * 0.6).mean())
        Lm = np.asarray(Image.fromarray(L.clip(0, 255).astype(np.uint8)).filter(
            ImageFilter.BoxBlur(max(2, int(px_per_m * 1.5)))), np.float32)
        detalj = np.clip(L / np.maximum(Lm, 1), 0.85, 1.15)[..., None]
        skugga = np.clip((ljus * 0.9 - L) / (ljus * 0.9), 0, 1)[..., None]
        k = (skugga * styrka * M[..., None])
        a[..., :3] = np.where(k > 0, np.clip(rgb * (1 - k) + ref * detalj * k, 0, 255), rgb)
        L2 = a[..., :3].mean(axis=2)
        rapport[namn] = {"skugga_fore": round(fore, 3), "skugga_efter": round(float((L2[inne] < ljus * 0.6).mean()), 3)}
    im.paste(Image.fromarray(a.astype(np.uint8), "RGBA"))
    return rapport
