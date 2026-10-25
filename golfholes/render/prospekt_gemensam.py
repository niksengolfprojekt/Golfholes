"""Gemensam hålsponsorpresentation: en PDF för hela klubben, samma för alla hål.

  python -m golfholes prospekt klubbar/<klubb> --gemensam [--ut mapp]

Sex sidor, samma mall som prospektet per hål (prospekt.py) men utan ett bestämt hål:
  1 Omslag   2 Skylten vid tee   3 Digitalt   4 Rapporten   5 Vilket blir ert hål?   6 Det här ingår + pris
Sidorna 2–4 visar ett exempelhål (`sponsring.exempelhal`). Sidan 5 visar alla hål med nummer, par,
längd och en kryssruta. Kryssen kommer ur `sponsring.status` i klubb.yaml (ledig, bokad, såld): klubben
ändrar där och kör kommandot igen. Rutorna för lediga hål är också riktiga kryssrutor i PDF:en
(AcroForm), så att klubben kan kryssa direkt i en PDF-läsare.
"""
from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

import yaml

from . import prospekt as P
from .halkort import Halkort
from .klubbmaterial import ATTRIBUTION, Klubb, Webblasare, e, hal_i_ruta, halkort_markerat, kontaktark, kr, qr

W, H, M = P.W, P.H, P.M
SIDOR = 6
MANADER = ("januari februari mars april maj juni juli augusti september oktober november december").split()

# Rutnätet på sidan "Vilket blir ert hål?" (px på sidan). Kryssrutornas lägen räknas ut här och
# används både i HTML och när PDF-fälten läggs in, så att de hamnar exakt på varandra.
KOL, GX, X0, Y0, RADH = 9, 22, M, 300, 364
KORT_H, RUTA = 238, 28


def _cellbredd() -> float:
    return (W - 2 * X0 - (KOL - 1) * GX) / KOL


