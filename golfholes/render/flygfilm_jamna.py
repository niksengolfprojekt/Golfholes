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


def steg_plan(rorelse: np.ndarray, n_ut: int, sigma: float = 4.0, bas: np.ndarray | None = None) -> np.ndarray:
    """Källpositioner (bråktal) för n_ut bilder så att stegen följer en utjämnad kurva.

    rorelse[i] = hur långt bilden flyttar sig mellan källbild i och i+1.
    bas = önskade källpositioner (t.ex. från synk mot den råa filmen); utan bas jämn takt."""
    m = np.asarray(rorelse, dtype=float) + 1e-3
    N = len(m) + 1
    C = np.concatenate([[0.0], np.cumsum(m)])
    Cs = np.concatenate([[0.0], np.cumsum(_utjamna(m, sigma))])
    Cs *= C[-1] / Cs[-1]
    bas = np.linspace(0, N - 1, n_ut) if bas is None else np.clip(np.asarray(bas, float), 0, N - 1)
    mal = np.interp(bas, np.arange(N), Cs)
    return np.interp(mal, C, np.arange(N))


def jamna(src: np.ndarray, n_ut: int, sigma: float = 4.0, stilla: bool = True,
          bas: np.ndarray | None = None) -> list[np.ndarray]:
    N = len(src)
    # float16 räcker för flödet och halverar minnet (långa klipp, 15 s+ = 450 bilder)
    fram = [_flode(src[i], src[i + 1]).astype(np.float16) for i in range(N - 1)]
    bak = [_flode(src[i + 1], src[i]).astype(np.float16) for i in range(N - 1)]
    rorelse = np.array([np.median(np.hypot(f[..., 0], f[..., 1])) for f in fram])
    ut = []
    for x in steg_plan(rorelse, n_ut, sigma, bas):
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
    del fram, bak
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


def _kanter(x: np.ndarray) -> np.ndarray:
    cv2 = _cv2()
    g = cv2.cvtColor(cv2.resize(x, (214, 120), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 1.5)
    m = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    m -= m.mean()
    return m / (m.std() + 1e-6)


def synk_bas(src: np.ndarray, ra: np.ndarray, max_steg: int = 3, sigma: float = 12.0) -> np.ndarray:
    """Vilken AI-bild (bråktal) som bäst motsvarar varje bild i den råa delen.

    Wan följer inte alltid förlagans takt (hål 9 del 2: greenbunkern hamnade 10-20 m fel
    vid jämn takt). Kantbilderna jämförs, en monoton väg letas fram (DTW, 0..max_steg
    AI-bilder per rå bild) och vägen jämnas ut så att bara den stora takten ändras."""
    fa = np.array([_kanter(a) for a in src])
    fr = np.array([_kanter(r) for r in ra])
    C = -np.einsum("ixy,jxy->ij", fr, fa) / fa[0].size
    R, A = C.shape
    D = np.full((R, A), np.inf)
    D[0, :15] = C[0, :15]
    P = np.zeros((R, A), int)
    for j in range(1, R):
        for k in range(A):
            lo = max(0, k - max_steg)
            m = int(np.argmin(D[j - 1, lo:k + 1]))
            D[j, k], P[j, k] = D[j - 1, lo + m] + C[j, k], lo + m
    k = int(np.argmin(D[-1, A - 20:])) + A - 20
    vag = [k]
    for j in range(R - 1, 0, -1):
        k = P[j, k]
        vag.append(k)
    v = np.maximum.accumulate(_utjamna(np.array(vag[::-1], float), sigma))
    return np.clip(v, 0, A - 1)


def las_del(film: Path, fran: int, n: int, b: int, h: int) -> np.ndarray:
    """Rutorna fran..fran+n ur en film, skalade till b x h."""
    r = subprocess.run([ffmpeg_bin(), "-loglevel", "error", "-i", str(film), "-vf",
                        f"select='between(n\\,{fran}\\,{fran + n - 1})',scale={b}:{h}", "-vsync", "0",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, h, b, 3)


def jamna_klipp(film: Path, n_ut: int, ut: Path, fps: int = 24, synk: Path | None = None, fran: int = 0) -> Path:
    src = las_klipp(film)
    bas = None
    if synk:
        bas = synk_bas(src, las_del(synk, fran, n_ut, src.shape[2], src.shape[1]))
    bilder = jamna(src, n_ut, bas=bas)
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
    ap.add_argument("--synk", type=Path, help="rå film att följa takten i (annars jämn takt)")
    ap.add_argument("--fran", type=int, default=0, help="delens första ruta i den råa filmen (med --synk)")
    a = ap.parse_args()
    print(jamna_klipp(a.klipp, a.rutor, a.ut, synk=a.synk, fran=a.fran))
