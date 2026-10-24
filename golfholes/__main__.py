"""Kommandon:

  python -m golfholes rapport  klubbar/<klubb>/hal-07.yaml [--tee 58]
  python -m golfholes halbild  klubbar/<klubb>/hal-07.yaml [--stil Gravyr] → output/<klubb>/hal-07-<stil>.png
  python -m golfholes skylt    klubbar/<klubb>/hal-07.yaml [--stil Gravyr] → output/<klubb>/skylt/
  python -m golfholes stilprov klubbar/<klubb>                      → output/<klubb>/stilprov/ (de sex att välja från)
  python -m golfholes aiprompt klubbar/<klubb>/hal-07.yaml [--stil Gravyr] → AI-prompten för klubbens stil

Stil väljs i klubb.yaml med `stil:` och ett av de sex namnen (beslut 2026-10-22):
  Akvarell · Sommarakvarell · Gravyr · Mjuk 3D · Arkitektskiss · Papperssnitt
(Glasriket har sin egen fotostil `stil: foto`.) Gamla `stil: 1–4` läses med en varning.
--stil på kommandoraden går före klubbens val.
  python -m golfholes halkort  klubbar/<klubb>/halkort/hal-14.yaml [--layout 1-7] → output/<klubb>/halkort/
  python -m golfholes layoutprov klubbar/<klubb>/halkort/hal-14.yaml  → samma hål i alla layouter + översikt

Layout väljs i klubb.yaml med `layout: 1` (eller en lista, t.ex. [1, 4]):
  1 Hålkort (spikad) · 2 Poster · 3 Mörk · 4 Skärm · 5 Banguide · 6 Sponsorhål
  python -m golfholes webb     klubbar/<klubb>                      → output/<klubb>/webb/
  python -m golfholes prospekt klubbar/<klubb>/halkort/hal-14.yaml  → output/<klubb>/prospekt/ (PDF + översikt)
  python -m golfholes prospekt klubbar/<klubb> --alla               → ett prospekt per hål som har hålbild
  python -m golfholes prospekt klubbar/<klubb> --gemensam           → en presentation för alla hål + kryssrutor
  python -m golfholes inlagg   klubbar/<klubb>                      → output/<klubb>/inlagg/ (PNG 4:5 + texter.md)
  python -m golfholes utsnitt  klubbar/<klubb> data/<klubb>/orto/*.tif  → data/<klubb>/utsnitt/orto.jpg + .jgw
  python -m golfholes sponsorrapport klubbar/<klubb> --sasong 2027 [--kalla mapp] → output/<klubb>/sponsorrapport/2027/
  python -m golfholes partnerexport  klubbar/<klubb>                  → output/<klubb>/partner/ (JSON per hål + zip)
  python -m golfholes flygfilm klubbar/<klubb>/hal-14.yaml [--data data/<klubb>] [--sek 12]
                                                                    → output/<klubb>/flygfilm/ (rå MP4 + nyckelbilder)
"""
from __future__ import annotations

import argparse
from datetime import date
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


def _stil_for(p: Path, stil: str | None):
    from .stilar import klubbens_stil

    return klubbens_stil(p if p.is_dir() else _club_dir(p), stil)


def halbild(path: str, stil: str | None) -> int:
    from .render.export import to_png
    from .render.styles import render_hole
    from .stilar import malad_bild

    p = Path(path)
    hole = Hole.from_yaml(p)
    stil = _stil_for(p, stil)
    malad = malad_bild(_club_dir(p), hole.number, stil)
    if malad.exists():
        print(f"Målad hålbild i {stil.namn} finns: {malad} (används i hålkort och webb).")
    svg = render_hole(hole, stil.ritmotor, width_px=600, fit=False)
    w, h = (float(v) for v in re.search(r'viewBox="0 0 (\S+) (\S+)"', svg).groups())
    out = Path("output") / _club_slug(p) / f"hal-{hole.number:02d}-{stil.nyckel}-kodritad.png"
    to_png(svg, out, w, h)
    out.with_suffix(".svg").write_text(svg, encoding="utf-8")
    print(f"Sparat: {out} och {out.with_suffix('.svg')}")
    return 0


