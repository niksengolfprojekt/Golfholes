"""Fairway i toppskick (Eric 2026-10-27): bruna fläckar (slitage på flygfotot) i fairway, på
tees och runt greenen färgas om till frisk grön. Bara kulören ändras: ljusheten behålls, så klippmönster, skuggor och
former ligger kvar exakt där de var.

    python verktyg/fairway_frisk.py klubbar/glasriket/hal-01.yaml [fler...] [--namn a5]

Gör om halbilder/hal-NN-<namn>.webp och -utan-flagga. Spelprickar och flagga rörs inte.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verktyg.orto_utsnitt  # noqa: E402,F401
from golfholes.hole import Hole  # noqa: E402
from golfholes.render.foto import fotounderlag, orto_for  # noqa: E402
from verktyg.skuggskydd import _mask  # noqa: E402


def _blur(a, r):
    """Gaussisk oskärpa på flyttal (OpenCV om det finns, annars Pillow i 8 bitar per kanal)."""
    try:
        import cv2
        return cv2.GaussianBlur(a.astype(np.float32), (0, 0), r)
    except ImportError:
        if a.ndim == 3:
            return np.dstack([_blur(a[..., i], r) for i in range(a.shape[2])])
        top = max(float(a.max()), 1e-6)
        b = Image.fromarray(np.clip(a / top * 255, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
        return np.asarray(b, np.float32) / 255 * top


def brunvikt(rgb):
    """0–1: hur brun/torr en bildpunkt är. Frisk gräsmatta har grönt över rött (R/G under 1),
    slitage drar mot orange-brunt (R/G över 1). Kvällsljusets gulgröna sken ligger strax under 1 och lämnas."""
    rg = rgb[..., 0] / np.maximum(rgb[..., 1], 1)
    w = np.clip((rg - 0.97) / 0.08, 0, 1)
    return np.where(prickmask(rgb), 0, w)


def prickmask(rgb):
    """Spelprickar, flagga och vita ringar (ritade av koden): de ska aldrig färgas om."""
    hsv = np.asarray(Image.fromarray(rgb.astype(np.uint8)).convert("HSV"), np.float32)
    h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    prick = ((s > 0.78) & (v > 0.88)) | (((h > 330) | (h < 15)) & (s > 0.55) & (v > 0.6)) | ((s < 0.12) & (v > 0.9))
    return np.asarray(Image.fromarray((prick * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3))
                      .filter(ImageFilter.MaxFilter(21))) > 0


def spelyta(im: Image.Image, hole: Hole, px) -> np.ndarray:
    """Fairway, tees och inspelsytan närmast greenen (15 m), utan bunkrar, vatten, träd och greenen själv."""
    px_per_m = float(np.hypot(*(np.subtract([float(v) for v in px(10, 0)], [float(v) for v in px(0, 0)])))) / 10
    tees = [t.polygon for t in getattr(hole, "tees", []) if getattr(t, "polygon", None)]
    M = np.asarray(_mask(im, list(hole.fairways) + tees, px, 0), np.float32) / 255
    green = np.asarray(_mask(im, [hole.green], px, 0), np.float32) / 255
    runt = np.clip(_blur(green, 7 * px_per_m) * 8, 0, 1)  # snabb utvidgning, ca 15 m
    M = np.maximum(M, runt * (1 - green))
    bort = [h.polygon for h in hole.hazards] + list(hole.trees)
    if bort:
        b = np.asarray(_mask(im, bort, px, 0), np.float32) / 255
        M *= 1 - np.clip(_blur(b, px_per_m) * 3, 0, 1)
    return M


def frisk(im: Image.Image, hole: Hole, px) -> float:
    """Bruna partier får det friska gräsets kulör. Mättnad och ljushet behålls, så klippmönster,
    skuggor och kvällsljus ligger kvar."""
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    rgb = a[..., :3]
    M = spelyta(im, hole, px)
    w = brunvikt(rgb) * M
    w = np.clip(_blur(w, 2) * 1.3, 0, 1)
    hsv = np.asarray(Image.fromarray(rgb.astype(np.uint8)).convert("HSV")).copy()
    frisk_px = (M > 0.5) & (w < 0.03) & (rgb[..., 1] > rgb[..., 0])
    mal = float(np.median(hsv[..., 0][frisk_px])) if frisk_px.sum() > 500 else 80 * 255 / 360
    hsv[..., 0] = np.uint8(np.clip(mal, 68 * 255 / 360, 95 * 255 / 360))
    ny = np.asarray(Image.fromarray(hsv, "HSV").convert("RGB"), np.float32)
    a[..., :3] = rgb * (1 - w[..., None]) + ny * w[..., None]
    im.paste(Image.fromarray(a.astype(np.uint8), "RGBA"))
    return float((w > 0.5)[M > 0.5].mean()) if (M > 0.5).any() else 0.0


def kor(hf: Path, namn: str = "a5") -> None:
    hole = Hole.from_yaml(hf)
    club = hf.parent
    for f in (club / "halbilder" / f"hal-{hole.number:02d}-{namn}.webp",
              club / "halbilder" / f"hal-{hole.number:02d}-{namn}-utan-flagga.webp"):
        if not f.exists():
            continue
        im = Image.open(f).convert("RGBA")
        _, px = fotounderlag(hole, orto_for(Path("data") / club.name), im.height)
        andel = frisk(im, hole, px)
        im.save(f, quality=92)
        print(f, f"{andel:.1%} av spelytan omfärgad")


if __name__ == "__main__":
    namn = sys.argv[sys.argv.index("--namn") + 1] if "--namn" in sys.argv else "a5"
    for a in sys.argv[1:]:
        if a.endswith(".yaml"):
            kor(Path(a), namn)
