"""Slagkurvor ("tracer") i flygfilmen: så bör hålet spelas (Eric 2026-10-25, efter en referensfilm).

Slagen kommer ur hålfilens `strategy` (klubbens PRO-råd), som meter från vald tee längs mittlinjen
(scorekortets skala). Varje slag ritas som en tunn bana i 3D (rak linje i plan, kulbana i höjd)
och projiceras ruta för ruta med samma kamera som filmen. Bollen flyger iväg när kameran är vid
utslagsplatsen och banan blir kvar tills kameran passerat nedslaget. Längden på slaget visas ovanför
nedräkningen. Bara kod, inga krediter. Landningspunkterna kontrolleras mot fairway i testerna.

Hålfilen:
  strategy:
    kalla: "PRO-råd banguide 2025: Spela som par fem för säkerhet"
    tee: '56'
    slag: [150, 270]     # nedslag, meter från tee; sista slaget går till greenens mitt
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .flygfilm_avstand import TYPSNITT, _hex, _langs, avstand_per_ruta, branna_in, synlighet
from .flygfilm_kontroll import Projektion

NAMN = ["Utslag", "Andra slaget", "Tredje slaget", "Fjärde slaget"]


@dataclass
class Slag:
    namn: str
    langd_m: int            # scorekortets meter
    fran: tuple[float, float]
    till: tuple[float, float]
    s_fran: float           # sträcka längs mittlinjen (geometrisk)
    s_till: float
    topp_m: float


def _punkt(linje: list, s: float) -> tuple[float, float]:
    acc = 0.0
    for a, b in zip(linje, linje[1:]):
        L = math.dist(a, b)
        if acc + L >= s:
            t = (s - acc) / L
            return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        acc += L
    return tuple(linje[-1])


def green_mitt(hal: dict) -> tuple[float, float]:
    g = hal["green"]
    return (sum(p[0] for p in g) / len(g), sum(p[1] for p in g) / len(g))


def slag_plan(hal: dict) -> list[Slag]:
    st = hal.get("strategy") or {}
    if not st.get("slag"):
        return []
    linje = hal["centerline"]
    tee = next(t for t in hal["tees"] if str(t["name"]) == str(st.get("tee", hal["tees"][0]["name"])))
    s_tee, total = _langs(linje, tee["point"])
    skala = tee["length_m"] / (total - s_tee)
    nedslag = [float(d) for d in st["slag"]]
    gm = green_mitt(hal)
    s_green = _langs(linje, gm)[0]
    punkter = [(tuple(tee["point"]), s_tee, 0.0)]
    punkter += [(_punkt(linje, s_tee + d / skala), s_tee + d / skala, d) for d in nedslag]
    punkter += [(gm, s_green, float(tee["length_m"]))]
    ut = []
    for k, ((a, sa, da), (b, sb, db)) in enumerate(zip(punkter, punkter[1:])):
        L = round(db - da)
        ut.append(Slag(NAMN[min(k, len(NAMN) - 1)] if k < len(punkter) - 2 else "Inspel", L, a, b, sa, sb,
                       topp_m=min(26.0, 4.0 + 0.14 * L)))
    return ut


def bana_3d(sl: Slag, proj: Projektion, n: int = 60) -> np.ndarray:
    """(n, 3) punkter: rak linje i plan, kulbana i höjd (lite brantare ner än upp, som ett riktigt slag)."""
    u = np.linspace(0, 1, n)
    e = sl.fran[0] + (sl.till[0] - sl.fran[0]) * u
    nn = sl.fran[1] + (sl.till[1] - sl.fran[1]) * u
    mark = proj.markhojd(e, nn)
    v = u ** 0.85                     # toppen lite efter mitten
    h = sl.topp_m * np.sin(np.pi * v)
    return np.stack([e, nn, mark + 0.3 + h], -1)


def tider(slag: list[Slag], kameror: list[dict], linje: list, fps: float, fran_ruta: int = 0,
          flygtid_s: float = 1.8) -> list[tuple]:
    """(start-ruta, slut-ruta, borta-ruta) per slag ur när kameran passerar utslag och nedslag.
    fran_ruta = rutan där kameran har landat vid tee (innan dess hänger den över hålet)."""
    s_kam = np.array([_langs(linje, (k["e"], k["n"]))[0] if j >= fran_ruta else -1e9
                      for j, k in enumerate(kameror)])
    ut = []
    for sl in slag:
        efter = np.nonzero(s_kam >= sl.s_fran - 12)[0]
        start = max(int(efter[0]) if len(efter) else len(kameror) - 1, fran_ruta)
        forbi = np.nonzero(s_kam >= sl.s_till - 30)[0]   # borta innan kameran når nedslaget
        borta = int(forbi[0]) if len(forbi) else len(kameror) + 1
        flyg = round(min(flygtid_s, 0.9 + 0.006 * sl.langd_m) * fps)      # korta slag landar fortare
        ut.append((start, start + flyg, max(borta, start + flyg + 6)))
    # bollen startar inte innan förra slaget landat
    for k in range(1, len(ut)):
        s, e, b = ut[k]
        s2 = max(s, ut[k - 1][1] + 4)
        ut[k] = (s2, s2 + (e - s), max(b, s2 + (e - s) + 6))
    if ut:   # sista slaget (in på green) står kvar en stund efter nedslaget, sedan tonas det bort
        s, e, b = ut[-1]
        ut[-1] = (s, e, min(b, e + round(0.9 * fps)))
    return ut


class Ritare:
    def __init__(self, hal: dict, klubb: dict, bana: dict, B: int, H: int):
        self.proj = Projektion(bana)
        self.skala = B / self.proj.bredd
        self.slag = slag_plan(hal)
        info = bana["info"]
        self.fps = len(bana["kameror"]) / info["sekunder"]
        self.tid = tider(self.slag, bana["kameror"], hal["centerline"], self.fps,
                         round(info["faser_s"]["ned"][1] * self.fps))
        self.banor = [bana_3d(s, self.proj) for s in self.slag]
        f = (klubb.get("profil") or {}).get("farger") or {}
        self.glod = _hex(f.get("glod", "#D9A441"))
        self.djup = _hex(f.get("djup", "#142219"))
        self.is_ = _hex(f.get("is", "#C8D6D0"))
        self.krist = _hex(f.get("kristall", "#F2F2EE"))
        typ = klubb.get("typsnitt") or {}
        s = H / 720
        self.ft = ImageFont.truetype(str(TYPSNITT / f"{typ.get('text', 'Hanken Grotesk').replace(' ', '')}-Medium.ttf"),
                                     round(19 * s))
        self.fs = ImageFont.truetype(str(TYPSNITT / f"{typ.get('siffror', 'Spectral').replace(' ', '')}-Medium.ttf"),
                                     round(26 * s))
        self.B, self.H, self.s = B, H, s

    def aktivt(self, i: int) -> int | None:
        for k, (start, slut, borta) in enumerate(self.tid):
            if start <= i < borta:
                nasta = self.tid[k + 1][0] if k + 1 < len(self.tid) else 10 ** 9
                if i < nasta:
                    return k
        return None

    def __call__(self, i: int, bild: Image.Image, syn: float) -> Image.Image:
        lager = Image.new("RGBA", (self.B, self.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lager)
        ritat = False
        for k, ((start, slut, borta), pts) in enumerate(zip(self.tid, self.banor)):
            if not (start <= i < borta):
                continue
            p = min(1.0, (i - start + 1) / max(1, slut - start))
            # bollen bromsas mot slutet (snabb ut, lugn ner)
            p = 1 - (1 - p) ** 1.6
            m = max(2, int(round(p * (len(pts) - 1))) + 1)
            x, y, fram = self.proj.px(i, pts[:m, 0], pts[:m, 1], pts[:m, 2])
            k_ = self.proj.kams[i]
            nara = np.hypot(pts[:m, 0] - k_.e, pts[:m, 1] - k_.n) > 18   # närmast kameran ritas inte (blir en skev streck)
            xy = [(float(a) * self.skala, float(b) * self.skala) for a, b, f, n_ in zip(x, y, fram, nara) if f and n_]
            if len(xy) < 2:
                continue
            tona = min(1.0, (borta - i) / 8)
            w = max(2, round(3 * self.s))
            d.line(xy, fill=self.glod + (round(235 * tona),), width=w, joint="curve")
            d.line(xy, fill=(255, 250, 235, round(230 * tona)), width=max(1, w // 2), joint="curve")
            if p < 1:
                bx, by = xy[-1]
                r = max(2, round(3 * self.s))
                d.ellipse((bx - r, by - r, bx + r, by + r), fill=(255, 255, 255, 255))
            ritat = True
        if ritat:
            glo = lager.filter(ImageFilter.GaussianBlur(3 * self.s))
            bild = Image.alpha_composite(Image.alpha_composite(bild.convert("RGBA"), glo), lager).convert("RGB")
        k = self.aktivt(i)
        if k is not None and syn > 0:
            bild = self._etikett(bild, self.slag[k], syn)
        return bild

    def _etikett(self, bild: Image.Image, sl: Slag, syn: float) -> Image.Image:
        """Liten rad ovanför nedräkningen: slagets namn och längd."""
        s = self.s
        d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        t1, t2 = sl.namn, f"{sl.langd_m} m"
        w = d0.textlength(t1, font=self.ft) + round(12 * s) + d0.textlength(t2, font=self.fs)
        pad = round(14 * s)
        W, Hh = round(w + 2 * pad + 4 * s), round(44 * s)
        im = Image.new("RGBA", (W, Hh), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, W - 1, Hh - 1), radius=round(8 * s), fill=self.djup + (round(210 * syn),))
        bas = round(30 * s)
        x = pad + round(4 * s)
        d.text((x, bas), t1, font=self.ft, fill=self.is_ + (round(255 * syn),), anchor="ls")
        d.text((x + d.textlength(t1, font=self.ft) + round(12 * s), bas + round(1 * s)), t2, font=self.fs,
               fill=self.glod + (round(255 * syn),), anchor="ls")
        marg = round(28 * s)
        y = self.H - marg - round(130 * s) - Hh - round(8 * s)
        bild = bild.convert("RGBA")
        bild.alpha_composite(im, (marg, max(0, y)))
        return bild.convert("RGB")


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Bränn in slagkurvor och nedräkning i en flygfilm")
    ap.add_argument("hal", type=Path)
    ap.add_argument("--kam", type=Path, required=True)
    ap.add_argument("--film", type=Path, required=True)
    ap.add_argument("--ut", type=Path, required=True)
    a = ap.parse_args(argv)
    hal = yaml.safe_load(a.hal.read_text(encoding="utf-8"))
    kf = a.hal.with_name("klubb.yaml")
    klubb = yaml.safe_load(kf.read_text(encoding="utf-8")) if kf.exists() else {}
    bana = json.loads(a.kam.read_text(encoding="utf-8"))
    info = bana["info"]
    fps = len(bana["kameror"]) / info["sekunder"]
    faser = info["faser_s"]
    st = hal.get("strategy") or {}
    meter = avstand_per_ruta(hal, bana["kameror"], st.get("tee") or info["tee"], round(faser["ned"][1] * fps))
    syn = synlighet(len(meter), fps, faser["ned"][1], faser["upp"][0] + 0.5)
    import subprocess
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(a.film)], capture_output=True, text=True, check=True).stdout.split(",")
    ritare = Ritare(hal, klubb, bana, int(p[0]), int(p[1]))
    branna_in(a.film, meter, syn, klubb, a.ut, extra=ritare)
    print(json.dumps({"ut": str(a.ut), "slag": [(s.namn, s.langd_m) for s in ritare.slag], "tider": ritare.tid}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
