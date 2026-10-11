"""Kommandon:

  python -m golfholes rapport  klubbar/<klubb>/hal-07.yaml [--tee 58]
  python -m golfholes halbild  klubbar/<klubb>/hal-07.yaml          → output/<klubb>/hal-07.png
  python -m golfholes skylt    klubbar/<klubb>/hal-07.yaml          → output/<klubb>/skylt/
  python -m golfholes webb     klubbar/<klubb>                      → output/<klubb>/webb/
  python -m golfholes utsnitt  klubbar/<klubb> data/<klubb>/orto/*.tif  → data/<klubb>/utsnitt/orto.jpg + .jgw
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

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


def _club_slug(path: Path) -> str:
    return (path if path.is_dir() else path.parent).name


def halbild(path: str) -> int:
    from .render import render_flat
    from .render.export import to_png

    p = Path(path)
    hole = Hole.from_yaml(p)
    svg = render_flat(hole, width_px=600)
    w, h = (float(v) for v in re.search(r'viewBox="0 0 (\S+) (\S+)"', svg).groups())
    out = Path("output") / _club_slug(p) / f"hal-{hole.number:02d}.png"
    to_png(svg, out, w, h)
    out.with_suffix(".svg").write_text(svg, encoding="utf-8")
    print(f"Sparat: {out} och {out.with_suffix('.svg')}")
    return 0


def skylt(path: str) -> int:
    from .render.sign import build_sign

    p = Path(path)
    files = build_sign(p, Path("output") / _club_slug(p) / "skylt")
    for k, v in files.items():
        if k != "qr_akta":
            print(f"  {k}: {v}")
    if not files["qr_akta"]:
        print("OBS: QR-koden är en platshållare. Installera 'segno' (pip install segno) och kör igen före tryck.")
    return 0


def webb(club_dir: str) -> int:
    from .render.web import build_site

    p = Path(club_dir)
    for f in build_site(p, Path("output") / p.name / "webb"):
        print(f"  {f}")
    return 0


def utsnitt(club_dir: str, tiffs: list[str], resolution: float | None) -> int:
    from .lantmateriet import mosaic_crop

    p = Path(club_dir)
    club = yaml.safe_load((p / "klubb.yaml").read_text(encoding="utf-8"))
    b = club["bbox_sweref99tm"]
    out = mosaic_crop(tiffs, (b["e_min"], b["n_min"], b["e_max"], b["n_max"]),
                      Path("data") / p.name / "utsnitt" / "orto.jpg", resolution)
    print(f"Sparat: {out} + {out.with_suffix('.jgw')} – öppna båda i verktyg/ritverktyg.html")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="golfholes")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rapport", help="Avstånd, längdkontroll och kamera för ett hål")
    r.add_argument("fil")
    r.add_argument("--tee", default=None)
    sub.add_parser("halbild", help="Hålbild (grafisk stil) som PNG + SVG").add_argument("fil")
    sub.add_parser("skylt", help="Skylt 70 × 100 cm: förhandsvisning + tryck-PDF per platta").add_argument("fil")
    sub.add_parser("webb", help="Digital banguide för en klubb").add_argument("klubbmapp")
    u = sub.add_parser("utsnitt", help="Klipp ut banan ur Lantmäteriets ortofoto")
    u.add_argument("klubbmapp")
    u.add_argument("tiffar", nargs="+")
    u.add_argument("--upplosning", type=float, default=None, help="meter per pixel (standard: som källan)")
    a = p.parse_args(argv)
    if a.cmd == "rapport":
        return rapport(a.fil, a.tee)
    if a.cmd == "halbild":
        return halbild(a.fil)
    if a.cmd == "skylt":
        return skylt(a.fil)
    if a.cmd == "webb":
        return webb(a.klubbmapp)
    if a.cmd == "utsnitt":
        return utsnitt(a.klubbmapp, a.tiffar, a.upplosning)
    return 2


if __name__ == "__main__":
    sys.exit(main())