def skylt(path: str, stil: str | None) -> int:
    from .render.sign import build_sign

    p = Path(path)
    files = build_sign(p, Path("output") / _club_slug(p) / "skylt", style=stil)
    print(f"Stil: {files.pop('stil')}")
    for k, v in files.items():
        if k != "qr_akta":
            print(f"  {k}: {v}")
    if not files["qr_akta"]:
        print("OBS: QR-koden är en platshållare. Installera 'segno' (pip install segno) och kör igen före tryck.")
    return 0


def stilprov(path: str) -> int:
    from .stilar import MENY, stilprov as bygg

    p = Path(path)
    files = bygg(Path("output") / _club_slug(p) / "stilprov")
    for k, v in files.items():
        print(f"  {k}: {v}")
    print("Klubben väljer en av: " + ", ".join(s.namn for s in MENY)
          + ". Skriv namnet som `stil:` i klubb.yaml, t.ex. `stil: Gravyr`.")
    return 0


def aiprompt(path: str, stil: str | None) -> int:
    p = Path(path)
    s = _stil_for(p, stil)
    print(f"Stil: {s.namn}\n")
    print(s.prompt)
    return 0


def _club_dir(p: Path) -> Path:
    for d in [p.parent, *p.parents]:
        if (d / "klubb.yaml").exists():
            return d
    return p.parent


def halkort(path: str, layout: str | None) -> int:
    from .render.halkort import Halkort, parse_layout, render

    p = Path(path)
    club_dir = _club_dir(p)
    club = yaml.safe_load((club_dir / "klubb.yaml").read_text(encoding="utf-8")) or {}
    layouts = parse_layout(layout if layout is not None else club.get("layout", 1))
    c = Halkort.from_yaml(p)
    fel = c.kontroll()
    for f in fel:
        print(f"FEL: {f}")
    if fel:
        return 1
    for n in layouts:
        out = render(c, n, Path("output") / club_dir.name / "halkort" / f"{p.stem}-layout{n}.png")
        print(f"  {out}")
    return 0


def layoutprov(path: str) -> int:
    from .render.halkort import Halkort, build_layout_samples

    p = Path(path)
    c = Halkort.from_yaml(p)
    for f in c.kontroll():
        print(f"FEL: {f}")
    for k, v in build_layout_samples(c, Path("output") / _club_dir(p).name / "layoutprov").items():
        print(f"  {k}: {v}")
    print("Klubben väljer layout och skriver in det som `layout:` i klubb.yaml.")
    return 0


def webb(club_dir: str) -> int:
    from .render.web import build_site

    p = Path(club_dir)
    for f in build_site(p, Path("output") / p.name / "webb"):
        print(f"  {f}")
    return 0


def prospekt(path: str, alla: bool, ut: str | None, gemensam: bool = False) -> int:
    from .render.klubbmaterial import Klubb
    from .render.prospekt import bygg_alla

    p = Path(path)
    if gemensam:
        from .render.prospekt_gemensam import bygg

        mapp = p if p.is_dir() else _club_dir(p)
        r = bygg(mapp, Path(ut) if ut else Path("output") / mapp.name / "prospekt")
        print(f"  {r['pdf']}\n  {r['oversikt']}")
        print(f"  {r['lediga']} av {r['hal']} hål lediga; {r['kryssrutor']} kryssrutor går att kryssa i PDF:en"
              + ("" if r["kryssrutor"] or not r["lediga"] else " (pypdf saknas: pip install pypdf)"))
        if not r["qr_akta"]:
            print("OBS: QR-koden är en platshållare. Installera 'segno' (pip install segno) och kör igen.")
        return 0
    if alla or p.is_dir():
        k = Klubb.from_dir(p if p.is_dir() else _club_dir(p))
        filer = list(k.halkort().values())
        saknas = sorted(set(range(1, 19)) - set(k.halkort()))
        if saknas:
            print(f"Hål utan hålbild (hoppas över): {', '.join(map(str, saknas))}")
    else:
        k = Klubb.from_dir(_club_dir(p))
        filer = [p]
    res = bygg_alla(filer, Path(ut) if ut else Path("output") / k.mapp.name / "prospekt")
    if not all(r["qr_akta"] for r in res):
        print("OBS: QR-koden är en platshållare. Installera 'segno' (pip install segno) och kör igen.")
    return 0


