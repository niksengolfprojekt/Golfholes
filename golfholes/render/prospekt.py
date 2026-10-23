"""Hålsponsorprospekt: en PDF per hål, samma mall för varje hål och varje klubb.

  python -m golfholes prospekt klubbar/<klubb>/halkort/hal-14.yaml
  python -m golfholes prospekt klubbar/<klubb> --alla          (alla hål som har en hålbild)

Klubben är avsändare. Allt klubbspecifikt kommer ur klubb.yaml (profil, sponsring), hålets
texter ur hålkortet och hålbilden är hålkortets bild med tees och T-flagga. Sex sidor:
  1 Omslag   2 Hålet   3 Skylten vid tee   4 Digitalt   5 Rapporten   6 Det här ingår + pris
Ett hålkort kan ändra omslagets texter med `prospekt: {rubrik: ..., ingress: ...}`. Pro:ns råd på
sidan 2 är hålkortets `kortrad` (en mening).
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .halkort import Halkort
from .klubbmaterial import (ATTRIBUTION, Klubb, Webblasare, css, e, hal_i_ruta, halkort_markerat,
                            kontaktark, kr, qr)

W, H, M = 1920, 1080, 120
SIDOR = 6

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:#888}
.pg{position:relative;width:1920px;height:1080px;overflow:hidden;background:var(--kristall);color:var(--djup);
  page-break-after:always;break-after:page}
.pg:last-child{page-break-after:auto;break-after:auto}
.dark{background:var(--djup);color:var(--kristall)}
.abs{position:absolute}
.hd{position:absolute;top:60px;display:flex;justify-content:space-between;font:600 14px/1 var(--sans);
  letter-spacing:.24em;text-transform:uppercase;color:var(--glas)}
.dark .hd{color:var(--is)}
.ey{font:600 17px/1 var(--sans);letter-spacing:.22em;text-transform:uppercase;color:var(--glod-m)}
.dark .ey{color:var(--glod)}
h1{font:400 76px/1.06 var(--serif);letter-spacing:-.01em;margin-top:26px;text-wrap:balance}
h1.xl{font-size:104px;line-height:1}
.lead{font:400 28px/1.48 var(--sans);margin-top:30px;color:#2C3D44;text-wrap:pretty}
.dark .lead{color:#D3E3E0}
.p{font:400 23px/1.55 var(--sans);color:#33454B;text-wrap:pretty}
.dark .p{color:#C9DAD6}
.note{font:400 16px/1.5 var(--sans);color:#4F6268}
.dark .note{color:var(--is);opacity:.85}
.src{position:absolute;font:400 15px/1.4 var(--sans);color:#5B6E73}
.dark .src,.src.ljus{color:var(--is);opacity:.8}
.tees{margin-top:30px;font:400 24px/1 var(--sans);font-variant-numeric:tabular-nums lining-nums}
.tees div{display:flex;justify-content:space-between;padding:15px 0;border-top:1px solid rgba(16,32,46,.16)}
.tees span:first-child{color:var(--glas)}
.tees b{font-weight:500}
.logo{border:2px dashed currentColor;display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:6px;font:600 15px/1 var(--sans);letter-spacing:.18em;text-transform:uppercase;text-align:center}
.logo small{font:400 13px/1.3 var(--sans);letter-spacing:.02em;text-transform:none;opacity:.75}
ul.d{list-style:none}
ul.d li{position:relative;padding:0 0 18px 34px;font:400 24px/1.45 var(--sans)}
ul.d li:before{content:'';position:absolute;left:2px;top:13px;width:9px;height:9px;transform:rotate(45deg);background:var(--glas)}
ul.d li i{font-style:normal;color:var(--glas)}
.tag{display:inline-block;font:600 12px/1 var(--sans);letter-spacing:.16em;text-transform:uppercase;padding:6px 9px;
  border:1.5px solid currentColor;border-radius:3px;margin-left:12px;vertical-align:3px;color:var(--glod-m)}
"""


