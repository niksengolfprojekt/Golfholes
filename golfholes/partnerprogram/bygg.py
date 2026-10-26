"""Bygger hela partnerprogrammet för en klubb: python -m golfholes partnerprogram klubbar/<klubb>.

Allt läses ur klubb.yaml + partnerprogram.yaml (+ standardbiblioteket) och partneröversikten (xlsx).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from . import Program, logg

DELAR = ("deck", "prospekt", "manual", "rapport", "kalender", "prislista", "oversikt", "beslut", "framtid", "xlsx")
MAN = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober", "november",
       "december"]


def idag_text(d: dt.date | None = None) -> str:
    d = d or dt.date.today()
    return f"{d.day} {MAN[d.month - 1]} {d.year}"


def bygg(klubbmapp: str | Path, ut: str | Path | None = None, logg_fil: str | Path | None = None,
         bara: set[str] | None = None, bilder: bool = True) -> dict:
    from ..render import partner_deck as D
    from ..render import partner_dok as K
    from ..render.klubbmaterial import Webblasare, data_uri

    prog = Program.from_dir(klubbmapp)
    namn = prog.klubb.mapp.name
    ut = Path(ut) if ut else Path("output") / namn / "partnerprogram"
    ut.mkdir(parents=True, exist_ok=True)
    logg_fil = Path(logg_fil) if logg_fil else Path("data") / namn / "partnerprogram" / f"partneroversikt-{prog.sasong}.xlsx"
    gor = (lambda d: d in bara) if bara else (lambda d: True)
    filer, varningar = [], []
    idag = idag_text()

    for niva, text in prog.kontroller():
        if niva == "stopp":
            raise SystemExit(f"Stopp: {text}")
        if niva == "beslut":
            varningar.append(text)

    # Partneröversikten: skapas om den saknas, annars läses status och säsongens data ur den.
    if not logg_fil.exists():
        logg.skapa(prog, logg_fil)
        filer.append(logg_fil)
    lagt = logg.las(logg_fil)
    for h in prog.hal:
        h.status = lagt["status"].get(f"hal-{h.nr:02d}", h.status)
    status_ovr = {k: v for k, v in lagt["status"].items() if not k.startswith("hal-")}
    prog.cfg.setdefault("status", {}).update(status_ovr)

    sf = f"{prog.klubb.namn} · Partnerprogram {prog.sasong}"
    nordvik, neutral = D.Sponsor(prog, True), D.Sponsor(prog, False)
    exnamn = (prog.cfg.get("exempel") or {}).get("namn", "Exempel")
    qr_falsk = False

    def deckpdf(sidor, fil):
        filer.append(wb.pdf(D._sida(prog, "".join(sidor)), 1920, 1080, ut / fil))

    with Webblasare() as wb:
        if gor("deck"):
            for sp, fil in ((nordvik, f"A-huvudpresentation-{exnamn}.pdf"), (neutral, "A-huvudpresentation.pdf")):
                sidor, akta = D.deck(prog, sp, idag)
                qr_falsk |= not akta
                deckpdf(sidor, fil)
                if bilder and sp is nordvik:
                    for i, s in enumerate(sidor, 1):
                        p = wb.png(D._sida(prog, s), 1920, 1080, ut / "bilder" / f"A-{i:02d}.png", skala=0.5)
                        filer.append(p)
        if gor("prospekt"):
            for h in prog.hal:
                for sp, fil in ((neutral, f"hal-{h.nr:02d}.pdf"), (nordvik, f"hal-{h.nr:02d}-{exnamn}.pdf")):
                    sidor, akta = D.prospekt_hal(prog, h, sp)
                    qr_falsk |= not akta
                    deckpdf(sidor, Path("B-prospekt") / fil)
            for pid in D.PRODUKTPROSPEKT:
                if pid not in prog.produkter:
                    continue
                for sp, fil in ((neutral, f"{pid}.pdf"), (nordvik, f"{pid}-{exnamn}.pdf")):
                    sidor, akta = D.prospekt_produkt(prog, prog.produkter[pid], sp)
                    qr_falsk |= not akta
                    deckpdf(sidor, Path("B-prospekt") / "produkter" / fil)
        if gor("framtid"):
            deckpdf([D.framtida_kanal(prog, neutral, False)], "framtida-kanal.pdf")
            deckpdf([D.framtida_kanal(prog, nordvik, True)], "INTERNT-framtida-kanal.pdf")
        if gor("manual"):
            filer.append(K.pdf(wb, K.html(prog, K.manual(prog)), ut / "C-forsaljningsmanual.pdf",
                               sidfot=sf + " · Försäljningsmanual"))
        if gor("rapport"):
            ex = {"foretag": exnamn, "produkt": "halsponsor", "hal": (prog.cfg.get("exempel") or {}).get("hal")}
            filer.append(K.pdf(wb, K.html(prog, K.rapport(prog, ex, {"mall": True})), ut / "D-arsrapport-mall.pdf",
                               sidfot=sf + " · Partnerrapport"))
            fotomapp = logg_fil.parent / "foton"
            for plats, p in lagt["partners"].items():
                data = dict(lagt["rapport"].get(plats) or {})
                for f in data.get("foton") or []:
                    if (fotomapp / f["fil"]).exists():
                        f["bild"] = data_uri(fotomapp / f["fil"], max_px=1200)
                hal = int(plats[4:]) if plats.startswith("hal-") else None
                partner = {"foretag": p["foretag"], "produkt": "premiumhal" if hal and next(
                    h for h in prog.hal if h.nr == hal).premium else ("halsponsor" if hal else plats), "hal": hal}
                filer.append(K.pdf(wb, K.html(prog, K.rapport(prog, partner, data)),
                                   ut / "D-rapporter" / f"{plats}-{_fil(p['foretag'])}.pdf", sidfot=sf + " · Partnerrapport"))
        if gor("kalender"):
            filer.append(K.pdf(wb, K.html(prog, K.kalender(prog), sida="A3 landscape", marg="14mm"),
                               ut / "E-arskalender.pdf", 420, 297))
        if gor("prislista"):
            filer.append(K.pdf(wb, K.html(prog, K.prislista(prog)), ut / "F-prislista.pdf"))
        if gor("oversikt"):
            filer.append(K.pdf(wb, K.html(prog, K.oversikt(prog, status_ovr, lagt["partners"], idag), marg="16mm"),
                               ut / "F-partneroversikt.pdf"))
        if gor("beslut"):
            filer.append(K.pdf(wb, K.html(prog, K.beslutsunderlag(prog)), ut / "beslutsunderlag.pdf",
                               sidfot=sf + " · Beslutsunderlag"))
    if qr_falsk:
        varningar.append("QR-koden är en platshållare (segno saknas): pip install segno. Tryck aldrig så.")
    return {"filer": filer, "varningar": varningar, "logg": logg_fil, "ut": ut}


def _fil(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")
