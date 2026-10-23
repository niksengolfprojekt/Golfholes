"""Utsnitt ur ortofotot med SWEREF 99 TM-rutnät – för att läsa av koordinater på tees och green.

Läser utsnittet (orto.jpg + orto.jgw) som `hamta`/`utsnitt` gör, ritar linjer var `steg` meter
med koordinaterna utskrivna och kan markera punkter (t.ex. tee 56 från översikten).

    python verktyg/rutnat.py ORTO.jpg E N --radie 250 --steg 25 --ut bild.jpg \
        --punkt 491586,6306147,T56 --punkt 491600,6306400,G
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None


def las_jgw(jpg: Path) -> tuple[float, float, float, float]:
    v = [float(x) for x in jpg.with_suffix(".jgw").read_text().split()]
    return v[0], v[3], v[4], v[5]  # px-storlek x, px-storlek y (negativ), e och n för första pixelns mitt


def rutnat(orto: Path, e: float, n: float, radie: float, steg: float, ut: Path,
           punkter: list[tuple[float, float, str]] = (), bredd: int = 1400) -> Path:
    sx, sy, e0, n0 = las_jgw(orto)
    im = Image.open(orto)
    x0, x1 = int((e - radie - e0) / sx), int((e + radie - e0) / sx)
    y0, y1 = int((n + radie - n0) / sy), int((n - radie - n0) / sy)
    bit = im.crop((x0, y0, x1, y1)).convert("RGB")
    skala = bredd / bit.width
    bit = bit.resize((bredd, int(bit.height * skala)), Image.LANCZOS)
    d = ImageDraw.Draw(bit)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    def px(E, N):
        return ((E - e0) / sx - x0) * skala, ((N - n0) / sy - y0) * skala

    emin, emax = e - radie, e + radie
    nmin, nmax = n - radie, n + radie
    g = (emin // steg + 1) * steg
    while g < emax:
        x, _ = px(g, n)
        d.line([(x, 0), (x, bit.height)], fill=(255, 255, 255), width=1)
        d.text((x + 3, 3), f"{g:.0f}", fill=(255, 255, 0), font=font, stroke_width=2, stroke_fill=(0, 0, 0))
        g += steg
    g = (nmin // steg + 1) * steg
    while g < nmax:
        _, y = px(e, g)
        d.line([(0, y), (bit.width, y)], fill=(255, 255, 255), width=1)
        d.text((3, y + 3), f"{g:.0f}", fill=(255, 255, 0), font=font, stroke_width=2, stroke_fill=(0, 0, 0))
        g += steg
    for E, N, txt in punkter:
        x, y = px(E, N)
        d.ellipse([x - 7, y - 7, x + 7, y + 7], outline=(255, 0, 0), width=3)
        d.text((x + 10, y - 8), txt, fill=(255, 0, 0), font=font, stroke_width=2, stroke_fill=(255, 255, 255))
    d.text((8, bit.height - 22), f"N uppåt · rutor {steg:g} m", fill=(255, 255, 255), font=font,
           stroke_width=2, stroke_fill=(0, 0, 0))
    ut.parent.mkdir(parents=True, exist_ok=True)
    bit.save(ut, quality=88)
    return ut


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("orto", type=Path)
    p.add_argument("e", type=float)
    p.add_argument("n", type=float)
    p.add_argument("--radie", type=float, default=250)
    p.add_argument("--steg", type=float, default=25)
    p.add_argument("--bredd", type=int, default=1400)
    p.add_argument("--ut", type=Path, required=True)
    p.add_argument("--punkt", action="append", default=[], help="E,N,text")
    a = p.parse_args()
    pk = []
    for s in a.punkt:
        e, n, *t = s.split(",")
        pk.append((float(e), float(n), t[0] if t else ""))
    print(rutnat(a.orto, a.e, a.n, a.radie, a.steg, a.ut, pk, a.bredd))


if __name__ == "__main__":
    main()
