"""Jämnar ut ett AI-klipp innan det klipps in i flygfilmen (Eric 2026-10-25: "får inte vara något flimmer").

Videomodellen (Wan 3.0) ger 30 bilder/s där var 5:e bild tar ett större kliv och har annan skärpa,
och gräset "kokar" lite mellan bilderna. Förut räknades klippet om till 24 bilder/s genom att var
5:e bild ströks, vilket gjorde rycken värre. Här görs i stället:

1. Lika långa steg: optiskt flöde mellan bilderna ger hur långt kameran flyttar sig per bild.
   Nya bilder räknas fram (mellanbilder med flödet) så att stegen följer en utjämnad kurva,
   exakt `n_ut` bilder. In- och utfart finns kvar, pulsen försvinner.
2. Stilla gräs: varje bild medlas med grannarna, flyttade på plats med flödet, och bara där de
   passar (annars rörs bilden inte). Det tar bort det mesta av kokandet utan dubbelkonturer.
3. Jämn skärpa: varje bild skärps eller mjukas lite så att detaljnivån följer en utjämnad kurva.

Bara omräkning av befintliga bilder, inga nya former. Kräver OpenCV (`opencv-python-headless`),
som inte är ett kärnberoende: körs där det finns (molnet: pip install --target).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .flygfilm import ffmpeg_bin


def _cv2():
    try:
        import cv2
    except ImportError as e:  # pragma: no cover
        raise SystemExit("jamna kräver OpenCV: pip install opencv-python-headless") from e
    return cv2


def las_klipp(film: Path) -> np.ndarray:
    """Klippet som (rutor, h, b, 3) uint8 i sin egen takt (ingen omräkning)."""
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(film)], capture_output=True, text=True, check=True).stdout.strip()
    b, h = (int(v) for v in p.split(",")[:2])
    r = subprocess.run([ffmpeg_bin(), "-loglevel", "error", "-i", str(film), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       stdout=subprocess.PIPE, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, h, b, 3)


def _flode(a: np.ndarray, b: np.ndarray, skala: float = 0.5) -> np.ndarray:
    cv2 = _cv2()
    ga = cv2.cvtColor(cv2.resize(a, None, fx=skala, fy=skala, interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
    gb = cv2.cvtColor(cv2.resize(b, None, fx=skala, fy=skala, interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
    f = cv2.calcOpticalFlowFarneback(ga, gb, None, 0.5, 4, 25, 4, 7, 1.5, 0)
    return cv2.resize(f, (a.shape[1], a.shape[0])) / skala


def _varpa(bild: np.ndarray, fl: np.ndarray, t: float) -> np.ndarray:
    cv2 = _cv2()
    h, w = bild.shape[:2]
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    t = np.float32(t)
    return cv2.remap(bild, (gx + fl[..., 0] * t).astype(np.float32), (gy + fl[..., 1] * t).astype(np.float32),
                     cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def _detalj(bild: np.ndarray) -> float:
    g = np.clip(bild, 0, 255).astype(np.float32).mean(axis=2)
    return float(np.abs(np.diff(g, 2, axis=0)).mean() + np.abs(np.diff(g, 2, axis=1)).mean())


def _utjamna(x: np.ndarray, sigma: float) -> np.ndarray:
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    return np.convolve(np.pad(x, r, mode="edge"), k, "valid")


def steg_plan(rorelse: np.ndarray, n_ut: int, sigma: float = 4.0) -> np.ndarray:
    """Källpositioner (bråktal) för n_ut bilder så att stegen följer en utjämnad kurva.

    rorelse[i] = hur långt bilden flyttar sig mellan källbild i och i+1."""
    m = np.asarray(rorelse, dtype=float) + 1e-3
    N = len(m) + 1
    C = np.concatenate([[0.0], np.cumsum(m)])
    Cs = np.concatenate([[0.0], np.cumsum(_utjamna(m, sigma))])
    Cs *= C[-1] / Cs[-1]
    mal = np.interp(np.linspace(0, N - 1, n_ut), np.arange(N), Cs)
    return np.interp(mal, C, np.arange(N))


def jamna(src: np.ndarray, n_ut: int, sigma: float = 4.0, stilla: bool = True) -> list[np.ndarray]:
    N = len(src)
    fram = [_flode(src[i], src[i + 1]) for i in range(N - 1)]
    bak = [_flode(src[i + 1], src[i]) for i in range(N - 1)]
    rorelse = np.array([np.median(np.hypot(f[..., 0], f[..., 1])) for f in fram])
    ut = []
    for x in steg_plan(rorelse, n_ut, sigma):
        i = min(int(np.floor(x)), N - 2)
        t = x - i
        if t < 1e-3:
            ut.append(src[i].astype(np.float32))
        elif t > 1 - 1e-3:
            ut.append(src[i + 1].astype(np.float32))
        else:   # mellanbild: a dras framåt, b bakåt längs flödet
            A = _varpa(src[i], bak[i], t).astype(np.float32)
            B = _varpa(src[i + 1], fram[i], 1 - t).astype(np.float32)
            ut.append(A * (1 - t) + B * t)
    if stilla:
        u8 = [np.clip(u, 0, 255).astype(np.uint8) for u in ut]
        nya = []
        for j in range(len(u8)):
            acc = ut[j] * 0.5
            vikt_sum = np.full(ut[j].shape[:2] + (1,), 0.5, np.float32)
            for q in (j - 1, j + 1):
                if 0 <= q < len(u8):
                    v = _varpa(u8[q], _flode(u8[j], u8[q]), 1.0).astype(np.float32)
                    fel = np.abs(v - ut[j]).mean(axis=2, keepdims=True)
                    vikt = 0.25 * np.clip(1 - (fel - 8) / 16, 0, 1)
                    acc += v * vikt
                    vikt_sum += vikt
            nya.append(acc / vikt_sum)
        ut = nya
    cv2 = _cv2()
    for _ in range(3):   # jämn skärpa
        e = np.array([_detalj(u) for u in ut])
        mal = _utjamna(e, sigma)
        ut = [np.clip(u + 1.6 * (m / ei - 1) * (u - cv2.GaussianBlur(u, (0, 0), 1.0)), 0, 255)
              for u, ei, m in zip(ut, e, mal)]
    return [u.astype(np.uint8) for u in ut]


def jamna_klipp(film: Path, n_ut: int, ut: Path, fps: int = 24) -> Path:
    bilder = jamna(las_klipp(film), n_ut)
    h, b = bilder[0].shape[:2]
    p = subprocess.Popen([ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{b}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                          "-crf", "14", str(ut)], stdin=subprocess.PIPE)
    for bild in bilder:
        p.stdin.write(bild.tobytes())
    p.stdin.close()
    p.wait()
    return ut


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Jämna ut ett AI-klipp till exakt N bilder (24/s) utan ryck och flimmer")
    ap.add_argument("klipp", type=Path)
    ap.add_argument("rutor", type=int, help="antal bilder ut = delens längd i den råa filmen")
    ap.add_argument("--ut", type=Path, required=True)
    a = ap.parse_args()
    print(jamna_klipp(a.klipp, a.rutor, a.ut))
