"""Klipper ut ett texturkit (ytor + trädsprites) ur en stilbild.

Används för att ta stilen från en AI-skiss eller en målad förlaga – aldrig geometrin.
Rutorna anges i bildens egna pixlar. Kör:  python verktyg/texturkit.py
Resultat: assets/texturer/<stil>/*.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = Path(sys.argv[1]) if len(sys.argv) > 1 else None

# Rutor (x0, y0, x1, y1) i originalbildernas pixlar (3392 × 5056).
KITS = {
    "nordisk": {
        "bild": "78e2b0ca-image.png",
        "ytor": {
            "fairway": (982, 2303, 1185, 2614),
            "green": (1169, 1680, 1403, 1867),
            "vatten": (1290, 2230, 1510, 2440),
            "lov": (742, 2895, 834, 2987),     # insidan av en trädkrona – trädens yta
        },
    },
    "klassisk": {
        "bild": "d0796e68-image.png",
        "ytor": {
            "skog": (581, 1938, 944, 2549),
            "fairway": (1040, 2206, 1345, 2549),
            "vatten": (1480, 2080, 1800, 2330),
            "green": (1402, 1767, 1574, 1900),
            "sand": (1170, 1895, 1255, 1965),
            "ruff": (1078, 3160, 1192, 3313),
        },
    },
}


def main():
    if UPLOADS is None:
        print("Ange mappen med stilbilderna: python verktyg/texturkit.py <mapp>")
        return 1
    for name, kit in KITS.items():
        out = ROOT / "assets" / "texturer" / name
        out.mkdir(parents=True, exist_ok=True)
        im = Image.open(UPLOADS / kit["bild"]).convert("RGB")
        for yta, box in kit["ytor"].items():
            im.crop(box).save(out / f"{yta}.png")
        print(name, "→", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