def inlagg(club_dir: str, ut: str | None) -> int:
    from .render.inlagg import bygg_kit

    p = Path(club_dir)
    bygg_kit(p, Path(ut) if ut else Path("output") / p.name / "inlagg")
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


def _club_bbox(club_dir: str) -> tuple[Path, dict]:
    p = Path(club_dir)
    club = yaml.safe_load((p / "klubb.yaml").read_text(encoding="utf-8"))
    if not club.get("bbox_sweref99tm"):
        raise SystemExit(f"{p / 'klubb.yaml'} saknar bbox_sweref99tm – banans yta måste anges först.")
    return p, club["bbox_sweref99tm"]


def sok(club_dir: str) -> int:
    from .geotorget import bbox_wgs84, sok as stac_sok

    _p, b = _club_bbox(club_dir)
    bbox = bbox_wgs84(b)
    for kat, namn in (("orto", "Ortofoto"), ("hojd", "Markhöjdmodell")):
        rutor = stac_sok(kat, bbox)
        print(f"{namn}: {len(rutor)} rutor")
        for r in sorted(rutor, key=lambda r: r.datum, reverse=True):
            print(f"  {r.datum}  {r.samling:<18} {r.id}")
    return 0


def hamta(club_dir: str, ar: int | None) -> int:
    from .geotorget import bbox_wgs84, hamta as stac_hamta

    p, b = _club_bbox(club_dir)
    data_dir = Path("data") / p.name
    logg = stac_hamta(bbox_wgs84(b), data_dir, ar)
    for f in logg["filer"]:
        print(f"  {f['katalog']:<5} {f['datum']}  {f['fil']}")
    orto = [f["fil"] for f in logg["filer"] if f["katalog"] == "orto"]
    print(f"Logg: {data_dir / 'lantmateriet.json'}")
    utsnitt(club_dir, orto, None)
    from .lantmateriet import hojd_utsnitt

    hojd = [f["fil"] for f in logg["filer"] if f["katalog"] == "hojd"]
    h = hojd_utsnitt(hojd, (b["e_min"], b["n_min"], b["e_max"], b["n_max"]), data_dir / "utsnitt")
    print(f"Höjd: {h['lagst']}–{h['hogst']} m ö.h. → {h['fil']} + hojd_skuggning.png")
    return 0


def utkast(fro_fil: str) -> int:
    from .utkast import kontrollbild, utkast_hal

    fp = Path(fro_fil)
    fro = yaml.safe_load(fp.read_text(encoding="utf-8"))
    fro["_fil"] = str(fp)
    hal, f, _ = utkast_hal(fro, fro["orto"])
    ut = fp.parent.parent / f"hal-{int(fro['hole']):02d}.yaml"
    huvud = (f"# UTKAST – genererat {date.today()} av `python -m golfholes utkast {fp}`.\n"
             "# Granska mot klubbens hålkarta och kontrollbilden innan det godkänns.\n")
    ut.write_text(huvud + yaml.safe_dump(hal, allow_unicode=True, sort_keys=False, default_flow_style=None, width=200),
                  encoding="utf-8")
    kb = kontrollbild(hal, f, Path("data") / fp.parent.parent.name / "utkast" / f"hal-{int(fro['hole']):02d}_kontroll.jpg")
    from .utkast import ritverktyg_json
    rj = ritverktyg_json(hal, kb.with_name(f"hal-{int(fro['hole']):02d}_ritverktyg.json"))
    n = {k: len(hal[k]) for k in ("fairways", "trees")}
    print(f"Sparat: {ut} (green {len(hal['green'])} punkter, {n['fairways']} fairway, "
          f"{sum(h['kind'] == 'bunker' for h in hal['hazards'])} bunkrar, "
          f"{sum(h['kind'] == 'water' for h in hal['hazards'])} vatten, {n['trees']} skogsytor)")
    print(f"Kontrollbild: {kb}")
    print(f"Rätta i verktyg/ritverktyg.html: öppna orto.jpg + orto.jgw + {rj}")
    return rapport(str(ut), None)


