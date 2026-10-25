"""AI-underlag i stil A: den lyfta hålbilden (verktyg/lyft.py) på mörk duk i aiunderlags placering.

    python verktyg/underlag_lyft.py klubbar/glasriket/hal-03.yaml [fler]
    Indata: halbilder/hal-NN-malad-utan-flagga.webp, annars ortofotot direkt (ny klubb).
    → typbilder/ai-underlag/hal-NN-underlag-lyft-mork.jpg
"""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verktyg.orto_utsnitt  # noqa: E402,F401
from golfholes.hole import Hole  # noqa: E402
from golfholes.render.foto import AI_SKALA, fotounderlag, orto_for  # noqa: E402
from verktyg.lyft import BOTTEN, lyft  # noqa: E402

for hf in map(Path, sys.argv[1:]):
    h = Hole.from_yaml(hf)
    n = h.number
    bild = hf.parent / "halbilder" / f"hal-{n:02d}-malad-utan-flagga.webp"
    if not bild.exists():  # ny klubb utan tidigare målning: lyft ortofotot direkt
        bild = Path("data") / hf.parent.name / "utkast" / f"hal-{n:02d}-foto.png"
        bild.parent.mkdir(parents=True, exist_ok=True)
        fotounderlag(h, orto_for(Path("data") / hf.parent.name), 4096)[0].save(bild)
    lyftad = lyft(hf, bild, hf.parent / "halbilder" / f"hal-{n:02d}-lyft.webp")
    hojd, bredd = 4096, 2304
    rot, _ = fotounderlag(h, orto_for(Path("data") / hf.parent.name), round(hojd * AI_SKALA))
    if rot.width > bredd * AI_SKALA:
        rot, _ = fotounderlag(h, orto_for(Path("data") / hf.parent.name), round(hojd * AI_SKALA * bredd * AI_SKALA / rot.width))
    l = Image.open(lyftad).convert("RGBA").resize(rot.size, Image.LANCZOS)
    duk = Image.new("RGB", (bredd, hojd), tuple(int(v) for v in BOTTEN))
    duk.paste(l, ((bredd - rot.width) // 2, (hojd - rot.height) // 2), l)
    ut = hf.parent / "typbilder" / "ai-underlag" / f"hal-{n:02d}-underlag-lyft-mork.jpg"
    duk.save(ut, quality=92)
    print(ut, flush=True)
