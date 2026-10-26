"""Kör `python -m golfholes ...` (flygfilm, flygfilm_kontroll m.fl.) på det sparade utsnittet i molnet.

    python verktyg/flygfilm_kor.py flygfilm klubbar/glasriket/hal-09.yaml --forlopp oversikt --hojd 28 --blick 160
    python verktyg/flygfilm_kor.py kontroll kameror klubbar/glasriket/hal-09.yaml --forlopp oversikt --hojd 28 ...
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verktyg.flygfilm_utsnitt as fu  # noqa: E402
from golfholes.render import flygfilm_kontroll as fk  # noqa: E402

steg, *rest = sys.argv[1:]
if "--data" not in rest:
    rest += ["--data", str(fu.DATA)]
if steg == "kontroll":
    sys.exit(fk.main(rest))
from golfholes.__main__ import main  # noqa: E402
sys.exit(main([steg, *rest]))
