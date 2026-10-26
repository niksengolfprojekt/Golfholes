"""Partnerprogrammets presentationer (1920 × 1080): huvudpresentationen (leverans A) och prospekten (B).

  python -m golfholes partnerprogram klubbar/<klubb> --bara deck,prospekt

Allt läses ur golfholes.partnerprogram.Program: klubbens profil och hål ur klubb.yaml, produkterna ur
standardbiblioteket med klubbens ändringar ur partnerprogram.yaml. Bilderna är klubbens egna: hålbilderna
(hålkorten), ögonhöjdsbilderna och hemsidans hålsida i `partnerprogram.yaml` → `bilder`.

Två versioner av allt som visar ett företag: med exempelföretaget (Nordvik, påhittat) och neutral
("[Ert företag]", tomt logotypfält). Ett riktigt företags namn och logotyp används bara med tillstånd.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..partnerprogram import HALSTATUS, Hal, Program, kr
from . import prospekt as P
from .klubbmaterial import ATTRIBUTION, css, data_uri, e, hal_i_ruta, qr

W, H, M = 1920, 1080, 120

EXTRA_CSS = """
.foto{position:absolute;background-size:cover;background-position:center}
.chip{display:inline-block;font:600 13px/1 var(--sans);letter-spacing:.16em;text-transform:uppercase;padding:9px 13px;
  border-radius:3px}