def ruta_lage(i: int) -> tuple[float, float, float]:
    """(x, y, sida) för kryssrutan i cell i (0-baserad), i px från sidans övre vänstra hörn."""
    cw = _cellbredd()
    x = X0 + (i % KOL) * (cw + GX)
    y = Y0 + (i // KOL) * RADH + KORT_H + 78
    return x, y, RUTA


# ------------------------------------------------------------------ hålen
def hal_lista(k: Klubb, markerat=halkort_markerat) -> list[dict]:
    """Alla klubbens hål i ordning: nummer, par, längder, status och hålbild (om den finns)."""
    d = yaml.safe_load((k.mapp / "klubb.yaml").read_text(encoding="utf-8")) or {}
    kort = k.halkort()
    ut = []
    for h in d.get("holes") or []:
        nr = int(h["hole"])
        c = markerat(kort[nr]) if nr in kort else None
        langder = sorted(int(m) for m in (h.get("tees") or {}).values())
        ut.append({"hal": nr, "par": h.get("par"), "langder": langder, "status": k.status(nr),
                   "bild": c.image if c else None})
    return ut


def _langd(m: list[int]) -> str:
    if not m:
        return ""
    return f"{m[0]}&nbsp;m" if m[0] == m[-1] else f"{m[0]}–{m[-1]}&nbsp;m"


def _datum(d: dt.date) -> str:
    return f"{d.day} {MANADER[d.month - 1]} {d.year}"


# ------------------------------------------------------------------ sidorna
def _hd(k: Klubb, nr: int, left: int = M, right: int = M) -> str:
    return (f"<div class='hd' style='left:{left}px;right:{right}px'><span>{e(k.namn)} · Hålsponsor {k.sasong}</span>"
            f"<span>{nr:02d}</span></div>")


def s1_omslag(k: Klubb, omslag: list[Halkort], antal_hal: int) -> str:
    n = max(len(omslag), 1)
    bw = 820 / n
    bilder = "".join(hal_i_ruta(c.image, 60 + i * bw, 70, bw - 14, 900, "center center", max_px=1600)
                     for i, c in enumerate(omslag))
    nummer = "".join(f"<div class='abs' style='left:{60 + i * bw:.0f}px;width:{bw - 14:.0f}px;top:990px;text-align:center;"
                     f"font:600 14px/1 var(--sans);letter-spacing:.22em;color:var(--is)'>HÅL {c.hole}</div>"
                     for i, c in enumerate(omslag))
    glod = "radial-gradient(ellipse 60% 55% at 50% 50%,rgba(63,127,134,.35),rgba(16,32,46,0) 70%)"
    antal = {18: "Arton", 9: "Nio", 27: "Tjugosju", 36: "Trettiosex"}.get(antal_hal, f"{antal_hal}")
    return f"""<div class='pg dark'>
<div class='abs' style='left:0;top:0;width:940px;height:1080px;background:{glod}'></div>
{bilder}{nummer}
<div class='abs' style='left:1000px;top:96px;display:flex;align-items:center;gap:22px'>
 <img src='{k.logga("mork")}' style='width:92px;height:92px'>
 <div style='font:600 16px/1.5 var(--sans);letter-spacing:.24em;text-transform:uppercase;color:var(--is)'>{e(k.namn)}<br>
 <span style='color:var(--glod)'>{e(k.bana)}</span></div></div>
<div class='abs' style='left:1000px;right:{M}px;top:330px'>
 <div class='ey'>Hålsponsor {k.sasong}</div>
 <h1 class='xl'>Ert namn på ett hål.</h1>
 <p class='lead' style='max-width:760px'>{antal} hål, och vart och ett har sin egen historia. Välj det som
 passar er. Hela säsongen stannar golfarna vid er skylt, och hålet bär ert namn överallt där klubben visar det.</p></div>
<div class='src' style='left:1000px;right:{M}px;bottom:56px'>{ATTRIBUTION}</div></div>"""


def _cell(i: int, h: dict) -> str:
    cw = _cellbredd()
    x = X0 + (i % KOL) * (cw + GX)
    y = Y0 + (i // KOL) * RADH
    tagen = h["status"] != "ledig"
    bild = ""
    if h["bild"]:
        bild = hal_i_ruta(h["bild"], x + 8, y + 8, cw - 16, KORT_H - 16, max_px=700,
                          extra="opacity:.38" if tagen else "")
    band = ""
    if tagen:
        band = (f"<div class='abs' style='left:{x}px;width:{cw:.1f}px;top:{y + KORT_H / 2 - 22}px;height:44px;"
                f"background:var(--glod);color:var(--djup);display:flex;align-items:center;justify-content:center;"
                f"font:600 17px/1 var(--sans);letter-spacing:.24em;text-transform:uppercase'>"
                f"{'Sålt' if h['status'] == 'såld' else 'Bokat'}</div>")
    rx, ry, rs = ruta_lage(i)
    kryss = ""
    if tagen:
        kryss = (f"<svg viewBox='0 0 10 10' style='position:absolute;inset:3px'><path d='M1.6 5.4 L4 7.8 L8.6 2.2' "
                 f"fill='none' stroke='var(--djup)' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'/></svg>")
    etikett = ("<b style='font-weight:600'>Sålt</b>" if h["status"] == "såld" else
               "<b style='font-weight:600'>Bokat</b>" if h["status"] == "bokad" else "Bokat / sålt")
    return f"""<div class='abs' style='left:{x}px;top:{y}px;width:{cw:.1f}px;height:{KORT_H}px;background:var(--djup);border-radius:4px'></div>
{bild}{band}
<div class='abs' style='left:{x}px;top:{y + KORT_H + 12}px;width:{cw:.1f}px;display:flex;align-items:baseline;justify-content:space-between'>
 <span style='font:400 34px/1 var(--serif)'>{h['hal']}</span>
 <span style='font:500 15px/1 var(--sans);color:var(--glas)'>Par {h['par']}</span></div>
<div class='abs' style='left:{x}px;top:{y + KORT_H + 52}px;font:400 15px/1 var(--sans);color:#4F6268;font-variant-numeric:tabular-nums'>{_langd(h['langder'])}</div>
<div class='abs' style='left:{rx}px;top:{ry}px;width:{rs}px;height:{rs}px;border:2px solid var(--djup);border-radius:3px;background:#fff'>{kryss}</div>
<div class='abs' style='left:{rx + rs + 12}px;top:{ry + rs / 2 - 9}px;font:400 16px/18px var(--sans);color:var(--djup)'>{etikett}</div>"""


def s5_valj(k: Klubb, hal: list[dict], idag: dt.date) -> str:
    lediga = sum(h["status"] == "ledig" for h in hal)
    celler = "".join(_cell(i, h) for i, h in enumerate(hal))
    lage = (f"Läget {_datum(idag)}: {lediga} av {len(hal)} hål lediga." if lediga < len(hal)
            else f"Läget {_datum(idag)}: alla hål är lediga.")
    return f"""<div class='pg'>
{_hd(k, 5)}
<div class='abs' style='left:{M}px;top:120px;width:1100px'>
 <div class='ey'>Välj hål</div>
 <h1>Vilket blir ert hål?</h1></div>
<div class='abs' style='left:1280px;right:{M}px;top:186px'>
 <p class='p' style='font-size:20px'>Ett kryss betyder att hålet är bokat eller sålt. Övriga hål är lediga för säsongen {k.sasong}.</p>
 <p class='note' style='margin-top:10px'>{lage}</p></div>
{celler}
<div class='src' style='left:{M}px;right:{M}px;bottom:24px'>Längder från främsta till bakersta tee. {ATTRIBUTION}</div></div>"""


def s6_erbjudande(k: Klubb, c: Halkort, qr_svg: str, url: str) -> str:
    sp = k.sponsring
    pris = sp.get("pris_per_hal")
    prisruta = (f"<div style='font:400 72px/1 var(--serif)'>{kr(pris)}&nbsp;kr</div>"
                f"<div style='font:400 22px/1.4 var(--sans);color:var(--is);margin-top:14px'>{e(sp.get('pris_villkor', 'per år'))}</div>"
                if pris else "<div style='font:400 34px/1.2 var(--serif)'>Pris enligt överenskommelse</div>")
    kontakt = sp.get("kontakt") or k.web
    return f"""<div class='pg'>
{_hd(k, 6, M, 760)}
<div class='abs' style='left:{M}px;top:150px;width:1000px'>
 <div class='ey'>Det här ingår</div>
 <h1>Ett hål. En hel säsong. Ert namn.</h1>
 <ul class='d' style='margin-top:46px'>
  <li>Hålet bär ert namn: <i>[Ert företag]-hålet</i></li>
  <li>Er logotyp på skylten vid tee, med QR-kod till hålets sida</li>
  <li>”Presenteras av” på hålets sida på klubbens webb</li>
  <li>Hålet med er logotyp i klubbens inlägg på Instagram och Facebook</li>
  <li>Ett färdigt inlägg att dela i era egna kanaler</li>
  <li>En rapport över visningarna efter säsongen</li>
  <li>Er logotyp i flygfilmen över hålet <span style='color:#5B6E73'>(under utveckling)</span></li></ul>
 <div style='margin-top:34px;padding-top:28px;border-top:1px solid rgba(16,32,46,.18)'>
  <div class='ey' style='font-size:14px'>Ni väljer hål. Vi gör resten.</div>
  <div style='font:500 26px/1.4 var(--sans);margin-top:14px'>{e(kontakt)}</div></div></div>
<div class='abs dark' style='left:{W - 680}px;top:0;width:680px;height:1080px;background:var(--djup)'>
 <div class='abs' style='left:70px;top:110px'><div class='ey'>Pris per hål</div><div style='margin-top:26px'>{prisruta}</div></div>
 <div class='abs' style='left:70px;right:70px;top:370px;border-top:1px solid rgba(156,201,195,.3)'></div>
 {hal_i_ruta(c.image, 60, 420, 300, 560, 'left center', max_px=1400)}
 <div class='abs' style='left:400px;top:560px;width:210px'>
  <div style='width:210px;height:210px;background:var(--kristall);padding:16px'>{qr_svg}</div>
  <div style='font:500 17px/1.4 var(--sans);color:var(--is);margin-top:16px'>Se alla hål</div>
  <div style='font:400 13px/1.4 var(--sans);color:var(--is);opacity:.75;word-break:break-all'>{e(url.replace('https://', ''))}</div></div>
 <div class='src' style='left:70px;right:70px;bottom:44px;font-size:13px'>Hål {c.hole}. {ATTRIBUTION}</div></div>
<div class='abs' style='left:{M}px;bottom:52px;display:flex;align-items:center;gap:16px'>
 <img src='{k.logga("ljus")}' style='width:58px;height:58px'>
 <div style='font:400 15px/1.5 var(--sans);color:#5B6E73'>{e(k.namn)} · {e(k.web.replace('https://', ''))}<br>
 <span style='font-size:13px;opacity:.8'>Material: TACADA</span></div></div></div>"""


# ------------------------------------------------------------------ bygg
def sponsorsida(k: Klubb) -> str:
    return k.sponsring.get("sponsorsida") or f"{k.web.rstrip('/')}/halsponsorer/"


def sidor(k: Klubb, idag: dt.date | None = None, markerat=halkort_markerat) -> tuple[list[str], list[dict], bool]:
    """HTML per sida, hållistan (för kryssrutorna) och om QR-koden är äkta."""
    kort = k.halkort()
    if not kort:
        raise SystemExit("Inga hål med hålbild ännu: den gemensamma presentationen behöver minst ett.")
    nr = int(k.sponsring.get("exempelhal") or 0)
    ex_fil = kort.get(nr) or next(iter(kort.values()))
    c = markerat(ex_fil)
    raw = yaml.safe_load(ex_fil.read_text(encoding="utf-8")) or {}
    d = {"gemensam": True, "sidnr": {3: 2, 4: 3, 5: 4}, "kortrad": raw.get("kortrad")}
    omslag = [markerat(kort[h]) for h in (k.sponsring.get("omslagshal") or []) if h in kort] or \
             [markerat(f) for f in list(kort.values())[:3]]
    hal = hal_lista(k, markerat)
    url = sponsorsida(k)
    qr_svg, akta = qr(url, k.farger["djup"])
    qr_halet, akta2 = qr(k.qr_lank(c.hole), k.farger["djup"])
    s = [s1_omslag(k, omslag, len(hal)), P.s3_skylt(k, c, d, qr_halet), P.s4_digitalt(k, c, d), P.s5_rapport(k, c, d),
         s5_valj(k, hal, idag or dt.date.today()), s6_erbjudande(k, c, qr_svg, url)]
    return s, hal, akta and akta2


def kryssrutor(pdf: Path, hal: list[dict], sida: int = 4) -> int:
    """Lägg in riktiga kryssrutor (AcroForm) över de lediga hålens rutor på sidan `sida` (0-baserad).
    Returnerar antalet fält. Kräver pypdf; utan pypdf blir rutorna bara tryckta (0)."""
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import (ArrayObject, BooleanObject, DecodedStreamObject, DictionaryObject, FloatObject,
                                   NameObject, NumberObject, TextStringObject)
    except ImportError:
        return 0
    logging.getLogger("pypdf").setLevel(logging.ERROR)   # Chromiums PDF ger en ofarlig varning
    r = PdfReader(str(pdf))
    w = PdfWriter(clone_from=r)
    pg = w.pages[sida]
    pw, ph = float(pg.mediabox.width), float(pg.mediabox.height)
    s = pw / W                                        # pt per px

    def strom(innehall: str, b: float):
        st = DecodedStreamObject()
        st.set_data(innehall.encode())
        st.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Form"),
                   NameObject("/BBox"): ArrayObject([FloatObject(0), FloatObject(0), FloatObject(b), FloatObject(b)])})
        return w._add_object(st)

    falt = ArrayObject()
    annots = pg.get("/Annots")
    annots = annots.get_object() if annots is not None else ArrayObject()
    for i, h in enumerate(hal):
        if h["status"] != "ledig":
            continue                                  # redan kryssat i klubb.yaml och tryckt på sidan
        x, y, r_px = ruta_lage(i)
        x0, b = x * s + 2 * s, r_px * s - 4 * s
        y0 = ph - (y + r_px) * s + 2 * s
        bock = (f"q 0.063 0.125 0.18 RG {1.6 * s * 1.2:.2f} w 1 J 1 j "
                f"{b * .16:.2f} {b * .46:.2f} m {b * .40:.2f} {b * .22:.2f} l {b * .86:.2f} {b * .78:.2f} l S Q")
        pa = strom(bock, b)
        av = strom("", b)
        f = DictionaryObject({
            NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"): NameObject("/Widget"),
            NameObject("/FT"): NameObject("/Btn"), NameObject("/T"): TextStringObject(f"hal-{h['hal']:02d}"),
            NameObject("/TU"): TextStringObject(f"Hål {h['hal']} bokat eller sålt"),
            NameObject("/Rect"): ArrayObject([FloatObject(x0), FloatObject(y0), FloatObject(x0 + b), FloatObject(y0 + b)]),
            NameObject("/F"): NumberObject(4), NameObject("/V"): NameObject("/Off"), NameObject("/AS"): NameObject("/Off"),
            NameObject("/MK"): DictionaryObject({NameObject("/CA"): TextStringObject("4")}),
            NameObject("/AP"): DictionaryObject({NameObject("/N"): DictionaryObject(
                {NameObject("/Yes"): pa, NameObject("/Off"): av})}),
            NameObject("/P"): pg.indirect_reference,
        })
        ref = w._add_object(f)
        annots.append(ref)
        falt.append(ref)
    pg[NameObject("/Annots")] = annots
    w._root_object[NameObject("/AcroForm")] = DictionaryObject({
        NameObject("/Fields"): falt, NameObject("/NeedAppearances"): BooleanObject(False)})
    with open(pdf, "wb") as fh:
        w.write(fh)
    return len(falt)


