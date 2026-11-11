"""Färdig flygfilm i 1080p ur uppskärpta rutor (0 krediter).

AI-videon levereras i 480p och är mjuk mitt i flygningen. `verktyg/flygfilm_skarpa.py` skärper
upp varje ruta till 1920 × 1080 (lokal modell, ändrar yta men aldrig form). Det här steget lägger
sedan på det som koden kan rita skarpt direkt i 1080p:

- den målade hålbilden i översikten i början och slutet (ur originalmålningen, inte uppförstorad),
- nedräkningen till flaggan (ritas om i 1080p ovanpå den gamla rutan).

    python verktyg/flygfilm_kor.py hd klubbar/glasriket/hal-09.yaml --kam kam.json --rutor hd/ \
        --malad-upp 55,85 --ut hal-09-1080p.mp4
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

from ..hole import Hole
from .flygfilm import ffmpeg_bin
from .flygfilm_avstand import avstand_per_ruta, skylt, synlighet
from .flygfilm_kontroll import MaladKarta, Projektion, klubbens_bakgrund, malad_i_ruta, vikter

B, H = 1920, 1080


def _mjuk(u: np.ndarray) -> np.ndarray:
    u = np.clip(u, 0, 1)
    return u * u * (3 - 2 * u)


def hd_film(halfil: Path, kam: Path, rutor: Path, ut: Path, data_dir: Path, malad_upp=None,
            flagga_over_m: float = 300.0, skarp_fran: float = 0.6, crf: int = 20, maxrate: str = "3600k",
            bara: list[int] | None = None, malad: Path | None = None, malad_utan: Path | None = None) -> dict:
    """rutor = mapp med 0000.png … (1920 × 1080, redan uppskärpta, med gamla nedräkningen inbränd).
    Hålbilden med flagga används högre än flagga_over_m över marken, annars utan (flaggan blir en
    platt dekal i snedvyer). Där hålbilden täcker mer än skarp_fran av rutan tonas den skarpa in."""
    hole = Hole.from_yaml(halfil)
    hal = yaml.safe_load(Path(halfil).read_text(encoding="utf-8"))
    klubb_fil = Path(halfil).with_name("klubb.yaml")
    klubb = yaml.safe_load(klubb_fil.read_text(encoding="utf-8")) if klubb_fil.exists() else {}
    kd = json.loads(Path(kam).read_text())
    info = kd["info"]
    proj = Projektion(kd, B, H)
    n = len(proj.kams)
    fps = n / info["sekunder"]
    hojd = info["hojd_over_mark_m"]
    mal, _ = vikter(hojd, malad_upp)
    skarp = _mjuk((mal - skarp_fran) / (1 - skarp_fran))
    orto = sorted((Path(data_dir) / "orto").glob("*.tif"))[0]
    bakgrund = klubbens_bakgrund(Path(halfil))
    mapp = Path(halfil).parent / "halbilder"
    kartor = {}

    def karta(med_flagga: bool) -> MaladKarta:
        if med_flagga not in kartor:
            fil = (malad if med_flagga else malad_utan or malad) or \
                mapp / f"hal-{hole.number:02d}-malad{'' if med_flagga else '-utan-flagga'}.webp"
            kartor[med_flagga] = MaladKarta(hole, orto, Path(fil), bakgrund)
        return kartor[med_flagga]

    faser = info["faser_s"]
    meter = avstand_per_ruta(hal, kd["kameror"], info["tee"], round(faser["ned"][1] * fps))
    syn = synlighet(n, fps, faser["ned"][1], faser["upp"][0] + 0.5)
    prof = klubb.get("profil", {})
    farger = prof.get("farger", {"djup": "#142219", "glod": "#D9A441", "kristall": "#F2F2EE", "is": "#C8D6D0"})
    typ = klubb.get("typsnitt", {})
    siffror, text = typ.get("siffror", "Spectral"), typ.get("text", "Hanken Grotesk")
    marg = round(28 * H / 720)
    skyltar: dict[int, Image.Image] = {}

    def ruta(i: int) -> Image.Image:
        r = np.asarray(Image.open(Path(rutor) / f"{i:04d}.png").convert("RGB"), np.float32)
        if skarp[i] > 0.001:
            m = malad_i_ruta(karta(hojd[i] >= flagga_over_m), proj, i)
            r = r * (1 - skarp[i]) + m * skarp[i]
        bild = Image.fromarray(np.clip(r + 0.5, 0, 255).astype(np.uint8))
        a = float(syn[i])
        if a > 0:
            if meter[i] not in skyltar:
                sk = skylt(meter[i], H, farger, siffror, text)
                # ogenomskinlig ruta: den gamla (uppförstorade) rutan under ska inte lysa igenom
                sk.putalpha(sk.getchannel("A").point(lambda v: 255 if v >= 128 else v * 2))
                skyltar[meter[i]] = sk
            sk = skyltar[meter[i]]
            if a < 1:
                sk = sk.copy()
                sk.putalpha(sk.getchannel("A").point(lambda v: round(v * a)))
            bild.paste(sk, (marg, H - marg - sk.height), sk)
        return bild

    if bara is not None:
        Path(ut).mkdir(parents=True, exist_ok=True)
        for i in bara:
            ruta(i).save(Path(ut) / f"hd-{i:04d}.png")
        return {"rutor": bara}
    skriv = subprocess.Popen([ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                              "-s", f"{B}x{H}", "-r", f"{fps:g}", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                              "-profile:v", "high", "-crf", str(crf), "-maxrate", maxrate, "-bufsize", "8M",
                              "-preset", "slow", "-movflags", "+faststart", str(ut)], stdin=subprocess.PIPE)
    for i in range(n):
        skriv.stdin.write(ruta(i).tobytes())
    skriv.stdin.close()
    skriv.wait()
    return {"ut": str(ut), "rutor": n, "skarp_halbild_rutor": int((skarp > 0.001).sum())}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Färdig flygfilm i 1080p ur uppskärpta rutor")
    ap.add_argument("hal", type=Path)
    ap.add_argument("--kam", type=Path, required=True)
    ap.add_argument("--rutor", type=Path, required=True, help="mapp med uppskärpta rutor 0000.png …")
    ap.add_argument("--data", type=Path, default=None)
    ap.add_argument("--malad-upp", default="", help="samma som i animatic, t.ex. 55,85")
    ap.add_argument("--malad", type=Path, default=None, help="hålbilden med flagga (standard: klubbens hal-NN-malad.webp)")
    ap.add_argument("--malad-utan", type=Path, default=None, help="samma hålbild utan flagga, för snedvyerna")
    ap.add_argument("--bara", default="", help="spara bara de här rutorna som png i --ut (kontroll)")
    ap.add_argument("--ut", type=Path, required=True)
    a = ap.parse_args(argv)
    upp = tuple(float(v) for v in a.malad_upp.split(",")) if a.malad_upp else None
    bara = [int(v) for v in a.bara.split(",")] if a.bara else None
    print(json.dumps(hd_film(a.hal, a.kam, a.rutor, a.ut, a.data or Path("data") / a.hal.parent.name, upp, bara=bara,
                             malad=a.malad, malad_utan=a.malad_utan)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