def _sida(k: Klubb, kropp: str) -> str:
    return (f"<!doctype html><html lang='sv'><head><meta charset='utf-8'><style>{css(k)}{CSS}</style></head>"
            f"<body>{kropp}</body></html>")


def _huvud(k: Klubb, c: Halkort, nr: int, left: int = M, right: int = M) -> str:
    return (f"<div class='hd' style='left:{left}px;right:{right}px'><span>{e(k.namn)} · Hålsponsor {k.sasong}</span>"
            f"<span>Hål {c.hole} · {nr:02d}</span></div>")


def _tees(c: Halkort) -> str:
    return "<div class='tees'>" + "".join(
        f"<div><span>Tee {e(t)}</span><b>{m}&nbsp;m</b></div>" for t, m in c.tees) + "</div>"


def _logofalt(w: int, h: int, farg: str = "var(--glas)", text: str = "Er logotyp här") -> str:
    return (f"<div class='logo' style='width:{w}px;height:{h}px;color:{farg}'>{text}"
            f"<small>i en färg</small></div>")


def _uppskattning(k: Klubb) -> tuple[str, str]:
    ronder, kalla = k.ronder()
    avrundat = int(round(ronder, -2))
    return (f"≈&nbsp;{kr(avrundat)}",
            f"Uppskattning: ronder per år × andelen ronder som spelar hålet. Här räknat på {e(kalla)} "
            f"({kr(ronder)} ronder) och att alla ronder spelar hålet. Visningar är antal gånger skylten "
            f"passeras, inte antal personer.")


# ------------------------------------------------------------------ sidorna
def s1_omslag(k: Klubb, c: Halkort, d: dict) -> str:
    rubrik = d.get("rubrik") or f"Ert namn på hål {c.hole}."
    ingress = d.get("ingress") or (f"{c.rubrik}. Hela säsongen slår golfarna ut vid er skylt, "
                                   f"och hålet bär ert namn överallt där klubben visar det.")
    glod = "radial-gradient(ellipse 60% 55% at 50% 50%,rgba(63,127,134,.35),rgba(16,32,46,0) 70%)"
    return f"""<div class='pg dark'>
<div class='abs' style='left:0;top:0;width:900px;height:1080px;background:{glod}'></div>
{hal_i_ruta(c.image, 80, 60, 740, 960)}
<div class='abs' style='left:980px;top:96px;display:flex;align-items:center;gap:22px'>
 <img src='{k.logga("mork")}' style='width:92px;height:92px'>
 <div style='font:600 16px/1.5 var(--sans);letter-spacing:.24em;text-transform:uppercase;color:var(--is)'>{e(k.namn)}<br>
 <span style='color:var(--glod)'>{e(k.bana)}</span></div></div>
<div class='abs' style='left:980px;right:{M}px;top:330px'>
 <div class='ey'>Hålsponsor {k.sasong} · Hål {c.hole}</div>
 <h1 class='xl'>{e(rubrik)}</h1>
 <p class='lead' style='max-width:780px'>{e(ingress)}</p></div>
<div class='src' style='left:980px;right:{M}px;bottom:56px'>{ATTRIBUTION}</div></div>"""


