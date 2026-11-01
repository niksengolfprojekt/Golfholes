"""Färgharmoni: gör gräsets kulör lika på alla hål i en serie (bara färg, aldrig form).

AI-målningen ger ibland ett hål en gulare eller blekare grön ton än de andra.
Verktyget mäter medelkulör och mättnad på det ljusa gräset och flyttar dem en
bit mot ett referenshål (standard hål 14, som Eric godkände 2026-11-01).
Bara spelytan ändras (fairway, tees, green och 15 m runt greenen ur hålfilen);
skog, ruff, sand, vatten, prickar och mörk bakgrund lämnas orörda.

    python verktyg/farg_harmoni.py klubbar/glasriket/hal-03.yaml [fler] --namn a6 [--ref 14] [--andel 0.8]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verktyg.orto_utsnitt  # noqa: E402,F401
from golfholes.hole import Hole  # noqa: E402
from golfholes.render.foto import fotounderlag, orto_for  # noqa: E402
from verktyg.fairway_frisk import _blur, prickmask, spelyta  # noqa: E402
from verktyg.skuggskydd import _mask  # noqa: E402


def _hsv(rgb):
    mx = rgb.max(-1); mn = rgb.min(-1); d = mx - mn
    h = np.zeros_like(mx)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    m = d > 1e-6
    rm = m & (mx == r); gm = m & (mx == g) & ~rm; bm = m & ~rm & ~gm
    h[rm] = ((g - b)[rm] / d[rm]) % 6
    h[gm] = (b - r)[gm] / d[gm] + 2
    h[bm] = (r - g)[bm] / d[bm] + 4
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0)
    return h * 60, s, mx


def _rgb(h, s, v):
    h = (h % 360) / 60
    i = np.floor(h).astype(int) % 6
    f = h - np.floor(h)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    sel = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)]
    out = np.zeros(h.shape + (3,))
    for k, (a, b, c) in enumerate(sel):
        m = i == k
        out[m] = np.stack([a[m], b[m], c[m]], -1)
    return out


def ytmask(im: Image.Image, hole: Hole, px) -> np.ndarray:
    """0–1: spelytan inkl. greenen, utan prickar och flagga, mjuk kant."""
    M = spelyta(im, hole, px)
    green = np.asarray(_mask(im, [hole.green], px, 0), np.float32) / 255
    M = np.maximum(M, green)
    rgb = np.asarray(im.convert("RGB"), np.float32)
    M = M * (~prickmask(rgb))
    return np.clip(_blur(M, 2), 0, 1)


def matt(rgb, w):
    h, s, _ = _hsv(rgb)
    w = w * (rgb[..., 1] > rgb[..., 2])  # bara gräs, inte skuggblått
    return float((h * w).sum() / w.sum()), float((s * w).sum() / w.sum())


def las(hf: Path, namn: str, suf: str = ""):
    hole = Hole.from_yaml(hf)
    f = hf.parent / "halbilder" / f"hal-{hole.number:02d}-{namn}{suf}.webp"
    if not f.exists():
        return None
    im = Image.open(f).convert("RGBA")
    _, px = fotounderlag(hole, orto_for(Path("data") / hf.parent.name), im.height)
    return f, im, ytmask(im, hole, px)


def harmonisera(im, w, mal_h, mal_s, andel=0.8):
    a = np.asarray(im).astype(np.float32) / 255
    rgb, alfa = a[..., :3], a[..., 3:]
    eg_h, eg_s = matt(rgb, w)
    dh = (mal_h - eg_h) * andel
    ks = 1 + (mal_s / eg_s - 1) * andel
    h, s, v = _hsv(rgb)
    ny = _rgb(h + dh, np.clip(s * ks, 0, 1), v)
    w3 = w[..., None]
    ut = rgb * (1 - w3) + ny * w3
    return Image.fromarray((np.concatenate([ut, alfa], -1) * 255).round().astype(np.uint8), "RGBA"), dh, ks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hal", nargs="+")
    ap.add_argument("--namn", default="a6")
    ap.add_argument("--ref", default="14")
    ap.add_argument("--andel", type=float, default=0.8)
    a = ap.parse_args()
    klubb = Path(a.hal[0]).parent
    _, rim, rw = las(klubb / f"hal-{a.ref}.yaml", a.namn)
    mal_h, mal_s = matt(np.asarray(rim.convert("RGB"), np.float32) / 255, rw)
    print(f"mål (hål {a.ref}): kulör {mal_h:.1f}°, mättnad {mal_s:.2f}")
    for hf in a.hal:
        for suf in ("", "-utan-flagga"):
            r = las(Path(hf), a.namn, suf)
            if r is None:
                continue
            f, im, w = r
            ny, dh, ks = harmonisera(im, w, mal_h, mal_s, a.andel)
            ny.save(f, quality=92)
            print(f"{f} kulör {dh:+.1f}°, mättnad x{ks:.2f}")


if __name__ == "__main__":
    main()