def fotobild(path: str) -> int:
    from .render.foto import fotobild as rita, orto_for

    p = Path(path)
    hole = Hole.from_yaml(p)
    club_dir = _club_dir(p)
    ut = club_dir / "halbilder" / f"hal-{hole.number:02d}-foto.webp"
    rita(hole, orto_for(Path("data") / club_dir.name), ut)
    print(f"Sparat: {ut} – lägg in som `bild:` i halkort/hal-{hole.number:02d}.yaml")
    return 0


def aiunderlag(path: str) -> int:
    from .render.foto import ai_underlag, orto_for

    p = Path(path)
    hole = Hole.from_yaml(p)
    club_dir = _club_dir(p)
    ut = club_dir / "typbilder" / "ai-underlag" / f"hal-{hole.number:02d}-underlag.jpg"
    ai_underlag(hole, orto_for(Path("data") / club_dir.name), ut, hojd_px=4096, bredd=2304)
    s = _stil_for(p, None)
    print(f"Sparat: {ut} – ge den till AI:n (9:16). Den får bara byta yta, aldrig form.")
    print(f"Klubbens stil: {s.namn}. Prompt (bara underlaget som referens, aldrig stilprovet):\n{s.prompt}")
    return 0


AI_GRANS = 0.7  # under detta har AI:n ritat om hålet (provat: trogna 0,80–0,88, omritade 0,38)


def aibild(path: str, malningar: list[str], stil: str | None = None) -> int:
    from .render.foto import ai_tillbaka, orto_for
    from .stilar import malad_bild

    p = Path(path)
    hole = Hole.from_yaml(p)
    club_dir = _club_dir(p)
    s = _stil_for(p, stil)
    ut = malad_bild(club_dir, hole.number, s)
    print(f"Stil: {s.namn}")
    kontroll = Path("data") / club_dir.name / "utkast" / f"hal-{hole.number:02d}_ai_kontroll.jpg"
    _, poang = ai_tillbaka(hole, orto_for(Path("data") / club_dir.name), [Path(m) for m in malningar], ut, kontroll)
    for i, r in enumerate(poang):
        print(f"  {'VALD ' if i == 0 else '     '}{r['poang']:.3f}  (likhet {r['likhet']:.3f}, kant {r['kant']:.3f})  {r['fil']}")
    if poang[0]["poang"] < AI_GRANS:
        print(f"VARNING: bästa formpoängen {poang[0]['poang']:.2f} är under {AI_GRANS} – AI:n har flyttat formen. Använd inte bilden, måla om.")
    print(f"Sparat: {ut}\nKontrollera {kontroll}: hålfilens linjer måste ligga på målningens kanter.")
    return 0


def sponsorrapport(club_dir: str, sasong: int, kalla: str | None, pdf: bool) -> int:
    from .statistik import bygg_rapport

    p = Path(club_dir)
    r, filer = bygg_rapport(p, sasong, Path("output") / p.name / "sponsorrapport" / str(sasong), kalla, pdf)
    for v in r.varningar:
        print(f"OBS: {v}")
    if r.testdata:
        print("TESTDATA: källan är testsiffror – rapporten är märkt TESTDATA och får inte gå till en sponsor.")
    for h in r.hal:
        delar = ", ".join(f"{k.namn} {'≈' if k.uppskattning else ''}{k.visningar}" for k in h.kanaler)
        print(f"  Hål {h.hal} · {h.sponsor.get('name')}: {delar or 'inga siffror'}")
    for f in filer:
        print(f"  {f}")
    return 0 if r.hal else 1


def partnerexport(club_dir: str) -> int:
    from .partnerexport import exportera

    p = Path(club_dir)
    filer, varningar = exportera(p, Path("output") / p.name / "partner")
    for v in varningar:
        print(f"OBS: {v}")
    print(f"{len(filer) - 1} hål exporterade:")
    for f in filer:
        print(f"  {f}")
    return 0