def s2_halet(k: Klubb, c: Halkort, d: dict) -> str:
    rad = d.get("kortrad") or c.slutrad or (c.rad[0] if c.rad else "")
    return f"""<div class='pg'>
<div class='abs' style='left:0;top:0;width:820px;height:1080px;background:var(--djup)'></div>
{hal_i_ruta(c.image, 70, 60, 680, 960)}
<div class='src ljus' style='left:70px;width:680px;bottom:24px;font-size:13px'>{ATTRIBUTION}</div>
{_huvud(k, c, 2, 920)}
<div class='abs' style='left:920px;right:{M}px;top:150px'>
 <div class='ey'>Hålet ni sponsrar</div>
 <div style='display:flex;align-items:flex-end;gap:44px;margin-top:18px'>
  <div style='font:400 230px/.8 var(--serif);letter-spacing:-.03em'>{c.hole}</div>
  <div style='padding-bottom:12px'><div style='font:400 44px/1.1 var(--serif)'>{e(c.rubrik)}</div>
   <div class='ey' style='margin-top:16px'>Par {c.par} · Index {c.index}</div></div></div>
 <div style='display:flex;gap:70px;margin-top:40px'>
  <div style='flex:1.25'><p class='p' style='font-size:26px'>{e(c.beskrivning)}</p>
   <div style='margin-top:34px;border-left:3px solid var(--glod-m);padding:4px 0 4px 26px'>
    <div class='ey' style='font-size:14px'>{e(c.rad_rubrik)}</div>
    <div style='font:italic 400 34px/1.25 var(--serif);margin-top:12px'>{e(rad)}</div></div></div>
  <div style='flex:1'>{_tees(c)}</div></div>
 {_strategi(c)}</div></div>"""


def _strategi(c: Halkort) -> str:
    if not (c.sakert and c.chansa):
        return ""
    kol = "".join(f"<div style='flex:1'><div class='ey' style='font-size:14px;color:var(--glas)'>{a}</div>"
                  f"<p class='p' style='font-size:21px;margin-top:12px'>{e(b)}</p></div>"
                  for a, b in (("Spela säkert", c.sakert), ("Ta chansen", c.chansa)))
    return (f"<div style='display:flex;gap:70px;margin-top:50px;padding-top:30px;"
            f"border-top:1px solid rgba(16,32,46,.16)'>{kol}</div>")


def s3_skylt(k: Klubb, c: Halkort, d: dict, qr_svg: str) -> str:
    siffra, forklaring = _uppskattning(k)
    sx, sy, sw, sh = 165, 110, 490, 700
    skylt = f"""
<div class='abs' style='left:{sx + 80}px;top:{sy + sh}px;width:22px;height:{H - sy - sh}px;background:#4A3C30'></div>
<div class='abs' style='left:{sx + sw - 102}px;top:{sy + sh}px;width:22px;height:{H - sy - sh}px;background:#4A3C30'></div>
<div class='abs' style='left:{sx}px;top:{sy}px;width:{sw}px;height:{sh}px;background:var(--sjo);padding:10px;display:flex;
 flex-direction:column;gap:8px;box-shadow:0 30px 60px rgba(16,32,46,.35)'>
 <div style='height:92px;background:var(--djup);display:flex;align-items:center;justify-content:center;
  font:400 38px/1 var(--serif);color:var(--kristall)'>[Ert företag]-hålet</div>
 <div style='flex:1;background:var(--djup);position:relative;overflow:hidden'>
  {hal_i_ruta(c.image, 10, 14, 230, 400, max_px=1400)}
  <div class='abs' style='left:258px;top:26px;font:400 112px/1 var(--serif);color:var(--kristall)'>{c.hole}</div>
  <div class='abs' style='left:262px;top:150px;font:600 12px/1 var(--sans);letter-spacing:.2em;color:var(--glod)'>PAR {c.par} · INDEX {c.index}</div>
  <div class='abs' style='left:262px;top:184px;right:16px;display:flex;flex-direction:column;gap:11px'>
   {''.join(f"<div style='display:flex;justify-content:space-between;font:500 15px/1 var(--sans);color:var(--kristall)'><span style='color:var(--is)'>{e(t)}</span>{m} m</div>" for t, m in c.tees)}</div></div>
 <div style='height:150px;background:var(--kristall);display:flex;align-items:center;justify-content:space-between;padding:0 22px'>
  <div><div style='font:600 11px/1 var(--sans);letter-spacing:.22em;color:var(--glas);margin-bottom:12px'>PRESENTERAS AV</div>
   {_logofalt(250, 82)}</div>
  <div style='text-align:center'><div style='width:92px;height:92px'>{qr_svg}</div>
   <div style='font:500 11px/1 var(--sans);color:var(--glas);margin-top:8px'>Hålguide</div></div></div></div>"""
    return f"""<div class='pg'>
<div class='abs' style='left:0;top:0;width:820px;height:1080px;background:linear-gradient(180deg,#DCE6E2 0%,#C9D6D0 100%)'></div>
{skylt}
<div class='abs note' style='left:44px;top:46px;font-size:14px'>Skylten vid tee, 70 × 100 cm. Er logotyp sitter på den nedre plattan.</div>
{_huvud(k, c, 3, 920)}
<div class='abs' style='left:920px;right:{M}px;top:150px'>
 <div class='ey'>Vid tee</div>
 <h1>Varje utslag börjar vid er skylt.</h1>
 <p class='lead'>Det är här golfarna stannar, väljer klubba och läser hålet. Ert namn står överst, er logotyp
 längst ner, och QR-koden tar dem vidare till hålets sida.</p>
 <div style='margin-top:56px;padding-top:34px;border-top:1px solid rgba(16,32,46,.18);display:flex;gap:40px;align-items:flex-end'>
  <div style='font:400 96px/.9 var(--serif);white-space:nowrap'>{siffra}</div>
  <div style='font:500 22px/1.35 var(--sans);padding-bottom:6px'>visningar vid tee per säsong<span class='tag'>Uppskattning</span></div></div>
 <p class='note' style='margin-top:22px;max-width:820px'>{forklaring}</p></div>
<div class='src' style='left:920px;right:{M}px;bottom:44px'>{ATTRIBUTION}</div></div>"""


