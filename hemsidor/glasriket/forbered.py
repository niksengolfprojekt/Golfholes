"""Gör i ordning sajtens fasta tillgångar (körs sällan, resultatet checkas in i tillgangar/):
typsnitt som woff2, sigillet som genomskinlig bild och favicon, och fotona i webbstorlek.

Källorna ligger i projektmappen (/mnt/project-files/glasriket/), som bara finns i molnet.
Bygget (bygg.py) behöver inte projektmappen – bara det som redan ligger i tillgangar/.

Kör:  python hemsidor/glasriket/forbered.py
Kräver: Pillow, fonttools + brotli (typsnitt) och playwright (sigillet).
"""
import re
import sys
from pathlib import Path

from PIL import Image

ROT = Path(__file__).resolve().parent
UT = ROT / "tillgangar"
KALLA = Path("/mnt/project-files/glasriket")

TYPSNITT = {
    "spectral-400": "Spectral-Regular.ttf",
    "spectral-500": "Spectral-Medium.ttf",
    "spectral-400i": "Spectral-Italic.ttf",
    "hanken-400": "HankenGrotesk-Regular.ttf",
    "hanken-500": "HankenGrotesk-Medium.ttf",
    "hanken-600": "HankenGrotesk-SemiBold.ttf",
}
# Latin + svenska tecken, typografiska citattecken, tankstreck, punkt, pil, euro, minus
TECKEN = "U+0000-00FF,U+0131,U+0152-0153,U+2013-2014,U+2018-201E,U+2022,U+2026,U+2032-2033,U+2039-203A,U+20AC,U+2122,U+2190-2193,U+2212,U+00A0"

# Ögonhöjdsbilder (visualiseringar). Bara godkända vyer på riktiga hål + en allmän.
FOTON = {
    "hal-03-inspel": "ogonhojd/v2/h03-inspel.jpg",
    "hal-05-inspel": "ogonhojd/v2/h05-inspel.jpg",
    "hal-05-tee": "ogonhojd/v2/h05-tee.jpg",
    "hal-14-inspel": "ogonhojd/v2/h14-inspel.jpg",
    "hal-14-tee": "ogonhojd/v2/h14-tee.jpg",
    "parken": "ogonhojd/v2/allm-park.jpg",
}


def typsnitt():
    from fontTools import subset

    (UT / "fonts").mkdir(parents=True, exist_ok=True)
    for namn, fil in TYPSNITT.items():
        ut = UT / "fonts" / f"{namn}.woff2"
        subset.main([str(KALLA / "profil" / "typsnitt" / fil), f"--unicodes={TECKEN}", "--flavor=woff2",
                     "--layout-features=kern,liga,lnum,pnum,tnum,onum", f"--output-file={ut}"])
        print(ut.name, ut.stat().st_size // 1024, "kB")


def sigill():
    """Sigillet 'Småland' som genomskinlig bild: SVG:n ritas i Chromium utan bakgrund."""
    from playwright.sync_api import sync_playwright

    (UT / "img").mkdir(parents=True, exist_ok=True)
    mapp = KALLA / "logo-fornyad" / "sigill" / "smaland"
    varianter = {"sigill": "fargad_ljus-botten", "sigill-mork": "fargad_mork-botten"}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for namn, var in varianter.items():
            svg = (mapp / f"Glasriket_sigill-smaland_{var}.svg").read_text(encoding="utf-8")
            svg = re.sub(r"<metadata>.*?</metadata>", "", svg, flags=re.S)
            # bakgrundsrutan tas bort så att bilden blir genomskinlig
            svg = re.sub(r'<rect x="-10" y="-10" width="220" height="220" fill="#[0-9A-Fa-f]{6}"/>', "", svg, count=1)
            sida = b.new_page(viewport={"width": 1024, "height": 1024})
            sida.set_content(f"<html><body style='margin:0;background:transparent'>"
                             f"<div style='width:1024px;height:1024px'>{svg.replace('width=\"3000\" height=\"3000\"', 'width=\"1024\" height=\"1024\"')}</div></body></html>")
            png = UT / "img" / f"{namn}-1024.png"
            sida.screenshot(path=str(png), omit_background=True)
            sida.close()
            im = Image.open(png).convert("RGBA")
            for storlek in (96, 192):
                im.resize((storlek, storlek), Image.LANCZOS).save(UT / "img" / f"{namn}-{storlek}.png", optimize=True)
            png.unlink()
        b.close()
    ljus = Image.open(UT / "img" / "sigill-192.png")
    ljus.resize((32, 32), Image.LANCZOS).save(UT / "favicon-32.png")
    duk = Image.new("RGBA", (180, 180), (238, 243, 236, 255))
    duk.alpha_composite(ljus.resize((160, 160), Image.LANCZOS), (10, 10))
    duk.convert("RGB").save(UT / "apple-touch-icon.png")


def foton():
    (UT / "img").mkdir(parents=True, exist_ok=True)
    for namn, fil in FOTON.items():
        im = Image.open(KALLA / fil).convert("RGB")
        for b in (800, 1600):
            kopia = im.resize((b, round(im.height * b / im.width)), Image.LANCZOS)
            kopia.save(UT / "img" / f"{namn}-{b}.webp", quality=78, method=6)
    # Banöversikten (Lantmäteriets ortofoto, bearbetat; källtexten finns i bilden)
    im = Image.open(KALLA / "oversikt" / "glasriket-oversikt-A-sommar.jpg").convert("RGB")
    for h in (1200, 2000):
        im.resize((round(im.width * h / im.height), h), Image.LANCZOS).save(
            UT / "img" / f"oversikt-{h}.webp", quality=80, method=6)


if __name__ == "__main__":
    delar = sys.argv[1:] or ["typsnitt", "sigill", "foton"]
    for d in delar:
        globals()[d]()
