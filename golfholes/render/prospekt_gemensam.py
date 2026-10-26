"""Gemensam hålsponsorpresentation: en PDF för hela klubben, samma för alla hål.

  python -m golfholes prospekt klubbar/<klubb> --gemensam [--ut mapp]

En komplett säljpresentation, samma mall som prospektet per hål (prospekt.py) men utan ett bestämt hål.
Allt börjar med hålsponsorskapet; resten är tillval (Erics beslut 2026-10-25):
  1 Omslag   2 Skylten vid tee   3 Digitalt   4 Rapporten   5 Allt som ingår   6 Vilket blir ert hål?
  7 Pris och nästa steg   8 Mer att synas med (klubbens anläggning)   9 Nya sätt att synas   10 Avslutning
Sidorna 8–9 läses ur `sponsring.tillval` i klubb.yaml (`finns` och `nytt`, varje post namn + text);
klubben sätter priserna på tillvalen. Sidorna 2–4 visar ett exempelhål (`sponsring.exempelhal`). Sidan 6 visar alla hål med nummer, par,
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
SIDOR = 10
KRYSS_SIDA = 5      # 0-baserad: sidan "Vilket blir ert hål?"
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
{_hd(k, 6)}
<div class='abs' style='left:{M}px;top:120px;width:1100px'>
 <div class='ey'>Välj hål</div>
 <h1>Vilket blir ert hål?</h1></div>
<div class='abs' style='left:1280px;right:{M}px;top:186px'>
 <p class='p' style='font-size:20px'>Ett kryss betyder att hålet är bokat eller sålt. Övriga hål är lediga för säsongen {k.sasong}.</p>
 <p class='note' style='margin-top:10px'>{lage}</p></div>
{celler}
<div class='src' style='left:{M}px;right:{M}px;bottom:24px'>Längder från främsta till bakersta tee. {ATTRIBUTION}</div></div>"""


def s_allt(k: Klubb, c: Halkort) -> str:
    """Sidan 5: allt som ingår, med räkneexemplet krona per visning vid tee."""
    pris = k.sponsring.get("pris_per_hal")
    ronder, _ = k.ronder()
    siffra, forklaring = P._uppskattning(k)
    per = ""
    if pris and ronder:
        per = (f"<div style='font:400 26px/1.4 var(--sans);color:#D3E3E0;margin-top:26px'>Med {kr(pris)}&nbsp;kr per år "
               f"blir det ungefär <b style='color:var(--glod);font-weight:500'>{pris / ronder:.2f}&nbsp;kr per visning</b>"
               f", bara vid tee.</div>").replace(f"{pris / ronder:.2f}", f"{pris / ronder:.2f}".replace(".", ","))
    poster = [
        ("Ert namn på hålet", "<i>[Ert företag]-hålet</i>, i hålguiden, på webben och i flödet. Hela säsongen."),
        ("Skylten vid tee", "70 × 100 cm med er logotyp. Varje utslag på hålet slås framför den."),
        ("QR-koden på skylten", "Golfaren skannar och landar på hålets sida, där ni presenterar hålet."),
        ("Hålets sida på webben", "”Presenteras av” och er logotyp, i mobilen hos alla som planerar rundan."),
        ("Klubbens Instagram och Facebook", "Hålet med er logotyp i klubbens egna inlägg."),
        ("Ett färdigt inlägg till er", "Klart att publicera i era kanaler. Ni behöver inte ta fram något själva."),
        ("Rapporten efter säsongen", "Visningarna kanal för kanal. Svart på vitt, att visa för styrelsen."),
        ("Flygfilmen över hålet", "Er logotyp när kameran landar över green. <span style='color:#5B6E73'>Under utveckling.</span>"),
    ]
    rutor = "".join(
        f"<div style='padding:22px 0 20px;border-top:1px solid rgba(16,32,46,.16)'>"
        f"<div style='font:600 21px/1.25 var(--sans);color:var(--djup)'>{a}</div>"
        f"<div style='font:400 19px/1.45 var(--sans);color:#33454B;margin-top:6px'>{b}</div></div>" for a, b in poster)
    return f"""<div class='pg'>
{_hd(k, 5, M, 700)}
<div class='abs' style='left:{M}px;top:130px;width:1060px'>
 <div class='ey'>Det här ingår</div>
 <h1>Allt det här, för ett enda hål.</h1>
 <div style='display:grid;grid-template-columns:1fr 1fr;column-gap:56px;margin-top:40px'>{rutor}</div>
 <p class='p' style='margin-top:26px;font-size:21px'>Ni godkänner allt innan det syns. Kansliet tar hand om resten.</p></div>
<div class='abs dark' style='left:{W - 600}px;top:0;width:600px;height:1080px;background:var(--djup)'>
 <div class='abs' style='left:64px;right:64px;top:150px'>
  <div class='ey'>Vid tee, per säsong</div>
  <div style='font:400 96px/1 var(--serif);margin-top:30px'>{siffra}</div>
  <div style='font:400 24px/1.4 var(--sans);color:var(--is);margin-top:14px'>visningar av er skylt<span class='tag' style='color:var(--glod)'>Uppskattning</span></div>
  {per}
  <div style='font:400 14px/1.5 var(--sans);color:var(--is);opacity:.8;margin-top:34px'>Räkneexempel, inte ett löfte. {forklaring}</div></div>
 {hal_i_ruta(c.image, 64, 680, 472, 360, 'center bottom', max_px=1200)}</div></div>"""


