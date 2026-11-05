"""Gör banrundans underlag av en PÅHITTAD bana (startsidan på tacada.se).

Eric 2026-11-05: TACADA-sidan ska inte visa Glasriket, hålen får vara påhittade.
Banbilden är målad av AI (ingen riktig klubb), så terrängen räknas fram ur bilden:
  - skog (grov, ojämn yta) höjs till trädhöjd 13-24 m, ljusa kronor högst,
  - vatten (blågrått, slätt) blir plant och lite nedsänkt,
  - spelytor och klubbhus ligger på mjukt böljande mark,
  - papperskanten (gräddvit) ligger platt.
Ingen riktig klubbs hålfil använder detta; regeln om verklig geometri gäller riktiga klubbar.

Kör:  python hemsida/verktyg/fiktiv_bana.py <banbild.png>
Skriver hemsida/public/img/banrunda/{karta.webp, karta-reserv.webp, terrang.json}.
"""
import base64
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

UT = Path(__file__).resolve().parents[1] / "public" / "img" / "banrunda"
BREDD_M = 1016.0      # banbildens bredd i meter (påhittad skala, ungefär en riktig 18-hålsbana)
STEG = 2.0            # rutnät i meter


def main(kalla):
    im = Image.open(kalla).convert("RGB")
    W, H = im.size
    hojd_m = BREDD_M * H / W
    nx, ny = int(BREDD_M / STEG), int(hojd_m / STEG)

    # Texturen till webben: 2048 bred, och en mindre reservbild utan 3D.
    k = im.resize((2048, round(2048 * H / W)), Image.LANCZOS)
    k.save(UT / "karta.webp", quality=84, method=6)
    r = im.resize((1100, round(1100 * H / W)), Image.LANCZOS)
    r.save(UT / "karta-reserv.webp", quality=80, method=6)

    # Analys på 1 m-nivå, sedan ner till 2 m-rutnätet.
    a = np.asarray(im.resize((nx * 2, ny * 2), Image.LANCZOS), dtype=np.float32) / 255
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    lum = .3 * R + .59 * G + .11 * B
    mx, mn = a.max(-1), a.min(-1)
    sat = (mx - mn) / (mx + 1e-4)
    lokal = np.sqrt(np.maximum(ndimage.uniform_filter(lum ** 2, 9) - ndimage.uniform_filter(lum, 9) ** 2, 0))

    papper = (lum > .9) & (sat < .12)
    jamn = ndimage.uniform_filter(lokal, 5)
    vatten = (jamn < .014) & (np.abs(G - B) < .07) & (R < G + .03) & (lum < .72) & ~papper
    vatten = ndimage.binary_opening(vatten, iterations=2)
    vatten = ndimage.binary_closing(vatten, iterations=3)
    # Bara stora vattenytor (sjön och bäcken), inte skuggor och grus.
    lab, n = ndimage.label(vatten)
    if n:
        st = ndimage.sum(vatten, lab, range(1, n + 1))
        vatten = np.isin(lab, 1 + np.nonzero(st > 3000)[0])
    # Spelytor: släta och gröna. Byggt: rött tak eller grått grus. Resten är skog.
    spel = (jamn < .075) & (G - B > .06) & (G >= R - .01) & (lum > .15) & ~vatten & ~papper
    spel = ndimage.binary_opening(spel, iterations=2)
    lab, n = ndimage.label(spel)
    if n:
        st = ndimage.sum(spel, lab, range(1, n + 1))
        spel = np.isin(lab, 1 + np.nonzero(st > 150)[0])
    byggt = ((R > G + .06) | ((sat < .15) & (lum > .45))) & ~papper
    byggt = ndimage.binary_opening(byggt, iterations=2)
    skog = ~spel & ~vatten & ~papper & ~byggt & (lum < .88)
    skog = ndimage.binary_opening(skog, iterations=2)
    lab, n = ndimage.label(~skog)
    if n:
        st = ndimage.sum(~skog, lab, range(1, n + 1))
        skog |= np.isin(lab, 1 + np.nonzero(st < 60)[0])
    lab, n = ndimage.label(skog)
    if n:
        st = ndimage.sum(skog, lab, range(1, n + 1))
        skog = np.isin(lab, 1 + np.nonzero(st >= 300)[0])

    # Trädkronor: ljusa toppar högre, mörka luckor lägre, mjuka kanter mot fairway.
    krona = ndimage.gaussian_filter(lum, 1.2)
    krona = (krona - krona[skog].min()) / (np.ptp(krona[skog]) + 1e-4) if skog.any() else krona
    # Mjuka kanter: annars sträcks bilden ut på branta väggar när kameran går lågt.
    kant = ndimage.gaussian_filter(skog.astype(np.float32), 4)
    trad = kant * (9 + 7 * ndimage.gaussian_filter(np.clip(krona, 0, 1), 2))

    # Mjukt böljande mark (påhittad), lägre mot sjön.
    rng = np.random.default_rng(7)
    mark = ndimage.gaussian_filter(rng.standard_normal(lum.shape), 60) * 900
    mark += ndimage.gaussian_filter(rng.standard_normal(lum.shape), 18) * 60
    vat_avst = ndimage.distance_transform_edt(~vatten)
    mark -= 4 * np.exp(-vat_avst / 40)
    ytniva = np.percentile(mark[vatten], 20) if vatten.any() else mark.min()
    mark = np.where(vatten, ytniva - .4, mark)
    mark = ndimage.gaussian_filter(mark, 1.5)
    pap = ndimage.gaussian_filter(papper.astype(np.float32), 6)
    hojd = (mark - mark.min()) * (1 - pap) + trad * (1 - pap)

    hojd = hojd.reshape(ny, 2, nx, 2).mean((1, 3))
    hz = np.clip(np.round(hojd * 100), 0, 65535).astype("<u2")
    T = {"nx": nx, "ny": ny, "steg": STEG, "bas": 0.0, "E0": 0.0, "N0": round(ny * STEG, 3),
         "B": round(nx * STEG, 3), "H": round(ny * STEG, 3),
         "data": base64.b64encode(hz.tobytes()).decode()}
    (UT / "terrang.json").write_text(json.dumps(T, separators=(",", ":")))
    print(f"{nx}x{ny} rutor, höjd {hojd.min():.1f}-{hojd.max():.1f} m, skog {skog.mean():.0%}, vatten {vatten.mean():.0%}")
    return skog, vatten, papper


if __name__ == "__main__":
    main(sys.argv[1])
