"""Skärp upp en färdig flygfilm (480p) till rutor i 1920 × 1080, bild för bild, utan krediter.

AI-videon (Wan 480p) är mjuk mitt i flygningen. Det här steget kör en liten lokal modell för
uppskärpning (Real-ESRGAN "general x4 v3", 5 MB, BSD-licens) på varje ruta: 854 × 480 → 4 gånger
större → nedräknat till 1920 × 1080. Modellen gör kanter (trädtoppar, bunkerkanter, klipplinjer)
skarpa men flyttar ingenting: formen är densamma som i 480p-filmen.

Kräver torch (cpu räcker, cirka 5–10 s per ruta) och opencv. I molnet:

    pip install --target /tmp/py torch --index-url https://download.pytorch.org/whl/cpu
    pip install --target /tmp/py opencv-python-headless
    curl -L -o realesr-general-x4v3.pth \
        https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth
    PYTHONPATH=/tmp/py python verktyg/flygfilm_skarpa.py film-480p.mp4 --modell realesr-general-x4v3.pth --ut hd/

Sedan: `python verktyg/flygfilm_kor.py hd <hål> --kam kam.json --rutor hd/ --ut film-1080p.mp4`.
Går att avbryta och starta om: färdiga rutor hoppas över.
"""
import argparse
import os
import subprocess
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class SRVGG(nn.Module):
    """Real-ESRGAN:s kompakta nät (SRVGGNetCompact), samma lager som i vikterna."""

    def __init__(self, nf: int = 64, nc: int = 32, upp: int = 4):
        super().__init__()
        self.upp = upp
        lager = [nn.Conv2d(3, nf, 3, 1, 1), nn.PReLU(nf)]
        for _ in range(nc):
            lager += [nn.Conv2d(nf, nf, 3, 1, 1), nn.PReLU(nf)]
        lager.append(nn.Conv2d(nf, 3 * upp * upp, 3, 1, 1))
        self.body = nn.ModuleList(lager)
        self.ps = nn.PixelShuffle(upp)

    def forward(self, x):
        o = x
        for lg in self.body:
            o = lg(o)
        return self.ps(o) + F.interpolate(x, scale_factor=self.upp, mode="nearest")


def ladda(vikter: Path) -> SRVGG:
    m = SRVGG()
    sd = torch.load(vikter, map_location="cpu")
    m.load_state_dict(sd.get("params", sd))
    return m.eval()


@torch.no_grad()
def skarpa(m: SRVGG, bgr: np.ndarray) -> np.ndarray:
    x = torch.from_numpy(bgr[:, :, ::-1].copy()).permute(2, 0, 1)[None].float() / 255
    y = m(x).clamp(0, 1)[0].permute(1, 2, 0).numpy()[:, :, ::-1]
    return (y * 255 + 0.5).astype(np.uint8)


def main() -> int:
    ap = argparse.ArgumentParser(description="Skärp upp en flygfilm till 1080p-rutor")
    ap.add_argument("film", type=Path)
    ap.add_argument("--modell", type=Path, required=True)
    ap.add_argument("--ut", type=Path, required=True)
    ap.add_argument("--storlek", default="1920x1080")
    a = ap.parse_args()
    B, H = (int(v) for v in a.storlek.split("x"))
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(a.film)], capture_output=True, text=True, check=True).stdout.strip().split(",")
    b, h = int(p[0]), int(p[1])
    m = ladda(a.modell)
    a.ut.mkdir(parents=True, exist_ok=True)
    las = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", str(a.film), "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                           stdout=subprocess.PIPE)
    i = 0
    while True:
        buf = las.stdout.read(b * h * 3)
        if len(buf) < b * h * 3:
            break
        fil = a.ut / f"{i:04d}.png"
        if not fil.exists():
            stor = cv2.resize(skarpa(m, np.frombuffer(buf, np.uint8).reshape(h, b, 3)), (B, H), interpolation=cv2.INTER_AREA)
            tmp = str(fil) + ".tmp.png"
            cv2.imwrite(tmp, stor, [cv2.IMWRITE_PNG_COMPRESSION, 1])
            os.rename(tmp, fil)
        i += 1
        if i % 50 == 0:
            print(i, flush=True)
    print("klar", i)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