def _mobil(k: Klubb, c: Halkort) -> str:
    """Hålets sida i mobilen (skiss)."""
    return f"""<div class='abs' style='left:0;top:0;width:380px;height:780px;border-radius:52px;background:#0B151E;padding:14px;
 box-shadow:0 30px 60px rgba(16,32,46,.3)'>
 <div style='position:relative;width:100%;height:100%;border-radius:40px;overflow:hidden;background:var(--djup)'>
  <div class='abs' style='left:26px;top:46px;font:600 12px/1 var(--sans);letter-spacing:.24em;color:var(--is)'>{e(k.namn.upper())}</div>
  <div class='abs' style='left:24px;top:72px;font:400 64px/1 var(--serif);color:var(--kristall)'>Hål {c.hole}</div>
  <div class='abs' style='left:26px;top:146px;font:600 12px/1 var(--sans);letter-spacing:.2em;color:var(--glod)'>PAR {c.par} · INDEX {c.index}</div>
  {hal_i_ruta(c.image, 20, 172, 312, 430, max_px=1400)}
  <div class='abs' style='left:22px;right:22px;top:620px;border-top:1px solid rgba(238,243,236,.25);padding-top:16px'>
   <div style='font:500 13px/1 var(--sans);color:var(--is);margin-bottom:10px'>Hålet presenteras av</div>
   {_logofalt(308, 70, 'var(--is)')}</div></div></div>"""


def _post(k: Klubb, c: Halkort) -> str:
    """Klubbens inlägg om hålet (skiss)."""
    konto = k.some.get("konto", k.mapp.name)
    return f"""<div class='abs' style='left:0;top:0;width:500px;background:#fff;box-shadow:0 30px 60px rgba(16,32,46,.25)'>
 <div style='display:flex;align-items:center;gap:12px;padding:14px 16px'>
  <img src='{k.logga("farg")}' style='width:36px;height:36px;border-radius:50%'>
  <div style='font:600 15px/1 var(--sans)'>{e(konto)}</div></div>
 <div style='position:relative;height:625px;background:var(--kristall)'>
  {hal_i_ruta(c.image, 14, 16, 250, 593, max_px=1400)}
  <div class='abs' style='left:280px;right:22px;top:70px'>
   <div style='font:600 11px/1 var(--sans);letter-spacing:.2em;color:var(--glod-m)'>HÅL FÖR HÅL</div>
   <div style='font:400 110px/.9 var(--serif);margin-top:18px'>{c.hole}</div>
   <div style='font:400 26px/1.15 var(--serif);margin-top:18px'>{e(c.rubrik)}</div>
   <div style='font:500 12px/1 var(--sans);color:var(--glas);margin:150px 0 10px'>Presenteras av</div>
   {_logofalt(198, 64)}</div></div>
 <div style='padding:14px 16px 18px;font:400 15px/1.45 var(--sans)'><b>{e(konto)}</b> Hål {c.hole}: {e(c.rubrik.lower())}.
  Hålet presenteras av [Ert företag].</div></div>"""