.chip.ledig{background:var(--glas);color:#fff}.chip.bokad{background:var(--glod);color:var(--djup)}
.chip.såld{background:#5B6E73;color:#fff}
.kort3{display:grid;grid-template-columns:repeat(3,1fr);column-gap:56px;row-gap:46px}
.kort2{display:grid;grid-template-columns:repeat(2,1fr);column-gap:56px;row-gap:30px}
.punkt{border-top:1px solid rgba(16,32,46,.16);padding-top:20px}
.dark .punkt{border-top-color:rgba(156,201,195,.28)}
.punkt .n{font:600 13px/1 var(--sans);letter-spacing:.22em;color:var(--glas)}
.dark .punkt .n{color:var(--glod)}
.punkt h3{font:400 34px/1.15 var(--serif);margin-top:12px}
.punkt p{font:400 22px/1.5 var(--sans);color:#33454B;margin-top:10px;text-wrap:pretty}
.dark .punkt p{color:#C9DAD6}
.senare{color:#5B6E73;font-style:normal}
.dark .senare{color:var(--is);opacity:.8}
.pris{font:400 40px/1 var(--serif);white-space:nowrap}
table.pl{width:100%;border-collapse:collapse;font:400 19px/1.35 var(--sans)}
table.pl td{padding:13px 0;border-top:1px solid rgba(16,32,46,.14);vertical-align:top}
.dark table.pl td{border-top-color:rgba(156,201,195,.25)}
table.pl td.p{text-align:right;white-space:nowrap;font:500 19px/1.35 var(--sans)}
table.pl small{display:block;font-size:15px;color:#5B6E73;margin-top:3px}
.dark table.pl small{color:var(--is)}
"""


# ------------------------------------------------------------------ byggstenar
class Sponsor:
    """Företaget i materialet: exempelföretaget eller neutralt "[Ert företag]"."""

    def __init__(self, prog: Program, exempel: bool):
        ex = prog.cfg.get("exempel") or {}
        self.exempel = exempel and bool(ex.get("namn"))
        self.namn = ex.get("namn", "") if self.exempel else "[Ert företag]"
        self._svg = ""
        if self.exempel and ex.get("logga"):
            f = prog.klubb.mapp / ex["logga"]
            if f.exists():
                self._svg = re.sub(r"<!--.*?-->", "", f.read_text(encoding="utf-8"), flags=re.S)

    @property
    def hal_namn(self) -> str:
        return f"{self.namn}-hålet"

    def logga(self, w: int, h: int, farg: str = "var(--djup)", ram: str | None = None) -> str:
        """Logotypen i en färg, inpassad i w × h. Neutral version: streckat fält."""
        if self._svg:
            svg = self._svg.replace("<svg ", f"<svg style='width:100%;height:100%;display:block' ", 1)
            return (f"<div style='width:{w}px;height:{h}px;color:{farg};display:flex;align-items:center;"
                    f"justify-content:center'>{svg}</div>")
        return (f"<div class='logo' style='width:{w}px;height:{h}px;color:{ram or farg}'>Er logotyp här"
                f"<small>i en färg</small></div>")


def _sida(prog: Program, kropp: str) -> str:
    return (f"<!doctype html><html lang='sv'><head><meta charset='utf-8'><style>{css(prog.klubb)}{P.CSS}{EXTRA_CSS}"
            f"</style></head><body>{kropp}</body></html>")


def _hd(prog: Program, nr: int | None, text: str = "Partnerprogram", left: int = M, right: int = M) -> str:
    k = prog.klubb
    hoger = f"{nr:02d}" if nr else ""
    return (f"<div class='hd' style='left:{left}px;right:{right}px'><span>{e(k.namn)} · {e(text)} {prog.sasong}</span>"
            f"<span>{hoger}</span></div>")


def bild(prog: Program, namn: str) -> Path | None:
    """En av klubbens bilder ur partnerprogram.yaml → bilder (sökväg relativt klubbmappen)."""
    b = (prog.cfg.get("bilder") or {}).get(namn)
    if not b:
        return None
    p = prog.klubb.mapp / b
    return p if p.exists() else None


def foto(prog: Program, namn: str, x, y, w, h, pos: str = "center", extra: str = "") -> str:
    p = bild(prog, namn)
    if not p:
        return f"<div class='abs' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:var(--sjo);{extra}'></div>"
    return (f"<div class='foto' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px;background-image:url({data_uri(p, 2000)});"
            f"background-position:{pos};{extra}'></div>")


def _hal(prog: Program, nr: int) -> Hal:
    return next(h for h in prog.hal if h.nr == nr)


def _omslagshal(prog: Program) -> list[Hal]:
    nr = prog.klubb.sponsring.get("omslagshal") or [h.nr for h in prog.hal[:3]]
    return [h for n in nr for h in prog.hal if h.nr == n and h.bild]


def _logga_klubb(prog: Program, x: int, y: int, mork: bool = True, storlek: int = 84) -> str:
    k = prog.klubb
    farg = "var(--is)" if mork else "var(--glas)"
    return f"""<div class='abs' style='left:{x}px;top:{y}px;display:flex;align-items:center;gap:22px'>
 <img src='{k.logga("mork" if mork else "ljus")}' style='width:{storlek}px;height:{storlek}px'>
 <div style='font:600 15px/1.5 var(--sans);letter-spacing:.24em;text-transform:uppercase;color:{farg}'>{e(k.namn)}<br>
 <span style='color:var({"--glod" if mork else "--glod-m"})'>{e(k.bana)}</span></div></div>"""


def skylt(prog: Program, h: Hal, sp: Sponsor, x: int, y: int, skala: float = 1.0, qr_svg: str = "",
          stolpar: int = 0) -> str:
    """Hålskylten vid tee (70 × 100 cm): rubrikplatta, hålguide och sponsorplatta. Ritad i 490 × 700 px."""
    tees = "".join(f"<div style='display:flex;justify-content:space-between;font:500 15px/1 var(--sans);color:var(--kristall)'>"
                   f"<span style='color:var(--is)'>{e(t)}</span>{m} m</div>" for t, m in h.tees[:5])
    rubrik = e(sp.hal_namn)
    storlek = 38 if len(sp.hal_namn) <= 16 else 32
    stolp = ""
    if stolpar:
        stolp = (f"<div class='abs' style='left:80px;top:700px;width:22px;height:{stolpar}px;background:#4A3C30'></div>"
                 f"<div class='abs' style='left:388px;top:700px;width:22px;height:{stolpar}px;background:#4A3C30'></div>")
    return f"""<div class='abs' style='left:{x}px;top:{y}px;width:490px;height:700px;transform:scale({skala});transform-origin:0 0'>
{stolp}
<div class='abs' style='left:0;top:0;width:490px;height:700px;background:var(--sjo);padding:10px;display:flex;
 flex-direction:column;gap:8px;box-shadow:0 30px 60px rgba(16,32,46,.35)'>
 <div style='height:92px;background:var(--djup);display:flex;align-items:center;justify-content:center;
  font:400 {storlek}px/1 var(--serif);color:var(--kristall)'>{rubrik}</div>
 <div style='flex:1;background:var(--djup);position:relative;overflow:hidden'>
  {hal_i_ruta(h.bild, 10, 14, 230, 400, max_px=1400) if h.bild else ''}
  <div class='abs' style='left:258px;top:26px;font:400 112px/1 var(--serif);color:var(--kristall)'>{h.nr}</div>
  <div class='abs' style='left:262px;top:150px;font:600 12px/1 var(--sans);letter-spacing:.2em;color:var(--glod)'>PAR {h.par} · INDEX {h.index}</div>
  <div class='abs' style='left:262px;top:184px;right:16px;display:flex;flex-direction:column;gap:11px'>{tees}</div></div>
 <div style='height:150px;background:var(--kristall);display:flex;align-items:center;justify-content:space-between;padding:0 22px'>
  <div><div style='font:600 11px/1 var(--sans);letter-spacing:.22em;color:var(--glas);margin-bottom:12px'>PRESENTERAS AV</div>
   {sp.logga(250, 70, ram='var(--glas)')}</div>
  <div style='text-align:center'><div style='width:92px;height:92px'>{qr_svg}</div>
   <div style='font:500 11px/1 var(--sans);color:var(--glas);margin-top:8px'>Hålguide</div></div></div></div></div>"""


def mobil(prog: Program, x: int, y: int, w: int = 380) -> str:
    """Hålets riktiga sida på klubbens hemsida i en mobil (skärmbild ur partnerprogram.yaml → bilder.halsida)."""
    p = bild(prog, "halsida")
    h = round(w * 2.05)
    inne = (f"<img src='{data_uri(p, 1200)}' style='width:100%;height:100%;object-fit:cover;object-position:top'>"
            if p else "")
    return f"""<div class='abs' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px;border-radius:52px;background:#0B151E;padding:14px;
 box-shadow:0 30px 60px rgba(16,32,46,.3)'><div style='width:100%;height:100%;border-radius:40px;overflow:hidden;background:var(--kristall)'>{inne}</div></div>"""


def inlagg(prog: Program, sp: Sponsor, x: int, y: int, w: int = 440) -> str:
    """Klubbens riktiga inlägg om hålet, med sponsorraden som det får när hålet har en sponsor."""
    k = prog.klubb
    p = bild(prog, "inlagg")
    konto = k.some.get("konto", k.mapp.name)
    h = round(w * 1.25)
    ex = prog.cfg.get("exempel") or {}
    hal = ex.get("hal", 14)
    bildtagg = f"<img src='{data_uri(p, 1200)}' style='width:100%;height:{h}px;object-fit:cover;display:block'>" if p else ""
    return f"""<div class='abs' style='left:{x}px;top:{y}px;width:{w}px;background:#fff;box-shadow:0 30px 60px rgba(16,32,46,.25)'>
 <div style='display:flex;align-items:center;gap:12px;padding:13px 16px'>
  <img src='{k.logga("farg")}' style='width:34px;height:34px;border-radius:50%'>
  <div style='font:600 15px/1 var(--sans)'>{e(konto)}</div></div>
 {bildtagg}
 <div style='padding:13px 16px 16px;font:400 15px/1.45 var(--sans);color:var(--djup)'><b>{e(konto)}</b> Hål {hal} har fått ett namn.
  Välkommen {e(sp.namn)}, ny partner på Fylleryd. Från säsongen {prog.sasong} heter hålet {e(sp.hal_namn)}.</div></div>"""


def entreskylt(prog: Program, sp: Sponsor, x: int, y: int, skala: float = 1.0) -> str:
    """Partnerveckans skylt vid entrén: en gatupratare med utbytbar platta."""
    k = prog.klubb
    return f"""<div class='abs' style='left:{x}px;top:{y}px;width:360px;height:620px;transform:scale({skala});transform-origin:0 0'>
 <div class='abs' style='left:30px;top:520px;width:300px;height:14px;background:#2B3A40;border-radius:3px'></div>
 <div class='abs' style='left:20px;top:0;width:320px;height:530px;background:var(--djup);border-radius:6px;
  box-shadow:0 24px 50px rgba(16,32,46,.35);padding:30px 26px;display:flex;flex-direction:column;align-items:center'>
  <img src='{k.logga("mork")}' style='width:64px;height:64px'>
  <div style='font:600 12px/1 var(--sans);letter-spacing:.26em;color:var(--glod);margin-top:26px'>VECKANS PARTNER</div>
  <div style='margin-top:24px;width:268px;height:160px;background:var(--kristall);display:flex;align-items:center;justify-content:center'>
   {sp.logga(220, 70, ram='var(--glas)')}</div>
  <div style='font:400 26px/1.2 var(--serif);color:var(--kristall);margin-top:28px;text-align:center'>{e(sp.hal_namn)}</div>
  <div style='font:400 15px/1.4 var(--sans);color:var(--is);margin-top:12px;text-align:center'>Tack för att ni gör<br>säsongen möjlig.</div></div></div>"""


# ------------------------------------------------------------------ leverans A: huvudpresentationen
def a01_omslag(prog: Program, sp: Sponsor) -> str:
    return f"""<div class='pg dark'>
{foto(prog, 'omslag', 760, 0, 1160, 1080, 'center 60%')}
<div class='abs' style='left:760px;top:0;width:520px;height:1080px;background:linear-gradient(90deg,var(--djup),rgba(16,32,46,0))'></div>
{_logga_klubb(prog, M, 100)}
<div class='abs' style='left:{M}px;top:330px;width:820px'>
 <div class='ey'>Partnerprogram {prog.sasong}</div>
 <h1 class='xl'>Er plats på {e(prog.klubb.bana)}.</h1>
 <p class='lead' style='max-width:640px'>Arton hål genom skogen, en range, en Pay &amp; Play-bana och en klubb
 där samma människor ses vecka efter vecka. Här är sätten att bli en del av den.</p></div>
<div class='src' style='left:{M}px;width:700px;bottom:48px'>Bilderna visar Fylleryd. {ATTRIBUTION}</div></div>"""


def a02_motesplats(prog: Program) -> str:
    r, kalla = prog.ronder()
    fakta = [(f"≈ {kr(round(r, -2))}", f"ronder per år ({e(kalla)})"),
             ("18 hål", "sedan 1997, i naturreservatet Fylleryd"),
             ("12 tees", "på Pay &amp; Play-banan, där nya golfare börjar"),
             ("4,5 km", "från Växjö centrum"),
             ("April–oktober", "spelas banan, varje dag")]
    rader = "".join(f"<div style='display:flex;align-items:baseline;gap:26px;padding:20px 0;border-top:1px solid rgba(16,32,46,.16)'>"
                    f"<div style='font:400 44px/1 var(--serif);width:300px;flex:none;white-space:nowrap'>{a}</div>"
                    f"<div style='font:400 21px/1.4 var(--sans);color:#33454B'>{b}</div></div>" for a, b in fakta)
    return f"""<div class='pg'>
{foto(prog, 'motesplats', 0, 0, 800, 1080, 'center')}
{_hd(prog, 2, left=900)}
<div class='abs' style='left:900px;right:{M}px;top:140px'>
 <div class='ey'>Klubben som mötesplats</div>
 <h1>Här ses samma människor varje vecka.</h1>
 <p class='lead' style='font-size:25px'>Morgonrundan före jobbet, tisdagsträningen med juniorerna, lördagens
 tävling. {e(prog.klubb.kortnamn)} är en plats man återvänder till, och det är därför ett namn här blir ihågkommet.</p>
 <div style='margin-top:36px'>{rader}</div></div>
<div class='src' style='left:900px;right:{M}px;bottom:36px'>Ronderna är en uppskattning från klubbens egen statistik. {ATTRIBUTION}</div></div>"""


def a03_varfor(prog: Program) -> str:
    skal = [("Lokal närvaro", "Ni syns där era kunder spelar, inte i ett flöde de scrollar förbi. Samma bana, samma vägar, varje vecka."),
            ("Relationer", "Fyra timmar på banan bygger mer än ett möte i ett konferensrum. Bjud in, spela, prata."),
            ("Tillhörighet", "Ett hål med ert namn blir en del av klubbens språk. Det sägs i klubbhuset efter varje runda."),
            ("Professionell exponering", "Allt i klubbens nya profil, godkänt av er innan det visas och redovisat svart på vitt efter säsongen.")]
    kort = "".join(f"<div class='punkt'><div class='n'>{i:02d}</div><h3>{a}</h3><p>{b}</p></div>" for i, (a, b) in enumerate(skal, 1))
    return f"""<div class='pg'>
{_hd(prog, 3)}
<div class='abs' style='left:{M}px;top:140px;width:1100px'>
 <div class='ey'>Varför bli partner</div>
 <h1>Fyra skäl att stå bredvid klubben.</h1></div>
<div class='abs kort2' style='left:{M}px;right:{M}px;top:420px;row-gap:56px'>{kort}</div></div>"""


def a04_miljo(prog: Program) -> str:
    return f"""<div class='pg dark'>
{foto(prog, 'miljo', 0, 0, 1920, 1080, 'center 55%')}
<div class='abs' style='left:0;top:0;width:1920px;height:1080px;background:linear-gradient(90deg,rgba(16,32,46,.92) 0%,rgba(16,32,46,.75) 42%,rgba(16,32,46,0) 75%)'></div>
{_hd(prog, 4)}
<div class='abs' style='left:{M}px;top:250px;width:860px'>
 <div class='ey'>Golfens miljö</div>
 <h1 class='xl'>Fyra timmar utan skärm.</h1>
 <p class='lead'>En runda golf är en av få platser där människor fortfarande pratar med varandra i timmar.
 Företagare, chefer, hantverkare och pensionärer i samma boll. Här byggs förtroende, en fairway i taget.</p>
 <p class='lead' style='margin-top:22px'>Den som syns här syns i ett sammanhang folk tycker om.</p></div>
<div class='src' style='left:{M}px;bottom:40px'>Fylleryd. {ATTRIBUTION}</div></div>"""


def a05_oversikt(prog: Program) -> str:
    kol = []
    for niva, prod in prog.per_niva().items():
        n = prog.nivaer[niva]
        rader = "".join(f"<div style='padding:12px 0;border-top:1px solid rgba(16,32,46,.14)'>"
                        f"<div style='font:500 22px/1.3 var(--sans)'>{e(p['namn'])}</div>"
                        f"<div style='font:400 17px/1.4 var(--sans);color:#4F6268;margin-top:2px'>{e(p['rubrik'])}</div></div>"
                        for p in prod)
        kol.append(f"<div><div style='font:400 46px/1.1 var(--serif)'>{e(n['namn'])}</div>"
                   f"<p class='p' style='font-size:20px;margin:14px 0 22px;min-height:62px'>{e(n['text'])}</p>{rader}</div>")
    return f"""<div class='pg'>
{_hd(prog, 5)}
<div class='abs' style='left:{M}px;top:140px;width:1300px'>
 <div class='ey'>Partnermöjligheter</div>
 <h1>Ett hål, en verksamhet eller hela klubben.</h1></div>
<div class='abs' style='left:1220px;right:{M}px;top:196px'><p class='p' style='font-size:23px'>Varje produkt går att köpa
 för sig. Börja där det känns rätt och bygg vidare när ni vill.</p></div>
<div class='abs kort3' style='left:{M}px;right:{M}px;top:380px'>{''.join(kol)}</div></div>"""


def a06_halet(prog: Program) -> str:
    hal = _omslagshal(prog)
    bw = 860 / max(len(hal), 1)
    bilder = "".join(hal_i_ruta(h.bild, 1000 + i * bw, 80, bw - 16, 860, max_px=1600) for i, h in enumerate(hal))
    nummer = "".join(f"<div class='abs' style='left:{1000 + i * bw:.0f}px;width:{bw - 16:.0f}px;top:972px;text-align:center;"
                     f"font:600 14px/1 var(--sans);letter-spacing:.22em;color:var(--is)'>HÅL {h.nr}</div>" for i, h in enumerate(hal))
    hs = prog.produkter["halsponsor"]
    return f"""<div class='pg dark'>
{bilder}{nummer}
{_hd(prog, 6, right=1000)}
<div class='abs' style='left:{M}px;top:200px;width:800px'>
 <div class='ey'>Huvudprodukten</div>
 <h1 class='xl'>Allt börjar med ett hål.</h1>
 <p class='lead'>{e(hs['ingress'])}</p>
 <p class='lead' style='margin-top:22px'>Hålets nummer och namn är kvar. Ert namn läggs till:
 <span style='color:var(--glod);white-space:nowrap'>[Ert företag]-hålet</span>.</p></div>
<div class='src' style='left:{M}px;width:800px;bottom:40px'>{ATTRIBUTION}</div></div>"""


def a07_exempel(prog: Program, sp: Sponsor, qr_svg: str) -> str:
    ex = prog.cfg.get("exempel") or {}
    h = _hal(prog, int(ex.get("hal", 14)))
    om = (f"{e(sp.namn)} är ett påhittat företag som visar hur det ser ut." if sp.exempel
          else "Ert företagsnamn och er logotyp sätts in här.")
    return f"""<div class='pg'>
<div class='abs' style='left:0;top:0;width:820px;height:1080px;background:linear-gradient(180deg,#DCE6E2 0%,#C9D6D0 100%)'></div>
{skylt(prog, h, sp, 165, 110, 1.0, qr_svg, stolpar=280)}
<div class='abs note' style='left:44px;top:46px;font-size:14px'>Skylten vid tee, 70 × 100 cm.</div>
{_hd(prog, 7, left=920)}
<div class='abs' style='left:920px;right:{M}px;top:150px'>
 <div class='ey'>Exempel · Hål {h.nr}</div>
 <h1>{e(sp.hal_namn)}.</h1>
 <p class='lead'>Hål {h.nr}, par {h.par}. {e(h.rubrik)}. {e(h.beskrivning)}</p>
 <p class='lead' style='margin-top:22px'>Varje boll som slås här slås framför ert namn. Och när rundan är slut är det
 {e(sp.hal_namn)} man pratar om.</p>
 <p class='note' style='margin-top:40px'>{om}</p></div>
<div class='src' style='left:920px;right:{M}px;bottom:40px'>{ATTRIBUTION}</div></div>"""


def a08_ytor(prog: Program) -> str:
    hs = prog.produkter["halsponsor"]
    kort = "".join(
        f"<div class='punkt' style='padding-top:16px'><div class='n'>{i:02d}</div>"
        f"<h3 style='font-size:28px'>{e(x['rubrik'])}{' <span class=senare style=font-size:18px>· under utveckling</span>' if x.get('senare') else ''}</h3>"
        f"<p style='font-size:18px'>{e(x['text'])}</p></div>" for i, x in enumerate(hs["ingar"], 1))
    return f"""<div class='pg'>
{_hd(prog, 8)}
<div class='abs' style='left:{M}px;top:130px;width:1400px'>
 <div class='ey'>Allt som ingår</div>
 <h1>Tio sätt att synas, för ett enda hål.</h1></div>
<div class='abs' style='left:{M}px;right:{M}px;top:340px;display:grid;grid-template-columns:repeat(5,1fr);column-gap:40px;row-gap:40px'>{kort}</div>
<div class='src' style='left:{M}px;right:{M}px;bottom:40px'>{e(prog.villkor['flygfilm'])}</div></div>"""


def a09_partnervecka(prog: Program, sp: Sponsor) -> str:
    v = prog.partnerveckor()
    ytor = prog.veckoytor()
    skylt = any(y.get("kraver") == "entreskylt" for y in ytor)
    lista = "".join(f"<li><i>{e(y['namn'])}.</i> {e(y['text'])}</li>" for y in ytor if y["namn"] != "Foto till rapporten")
    exv = next((w for w, (k, _) in v["plan"].items() if k == f"hal-{int((prog.cfg.get('exempel') or {}).get('hal', 14)):02d}"), None)
    remsa = "".join(
        f"<div style='flex:1;height:44px;border-radius:3px;background:{'var(--glod)' if w == exv else 'rgba(16,32,46,.10)'};"
        f"display:flex;align-items:center;justify-content:center;font:500 13px/1 var(--sans);color:{'var(--djup)' if w == exv else '#4F6268'}'>{w}</div>"
        for w in range(v["forsta"], v["sista"] + 1))
    return f"""<div class='pg'>
{_hd(prog, 9)}
<div class='abs' style='left:{M}px;top:140px;width:960px'>
 <div class='ey'>Er partnervecka</div>
 <h1>En vecka då hela klubben ser er.</h1>
 <p class='lead' style='font-size:25px'>Varje hålpartner får en egen vecka under säsongen. Ingen extra kostnad,
 inget extra arbete för er.</p>
 <ul class='d' style='margin-top:34px'>{lista}</ul></div>
{entreskylt(prog, sp, 1290, 150, 1.0) if skylt else inlagg(prog, sp, 1240, 130, 480)}
{"<div class='abs note' style='left:1310px;top:790px;width:400px'>Partnerveckans skylt vid entrén. Plattan med er logotyp byts in en måndag.</div>" if skylt else ""}
<div class='abs' style='left:{M}px;right:{M}px;top:900px'>
 <div style='font:600 13px/1 var(--sans);letter-spacing:.2em;color:var(--glas);margin-bottom:14px'>SÄSONGENS VECKOR · {'EXEMPEL: ' + e(sp.hal_namn).upper() + ' VECKA ' + str(exv) if exv else ''}</div>
 <div style='display:flex;gap:6px'>{remsa}</div></div></div>"""


def a10_digitalt(prog: Program, sp: Sponsor) -> str:
    return f"""<div class='pg'>
{_hd(prog, 10)}
<div class='abs' style='left:{M}px;top:150px;width:700px'>
 <div class='ey'>Digital exponering</div>
 <h1>Hålet följer med hem.</h1>
 <p class='lead'>Golfarna planerar rundan i mobilen och minns den i flödet. På hålets sida och i klubbens inlägg
 står ert namn bredvid hålet.</p>
 <ul class='d' style='margin-top:40px'>
  <li>Hålets sida på klubbens hemsida, med logotyp och länk till er</li>
  <li>Presentationsinlägget när ni blir partner</li>
  <li>Ett färdigt inlägg att publicera i era egna kanaler</li>
  <li>Hemsidans startsida under er partnervecka</li></ul></div>
{mobil(prog, 930, 130, 380)}
{inlagg(prog, sp, 1370, 150, 430)}
<div class='abs note' style='left:930px;top:944px;width:380px'>Hålets sida på klubbens hemsida.</div>
<div class='abs note' style='left:1370px;top:944px;width:430px'>Klubbens inlägg när hålet får sitt namn.</div>
<div class='src' style='left:930px;right:{M}px;bottom:40px'>{ATTRIBUTION}</div></div>"""


def rapport_kort(prog: Program, sp: Sponsor, x: int, y: int, w: int = 640) -> str:
    """Årsrapportens första sida i miniatyr: de tre sorternas siffror hålls isär."""
    ex = prog.cfg.get("exempel") or {}
    h = _hal(prog, int(ex.get("hal", 14)))
    tee = prog.uppskattning_tee()
    grupper = [
        ("Uppmätt", "Räknat under säsongen", [("Hålets sida på webben", "sidvisningar", "mäts"),
                                             ("QR-koden på skylten", "skanningar", "mäts"),
                                             ("Klubbens inlägg", "visningar enligt Meta", "mäts")]),
        ("Uppskattat", "Räknat ur klubbens ronder", [("Skylten vid tee", "passager", f"≈ {kr(tee)}")]),
        ("Levererat", "Genomfört och fotograferat", [("Skylt, inlägg och partnervecka", "med datum och foto", "✓")]),
    ]
    g = ""
    for rubrik, under, rader in grupper:
        g += (f"<div style='margin-top:18px'><div style='display:flex;justify-content:space-between;align-items:baseline'>"
              f"<span style='font:600 12px/1 var(--sans);letter-spacing:.2em;color:var(--glas)'>{rubrik.upper()}</span>"
              f"<span style='font:400 13px/1 var(--sans);color:#7A8B8F'>{under}</span></div>")
        for a, b, v in rader:
            g += (f"<div style='display:flex;justify-content:space-between;padding:12px 0;border-top:1px solid #DDE5E1;margin-top:10px'>"
                  f"<div><div style='font:500 17px/1.2 var(--sans)'>{a}</div><div style='font:400 13px/1.3 var(--sans);color:#5B6E73'>{b}</div></div>"
                  f"<div style='font:500 20px/1.2 var(--sans);color:{'#7A8B8F' if v == 'mäts' else 'var(--djup)'}'>{v}</div></div>")
        g += "</div>"
    return f"""<div class='abs' style='left:{x}px;top:{y}px;width:{w}px;background:#fff;box-shadow:0 24px 50px rgba(16,32,46,.18)'>
 <div style='background:var(--djup);color:var(--kristall);padding:28px 32px;display:flex;justify-content:space-between;align-items:center'>
  <div><div style='font:600 11px/1 var(--sans);letter-spacing:.22em;color:var(--glod)'>ÅRSRAPPORT {prog.sasong}</div>
   <div style='font:400 34px/1 var(--serif);margin-top:12px'>{e(sp.hal_namn)}</div>
   <div style='font:400 14px/1 var(--sans);color:var(--is);margin-top:10px'>Hål {h.nr} · {e(prog.klubb.namn)}</div></div>
  <img src='{prog.klubb.logga("mork")}' style='width:62px;height:62px'></div>
 <div style='padding:8px 32px 28px'>{g}</div></div>"""


def a11_rapport(prog: Program, sp: Sponsor) -> str:
    return f"""<div class='pg'>
<div class='abs' style='left:0;top:0;width:860px;height:1080px;background:#DCE6E2'></div>
{rapport_kort(prog, sp, 110, 110, 640)}
{_hd(prog, 11, left=960)}
<div class='abs' style='left:960px;right:{M}px;top:150px'>
 <div class='ey'>Efter säsongen</div>
 <h1>Ni ser vad pengarna gav.</h1>
 <p class='lead'>Varje partner får en årsrapport: vad som visades, vad som mättes och vad klubben genomförde,
 med bilder från era platser. Att visa för styrelsen, eller spara till nästa år.</p>
 <p class='p' style='margin-top:34px'>Siffrorna hålls isär. Det som mäts redovisas som mätt. Skylten vid tee är en
 uppskattning ur klubbens ronder, och den kallas så. Inget läggs ihop till ett större tal än det är.</p>
 <p class='note' style='margin-top:30px;max-width:780px'><b>Visningar och passager</b> är antal gånger något har synts,
 inte antal personer.</p></div>
<div class='src' style='left:960px;right:{M}px;bottom:40px'>Rapportens första sida. Mätvärdena fylls i under säsongen.</div></div>"""


def a12_andra(prog: Program) -> str:
    ids = [i for i in ("range", "puttinggreen", "korthal", "junior") if i in prog.produkter]
    kort = "".join(
        f"<div class='punkt'><div class='n'>{e(prog.produkter[i]['namn']).upper()}</div>"
        f"<h3>{e(prog.produkter[i]['rubrik'])}</h3><p>{e(prog.produkter[i]['ingress'])}</p></div>" for i in ids)
    till = prog.med_status("tillagg")
    tillagg = ""
    if till:
        tillagg = (f"<div class='abs' style='left:{M}px;right:{M}px;top:900px;padding-top:22px;border-top:1px solid rgba(156,201,195,.28);"
                   f"font:400 22px/1.5 var(--sans);color:#C9DAD6'><span style='color:var(--glod)'>Det finns också plats för en partner vid</span> "
                   + _och([e(p.get('plats') or p['namn']) for p in till]) + ".</div>")
    return f"""<div class='pg dark'>
{_hd(prog, 12)}
<div class='abs' style='left:{M}px;top:130px;width:1300px'>
 <div class='ey'>Fler platser</div>
 <h1>Bortom fairway.</h1>
 <p class='lead' style='font-size:25px;max-width:1080px'>Hela anläggningen är full av ställen där människor stannar.
 Varje plats har en partner, aldrig fler.</p></div>
<div class='abs kort2' style='left:{M}px;right:{M}px;top:400px;row-gap:46px'>{kort}</div>
{tillagg}</div>"""


def _och(ord: list[str]) -> str:
    return ord[0] if len(ord) == 1 else ", ".join(ord[:-1]) + " och " + ord[-1]


def a13_aktiviteter(prog: Program) -> str:
    ids = [i for i in ("tavling", "foretagsdag", "huvudpartner") if i in prog.produkter]
    kort = "".join(
        f"<div class='punkt'><div class='n'>{e(prog.produkter[i]['namn']).upper()}</div>"
        f"<h3 style='font-size:36px'>{e(prog.produkter[i]['rubrik'])}</h3><p style='font-size:23px'>{e(prog.produkter[i]['ingress'])}</p></div>" for i in ids)
    return f"""<div class='pg'>
{foto(prog, 'aktiviteter', 1180, 0, 740, 1080, 'center')}
{_hd(prog, 13, right=860)}
<div class='abs' style='left:{M}px;top:130px;width:940px'>
 <div class='ey'>Verksamhet och aktiviteter</div>
 <h1>Träffa människorna, inte bara synas.</h1>
 <div style='display:flex;flex-direction:column;gap:34px;margin-top:46px'>{kort}</div></div></div>"""


def _prisrad(p: dict, pris: str | None = None) -> str:
    if pris is None:
        pris = f"{kr(p['pris'])} kr" if p.get("pris") else "Offert"
    enhet = p.get("prisenhet", "")
    enhet = "" if enhet in ("per år", "offert") else f"<small>{e(enhet)}</small>"
    return (f"<tr><td>{e(p['namn'])}<small>{e(p['rubrik'])}</small></td>"
            f"<td class='p'>{pris}{enhet}</td></tr>")


def a14_priser(prog: Program) -> str:
    kol = []
    for niva, prod in prog.per_niva().items():
        n = prog.nivaer[niva]
        rader = ""
        for p in prod:
            if p["id"] == "premiumhal":
                nr = ", ".join(str(x) for x in (prog.cfg.get("premiumhal") or {}))
                p = {**p, "rubrik": f"Hål {nr}"}
            if p["id"] == "huvudpartner":
                rader += _prisrad(p, f"från {kr(p['pris'])} kr")
            elif p["id"] == "tavling":
                rader += _prisrad(p, f"från {kr(p['pris'])} kr")
            else:
                rader += _prisrad(p)
        mer = ""
        if niva == "huvud" and prod:
            mer = ("<ul class='d' style='margin-top:26px'>" + "".join(
                f"<li style='font-size:19px;padding-bottom:10px'>{e(x['rubrik'])}</li>" for x in prod[0]["ingar"]) + "</ul>")
        kol.append(f"<div><div style='font:400 40px/1.1 var(--serif)'>{e(n['namn'])}</div>"
                   f"<table class='pl' style='margin-top:22px'>{rader}</table>{mer}</div>")
    v = prog.villkor
    return f"""<div class='pg'>
{_hd(prog, 14)}
<div class='abs' style='left:{M}px;top:130px;width:1400px'>
 <div class='ey'>Partnernivåer och priser</div>
 <h1>Tydliga priser, per år.</h1></div>
<div class='abs kort3' style='left:{M}px;right:{M}px;top:340px'>{''.join(kol)}</div>
<div class='abs' style='left:{M}px;right:{M}px;top:900px;padding-top:24px;border-top:1px solid rgba(16,32,46,.18);display:flex;gap:70px'>
 <div style='font:400 19px/1.5 var(--sans);color:#33454B;flex:1'><b style='font-weight:600'>Treårsavtal.</b> {e(v['treaarsfordel'])}</div>
 <div style='font:400 19px/1.5 var(--sans);color:#33454B;flex:1'><b style='font-weight:600'>Ettårsavtal.</b> {e(v['startkostnad_text'])}</div>
 <div style='font:400 19px/1.5 var(--sans);color:#33454B;flex:1'><b style='font-weight:600'>Ensamrätt.</b> En partner per hål och per plats.</div></div></div>"""


def a15_tillgangligt(prog: Program, idag: str) -> str:
    cw, gx = 168, 17
    celler = ""
    for i, h in enumerate(prog.hal):
        x = M + (i % 9) * (cw + gx)
        y = 300 + (i // 9) * 262
        tagen = h.status != "ledig"
        bildhtml = hal_i_ruta(h.bild, x + 6, y + 6, cw - 12, 160, max_px=600, extra="opacity:.35" if tagen else "") if h.bild else ""
        prem = "<span style='color:var(--glod-m)'> · premium</span>" if h.premium else ""
        celler += (f"<div class='abs' style='left:{x}px;top:{y}px;width:{cw}px;height:172px;background:var(--djup);border-radius:4px'></div>{bildhtml}"
                   f"<div class='abs' style='left:{x}px;top:{y + 184}px;width:{cw}px;display:flex;justify-content:space-between;align-items:baseline'>"
                   f"<span style='font:400 30px/1 var(--serif)'>{h.nr}</span><span style='font:500 15px/1 var(--sans);color:var(--glas)'>Par {h.par}</span></div>"
                   f"<div class='abs' style='left:{x}px;top:{y + 222}px;width:{cw + 10}px;font:500 15px/1.2 var(--sans);color:{'#5B6E73' if tagen else 'var(--djup)'}'>"
                   f"{HALSTATUS[h.status]}{prem}</div>")
    ovr = [p for p in prog.aktiva() if p["niva"] != "hal" and p.get("max") == 1]
    st = (prog.cfg.get("status") or {})
    lista = "".join(f"<div style='padding:14px 0;border-top:1px solid rgba(16,32,46,.16)'>"
                    f"<div style='font:500 19px/1.25 var(--sans)'>{e(p['namn'])}</div><div style='font:400 16px/1.3 var(--sans);color:var(--glas);margin-top:4px'>"
                    f"{e(HALSTATUS.get(_status(st.get(p['id'])), 'Ledigt'))}</div></div>" for p in ovr)
    prem = "; ".join(f"hål {n}: {e(p['namn'].lower())}" for n, p in (prog.cfg.get('premiumhal') or {}).items())
    return f"""<div class='pg'>
{_hd(prog, 15)}
<div class='abs' style='left:{M}px;top:130px;width:1100px'>
 <div class='ey'>Tillgängligt {prog.sasong}</div>
 <h1>Vilket blir ert?</h1></div>
<div class='abs note' style='left:{M}px;top:250px'>Läget {e(idag)}. Premiumhål med extra yta: {prem}.</div>
{celler}
<div class='abs' style='left:{M}px;right:{M}px;top:870px;display:grid;grid-template-columns:repeat({max(len(ovr), 1)},1fr);column-gap:36px'>{lista}</div></div>"""


def _status(v) -> str:
    v = str(v or "ledig").lower()
    return {"reserverad": "bokad", "reserverat": "bokad", "bokat": "bokad", "sålt": "såld", "sald": "såld"}.get(v, v)


def a16_kontakt(prog: Program, qr_svg: str, url: str) -> str:
    c = prog.kontakt()
    steg = [("Välj er plats.", "Ett hål, en verksamhet eller hela klubben."),
            ("Vi tar fram allt.", "Skylt, sidor och inlägg med er logotyp. Ni godkänner innan något visas."),
            (f"Säsongen {prog.sasong} är er.", "Från första start till sista putt, och en rapport när den är slut.")]
    rader = "".join(f"<div style='display:flex;gap:28px;padding:24px 0;border-top:1px solid rgba(156,201,195,.28)'>"
                    f"<div style='font:400 46px/1 var(--serif);color:var(--glod);width:40px'>{i}</div>"
                    f"<div><div style='font:400 34px/1.15 var(--serif)'>{a}</div>"
                    f"<div style='font:400 20px/1.5 var(--sans);color:#C9DAD6;margin-top:8px'>{b}</div></div></div>"
                    for i, (a, b) in enumerate(steg, 1))
    return f"""<div class='pg dark'>
{foto(prog, 'avslutning', 1220, 0, 700, 1080, 'center')}
{_logga_klubb(prog, M, 100)}
<div class='abs' style='left:{M}px;top:280px;width:960px'>
 <h1 class='xl'>Nästa steg är ett samtal.</h1>
 <div style='margin-top:40px'>{rader}</div>
 <div style='display:flex;align-items:center;gap:30px;margin-top:40px'>
  <div style='width:140px;height:140px;background:var(--kristall);padding:12px;flex:none'>{qr_svg}</div>
  <div><div style='font:400 20px/1.4 var(--sans);color:var(--is)'>{e(c['namn'])}</div>
  <div style='font:500 28px/1.4 var(--sans)'>{e(c['epost'])} · {e(c['telefon'])}</div>
  <div style='font:400 17px/1.4 var(--sans);color:var(--is);margin-top:4px'>{e(url.replace('https://', ''))}</div></div></div></div>
<div class='src' style='left:{M}px;width:1000px;bottom:40px'>{ATTRIBUTION} · Material: TACADA</div></div>"""


def deck(prog: Program, sp: Sponsor, idag: str) -> tuple[list[str], bool]:
    from .prospekt_gemensam import sponsorsida

    url = sponsorsida(prog.klubb)
    qr_sida, akta = qr(url, prog.klubb.farger["djup"])
    ex = int((prog.cfg.get("exempel") or {}).get("hal", 14))
    qr_hal, akta2 = qr(prog.klubb.qr_lank(ex), prog.klubb.farger["djup"])
    s = [a01_omslag(prog, sp), a02_motesplats(prog), a03_varfor(prog), a04_miljo(prog), a05_oversikt(prog),
         a06_halet(prog), a07_exempel(prog, sp, qr_hal), a08_ytor(prog), a09_partnervecka(prog, sp),
         a10_digitalt(prog, sp), a11_rapport(prog, sp), a12_andra(prog), a13_aktiviteter(prog), a14_priser(prog),
         a15_tillgangligt(prog, idag), a16_kontakt(prog, qr_sida, url)]
    return s, akta and akta2


# ------------------------------------------------------------------ framtida kanal (separat, aktiveras när avtal finns)
def framtida_kanal(prog: Program, sp: Sponsor, intern: bool) -> str:
    namn = (prog.cfg.get("framtida_kanal") or {}).get("intern_namn", "") if intern else ""
    rubrik = f"Hålet i {namn}." if namn else "Nästa kanal för hålet."
    text = ("Internt underlag. Visas inte för klubbar eller sponsorer innan avtal och sekretessavtal är klara."
            if intern else "Fler digitala kanaler för hålet är under utveckling. När de finns kan de läggas till ert hålsponsorskap.")
    return f"""<div class='pg dark'>
{_hd(prog, None, "Framtida tillval")}
<div class='abs' style='left:{M}px;top:200px;width:980px'>
 <div class='ey'>{'Internt · ' if intern else ''}Under utveckling</div>
 <h1 class='xl'>{e(rubrik)}</h1>
 <p class='lead'>Golfarna har banan i mobilen under hela rundan. När hålet visas där kan ert namn och er logotyp
 följa med, hål för hål.</p>
 <ul class='d' style='margin-top:40px'>
  <li>Ingår inte i något paket och säljs inte i dag</li>
  <li>Aktiveras först när avtal finns, som ett tillägg till hålsponsorskapet</li>
  <li>Visningarna redovisas i årsrapporten när kanalen är i gång</li></ul>
 <p class='note' style='margin-top:40px;max-width:900px'>{e(text)}</p></div>
<div class='abs' style='left:1240px;top:150px;width:420px;height:800px;border-radius:52px;background:#0B151E;padding:14px'>
 <div style='width:100%;height:100%;border-radius:40px;background:var(--sjo);position:relative;overflow:hidden'>
  {hal_i_ruta(_hal(prog, int((prog.cfg.get('exempel') or {}).get('hal', 14))).bild, 30, 60, 332, 560, max_px=1200)}
  <div class='abs' style='left:24px;right:24px;bottom:30px;height:96px;background:var(--kristall);border-radius:16px;display:flex;align-items:center;justify-content:center'>
   {sp.logga(240, 56, ram='var(--glas)')}</div></div></div>
<div class='abs note' style='left:1240px;top:970px;width:420px'>Skiss. Inte en befintlig produkt.</div></div>"""


# ------------------------------------------------------------------ leverans B: prospekt per hål och produkt
def b_hal_1(prog: Program, h: Hal, sp: Sponsor, qr_svg: str) -> str:
    chip = f"<span class='chip {h.status}'>{HALSTATUS[h.status]} {prog.sasong}</span>"
    prem = ""
    if h.premium:
        prem = (f"<div style='margin-top:30px;border-left:3px solid var(--glod-m);padding:4px 0 4px 24px'>"
                f"<div class='ey' style='font-size:14px'>Premiumhål · {e(h.premium['namn'])}</div>"
                f"<div style='font:400 22px/1.5 var(--sans);color:#33454B;margin-top:10px'>{e(h.premium['extra'])}</div></div>")
    tees = "".join(f"<div style='display:flex;justify-content:space-between;padding:12px 0;border-top:1px solid rgba(16,32,46,.14);"
                   f"font:400 21px/1 var(--sans)'><span style='color:var(--glas)'>Tee {e(t)}</span><b style='font-weight:500'>{m} m</b></div>"
                   for t, m in h.tees)
    return f"""<div class='pg'>
<div class='abs' style='left:0;top:0;width:760px;height:1080px;background:var(--djup)'></div>
{hal_i_ruta(h.bild, 60, 60, 640, 960) if h.bild else ''}
<div class='src ljus' style='left:60px;width:640px;bottom:22px;font-size:13px'>{ATTRIBUTION}</div>
{_hd(prog, None, "Hålsponsor", left=840)}
<div class='abs' style='left:840px;top:140px;width:560px'>
 <div style='display:flex;align-items:flex-end;gap:30px'>
  <div style='font:400 200px/.8 var(--serif);letter-spacing:-.03em'>{h.nr}</div>
  <div style='padding-bottom:8px'><div class='ey'>Par {h.par} · Index {h.index}</div>
   <div style='margin-top:16px'>{chip}</div></div></div>
 <h1 style='font-size:62px;margin-top:40px'>{e(sp.hal_namn)}</h1>
 <p class='p' style='margin-top:20px;font-size:22px'><b style='font-weight:600'>{e(h.rubrik)}.</b> {e(h.beskrivning)}</p>
 {prem}
 <div style='margin-top:30px'>{tees}</div></div>
{skylt(prog, h, sp, 1440, 150, 0.72, qr_svg, stolpar=320)}
<div class='abs note' style='left:1440px;top:930px;width:360px;font-size:14px'>Skylten vid tee, 70 × 100 cm.{' ' + e(sp.namn) + ' är ett påhittat exempel.' if sp.exempel else ''}</div></div>"""


def b_villkor(prog: Program, p: dict, pris: int | None, status: str, sp: Sponsor, qr_svg: str, url: str,
              rubrik: str, extra: str = "") -> str:
    """Prospektets andra sida: vad som ingår, pris, avtal, tillgänglighet och kontakt."""
    c = prog.kontakt()
    v = prog.villkor
    ingar = "".join(
        f"<div class='punkt' style='padding-top:14px'><h3 style='font-size:26px;margin-top:0'>{e(x['rubrik'])}"
        f"{' <span class=senare style=font-size:17px>· under utveckling</span>' if x.get('senare') else ''}</h3>"
        f"<p style='font-size:19px;margin-top:6px'>{e(x['text'])}</p></div>" for x in p["ingar"])
    if pris:
        prisrad = f"<div style='font:400 84px/1 var(--serif)'>{kr(pris)}&nbsp;kr</div>"
        enhet = p.get("prisenhet", "per år")
    else:
        prisrad = "<div style='font:400 60px/1 var(--serif)'>Offert</div>"
        enhet = "efter antal gäster och upplägg"
    start = p.get("startkostnad") or 0
    avtal = (f"Ett eller tre år. {e(v['treaarsfordel'])}" + (f" Ettårsavtal: startkostnad {kr(start)} kr." if start else "")
             if p.get("prisenhet") == "per år" else "Per tillfälle.")
    tillg = {"ledig": f"Ledigt för säsongen {prog.sasong}.", "bokad": "Reserverat. Fråga om kölistan.",
             "såld": f"Sålt för {prog.sasong}. Fråga om andra platser."}[status]
    return f"""<div class='pg'>
{_hd(prog, None, rubrik)}
<div class='abs' style='left:{M}px;top:130px;width:1040px'>
 <div class='ey'>Det här ingår</div>
 <h1 style='font-size:64px'>{e(p['namn'] if not sp else (sp.hal_namn if p['niva'] == 'hal' else p['namn']))}</h1>
 {extra}
 <div class='kort2' style='margin-top:30px;row-gap:16px;column-gap:44px'>{ingar}</div></div>
<div class='abs dark' style='left:{W - 640}px;top:0;width:640px;height:1080px;background:var(--djup)'>
 <div class='abs' style='left:70px;right:70px;top:120px'>
  <div class='ey'>Pris</div><div style='margin-top:24px'>{prisrad}</div>
  <div style='font:400 21px/1.4 var(--sans);color:var(--is);margin-top:12px'>{e(enhet)}</div>
  <div style='margin-top:40px;border-top:1px solid rgba(156,201,195,.3);padding-top:24px'>
   <div class='ey' style='font-size:14px'>Avtal</div>
   <div style='font:400 19px/1.5 var(--sans);color:#D3E3E0;margin-top:10px'>{avtal}</div></div>
  <div style='margin-top:24px;border-top:1px solid rgba(156,201,195,.3);padding-top:24px'>
   <div class='ey' style='font-size:14px'>Tillgänglighet</div>
   <div style='font:400 19px/1.5 var(--sans);color:#D3E3E0;margin-top:10px'>{tillg} {e(p.get('exklusivt', ''))}</div></div>
  <div style='margin-top:24px;border-top:1px solid rgba(156,201,195,.3);padding-top:24px;display:flex;gap:24px;align-items:center'>
   <div style='width:120px;height:120px;background:var(--kristall);padding:10px;flex:none'>{qr_svg}</div>
   <div><div style='font:400 17px/1.4 var(--sans);color:var(--is)'>{e(c['namn'])}</div>
    <div style='font:500 21px/1.4 var(--sans)'>{e(c['epost'])}</div><div style='font:500 21px/1.4 var(--sans)'>{e(c['telefon'])}</div>
    <div style='font:400 14px/1.4 var(--sans);color:var(--is);margin-top:4px;word-break:break-all'>{e(url.replace('https://', ''))}</div></div></div></div>
 <div class='src' style='left:70px;right:70px;bottom:36px;font-size:13px'>Material: TACADA</div></div>
<div class='abs' style='left:{M}px;bottom:44px;display:flex;align-items:center;gap:16px'>
 <img src='{prog.klubb.logga("ljus")}' style='width:52px;height:52px'>
 <div style='font:400 15px/1.5 var(--sans);color:#5B6E73'>{e(prog.klubb.namn)} · {e(prog.klubb.web.replace('https://', ''))}</div></div></div>"""


def prospekt_hal(prog: Program, h: Hal, sp: Sponsor) -> tuple[list[str], bool]:
    qr_svg, akta = qr(prog.klubb.qr_lank(h.nr), prog.klubb.farger["djup"])
    p = prog.produkter[h.produkt]
    if h.premium:
        p = {**p, "ingar": prog.produkter["halsponsor"]["ingar"][:-1] +
             [{"rubrik": h.premium["namn"], "text": h.premium["extra"]}] + prog.produkter["halsponsor"]["ingar"][-1:]}
    url = prog.klubb.halsida(h.nr)
    return [b_hal_1(prog, h, sp, qr_svg),
            b_villkor(prog, p, h.pris, h.status, sp, qr_svg, url, f"Hålsponsor · Hål {h.nr}")], akta


# Visualiseringar för produkterna: ritade, inga bilder av ytor som inte finns i klubbens material.
def _viz(prog: Program, pid: str, sp: Sponsor) -> str:
    k = prog.klubb
    if pid == "range":
        ban = lambda y: (f"<div class='abs' style='left:0;top:{y}px;width:640px;height:170px;background:var(--kristall);border-radius:4px;"
                         f"box-shadow:0 20px 40px rgba(0,0,0,.25);display:flex;align-items:center;justify-content:space-between;padding:0 40px'>"
                         f"<div style='font:400 40px/1.1 var(--serif);color:var(--djup)'>{e(sp.namn if sp.exempel else '[Ert företag]')}-rangen</div>"
                         f"{sp.logga(200, 64, ram='var(--glas)')}</div>")
        return ban(0) + "<div class='abs note' style='left:0;top:190px;color:var(--is)'>Banderollen vid utslagsplatserna, 200 × 70 cm.</div>"
    if pid == "puttinggreen":
        flagga = (f"<div style='position:relative;width:120px;height:330px'><div class='abs' style='left:8px;top:0;width:5px;height:330px;background:#C9D6D0'></div>"
                  f"<div class='abs' style='left:13px;top:6px;width:104px;height:70px;background:var(--kristall);display:flex;align-items:center;justify-content:center;padding:8px'>"
                  f"{sp.logga(88, 40, ram='var(--glas)')}</div></div>")
        return (f"<div style='display:flex;gap:46px'>{flagga * 4}</div>"
                "<div class='note' style='margin-top:20px;color:var(--is)'>Flaggorna på puttinggreenen, med er logotyp.</div>")
    if pid == "korthal":
        return (f"<div style='width:520px;background:var(--kristall);padding:36px 40px;border-radius:4px;box-shadow:0 20px 40px rgba(0,0,0,.25)'>"
                f"<div style='font:600 13px/1 var(--sans);letter-spacing:.22em;color:var(--glas)'>PAY &amp; PLAY · 12 TEES</div>"
                f"<div style='font:400 50px/1.05 var(--serif);color:var(--djup);margin-top:18px'>{e(sp.namn if sp.exempel else '[Ert företag]')}-banan</div>"
                f"<div style='margin-top:30px'>{sp.logga(260, 80, ram='var(--glas)')}</div></div>"
                "<div class='note' style='margin-top:20px;color:var(--is)'>Skylten vid banans första tee.</div>")
    if pid == "junior":
        trojan = (f"<svg viewBox='0 0 300 300' style='width:360px;height:360px'><path d='M95 30 L60 45 L20 95 L55 125 L75 105 L75 280 L225 280 L225 105 L245 125 L280 95 L240 45 L205 30 Q150 70 95 30 Z' "
                  f"fill='{k.farger['sjo']}' stroke='{k.farger['is']}' stroke-width='2'/></svg>")
        return (f"<div style='position:relative;width:360px;height:360px'>{trojan}"
                f"<div class='abs' style='left:115px;top:120px;width:130px;height:50px;color:var(--kristall);display:flex;align-items:center'>"
                f"{sp.logga(130, 40, 'var(--kristall)', ram='var(--is)')}</div></div>"
                "<div class='note' style='margin-top:10px;color:var(--is)'>Juniorernas träningströja, med er logotyp i en färg.</div>")
    if pid == "tavling":
        namn = f"{sp.namn} Open" if sp.exempel else "[Ert företag] Open"
        rader = "".join(f"<div style='display:flex;justify-content:space-between;padding:10px 0;border-top:1px solid #DDE5E1;font:400 17px/1 var(--sans)'>"
                        f"<span>{t}</span><span style='color:#5B6E73'>Tee 1</span></div>" for t in ("08.00", "08.10", "08.20", "08.30"))
        return (f"<div style='width:520px;background:#fff;padding:34px 38px;border-radius:4px;box-shadow:0 20px 40px rgba(0,0,0,.25);color:var(--djup)'>"
                f"<div style='font:600 12px/1 var(--sans);letter-spacing:.22em;color:var(--glas)'>STARTLISTA</div>"
                f"<div style='font:400 44px/1.05 var(--serif);margin-top:14px'>{e(namn)}</div>"
                f"<div style='margin:22px 0 14px'>{sp.logga(200, 56, ram='var(--glas)')}</div>{rader}</div>")
    if pid == "foretagsdag":
        prog_ = [("13.00", "Välkomna, kaffe"), ("13.30", "PRO:n visar grunderna på rangen"), ("14.30", "Puttning och närspel"),
                 ("15.30", "Gruppen spelar Pay & Play-banan"), ("17.30", "Middag i klubbhuset")]
        rader = "".join(f"<div style='display:flex;gap:26px;padding:14px 0;border-top:1px solid rgba(156,201,195,.28);font:400 19px/1.3 var(--sans)'>"
                        f"<span style='color:var(--glod);width:60px'>{a}</span><span>{e(b)}</span></div>" for a, b in prog_)
        return f"<div style='width:560px'><div class='ey' style='margin-bottom:18px'>Exempel på en eftermiddag</div>{rader}</div>"
    if pid == "huvudpartner":
        return (f"<div style='width:600px;background:var(--kristall);border-radius:4px;box-shadow:0 20px 40px rgba(0,0,0,.25);padding:30px 36px;color:var(--djup)'>"
                f"<div style='font:600 12px/1 var(--sans);letter-spacing:.22em;color:var(--glas)'>HEMSIDANS SIDFOT</div>"
                f"<div style='display:flex;align-items:center;gap:26px;margin-top:22px'><img src='{k.logga('ljus')}' style='width:70px;height:70px'>"
                f"<div style='font:400 26px/1.2 var(--serif)'>{e(k.namn)}</div></div>"
                f"<div style='margin-top:26px;padding-top:20px;border-top:1px solid #DDE5E1;font:500 13px/1 var(--sans);color:var(--glas)'>Huvudpartner</div>"
                f"<div style='margin-top:12px'>{sp.logga(240, 64, ram='var(--glas)')}</div></div>")
    return ""


def b_produkt_1(prog: Program, p: dict, sp: Sponsor) -> str:
    return f"""<div class='pg dark'>
{_hd(prog, None, p['namn'])}
<div class='abs' style='left:{M}px;top:200px;width:880px'>
 <div class='ey'>{e(prog.nivaer[p['niva']]['namn'])}</div>
 <h1 class='xl'>{e(p['rubrik'])}</h1>
 <p class='lead'>{e(p['ingress'])}</p>
 <div style='margin-top:44px'><div class='ey' style='font-size:14px'>Passar</div>
  <ul class='d' style='margin-top:20px'>{''.join(f'<li style="font-size:22px">{e(x)}</li>' for x in p.get('passar') or [])}</ul></div></div>
<div class='abs' style='left:1100px;top:230px;width:660px;transform:scale(1.3);transform-origin:0 0'>{_viz(prog, p['id'], sp)}</div>
<div class='src' style='left:{M}px;bottom:40px'>{(e(sp.namn) + ' är ett påhittat exempel.') if sp.exempel else 'Er logotyp sätts in i en färg.'}</div></div>"""


def prospekt_produkt(prog: Program, p: dict, sp: Sponsor) -> tuple[list[str], bool]:
    from .prospekt_gemensam import sponsorsida

    url = sponsorsida(prog.klubb)
    qr_svg, akta = qr(url, prog.klubb.farger["djup"])
    status = _status((prog.cfg.get("status") or {}).get(p["id"]))
    return [b_produkt_1(prog, p, sp), b_villkor(prog, p, p.get("pris"), status, sp, qr_svg, url, p["namn"])], akta


PRODUKTPROSPEKT = ("range", "puttinggreen", "korthal", "junior", "tavling", "foretagsdag", "huvudpartner")


__all__ = ["PRODUKTPROSPEKT", "Sponsor", "deck", "framtida_kanal", "prospekt_hal", "prospekt_produkt", "rapport_kort",
           "_sida", "W", "H"]
