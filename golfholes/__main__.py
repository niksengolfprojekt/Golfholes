"""Kör: python -m golfholes rapport klubbar/exempel-ekbacka/hal-07.yaml [--tee 58]"""
from __future__ import annotations

import argparse
import json
import sys

from .hole import Hole


def rapport(path: str, tee: str | None) -> int:
    hole = Hole.from_yaml(path)
    t = hole.tee(tee)
    print(f"{hole.club} · Hål {hole.number} · Par {hole.par}" + (f" · Index {hole.index}" if hole.index else ""))
    print()
    print("Längdkontroll mot scorekortet:")
    all_ok = True
    for r in hole.check_lengths():
        status = "ok" if r.get("ok") else ("AVVIKER" if "ok" in r else "–")
        all_ok &= r.get("ok", True)
        extra = f"  scorekort {r['scorekort']} m ({r['avvikelse_%']:+} %)" if r["scorekort"] else ""
        print(f"  Tee {r['tee']:>4}: {r['uppmätt']} m{extra}  {status}")
    print()
    print(f"Avstånd från tee {t.name}:")
    for r in hole.hazard_distances(t.name):
        name = f" ({r['namn']})" if r["namn"] else ""
        print(f"  {r['typ']}{name}, {r['sida']}: {r['till']}–{r['carry']} m")
    gd = hole.green_distances(t.name)
    print(f"  Green: fram {gd['fram']:.0f} m · mitt {gd['mitt']:.0f} m · bak {gd['bak']:.0f} m")
    print()
    print("Kamera för tee-vy:")
    print(json.dumps(hole.camera(t.name), ensure_ascii=False, indent=2))
    return 0 if all_ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="golfholes")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rapport", help="Avstånd, längdkontroll och kamera för ett hål")
    r.add_argument("fil")
    r.add_argument("--tee", default=None)
    a = p.parse_args(argv)
    if a.cmd == "rapport":
        return rapport(a.fil, a.tee)
    return 2


if __name__ == "__main__":
    sys.exit(main())