def s4_digitalt(k: Klubb, c: Halkort, d: dict) -> str:
    return f"""<div class='pg'>
{_huvud(k, c, 4)}
<div class='abs' style='left:{M}px;top:150px;width:720px'>
 <div class='ey'>I mobilen och i flödet</div>
 <h1>Hålet följer med hem.</h1>
 <p class='lead'>Golfarna planerar rundan i mobilen och minns den i flödet. På hålets sida och i klubbens
 inlägg är det ert företag som presenterar hålet.</p>
 <ul class='d' style='margin-top:44px'>
  <li>Hålets egen sida: hela hålet, längderna och er logotyp</li>
  <li>Inlägg om hålet på klubbens Instagram och Facebook</li>
  <li>Ett färdigt inlägg att dela i era egna kanaler</li></ul></div>
<div class='abs' style='left:960px;top:150px;width:380px;height:800px'>{_mobil(k, c)}</div>
<div class='abs' style='left:1380px;top:150px;width:500px;height:800px'>{_post(k, c)}</div>
<div class='abs note' style='left:960px;top:948px;width:380px'>Hålets sida i mobilen</div>
<div class='abs note' style='left:1380px;top:948px;width:420px'>Klubbens inlägg om hålet</div>
<div class='src' style='left:960px;right:{M}px;bottom:44px'>Skisser av format. {ATTRIBUTION}</div></div>"""


def s5_rapport(k: Klubb, c: Halkort, d: dict) -> str:
    siffra, _ = _uppskattning(k)
    rader = [("Tee-skylten", "Ronder × andel som spelar hålet", siffra, True),
             ("Hålets sida på webben", "Sidvisningar av hålets sida", "mäts", False),
             ("&nbsp;&nbsp;varav via QR-koden", "Visningar efter skanning vid tee", "mäts", False),
             ("Klubbens inlägg", "Visningar av inläggen om hålet", "mäts", False)]
    tabell = "".join(
        f"<div style='display:flex;justify-content:space-between;align-items:flex-start;padding:18px 0;border-top:1px solid #DDE5E1'>"
        f"<div><div style='font:500 19px/1.2 var(--sans)'>{a}{'<span class=tag>Uppskattning</span>' if u else ''}</div>"
        f"<div style='font:400 14px/1.3 var(--sans);color:#5B6E73;margin-top:6px'>{b}</div></div>"
        f"<div style='font:{'500 24px' if u else '400 16px'}/1.2 var(--sans);color:{'var(--djup)' if u else '#7A8B8F'}'>{v}</div></div>"
        for a, b, v, u in rader)
    rapport = f"""<div class='abs' style='left:110px;top:120px;width:600px;background:#fff;box-shadow:0 24px 50px rgba(16,32,46,.18)'>
 <div style='background:var(--djup);color:var(--kristall);padding:30px 34px 26px;display:flex;justify-content:space-between;align-items:center'>
  <div><div style='font:400 34px/1 var(--serif)'>[Ert företag]-hålet</div>
   <div style='font:400 14px/1 var(--sans);color:var(--is);margin-top:12px'>Hål {c.hole} · {e(k.namn)} · Säsong {k.sasong}</div></div>
  <img src='{k.logga("mork")}' style='width:64px;height:64px'></div>
 <div style='padding:10px 34px 30px;position:relative;height:640px'>
  <div style='display:flex;gap:26px;margin:16px 0 18px'>
   <div style='width:160px;height:250px;background:var(--djup);position:relative;border-radius:4px'>{hal_i_ruta(c.image, 8, 8, 144, 234, max_px=900)}</div>
   <div><div style='font:600 12px/1 var(--sans);letter-spacing:.2em;color:var(--glas)'>VISNINGAR PER KANAL</div>
    <div style='font:400 15px/1.5 var(--sans);color:#33454B;margin-top:14px;max-width:330px'>Varje kanal redovisas för sig.
    Siffrorna läggs aldrig ihop över kanaler, så ni ser exakt var hålet har synts.</div>
    <div style='margin-top:22px'>{_logofalt(220, 70)}</div></div></div>
  {tabell}</div></div>"""
    return f"""<div class='pg'>
<div class='abs' style='left:0;top:0;width:820px;height:1080px;background:#DCE6E2'></div>{rapport}
{_huvud(k, c, 5, 920)}
<div class='abs' style='left:920px;right:{M}px;top:150px'>
 <div class='ey'>Efter säsongen</div>
 <h1>Ni ser vad pengarna gav.</h1>
 <p class='lead'>När säsongen är slut får ni en rapport med hålet, er logotyp och hur många gånger de har
 visats, kanal för kanal. Svart på vitt, att visa för styrelsen eller spara till nästa år.</p>
 <p class='note' style='margin-top:40px;max-width:780px'><b>Visningar</b> är antal gånger hålet och er logotyp har
 visats, inte antal personer. Skylten vid tee är en uppskattning. Webb och inlägg mäts under säsongen.</p></div>
<div class='src' style='left:920px;right:{M}px;bottom:44px'>Skiss av rapporten. {ATTRIBUTION}</div></div>"""