def s_pris(k: Klubb, c: Halkort, qr_svg: str, url: str) -> str:
    """Sidan 7: pris, tre steg och kontakt."""
    sp = k.sponsring
    pris = sp.get("pris_per_hal")
    prisruta = (f"<div style='font:400 88px/1 var(--serif)'>{kr(pris)}&nbsp;kr</div>"
                f"<div style='font:400 24px/1.4 var(--sans);color:var(--is);margin-top:14px'>{e(sp.get('pris_villkor', 'per år'))} och hål</div>"
                if pris else "<div style='font:400 40px/1.2 var(--serif)'>Pris enligt överenskommelse</div>")
    kontakt = sp.get("kontakt") or k.web
    steg = [("Ni väljer hål.", "Ett kryss på sidan innan och ett samtal till kansliet. Mer än så behövs inte."),
            ("Vi tar fram allt.", "Skylt, hålets sida och inlägg med er logotyp. Ni ser och godkänner allt innan det syns."),
            ("Hålet är ert.", f"Från första start {k.sasong} bär hålet ert namn, ända till säsongens sista putt.")]
    rader = "".join(
        f"<div style='display:flex;gap:30px;padding:28px 0;border-top:1px solid rgba(16,32,46,.16)'>"
        f"<div style='font:400 54px/1 var(--serif);color:var(--glas);width:48px'>{i}</div>"
        f"<div><div style='font:400 38px/1.15 var(--serif)'>{a}</div>"
        f"<div style='font:400 21px/1.5 var(--sans);color:#33454B;margin-top:10px;max-width:760px'>{b}</div></div></div>"
        for i, (a, b) in enumerate(steg, 1))
    return f"""<div class='pg'>
{_hd(k, 7, M, 760)}
<div class='abs' style='left:{M}px;top:140px;width:960px'>
 <div class='ey'>Så blir hålet ert</div>
 <h1>Ni väljer hål. Vi gör resten.</h1>
 <div style='margin-top:40px'>{rader}</div>
 <div style='padding-top:26px;border-top:1px solid rgba(16,32,46,.16);font:500 26px/1.4 var(--sans)'>{e(kontakt)}</div></div>
<div class='abs dark' style='left:{W - 680}px;top:0;width:680px;height:1080px;background:var(--djup)'>
 <div class='abs' style='left:70px;top:120px'><div class='ey'>Pris per hål</div><div style='margin-top:28px'>{prisruta}</div></div>
 <div class='abs' style='left:70px;right:70px;top:400px;border-top:1px solid rgba(156,201,195,.3)'></div>
 {hal_i_ruta(c.image, 60, 440, 300, 560, 'left center', max_px=1400)}
 <div class='abs' style='left:400px;top:580px;width:210px'>
  <div style='width:210px;height:210px;background:var(--kristall);padding:16px'>{qr_svg}</div>
  <div style='font:500 17px/1.4 var(--sans);color:var(--is);margin-top:16px'>Se alla hål</div>
  <div style='font:400 13px/1.4 var(--sans);color:var(--is);opacity:.75;word-break:break-all'>{e(url.replace('https://', ''))}</div></div>
 <div class='src' style='left:70px;right:70px;bottom:44px;font-size:13px'>Hål {c.hole}. {ATTRIBUTION}</div></div></div>"""


