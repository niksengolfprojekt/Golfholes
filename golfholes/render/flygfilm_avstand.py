"""Nedräkning till flaggan, inbränd i flygfilmen (Eric 2026-10-25: "ha den på filmen på hålen").

Avståndet räknas ur kamerans läge i varje ruta (kamerabanan från `flygfilm --forlopp oversikt`),
längs hålets mittlinje, skalat så att vald tee = scorekortets längd. Det står på tee-längden tills
kameran är vid tee och räknar sedan bara nedåt. Siffran visas under flygningen (tonas in när
kameran landat vid tee, ut när den stiger), aldrig över översikten. Klubbens färger och typsnitt
från klubb.yaml.
"""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

from .flygfilm import ffmpeg_bin

TYPSNITT = Path(__file__).resolve().parents[2] / "assets" / "typsnitt"


def _langs(linje: list, p) -> tuple[float, float]:
    """Sträckan längs mittlinjen (m) till punktens närmaste läge på linjen, och linjens längd."""
    bast, s0 = (1e18, 0.0), 0.0
    for (ax, ay), (bx, by) in zip(linje, linje[1:]):
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (L * L)))
        d = math.hypot(ax + t * dx - p[0], ay + t * dy - p[1])
        if d < bast[0]:
            bast = (d, s0 + t * L)
        s0 += L
    return bast[1], s0


def avstand_per_ruta(hal: dict, kameror: list[dict], tee_namn: str, vid_tee: int = 0) -> list[int]:
    """Meter kvar till flaggan för varje ruta. Tee-längden fram till rutan vid_tee (kameran har landat
    vid tee; innan dess hänger den över hålet), sedan bara nedåt."""
    linje = hal["centerline"]
    tee = next(t for t in hal["tees"] if str(t["name"]) == str(tee_namn))
    s_tee, total = _langs(linje, tee["point"])
    skala = tee["length_m"] / (total - s_tee)
    meter = [max(0, min(tee["length_m"], round((total - max(_langs(linje, (k["e"], k["n"]))[0], s_tee)) * skala)))
             for k in kameror]
    ut, minst = [], tee["length_m"]
    for i, m in enumerate(meter):
        if i >= vid_tee:
            minst = min(minst, m)
        ut.append(minst)
    return ut


def synlighet(n: int, fps: float, fran_s: float, till_s: float, tona_s: float = 0.5) -> np.ndarray:
    """0–1 per ruta: tonas in vid fran_s och ut fram till till_s."""
    t = np.arange(n) / fps
    a = np.clip((t - fran_s) / tona_s, 0, 1)
    b = np.clip((till_s - t) / tona_s, 0, 1)
    return np.minimum(a, b)


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def skylt(meter: int, hojd: int, farger: dict, siffror: str, text: str) -> Image.Image:
    """Den lilla rutan: stor siffra i klubbens siffertypsnitt med "m" på samma baslinje, "till flaggan" under."""
    s = hojd / 720
    fs = ImageFont.truetype(str(TYPSNITT / f"{siffror.replace(' ', '')}-Medium.ttf"), round(66 * s))
    fm = ImageFont.truetype(str(TYPSNITT / f"{siffror.replace(' ', '')}-Medium.ttf"), round(30 * s))
    ft = ImageFont.truetype(str(TYPSNITT / f"{text.replace(' ', '')}-Medium.ttf"), round(21 * s))
    tal, under = f"{meter}", "till flaggan"
    mat = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    w_tal = mat.textlength(tal, font=fs)
    w = max(w_tal + round(8 * s) + mat.textlength("m", font=fm), mat.textlength(under, font=ft))
    pad = round(20 * s)
    bas = pad + round(54 * s)                  # siffrans baslinje
    W, H = round(w + 2 * pad + 4 * s), bas + round(34 * s) + pad
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=round(10 * s), fill=_hex(farger["djup"]) + (210,))
    d.rectangle((0, round(10 * s), round(4 * s), H - round(10 * s)), fill=_hex(farger["glod"]) + (255,))
    x = pad + round(4 * s)
    d.text((x, bas), tal, font=fs, fill=_hex(farger["kristall"]) + (255,), anchor="ls")
    d.text((x + w_tal + round(8 * s), bas), "m", font=fm, fill=_hex(farger["is"]) + (255,), anchor="ls")
    d.text((x, bas + round(30 * s)), under, font=ft, fill=_hex(farger["is"]) + (255,), anchor="ls")
    return im