def s6_erbjudande(k: Klubb, c: Halkort, d: dict, qr_svg: str, url: str) -> str:
    sp = k.sponsring
    pris = sp.get("pris_per_hal")
    prisruta = (f"<div style='font:400 64px/1 var(--serif)'>{kr(pris)}&nbsp;kr</div>"
                f"<div style='font:400 20px/1.4 var(--sans);color:var(--is);margin-top:14px'>{e(sp.get('pris_villkor', 'per år'))}</div>"
                if pris else "<div style='font:400 34px/1.2 var(--serif)'>Pris enligt överenskommelse</div>")
    kontakt = sp.get("kontakt") or k.web
    return f"""<div class='pg'>
{_huvud(k, c, 6, M, 760)}
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
  <div class='ey' style='font-size:14px'>Prata med kansliet</div>
  <div style='font:500 26px/1.4 var(--sans);margin-top:14px'>{e(kontakt)}</div></div></div>
<div class='abs dark' style='left:{W - 680}px;top:0;width:680px;height:1080px;background:var(--djup)'>
 <div class='abs' style='left:70px;top:110px'><div class='ey'>Pris för hål {c.hole}</div><div style='margin-top:26px'>{prisruta}</div></div>
 <div class='abs' style='left:70px;right:70px;top:360px;border-top:1px solid rgba(156,201,195,.3)'></div>
 {hal_i_ruta(c.image, 60, 410, 300, 560, 'left center', max_px=1400)}
 <div class='abs' style='left:400px;top:560px;width:210px'>
  <div style='width:210px;height:210px;background:var(--kristall);padding:16px'>{qr_svg}</div>
  <div style='font:500 17px/1.4 var(--sans);color:var(--is);margin-top:16px'>Se hål {c.hole}</div>
  <div style='font:400 13px/1.4 var(--sans);color:var(--is);opacity:.75;word-break:break-all'>{e(url.replace('https://', ''))}</div></div>
 <div class='src' style='left:70px;right:70px;bottom:44px;font-size:13px'>{ATTRIBUTION}</div></div>
<div class='abs' style='left:{M}px;bottom:52px;display:flex;align-items:center;gap:16px'>
 <img src='{k.logga("ljus")}' style='width:58px;height:58px'>
 <div style='font:400 15px/1.5 var(--sans);color:#5B6E73'>{e(k.namn)} · {e(k.web.replace('https://', ''))}<br>
 <span style='font-size:13px;opacity:.8'>Material: TACADA</span></div></div></div>"""


