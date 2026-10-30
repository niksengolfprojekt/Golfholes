"""Tona en fairwaybit i AI-underlaget (Eric 2026-10-30, hål 1 i stil B).
Stil B ritar en tuschkant runt varje fairway, så en smal förbindelse som bara ser ut som ruff
i underlaget blir två skilda fairways. Det här tonar polygonen mot fairwayfärgen direkt i
underlaget (samma `tona` som för färdiga bilder), så AI:n ser en sammanhängande fairway.

    python verktyg/underlag_fairway_ton.py klubbar/glasriket/hal-01.yaml 2
"""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verktyg.orto_utsnitt  # noqa: E402,F401
from golfholes.hole import Hole  # noqa: E402
from golfholes.render.foto import AI_SKALA, fotounderlag, orto_for  # noqa: E402
from verktyg.fairway_ton import tona  # noqa: E402

hf, nr = Path(sys.argv[1]), int(sys.argv[2])
h = Hole.from_yaml(hf)
o = orto_for(Path("data") / hf.parent.name)
ut = hf.parent / "typbilder" / "ai-underlag" / f"hal-{h.number:02d}-underlag-lyft-mork.jpg"
im = Image.open(ut).convert("RGBA")
bredd, hojd = im.size
# samma placering som underlag_lyft.py
rot, px = fotounderlag(h, o, round(hojd * AI_SKALA))
if rot.width > bredd * AI_SKALA:
    rot, px = fotounderlag(h, o, round(hojd * AI_SKALA * bredd * AI_SKALA / rot.width))
dx, dy = (bredd - rot.width) // 2, (hojd - rot.height) // 2


def px_duk(e, n):
    x, y = px(e, n)
    return (x + dx, y + dy)


for _ in range(2):  # två varv: bandet blir lika ljust som resten av fairwayn
    print(f"{tona(im, h, px_duk, nr):.0f} bildpunkter tonade")
im.convert("RGB").save(ut, quality=92)
print(ut)