def _tillval_kort(poster: list[dict], dark: bool) -> str:
    ram = "rgba(156,201,195,.28)" if dark else "rgba(16,32,46,.16)"
    text = "#C9DAD6" if dark else "#33454B"
    nr = "var(--glod)" if dark else "var(--glas)"
    return "".join(
        f"<div style='border-top:1px solid {ram};padding-top:26px'>"
        f"<div style='font:600 14px/1 var(--sans);letter-spacing:.22em;color:{nr}'>{i:02d}</div>"
        f"<div style='font:400 44px/1.12 var(--serif);margin-top:16px'>{e(p['namn'])}</div>"
        f"<div style='font:400 23px/1.5 var(--sans);color:{text};margin-top:14px'>{e(p['text'])}</div></div>"
        for i, p in enumerate(poster, 1))


def s_tillval(k: Klubb, nr: int, poster: list[dict], ey: str, rubrik: str, ingress: str, dark: bool) -> str:
    """Sidorna 8–9: tillval efter hålet, upp till sex kort i tre kolumner. Tom lista = ingen sida."""
    if not poster:
        return ""
    kontakt = k.sponsring.get("kontakt") or k.web
    return f"""<div class='pg{' dark' if dark else ''}'>
{_hd(k, nr)}
<div class='abs' style='left:{M}px;top:130px;width:1100px'>
 <div class='ey'>{ey}</div>
 <h1>{rubrik}</h1>
 <p class='lead' style='margin-top:22px;max-width:1040px;font-size:25px'>{ingress}</p></div>
<div class='abs' style='left:{M}px;right:{M}px;top:420px;display:grid;grid-template-columns:repeat(3,1fr);column-gap:64px;row-gap:56px'>
 {_tillval_kort(poster[:6], dark)}</div>
<div class='src{' ljus' if dark else ''}' style='left:{M}px;right:{M}px;bottom:40px'>Tillvalen prissätts av klubben. Fråga kansliet: {e(kontakt)}</div></div>"""


def s_slut(k: Klubb, omslag: list[Halkort], qr_svg: str, url: str) -> str:
    """Sidan 10: avslutning."""
    kontakt = k.sponsring.get("kontakt") or k.web
    bilder = "".join(hal_i_ruta(c.image, 1060 + i * 250, 120, 236, 840, "center center", max_px=1400)
                     for i, c in enumerate(omslag[:3]))
    return f"""<div class='pg dark'>
{bilder}
<div class='abs' style='left:{M}px;top:120px;display:flex;align-items:center;gap:22px'>
 <img src='{k.logga("mork")}' style='width:84px;height:84px'>
 <div style='font:600 15px/1.5 var(--sans);letter-spacing:.24em;text-transform:uppercase;color:var(--is)'>{e(k.namn)}<br>
 <span style='color:var(--glod)'>{e(k.bana)}</span></div></div>
<div class='abs' style='left:{M}px;top:320px;width:840px'>
 <div class='ey'>Säsongen {k.sasong}</div>
 <h1 class='xl'>Allt börjar med ett hål.</h1>
 <p class='lead' style='max-width:760px'>Välj hålet först. Det är grunden, och det är ert hela säsongen.
 Resten bygger ni på när ni vill, i den takt som passar er.</p>
 <div style='display:flex;align-items:center;gap:30px;margin-top:56px'>
  <div style='width:150px;height:150px;background:var(--kristall);padding:12px;flex:none'>{qr_svg}</div>
  <div><div style='font:500 26px/1.4 var(--sans)'>{e(kontakt)}</div>
  <div style='font:400 17px/1.4 var(--sans);color:var(--is);margin-top:8px'>{e(url.replace('https://', ''))}</div></div></div></div>
<div class='src' style='left:{M}px;right:{M}px;bottom:40px'>{ATTRIBUTION} · Material: TACADA</div></div>"""


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
    tv = k.sponsring.get("tillval") or {}
    s = [s1_omslag(k, omslag, len(hal)), P.s3_skylt(k, c, d, qr_halet), P.s4_digitalt(k, c, d), P.s5_rapport(k, c, d),
         s_allt(k, c), s5_valj(k, hal, idag or dt.date.today()), s_pris(k, c, qr_svg, url),
         s_tillval(k, 8, tv.get("finns") or [], "När hålet är ert", "Mer att synas med.",
                   f"Hålet är grunden. Den som vill synas mer kan bygga vidare på {e(k.bana)}, "
                   "på rangen, vid kiosken och långt utanför fairway.", False),
         s_tillval(k, 9, tv.get("nytt") or [], "Nya sätt att synas", "Fler platser att sätta sin prägel.",
                   "Sex idéer för företag som vill ett steg längre. Klubben berättar gärna mer.", True),
         s_slut(k, omslag, qr_svg, url)]
    s = [x for x in s if x]
    return s, hal, akta and akta2


def kryssrutor(pdf: Path, hal: list[dict], sida: int = KRYSS_SIDA) -> int:
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