# ------------------------------------------------------------------ bygg
def sidor(k: Klubb, c: Halkort, prospekt: dict | None = None) -> tuple[list[str], bool]:
    """HTML för prospektets sidor (en sträng per sida) och om QR-koden är äkta."""
    d = prospekt or {}
    url = k.halsida(c.hole)
    qr_ljus, akta = qr(url, k.farger["djup"])
    return [s1_omslag(k, c, d), s2_halet(k, c, d), s3_skylt(k, c, d, qr_ljus), s4_digitalt(k, c, d),
            s5_rapport(k, c, d), s6_erbjudande(k, c, d, qr_ljus, url)], akta


def bygg(halkortfil: Path, ut: Path, wb: Webblasare, forhand: Path | None = None) -> dict:
    """En PDF för ett hål. forhand: mapp där varje sida också sparas som JPG."""
    halkortfil = Path(halkortfil)
    k = Klubb.from_dir(halkortfil.parent.parent)
    c = halkort_markerat(halkortfil)
    raw = yaml.safe_load(halkortfil.read_text(encoding="utf-8")) or {}
    d = {"kortrad": raw.get("kortrad"), **(raw.get("prospekt") or {})}
    s, akta = sidor(k, c, d)
    pdf = Path(ut) / f"{k.filnamn}_halsponsorprospekt_hal-{c.hole:02d}.pdf"
    wb.pdf(_sida(k, "".join(s)), W, H, pdf)
    bilder = []
    if forhand:
        from PIL import Image
        for i, sida in enumerate(s, 1):
            png = wb.png(_sida(k, sida), W, H, Path(forhand) / f"hal-{c.hole:02d}-s{i}.png")
            jpg = png.with_suffix(".jpg")
            Image.open(png).convert("RGB").save(jpg, quality=88)
            png.unlink()
            bilder.append(jpg)
    return {"hal": c.hole, "pdf": pdf, "qr_akta": akta, "sidor": bilder, "url": k.halsida(c.hole)}


def bygg_alla(filer: list[Path], ut: Path) -> list[dict]:
    """PDF per hål + översikt.jpg (alla sidor för första hålet och omslagen för alla hål)."""
    import tempfile

    ut = Path(ut)
    res = []
    with tempfile.TemporaryDirectory() as td, Webblasare() as wb:
        for f in filer:
            r = bygg(f, ut, wb, Path(td))
            print(f"  hål {r['hal']:>2}: {r['pdf']}" + ("" if r["qr_akta"] else "  (QR-PLATSHÅLLARE)"))
            res.append(r)
        if res:
            ref = next((r for r in res if r["hal"] == 14), res[0])
            kontaktark(ref["sidor"], ut / "oversikt-sidor.jpg", 2, 2400,
                       etiketter=[f"Hål {ref['hal']} · sida {i}" for i in range(1, SIDOR + 1)])
            kontaktark([r["sidor"][0] for r in res], ut / "oversikt-omslag.jpg", 4, 2400,
                       etiketter=[f"Hål {r['hal']}" for r in res])
            _stapla([ut / "oversikt-sidor.jpg", ut / "oversikt-omslag.jpg"], ut / "översikt.jpg")
    return res


def _stapla(bilder: list[Path], ut: Path) -> Path:
    from PIL import Image

    ims = [Image.open(b) for b in bilder]
    w = max(i.width for i in ims)
    ark = Image.new("RGB", (w, sum(i.height for i in ims)), "#E4EAE6")
    y = 0
    for i in ims:
        ark.paste(i, (0, y))
        y += i.height
    ark.save(ut, quality=86)
    for b in bilder:
        b.unlink()
    return ut