def bygg(klubbmapp: Path, ut: Path, idag: dt.date | None = None) -> dict:
    """PDF + översikt.jpg för klubbens gemensamma presentation."""
    import tempfile

    from PIL import Image

    k = Klubb.from_dir(klubbmapp)
    ut = Path(ut)
    s, hal, akta = sidor(k, idag)
    pdf = ut / f"{k.filnamn}_halsponsorpresentation.pdf"
    bilder = []
    with Webblasare() as wb, tempfile.TemporaryDirectory() as td:
        wb.pdf(P._sida(k, "".join(s)), W, H, pdf)
        for i, sida in enumerate(s, 1):
            png = wb.png(P._sida(k, sida), W, H, Path(td) / f"s{i}.png")
            jpg = Path(td) / f"s{i}.jpg"
            Image.open(png).convert("RGB").save(jpg, quality=88)
            bilder.append(jpg)
        oversikt = kontaktark(bilder, ut / f"{k.filnamn}_halsponsorpresentation_oversikt.jpg", 2, 2400,
                              etiketter=[f"Sida {i}" for i in range(1, len(bilder) + 1)])
    falt = kryssrutor(pdf, hal)
    return {"pdf": pdf, "oversikt": oversikt, "qr_akta": akta, "kryssrutor": falt,
            "lediga": sum(h["status"] == "ledig" for h in hal), "hal": len(hal)}
