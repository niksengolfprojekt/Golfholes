"""Lyft en färdig hålbild lite (Eric 2026-11-01: "kan liva upp bilden lite"). Inga krediter, ingen form.
Vibrans (mättar de dova färgerna mer än de redan starka), en mjuk S-kurva för kontrast och en lätt
oskarp mask. Dämpas mot den mörka bakgrunden så att kanten inte blir grumlig.

    python verktyg/liva_upp.py klubbar/glasriket/hal-14.yaml [fler] [--namn a6] [--styrka 1.0]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from golfholes.hole import Hole  # noqa: E402


def liva(im: Image.Image, styrka: float = 1.0) -> Image.Image:
    a = np.asarray(im.convert("RGBA")).astype(np.float32) / 255
    rgb, alfa = a[..., :3], a[..., 3:]
    lum = (rgb * [0.299, 0.587, 0.114]).sum(-1, keepdims=True)
    mx, mn = rgb.max(-1, keepdims=True), rgb.min(-1, keepdims=True)
    satt = (mx - mn) / (mx + 1e-4)
    # vibrans: dova ytor (sunkigt gräs) får mest
    v = 1 + 0.28 * styrka * (1 - satt)
    rgb = np.clip(lum + (rgb - lum) * v, 0, 1)
    # mjuk S-kurva runt mitten
    k = 0.10 * styrka
    rgb = rgb + k * np.sin((rgb - 0.5) * np.pi) * 0.5 / np.pi * 2 * (rgb * (1 - rgb)) * 4
    rgb = np.clip(rgb, 0, 1) ** (1 - 0.05 * styrka)  # lite ljusare mellantoner
    # bakgrunden (mörkt, omättat) lämnas i fred
    vikt = np.clip((lum - 0.10) / 0.10, 0, 1)
    ut = a[..., :3] * (1 - vikt) + rgb * vikt
    bild = Image.fromarray((np.concatenate([ut, alfa], -1) * 255).astype(np.uint8), "RGBA")
    return bild.filter(ImageFilter.UnsharpMask(radius=2.0, percent=int(45 * styrka), threshold=2))


def kor(hf: Path, namn: str, styrka: float) -> None:
    n = Hole.from_yaml(hf).number
    for f in (hf.parent / "halbilder" / f"hal-{n:02d}-{namn}.webp",
              hf.parent / "halbilder" / f"hal-{n:02d}-{namn}-utan-flagga.webp"):
        if f.exists():
            liva(Image.open(f), styrka).save(f, quality=92)
            print(f, "livad")


if __name__ == "__main__":
    args = sys.argv[1:]
    namn, styrka = "a6", 1.0
    if "--namn" in args:
        i = args.index("--namn"); namn = args[i + 1]; del args[i:i + 2]
    if "--styrka" in args:
        i = args.index("--styrka"); styrka = float(args[i + 1]); del args[i:i + 2]
    for hf in map(Path, args):
        kor(hf, namn, styrka)