def flygfilm(path: str, data: str | None, ut: str | None, sek: float, slut: float) -> int:
    from .render.flygfilm import ATTRIBUTION, flygfilm as rendera

    p = Path(path)
    hole = Hole.from_yaml(p)
    club_dir = _club_dir(p)
    data_dir = Path(data) if data else Path("data") / club_dir.name
    ut_dir = Path(ut) if ut else Path("output") / club_dir.name / "flygfilm"
    r = rendera(hole, data_dir, ut_dir, sekunder=sek, slut_s=slut)
    for k, v in r["filer"].items():
        print(f"  {k}: {v}")
    print("  " + ", ".join(f"{k}={v}" for k, v in r["info"].items()))
    if r["info"]["lyft_for_trad_vid_m"]:
        print(f"OBS: kameran lyftes över träd vid {r['info']['lyft_for_trad_vid_m']} m från tee.")
    print(f"Rå film ur Lantmäteriets data, ingen AI. Märk publikt material: {ATTRIBUTION}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="golfholes")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rapport", help="Avstånd, längdkontroll och kamera för ett hål")
    r.add_argument("fil")
    r.add_argument("--tee", default=None)
    for name, hjalp in (("halbild", "Hålbild i klubbens stil som PNG + SVG"),
                        ("skylt", "Skylt 70 × 100 cm: förhandsvisning + tryck-PDF per platta")):
        sp = sub.add_parser(name, help=hjalp)
        sp.add_argument("fil")
        sp.add_argument("--stil", default=None, help="Akvarell, Sommarakvarell, Gravyr, Mjuk 3D, Arkitektskiss, "
                        "Papperssnitt (standard: klubbens val)")
    sub.add_parser("stilprov", help="De sex stilarna sida vid sida + AI-prompt per stil – för klubbens val"
                   ).add_argument("fil", help="klubbmapp eller hålfil")
    ap = sub.add_parser("aiprompt", help="AI-prompten för klubbens stil (OpenArt, bara ytan byts)")
    ap.add_argument("fil")
    ap.add_argument("--stil", default=None)
    hk = sub.add_parser("halkort", help="Hålkort i klubbens layout (PNG)")
    hk.add_argument("fil")
    hk.add_argument("--layout", default=None, help="1–7 (standard: klubbens val i klubb.yaml)")
    sub.add_parser("layoutprov", help="Samma hål i alla layouter – för klubbens val").add_argument("fil")
    sub.add_parser("webb", help="Digital banguide för en klubb").add_argument("klubbmapp")
    pr = sub.add_parser("prospekt", help="Hålsponsorprospekt (PDF) per hål, med klubben som avsändare")
    pr.add_argument("fil", help="halkort/hal-NN.yaml, eller klubbmappen tillsammans med --alla")
    pr.add_argument("--alla", action="store_true", help="alla hål i klubben som har en hålbild")
    pr.add_argument("--gemensam", action="store_true",
                    help="en presentation för alla hål, med sidan 'Vilket blir ert hål?' (kryss ur klubb.yaml)")
    pr.add_argument("--ut", default=None, help="mapp för PDF:erna (standard: output/<klubb>/prospekt)")
    il = sub.add_parser("inlagg", help="Inlägg för sociala medier (4:5) ur some/inlagg.yaml")
    il.add_argument("klubbmapp")
    il.add_argument("--ut", default=None, help="mapp för inläggen (standard: output/<klubb>/inlagg)")
    u = sub.add_parser("utsnitt", help="Klipp ut banan ur Lantmäteriets ortofoto")
    u.add_argument("klubbmapp")
    u.add_argument("tiffar", nargs="+")
    u.add_argument("--upplosning", type=float, default=None, help="meter per pixel (standard: som källan)")
    sub.add_parser("sok", help="Vilka ortofoton och höjdmodeller Lantmäteriet har för banan (ingen inloggning)"
                   ).add_argument("klubbmapp")
    h = sub.add_parser("hamta", help="Hämta nyaste ortofoto + höjdmodell från Lantmäteriet och gör utsnitt")
    h.add_argument("klubbmapp")
    h.add_argument("--ar", type=int, default=None, help="ortofotots år (standard: nyaste)")
    sub.add_parser("utkast", help="Utkast av ett hål ur ortofotot från fröpunkter (trollstav)").add_argument("frofil")
    sub.add_parser("fotobild", help="Hålbild i fotostil ur ortofotot (för hålkortet)").add_argument("fil")
    sub.add_parser("aiunderlag", help="Fotounderlag utan markeringar för AI-målning (9:16)").add_argument("fil")
    ai = sub.add_parser("aibild", help="Lägg AI-målningen på hålets exakta form + prickar och flagga")
    ai.add_argument("fil")
    ai.add_argument("malning", nargs="+", help="AI-bilder gjorda på aiunderlag; den med bäst formpoäng väljs")
    ai.add_argument("--stil", default=None, help="stilen målningen är gjord i (standard: klubbens val)")
    ff = sub.add_parser("flygfilm", help="Rå flygfilm 5 m över hålet ur Lantmäteriets data (MP4 + nyckelbilder)")
    ff.add_argument("fil")
    ff.add_argument("--data", default=None, help="mapp med orto/, hojd/, laser/ (standard: data/<klubb>)")
    ff.add_argument("--ut", default=None, help="utmapp (standard: output/<klubb>/flygfilm)")
    ff.add_argument("--sek", type=float, default=12.0, help="filmens längd i sekunder (standard 12)")
    ff.add_argument("--slut", type=float, default=4.0, help="sekunder för stigning till vy ovanifrån (standard 4)")
    sr = sub.add_parser("sponsorrapport", help="Visningar per sponsor och kanal för en säsong (PNG + PDF per sponsor)")
    sr.add_argument("klubbmapp")
    sr.add_argument("--sasong", type=int, required=True)
    sr.add_argument("--kalla", default=None, help="mapp med säsongens exporter (standard: data/<klubb>/statistik/<säsong>/)")
    sr.add_argument("--utan-pdf", action="store_true", help="bara PNG")
    sub.add_parser("partnerexport", help="Sponsorer per hål som JSON + zip till digitala partnerkanaler"
                   ).add_argument("klubbmapp")
    a = p.parse_args(argv)
    if a.cmd == "sponsorrapport":
        return sponsorrapport(a.klubbmapp, a.sasong, a.kalla, not a.utan_pdf)
    if a.cmd == "partnerexport":
        return partnerexport(a.klubbmapp)
    if a.cmd == "flygfilm":
        return flygfilm(a.fil, a.data, a.ut, a.sek, a.slut)
    if a.cmd == "aiunderlag":
        return aiunderlag(a.fil)
    if a.cmd == "aibild":
        return aibild(a.fil, a.malning, a.stil)
    if a.cmd == "fotobild":
        return fotobild(a.fil)
    if a.cmd == "utkast":
        return utkast(a.frofil)
    if a.cmd == "sok":
        return sok(a.klubbmapp)
    if a.cmd == "hamta":
        return hamta(a.klubbmapp, a.ar)
    if a.cmd == "rapport":
        return rapport(a.fil, a.tee)
    if a.cmd == "halbild":
        return halbild(a.fil, a.stil)
    if a.cmd == "skylt":
        return skylt(a.fil, a.stil)
    if a.cmd == "aiprompt":
        return aiprompt(a.fil, a.stil)
    if a.cmd == "stilprov":
        return stilprov(a.fil)
    if a.cmd == "halkort":
        return halkort(a.fil, a.layout)
    if a.cmd == "layoutprov":
        return layoutprov(a.fil)
    if a.cmd == "prospekt":
        return prospekt(a.fil, a.alla, a.ut, a.gemensam)
    if a.cmd == "inlagg":
        return inlagg(a.klubbmapp, a.ut)
    if a.cmd == "webb":
        return webb(a.klubbmapp)
    if a.cmd == "utsnitt":
        return utsnitt(a.klubbmapp, a.tiffar, a.upplosning)
    return 2


if __name__ == "__main__":
    sys.exit(main())
