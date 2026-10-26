"""Lägg AI-målningar på hålets exakta form som ett TEST, utan att röra den levererade bilden.

    python verktyg/ai_tillbaka_test.py klubbar/glasriket/hal-14.yaml wow data/glasriket/ai-wow/h14-*.png
    → halbilder/hal-14-wow.webp (+ -utan-flagga) och data/glasriket/utkast/hal-14_wow_kontroll.jpg
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verktyg.orto_utsnitt  # noqa: E402,F401
from golfholes.hole import Hole  # noqa: E402
from golfholes.render.foto import ai_tillbaka, flaggstil, orto_for  # noqa: E402

hf, namn, *malningar = sys.argv[1:]
hf = Path(hf)
hole = Hole.from_yaml(hf)
club = hf.parent
ut = club / "halbilder" / f"hal-{hole.number:02d}-{namn}.webp"
kontroll = Path("data") / club.name / "utkast" / f"hal-{hole.number:02d}_{namn}_kontroll.jpg"
_, poang = ai_tillbaka(hole, orto_for(Path("data") / club.name), [Path(m) for m in malningar], ut, kontroll,
                       flagga=flaggstil(club))
for i, r in enumerate(poang):
    print(f"  {'VALD ' if i == 0 else '     '}{r['poang']:.3f}  (likhet {r['likhet']:.3f}, kant {r['kant']:.3f})  {r['fil']}")
print(ut, kontroll)