def branna_in(film: Path, meter: list[int], syn: np.ndarray, klubb: dict, ut: Path, crf: int = 16) -> Path:
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                        "stream=width,height,r_frame_rate", "-of", "csv=p=0", str(film)],
                       capture_output=True, text=True, check=True).stdout.strip().split(",")
    B, H = int(p[0]), int(p[1])
    t, n = p[2].split("/")
    fps = int(t) / int(n)
    prof = klubb.get("profil", {})
    farger = prof.get("farger", {"djup": "#142219", "glod": "#D9A441", "kristall": "#F2F2EE", "is": "#C8D6D0"})
    typ = klubb.get("typsnitt", {})
    siffror, text = typ.get("siffror", "Spectral"), typ.get("text", "Hanken Grotesk")
    las = subprocess.Popen([ffmpeg_bin(), "-loglevel", "error", "-i", str(film), "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-"], stdout=subprocess.PIPE)
    skriv = subprocess.Popen([ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                              "-s", f"{B}x{H}", "-r", f"{fps:g}", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                              "-crf", str(crf), "-preset", "slow", "-movflags", "+faststart", str(ut)],
                             stdin=subprocess.PIPE)
    cache: dict[int, Image.Image] = {}
    marg = round(28 * H / 720)
    i = 0
    while True:
        rad = las.stdout.read(B * H * 3)
        if len(rad) < B * H * 3:
            break
        a = float(syn[min(i, len(syn) - 1)])
        if a > 0:
            m = meter[min(i, len(meter) - 1)]
            if m not in cache:
                cache[m] = skylt(m, H, farger, siffror, text)
            sk = cache[m]
            bild = Image.frombuffer("RGB", (B, H), rad).copy()
            if a < 1:
                sk = sk.copy()
                sk.putalpha(sk.getchannel("A").point(lambda v: round(v * a)))
            bild.paste(sk, (marg, H - marg - sk.height), sk)
            rad = bild.tobytes()
        skriv.stdin.write(rad)
        i += 1
    skriv.stdin.close()
    skriv.wait()
    las.wait()
    return ut


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Bränn in nedräkningen till flaggan i en flygfilm")
    ap.add_argument("hal", type=Path)
    ap.add_argument("--kam", type=Path, required=True, help="kamerabanan (json) som filmen gjordes med")
    ap.add_argument("--film", type=Path, required=True)
    ap.add_argument("--ut", type=Path, required=True)
    ap.add_argument("--tee", default=None, help="tee som filmen startar vid (standard: kamerabanans)")
    a = ap.parse_args(argv)
    hal = yaml.safe_load(a.hal.read_text(encoding="utf-8"))
    klubb_fil = a.hal.with_name("klubb.yaml")
    klubb = yaml.safe_load(klubb_fil.read_text(encoding="utf-8")) if klubb_fil.exists() else {}
    bana = json.loads(a.kam.read_text(encoding="utf-8"))
    info = bana["info"]
    fps = len(bana["kameror"]) / info["sekunder"]
    faser = info["faser_s"]
    meter = avstand_per_ruta(hal, bana["kameror"], a.tee or info["tee"], round(faser["ned"][1] * fps))
    # in när kameran står vid tee (slutet av nedstigningen), ut när den börjar stiga
    syn = synlighet(len(meter), fps, faser["ned"][1], faser["upp"][0] + 0.5)
    branna_in(a.film, meter, syn, klubb, a.ut)
    print(json.dumps({"ut": str(a.ut), "start_m": meter[0], "slut_m": meter[-1]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
