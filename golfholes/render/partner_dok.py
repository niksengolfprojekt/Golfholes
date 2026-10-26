"""Partnerprogrammets dokument i A4/A3: försäljningsmanual (C), årsrapport (D), årskalender (E),
prislista och partneröversikt (F) och klubbens beslutsunderlag (den ekonomiska granskningen).

Allt läses ur golfholes.partnerprogram.Program. Årsrapporten läser säsongens data ur
partneröversikten (xlsx, golfholes.partnerprogram.logg) och skriver aldrig ett påhittat värde:
saknas en siffra står det att den fylls i.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from ..partnerprogram import HALSTATUS, Program, kr
from .klubbmaterial import ATTRIBUTION, css, e, hal_i_ruta

A4 = (794, 1123)
A3L = (1587, 1123)
A4L = (1123, 794)

DOK_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:#fff}
body{font:400 10.5pt/1.55 var(--sans);color:var(--djup);-webkit-print-color-adjust:exact;print-color-adjust:exact}
h1{font:400 30pt/1.08 var(--serif);letter-spacing:-.01em;margin:0 0 10pt;text-wrap:balance}
h2{font:400 19pt/1.15 var(--serif);margin:22pt 0 8pt;break-after:avoid;text-wrap:balance}
h3{font:600 11pt/1.3 var(--sans);margin:14pt 0 4pt;break-after:avoid}
p{margin:0 0 7pt;text-wrap:pretty}
.ey{font:600 8pt/1 var(--sans);letter-spacing:.2em;text-transform:uppercase;color:var(--glod-m);margin-bottom:8pt}
.lead{font:400 13pt/1.5 var(--sans);color:#2C3D44}
.liten{font-size:8.5pt;color:#5B6E73}
ul,ol{margin:0 0 8pt 16pt}
li{margin:0 0 4pt}
table{width:100%;border-collapse:collapse;margin:6pt 0 12pt;break-inside:auto}
th{font:600 7.5pt/1.2 var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--glas);text-align:left;
  padding:6pt 6pt 6pt 0;border-bottom:1.2pt solid var(--djup)}
td{padding:6pt 6pt 6pt 0;border-bottom:.6pt solid #CFDAD6;vertical-align:top}
tr{break-inside:avoid}
td.n,th.n{text-align:right;white-space:nowrap}
.ruta{background:var(--kristall);padding:12pt 14pt;border-radius:3pt;margin:8pt 0 12pt;break-inside:avoid}
.ruta.mork{background:var(--djup);color:var(--kristall)}
.ruta.mork .ey{color:var(--glod)}
.mejl{border-left:2.5pt solid var(--glas);padding:4pt 0 4pt 12pt;margin:6pt 0 14pt;break-inside:avoid}
.mejl .amne{font:600 10pt/1.4 var(--sans);margin-bottom:6pt}
.tag{display:inline-block;font:600 6.5pt/1 var(--sans);letter-spacing:.14em;text-transform:uppercase;padding:3pt 5pt;
  border:.8pt solid currentColor;border-radius:2pt;vertical-align:1pt;margin-left:4pt}
.t-matt{color:var(--glas)}.t-upp{color:var(--glod-m)}.t-lev{color:#4F6268}
.sid{break-before:page}
@page omslag{margin:0}
.omslag{page:omslag;width:210mm;height:297mm;background:var(--djup);color:var(--kristall);position:relative;break-after:page;overflow:hidden}
.hall{break-inside:avoid}
.tat td{padding:3.5pt 6pt 3.5pt 0}
.kol2{columns:2;column-gap:18pt}
.kol2 > *{break-inside:avoid}
"""


def html(prog: Program, kropp: str, sida: str = "A4", marg: str = "20mm 18mm 22mm") -> str:
    return (f"<!doctype html><html lang='sv'><head><meta charset='utf-8'><style>{css(prog.klubb)}{DOK_CSS}"
            f"@page{{size:{sida};margin:{marg}}}</style></head><body>{kropp}</body></html>")


def pdf(wb, sida_html: str, ut: Path, bredd_mm: float = 210, hojd_mm: float = 297, sidfot: str = "") -> Path:
    """PDF med sidbrytningar (CSS @page). sidfot: text längst ner på varje sida + sidnummer."""
    ut = Path(ut)
    ut.parent.mkdir(parents=True, exist_ok=True)
    pg = wb._b.new_page()
    pg.set_content(sida_html, wait_until="load")
    pg.evaluate("document.fonts.ready")
    mall = (f"<div style='font:7px Arial;color:#7A8B8F;width:100%;padding:0 18mm;display:flex;justify-content:space-between'>"
            f"<span>{e(sidfot)}</span><span><span class='pageNumber'></span></span></div>") if sidfot else "<span></span>"
    pg.pdf(path=str(ut), width=f"{bredd_mm}mm", height=f"{hojd_mm}mm", print_background=True, prefer_css_page_size=True,
           display_header_footer=bool(sidfot), header_template="<span></span>", footer_template=mall)
    pg.close()
    return ut


def _kontakt(prog: Program) -> str:
    c = prog.kontakt()
    return f"{c['namn']}, {c['epost']}, {c['telefon']}"


def _omslag(prog: Program, ey: str, rubrik: str, ingress: str, h_nr: list[int] | None = None) -> str:
    k = prog.klubb
    hal = [h for n in (h_nr or k.sponsring.get("omslagshal") or []) for h in prog.hal if h.nr == n and h.bild]
    bilder = "".join(hal_i_ruta(h.bild, 420 + i * 120, 80, 110, 520, max_px=900) for i, h in enumerate(hal[:3]))
    return f"""<div class='omslag'>
{bilder}
<div style='position:absolute;left:68px;top:70px;display:flex;align-items:center;gap:14px'>
 <img src='{k.logga("mork")}' style='width:54px;height:54px'>
 <div style='font:600 9px/1.5 var(--sans);letter-spacing:.24em;text-transform:uppercase;color:var(--is)'>{e(k.namn)}<br>
 <span style='color:var(--glod)'>{e(k.bana)}</span></div></div>
<div style='position:absolute;left:68px;right:68px;top:640px'>
 <div class='ey' style='color:var(--glod)'>{e(ey)}</div>
 <div style='font:400 40pt/1.05 var(--serif);margin-top:10pt;max-width:560px'>{e(rubrik)}</div>
 <div style='font:400 12.5pt/1.5 var(--sans);color:#D3E3E0;margin-top:16pt;max-width:520px'>{e(ingress)}</div></div>
<div style='position:absolute;left:68px;right:68px;bottom:56px;font:400 7.5pt/1.4 var(--sans);color:var(--is);opacity:.8'>
 Partnerprogram {prog.sasong} · Material: TACADA · {ATTRIBUTION}</div></div>"""


def _prisrad(p: dict) -> str:
    if p.get("prisenhet") == "offert" or not p.get("pris"):
        return "Offert"
    fran = "från " if p["id"] in ("tavling", "huvudpartner") else ""
    enhet = "" if p.get("prisenhet") == "per år" else f" {p.get('prisenhet')}"
    return f"{fran}{kr(p['pris'])} kr{enhet}"


# ------------------------------------------------------------------ F: prislista
def prislista(prog: Program) -> str:
    v = prog.villkor
    rader = ""
    for niva, prod in prog.per_niva().items():
        rader += f"</tbody><tbody style='break-inside:avoid'><tr><td colspan='3' style='border:0;padding-top:14pt'><b style='font:400 15pt/1 var(--serif)'>{e(prog.nivaer[niva]['namn'])}</b></td></tr>"
        for p in prod:
            ingar = "; ".join(x["rubrik"] + (" (under utveckling)" if x.get("senare") else "") for x in p["ingar"])
            if p["id"] == "premiumhal":
                ingar = "Allt i hålsponsorskapet + hålets extra yta: " + "; ".join(
                    f"hål {n}: {x['yta'].lower()}" for n, x in (prog.cfg.get("premiumhal") or {}).items())
            start = f"{kr(p['startkostnad'])} kr" if p.get("startkostnad") else "–"
            rader += (f"<tr><td style='width:30%'><b style='font-weight:600'>{e(p['namn'])}</b><br><span class='liten'>{e(p['exklusivt'])}</span></td>"
                      f"<td class='liten' style='color:#33454B'>{e(ingar)}</td>"
                      f"<td class='n' style='width:17%'><b style='font-weight:600'>{_prisrad(p)}</b><br><span class='liten'>start {start}</span></td></tr>")
    tillagg = "".join(f"<li><b style='font-weight:600'>{e(p['namn'])}</b> ({e(p['plats'])}): {_prisrad(p)}. {e(p.get('forutsattning', ''))}</li>"
                      for p in prog.med_status("tillagg"))
    k = prog.klubb
    return f"""
<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:18pt'>
 <div style='display:flex;align-items:center;gap:12px'><img src='{k.logga("ljus")}' style='width:46px;height:46px'>
 <div style='font:600 7.5pt/1.5 var(--sans);letter-spacing:.22em;text-transform:uppercase;color:var(--glas)'>{e(k.namn)}<br>Partnerprogram {prog.sasong}</div></div>
 <div class='liten'>Förslag {dt.date.today().strftime('%Y-%m-%d')} · klubben fastställer priserna</div></div>
<h1>Prislista {prog.sasong}</h1>
<p class='lead'>Alla priser gäller per år om inget annat står. Varje produkt kan köpas för sig.</p>
<table><tbody><tr><th>Produkt</th><th>Det här ingår</th><th class='n'>Pris</th></tr>{rader}</tbody></table>
<h3>Även på förfrågan</h3><ul class='liten' style='color:#33454B'>{tillagg}</ul>
<div class='ruta' style='margin-top:14pt'>
 <h3 style='margin-top:0'>Avtal och villkor</h3>
 <ul style='margin-bottom:0'>
  <li><b>Avtalsperiod:</b> ett eller tre år. {e(v['treaarsfordel'])}</li>
  <li><b>Startkostnad:</b> {e(v['startkostnad_text'])}</li>
  <li><b>Ensamrätt:</b> en partner per hål och per plats. Branschskydd ingår bara för huvudpartnern.</li>
  <li><b>Kombinationer:</b> en huvudpartner med eget hål eller range får en partnervecka, inte två. En yta säljs aldrig två gånger.</li>
  <li><b>Befintliga partners:</b> {e(v['forstahandsratt'])}</li>
  <li><b>Betalning:</b> {e(v['betalning'])}</li>
  <li><b>Logotyp:</b> {e(v['logotyp'])} {e(v['godkannande'])}</li>
  <li><b>Flygfilmen:</b> {e(v['flygfilm'])}</li></ul></div>
<p class='liten'>Kontakt: {e(_kontakt(prog))}</p>"""


# ------------------------------------------------------------------ F: partneröversikt (sålt, ledigt, reserverat)
def oversikt(prog: Program, status_ovr: dict, partners: dict, idag: str) -> str:
    farg = {"ledig": "var(--glas)", "bokad": "var(--glod-m)", "såld": "var(--djup)"}
    hal_rader = ""
    for h in prog.hal:
        p = partners.get(f"hal-{h.nr:02d}") or {}
        hal_rader += (f"<tr style='font-size:9pt'><td style='width:7%;padding:3pt 0'><b style='font:400 12pt/1 var(--serif)'>{h.nr}</b></td><td>Par {h.par}"
                      f"{' · <b style=\"color:var(--glod-m);font-weight:600\">premium</b>' if h.premium else ''}</td>"
                      f"<td class='n'>{kr(h.pris)} kr</td>"
                      f"<td style='color:{farg[h.status]};font-weight:600'>{HALSTATUS[h.status]}</td>"
                      f"<td>{e(p.get('foretag', ''))}</td><td>{e(p.get('avtal_till', ''))}</td><td style='width:12%'></td></tr>")
    ovr_rader = ""
    for pr in prog.aktiva():
        if pr["niva"] == "hal" or pr.get("max") != 1:
            continue
        st = status_ovr.get(pr["id"], "ledig")
        p = partners.get(pr["id"]) or {}
        ovr_rader += (f"<tr><td colspan='2'><b style='font-weight:600'>{e(pr['namn'])}</b></td><td class='n'>{_prisrad(pr)}</td>"
                      f"<td style='color:{farg[st]};font-weight:600'>{HALSTATUS[st]}</td><td>{e(p.get('foretag', ''))}</td>"
                      f"<td>{e(p.get('avtal_till', ''))}</td><td></td></tr>")
    salda = sum(h.status == "såld" for h in prog.hal)
    res = sum(h.status == "bokad" for h in prog.hal)
    intakt = sum(h.pris for h in prog.hal if h.status == "såld")
    return f"""
<div style='display:flex;justify-content:space-between;align-items:flex-end'>
 <div><div class='ey'>Internt · klubbchefens översikt</div><h1 style='margin:0'>Partneröversikt {prog.sasong}</h1></div>
 <div class='liten' style='text-align:right'>Läget {e(idag)}<br>Sålt {salda} · reserverat {res} · ledigt {len(prog.hal) - salda - res} hål
 <br>Sålda hål: {kr(intakt)} kr</div></div>
<table class='tat' style='margin-top:12pt'><tr><th>Hål</th><th>Typ</th><th class='n'>Pris</th><th>Status</th><th>Företag</th><th>Avtal till</th><th>Nästa steg</th></tr>
{hal_rader}<tr><td colspan='7' style='border:0;padding-top:12pt'><b style='font:400 13pt/1 var(--serif)'>Verksamhet och huvudpartner</b></td></tr>{ovr_rader}</table>
<p class='liten'>{e(str(prog.cfg.get('idag', {}).get('salda_hal', '')))} hål har en partner 2026 till dagens pris. De har förstahandsrätt till sitt hål till {e(str((prog.cfg.get('befintliga') or {}).get('sista_dag', '')))} och står som lediga tills avtalet för {prog.sasong} är skrivet.<br>Status ändras i partneröversikten (Excel) eller i klubb.yaml. Reserverat = muntligt ja, avtal inte påskrivet; hålls högst 14 dagar.</p>"""


# ------------------------------------------------------------------ E: årskalender
MANADER = ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "Maj", "Jun", "Jul", "Aug", "Sep", "Okt"]


def kalender(prog: Program) -> str:
    s = prog.sasong
    rader = [
        ("Försäljning", {0: "Säljstart. Förnyelser först", 1: "Avtal skrivs", 2: "Avtal skrivs", 3: "Sista dag för skylt i april"}),
        ("Skyltar och platser", {3: "Logotyper in. TACADA levererar allt digitalt", 4: "Tryck av plattor", 5: "Allt upp före första start", 11: "Banderoller och flaggor in"}),
        ("Inlägg", {2: "Nya partners presenteras", 3: "Nya partners presenteras", 4: "Nya partners presenteras", 5: "Säsongsstart med partners",
                    6: "Veckans partner varje måndag", 7: "Veckans partner", 8: "Veckans partner", 9: "Veckans partner", 10: "Veckans partner",
                    11: "Tack till partners"}),
        ("Partnerveckor", {5: "v. 18 start", 6: "Plattan byts måndag", 7: "", 8: "Golfveckan v. 30", 9: "", 10: "v. 41 sista"}),
        ("Aktiviteter", {4: "Tävlingsprogram + partners", 5: "Säsongsöppningen", 8: "Golfveckan", 9: "Klubbmästerskapen",
                         10: "Partnertävlingen", 11: "Säsongsavslutningen"}),
        ("Statistik", {6: "Ronder per månad", 7: "Ronder", 8: "Ronder", 9: "Ronder", 10: "Ronder", 11: "Ronder + export"}),
        ("Rapport och förnyelse", {11: "Årsrapporterna klara", 0: "Förnyelsesamtal (förra året)"}),
    ]
    ar = lambda i: s - 1 if i < 2 else s
    huvud = "".join(f"<th style='text-align:center'>{m}<br><span style='font-weight:400;letter-spacing:0'>{ar(i)}</span></th>" for i, m in enumerate(MANADER))
    kropp = ""
    for namn, celler in rader:
        kropp += f"<tr><td style='font-weight:600;width:11%'>{e(namn)}</td>"
        for i in range(12):
            t = celler.get(i)
            bg = "background:var(--kristall);" if t is not None else ""
            kropp += f"<td style='{bg}font-size:8pt;line-height:1.3;border-left:.6pt solid #fff;padding:6pt 4pt'>{e(t or '')}</td>"
        kropp += "</tr>"
    v = prog.partnerveckor()
    rad = [f"<tr><td>v. {w}</td><td>{e(n)}</td><td></td></tr>" for w, (_, n) in v["plan"].items()]
    halv = (len(rad) + 1) // 2
    plan = "".join(f"<table style='font-size:8pt;margin:0'><tr><th>Vecka</th><th>Partner</th><th>Klar</th></tr>{''.join(d)}</table>"
                   for d in (rad[:halv], rad[halv:]))
    ytor = "".join(f"<li><b>{e(y['namn'])}</b> ({y['tid_min']} min): {e(y['text'])}</li>" for y in prog.veckoytor())
    tid = prog.klubbens_tid(len(prog.hal) + 4)
    return f"""
<div style='display:flex;justify-content:space-between;align-items:flex-end'>
 <div><div class='ey'>Internt · leveransplan</div><h1 style='margin:0'>Året runt med partnerprogrammet</h1></div>
 <div class='liten' style='text-align:right'>{e(prog.klubb.namn)} · säsongen {s}</div></div>
<table style='margin-top:14pt;table-layout:fixed'><tr><th style='width:11%'></th>{huvud}</tr>{kropp}</table>
<div style='display:flex;gap:24pt'>
 <div style='flex:1.1'>
  <h3>Veckorutinen under partnerveckorna</h3><ul class='liten' style='color:#33454B'>{ytor}</ul>
  <h3>Vem gör vad</h3>
  <ul class='liten' style='color:#33454B'>
   <li><b>Klubbchefen:</b> säljer, skriver avtal, för partneröversikten, för förnyelsesamtalen.</li>
   {"<li><b>Receptionen:</b> byter plattan i entréskylten måndag morgon och mejlar ett foto.</li>" if (prog.cfg.get("partnerveckor") or {}).get("entreskylt") else ""}
   <li><b>Banpersonalen:</b> sätter upp skyltar, banderoller och flaggor i april och tar in dem i oktober.</li>
   <li><b>TACADA:</b> tar fram allt digitalt material och levererar det färdigt i ett paket inför säsongen: plattornas tryckfiler, hålsidorna, inläggen och veckans partner på startsidan. Årsrapporterna sammanställs automatiskt efter säsongen.</li>
   <li><b>Klubben och partnern:</b> formar partnerveckan tillsammans, till exempel med ett erbjudande till medlemmarna eller en träff på klubben.</li></ul>
  <div class='ruta'><b>Klubbens arbetstid:</b> ungefär {round(tid)} timmar per år med alla 18 hål och fyra verksamhetspartners sålda,
  eller cirka {str(round(tid / (len(prog.hal) + 4), 1)).replace('.', ',')} timmar per avtal. Det mesta är säljmöten och förnyelsesamtal.</div></div>
 <div style='flex:.9'>
  <h3>Partnerveckor {s} (förslag)</h3>
  <p class='liten'>Veckorna delas ut i den ordning avtalen skrivs. Förslaget nedan följer hålens ordning.</p>
  <div style='display:flex;gap:14pt'>{plan}</div></div></div>"""


# ------------------------------------------------------------------ beslutsunderlag (ekonomisk granskning)
def beslutsunderlag(prog: Program) -> str:
    sc = "".join(f"<tr><td>{e(r['text'])}</td><td class='n'>{kr(r['summa'])} kr</td><td class='liten'>{'nuläget' if r.get('idag') else 'räkneexempel'}</td></tr>"
                 for r in prog.scenarier())
    mod = "".join(f"<tr><td>{e(m['namn'])}{' <b>(i materialet)</b>' if m['vald'] else ''}</td><td class='n'>{kr(m['halpris'])} kr</td>"
                  f"<td class='n'>{kr(m['premiumpris'])} kr</td><td class='n'>{kr(m['summa'])} kr</td></tr>" for m in prog.modeller())
    trappa = prog.befintliga_trappa()
    idag = prog.cfg.get("idag") or {}
    ek = "".join(f"<tr><td>{e(r['namn'])}</td><td class='n'>{_prisrad(prog.produkter[r['id']])}</td>"
                 f"<td class='n'>{kr(r['kostnad']) + ' kr' if r['kostnad'] is not None else '–'}</td><td class='n'>{r['tid_h']} h</td>"
                 f"<td class='n'>{kr(r['netto']) + ' kr' if r['netto'] else '–'}</td><td class='liten'>{e(r['kostnad_text'])}</td></tr>"
                 for r in prog.produktekonomi())
    hp = prog.helt_program()
    hp_rader = "".join(f"<tr><td>{e(n)}</td><td class='n'>{kr(b)} kr</td></tr>" for n, b in hp["ovrigt"])
    fd = prog.foretagsdag(12)
    r, kalla = prog.ronder()
    besluten = beslut(prog)
    b_rader = "".join(f"<tr><td style='width:4%'>{i}</td><td><b style='font-weight:600'>{e(a)}</b><br><span class='liten' style='color:#33454B'>{e(b)}</span></td>"
                      f"<td class='liten' style='width:28%'>{e(c)}</td></tr>" for i, (a, b, c) in enumerate(besluten, 1))
    kontroller = "".join(f"<li>{e(t)}</li>" for niva, t in prog.kontroller() if niva != "stopp")
    return f"""{_omslag(prog, 'Underlag för klubbens beslut', 'Partnerprogram ' + str(prog.sasong) + ': ekonomi och beslut',
                     'Vad programmet kan ge, vad det kostar klubben i pengar och tid, och vilka beslut som behövs innan försäljningen börjar.')}
<h1>Det korta svaret</h1>
<p class='lead'>Idag ger hålsponsringen {kr(idag.get('salda_hal', 0) * idag.get('pris', 0))} kr om året från {idag.get('salda_hal', 0)} av {len(prog.hal)} hål.
Det nya hålsponsorskapet innehåller tio delar i stället för två, och priset höjs därefter. Hela erbjudandet sålt en gång är
{kr(hp['summa'])} kr, men det är ett räkneexempel, inte en prognos.</p>
<div class='ruta mork'><div class='ey'>Det obekväma först</div>
<p style='margin:0'>En dubblering av priset för dagens sju hålsponsorer är den största risken i programmet. Utan en övergång kan
klubben tappa partners som betalat i flera år. Förslaget är en trappa med treårsavtal ({' / '.join(kr(t) for t in trappa)} kr) och
förstahandsrätt till sitt hål till {e((prog.cfg.get('befintliga') or {}).get('sista_dag', ''))}. Den andra risken är tid: programmet
kräver säljmöten. Materialet kommer färdigt från TACADA. Klubbens kontakter och säljmöten gör resten.</p></div>

<h2>Räkneexempel: hålsponsringen</h2>
<table><tr><th>Exempel</th><th class='n'>Per år</th><th></th></tr>{sc}</table>
<h3>Två prismodeller, alla {len(prog.hal)} hål sålda</h3>
<table><tr><th>Modell</th><th class='n'>Vanligt hål</th><th class='n'>Premiumhål</th><th class='n'>Alla sålda</th></tr>{mod}</table>
<p class='hall'><b>Rekommendation:</b> två priser. Skillnaden i intäkt är liten ({kr(prog.modeller()[0]['summa'] - prog.modeller()[1]['summa'])} kr), men
premiumhålen ger klubbchefen något att erbjuda den som vill ha det bästa, och de har en verklig extra yta. Ett enda pris är
enklare att säga. Båda fungerar; det viktiga är att klubben väljer en och håller fast vid den. 25 000 kr för alla hål (TACADA:s
tidigare förslag) ger mest på papperet men är svårast att motivera för dagens sponsorer.
Befintliga hålsponsorer i trappan: {idag.get('salda_hal', 0)} hål × {kr(trappa[0]) if trappa else '–'} kr = {kr(idag.get('salda_hal', 0) * (trappa[0] if trappa else 0))} kr år 1.</p>

<h2>Varje produkt: pris, kostnad och arbete</h2>
<p>Kostnaden är klubbens egen utgift per år (tryck, skyltar, självkostnad). Tiden är klubbens arbete per avtal och år, utan
säljmötet. TACADA:s material ingår i klubbens avtal med TACADA.</p>
<table><tr><th>Produkt</th><th class='n'>Pris</th><th class='n'>Kostnad</th><th class='n'>Tid</th><th class='n'>Kvar</th><th>Kostnaden består av</th></tr>{ek}</table>
<h3>Ändringar mot arbetsförslaget</h3>
<ul>
 <li><b>Pay &amp; Play-partner: 12 500 kr i stället för 20 000.</b> Banan har betydligt färre ronder än stora banan. Samma pris som
 ett hål går inte att försvara inför en företagare som räknar.</li>
 <li><b>Puttinggreenpartner: 12 500 kr i stället för 15 000.</b> Ytan passeras av nästan alla men är liten. Flaggorna är det som syns.</li>
 <li><b>Digital klubbhuspartner: vilande.</b> Klubben har ingen bekräftad skärm. Produkten säljs först när skärmen finns
 (ca 6 000–9 000 kr för skärm och mediaspelare).</li>
 <li><b>Juniorpartner: 10 000 kr, men bara om tröjorna redan köps.</b> Annars äter tröjorna upp intäkten.</li>
 <li><b>Första tee och hole-in-one-tavlan</b> är inte längre egna tillval. De är premiumhålens extra yta, så att samma yta inte säljs två gånger.</li>
 <li><b>Partnerveckan</b> är digital: hålets inlägg den veckan och partnern på hemsidans startsida. Ingen skylt att byta, inget veckoarbete för klubben.</li>
 <li><b>Företagsdag:</b> räknemall i stället för fast pris. Exempel: {fd['deltagare']} gäster, självkostnad {kr(fd['sjalvkostnad'])} kr,
 pris {kr(fd['pris'])} kr (ca {kr(fd['per_person'])} kr per gäst).</li></ul>

<h2>Hela erbjudandet sålt en gång (räkneexempel)</h2>
<table><tr><th>Del</th><th class='n'>Per år</th></tr><tr><td>Alla {len(prog.hal)} hål</td><td class='n'>{kr(hp['hal'])} kr</td></tr>{hp_rader}
<tr><td><b>Summa</b></td><td class='n'><b>{kr(hp['summa'])} kr</b></td></tr></table>
<p class='liten'>Ingen klubb säljer allt första året. Exemplet visar taket, inte målet.</p>

<h2>Exponering: vad som får sägas</h2>
<ul>
 <li>Skylten vid tee räknas som <b>passager</b> = ronder × andelen ronder som spelar hålet. Här: ≈ {kr(round(r, -2))} per hål och år
 ({e(kalla)}). Det är en uppskattning och kallas alltid så. Det är inte antal personer.</li>
 <li>Hemsida, QR-kod och inlägg <b>mäts</b> och redovisas som de är, kanal för kanal. Siffror läggs aldrig ihop till ett större tal.</li>
 <li>Flygfilmen och fler digitala kanaler säljs inte som levererade förrän de finns.</li>
 <li>Inga löften om fler kunder, mer försäljning eller avkastning för partnern.</li></ul>
<p class='liten'>Ronderna ska bytas mot 2025 års siffra från klubbens bokningssystem innan materialet används externt.</p>

<h2 class='sid'>Beslut som behövs innan försäljningen börjar</h2>
<table><tr><th></th><th>Beslut</th><th>Förslag</th></tr>{b_rader}</table>
<h3>Att bekräfta</h3><ul class='liten' style='color:#33454B'>{kontroller}</ul>"""


def beslut(prog: Program) -> list[tuple[str, str, str]]:
    """(beslut, varför, förslag) – det klubben (och TACADA) måste ta ställning till."""
    idag = prog.cfg.get("idag") or {}
    trappa = prog.befintliga_trappa()
    return [
        ("Prismodell för hålen", "Två priser (20 000 / 25 000 för premiumhål) eller ett pris för alla.", "Två priser."),
        ("Premiumhål", "Hål 1 (första tee) och 17 (signaturhålet) har en extra yta. Hål 18 kan bli premium om greenen syns från klubbhuset.",
         "Hål 1 och 17. Hål 18 om klubben bekräftar."),
        ("Dagens sponsorer", f"{idag.get('salda_hal', 0)} hål till {kr(idag.get('pris', 0))} kr. Vilka hål och vilka företag?",
         f"Trappa {' / '.join(kr(t) for t in trappa)} kr med treårsavtal och förstahandsrätt."),
        ("Övriga produkters priser", "Range, puttinggreen, Pay & Play, junior, tävling, huvudpartner.", "Enligt prislistan."),
        ("Startkostnad vid ettårsavtal", "Täcker sponsorplatta och tryck. Gör treårsavtal mer attraktiva.", "2 500 kr (range 4 000 kr)."),
        ("Moms", "Om priserna anges med eller utan moms, och hur klubben momsredovisar sponsring.", "Klubbens revisor avgör. Materialet skriver inget om moms."),
        ("Ronder 2025", "Underlaget för skylten vid tee. Idag används 2020 års siffra.", "Klubben tar fram siffran ur bokningssystemet."),
        ("Klubbhusskärm", "Finns en skärm där gäster samlas? Utan skärm är skärmpartnern vilande.", "Vilande tills skärmen finns."),
        ("Juniortröjor och bilder", "Köper klubben tröjor ändå? Samtycke från föräldrar för lagbilder.", "Bekräftas av juniorledaren."),
        ("Kiosken vid nian", "Är den öppen 2027?", "Tillägg bara om den är öppen."),
        ("Huvudpartnerns branschskydd", "Ger huvudpartnern ensamrätt i sin bransch bland klubbens partners.", "Ja, bara för huvudpartnern."),
        ("Vem säljer", "Klubbchefen eller någon i styrelsen med kontaktnät.", "Klubbchefen, med styrelsen som dörröppnare."),
        ("TACADA:s del", "Sponsorplattornas tryckoriginal, loggan på hålsidorna, inläggen, veckans partner på startsidan och "
         "årsrapporterna varje säsong. Fysiska skyltar och plattor är tillägg enligt TACADA:s prislista, med olika pris med och utan fäste.",
         "Ingår i referensavtalet under avtalets tre år (Erics beslut 2026-10-26). Därefter enligt TACADA:s prislista."),
        ("Exempelföretaget", "Materialet visar Nordvik (påhittat). Emtec kan visas bara med Emtecs skriftliga tillstånd.", "Nordvik tills tillstånd finns."),
    ]


# ------------------------------------------------------------------ C: försäljningsmanual
def manual(prog: Program) -> str:
    k = prog.klubb
    c = prog.kontakt()
    trappa = prog.befintliga_trappa()
    idag = prog.cfg.get("idag") or {}
    hs = prog.produkter["halsponsor"]
    passar = "".join(
        f"<tr><td style='width:24%'><b style='font-weight:600'>{e(p['namn'])}</b><br><span class='liten'>{_prisrad(p)}</span></td>"
        f"<td>{'<br>'.join(e(x) for x in p.get('passar') or [])}</td><td class='liten' style='color:#33454B;width:38%'>{e(p.get('varfor', ''))}</td></tr>"
        for p in prog.aktiva())
    fd = prog.foretagsdag(12)
    fdk = prog.cfg.get("foretagsdag") or {}
    stege = [p for p in prog.aktiva() if p.get("pris") and p["niva"] == "verksamhet"]
    stege.sort(key=lambda p: p["pris"])
    stege_txt = "".join(f"<li><b>{e(p['namn'])}</b> ({_prisrad(p)}): {e(p['rubrik'].lower())}.</li>" for p in stege)
    sign = f"{c['namn']}<br>{e(k.namn)}<br>{e(c['telefon'])} · {e(c['epost'])}"
    return f"""{_omslag(prog, 'Internt · klubbchefens manual', 'Så säljer vi partnerskapen', 'Vilka företag som passar vad, hur mötet går till, vad man säger när någon tvekar och hur man håller kvar de partners man har.')}
<h1>Innan du börjar</h1>
<p class='lead'>Det här är ingen manus att läsa högt. Det är ett stöd för att ta ett säljmöte med gott samvete: du säljer något
som håller, till ett pris som går att förklara, och du lovar aldrig mer än klubben kan leverera.</p>
<div class='ruta'><b>Tre saker att komma ihåg.</b>
<ol style='margin:6pt 0 0 14pt'><li>Hålet först. Allt annat är ett komplement.</li>
<li>Sälj värdet, aldrig avkastningen. Vi lovar synlighet och ett genomfört år, inte nya kunder.</li>
<li>Varje samtal slutar med ett datum för nästa steg.</li></ol></div>
<h2>Programmet på en sida</h2>
<table><tr><th>Produkt</th><th>Passar</th><th>Varför de köper</th></tr>{passar}</table>

<h2 class='sid'>Vem du ska ringa</h2>
<p>Börja med de varmaste kontakterna. En medlem som äger ett företag är lättare att boka än ett företag som aldrig hört talas
om klubben.</p>
<ol>
 <li><b>Dagens {idag.get('salda_hal', 0)} hålsponsorer.</b> Före alla andra, och före {e((prog.cfg.get('befintliga') or {}).get('sista_dag', '30 november'))}.</li>
 <li><b>Medlemmar som driver företag.</b> Fråga styrelsen om tio namn var. De är redan stolta över klubben.</li>
 <li><b>Företag som redan spelar företagsgolf</b> eller bokar greenfee för kunder.</li>
 <li><b>Lokala branscher som lever på förtroende:</b> bygg, el och VVS, bil, bank och försäkring, mäklare, redovisning,
 tandvård, IT och konsulter. De vill synas där människor i Växjö umgås, inte i ett flöde.</li>
 <li><b>Företag som sponsrar annan idrott</b> i kommunen. De har budget och vet hur sponsring fungerar.</li></ol>
<p class='liten'>Ring inte två företag i samma bransch om samma hål samma vecka. Om båda vill ha det: först till avtal.</p>

<h2>Så presenterar du erbjudandet</h2>
<p>Använd huvudpresentationen på surfplattan eller skicka PDF:en efter mötet, aldrig före. Ordningen:</p>
<ol>
 <li><b>Klubben</b> (sida 2–4): vilka som spelar här, hur ofta, och varför det är en bra plats att synas.</li>
 <li><b>Hålet</b> (sida 6–8): visa exemplet med skylten, låt dem se hålets sida i mobilen.</li>
 <li><b>Partnerveckan och rapporten</b> (sida 9–11): det här är det som skiljer det nya från det gamla.</li>
 <li><b>Välj hål</b> (sida 15): låt dem peka. Det hål de pekar på är det de köper.</li>
 <li><b>Priset sist</b> (sida 14). Säg det utan att be om ursäkt.</li></ol>

<h2>Så öppnar du mötet</h2>
<div class='mejl'><p>”Tack för att ni tog er tid. Jag tänkte inte hålla någon dragning om golf. Jag vill visa vad det innebär att ha
ett eget hål hos oss från nästa säsong, och sedan höra vad som är viktigt för er. Passar det att vi tar en halvtimme?”</p></div>
<p>Fråga sedan, och lyssna mer än du pratar:</p>
<ul>
 <li>Vilka är era kunder, och var träffar ni dem i dag?</li>
 <li>Har ni sponsrat något tidigare? Vad var bra, vad saknades?</li>
 <li>Bjuder ni kunder eller personal på något under året?</li>
 <li>Vem mer på företaget behöver vara med och tycka till?</li></ul>

<div class='hall'><h2>Samtalets struktur (30 minuter)</h2>
<table><tr><th>Minut</th><th>Vad</th><th>Mål</th></tr>
<tr><td>0–5</td><td>Öppning och syfte</td><td>De vet vad mötet handlar om och hur lång tid det tar.</td></tr>
<tr><td>5–12</td><td>Frågor om deras kunder och mål</td><td>Du vet vilken produkt som passar.</td></tr>
<tr><td>12–22</td><td>Visa hålet, partnerveckan, rapporten</td><td>De ser sitt namn på ett hål.</td></tr>
<tr><td>22–27</td><td>Förslag och pris</td><td>Ett konkret förslag: ett hål, ett pris, ett eller tre år.</td></tr>
<tr><td>27–30</td><td>Nästa steg</td><td>Ett datum. Reservera hålet i högst 14 dagar.</td></tr></table></div>

<h2>Värdet, utan löften</h2>
<p>Företagare räknar. Ge dem siffror som håller, och kalla uppskattningar för uppskattningar.</p>
<table><tr><th>Säg</th><th>Säg aldrig</th></tr>
<tr><td>”Varje runda passerar skylten. Förra året spelades ungefär {kr(round(prog.ronder()[0], -2))} ronder.”</td><td>”{kr(round(prog.ronder()[0], -2))} personer ser er logga.”</td></tr>
<tr><td>”Efter säsongen får ni en rapport med vad som mättes och vad som genomfördes.”</td><td>”Ni får garanterat nya kunder.”</td></tr>
<tr><td>”Det kostar {kr(hs['pris'])} kr om året, ungefär {kr(round(hs['pris'] / 52))} kr i veckan.”</td><td>”Det betalar sig själv.”</td></tr>
<tr><td>”Flygfilmen kommer när den är färdig. Då ingår den.”</td><td>”Ni syns i flygfilmen och i golfappen.”</td></tr>
<tr><td>”Ni bestämmer själva hur ni använder hålet mot era kunder.”</td><td>”Alla i Växjö kommer att känna till er.”</td></tr></table>

<h2>Vanliga invändningar</h2>
<table><tr><th style='width:34%'>De säger</th><th>Du svarar</th></tr>
<tr><td>”Det är för dyrt.”</td><td>”Jämfört med vad? Ett hål kostar ungefär {kr(round(hs['pris'] / 52))} kr i veckan och syns hela säsongen. Vill ni börja mindre
finns tävlingspartner från {kr(prog.produkter['tavling']['pris'])} kr.” Sänk aldrig priset på hålet; erbjud en annan produkt.</td></tr>
<tr><td>”Förut kostade det {kr(idag.get('pris', 10000))} kr.”</td><td>”Det stämmer, och då fick ni en skylt. Nu får ni tio saker, en egen vecka och en rapport.
Ni som var med från början får en trappa, så att höjningen kommer i steg.”</td></tr>
<tr><td>”Vi har ingen budget i år.”</td><td>”Då reserverar jag inte, men får jag höra av mig i januari när ni har ny budget? Vilket datum passar?”</td></tr>
<tr><td>”Vad får vi ut av det?”</td><td>”Synlighet där era kunder är, en egen vecka och ett namn som sägs på banan. Vi lovar inga affärer,
men vi visar svart på vitt vad som har synts.”</td></tr>
<tr><td>”Ingen läser skyltar.”</td><td>”Det är där man står och väntar på sin tur, med klubban i handen. Och skylten är bara en av tio delar.”</td></tr>
<tr><td>”Vi sponsrar redan fotbollen.”</td><td>”Bra, då vet ni hur det fungerar. Golfen når en annan publik, ofta beslutsfattare, och hela säsongen.”</td></tr>
<tr><td>”Vi vill ha ett annat hål.”</td><td>”Vilket? Är det sålt kan jag sätta er först i kön, och erbjuda ett av de lediga i år.”</td></tr>
<tr><td>”Kan vi få det billigare om vi tar tre år?”</td><td>”Med tre år är priset låst och startkostnaden borta. Det är rabatten.”</td></tr>
<tr><td>”Vi måste fråga styrelsen.”</td><td>”Självklart. Jag skickar presentationen och prospektet för ert hål. När träffas styrelsen? Då ringer jag dagen efter.”</td></tr>
<tr><td>”Vi vill synas i appen.”</td><td>”Fler digitala kanaler är på gång. Den dag de finns kan de läggas till. I dag säljer vi bara det som finns.”</td></tr></table>

<h2 class='sid'>Dagens hålsponsorer</h2>
<p>De {idag.get('salda_hal', 0)} företag som redan har ett hål är programmets viktigaste kunder. Ring dem först, innan materialet
syns någon annanstans.</p>
<ol>
 <li>Ring, mejla inte. Boka ett möte på deras kontor eller i klubbhuset.</li>
 <li>Börja med tack: hur länge de har varit med, vad det har betytt för klubben.</li>
 <li>Visa det nya hålsponsorskapet. Säg rakt ut att priset höjs, och varför.</li>
 <li>Erbjud trappan: {', '.join(f'{kr(t)} kr {prog.sasong + i}' for i, t in enumerate(trappa))}, med treårsavtal och förstahandsrätt till hålet till
 {e((prog.cfg.get('befintliga') or {}).get('sista_dag', '30 november'))}.</li>
 <li>Säger de nej till trappan: erbjud ett ettårsavtal till ordinarie pris, eller en mindre produkt. Säger de nej till allt: tacka, och fråga om ni får höra av er inför nästa säsong.</li></ol>
<h3>Så presenterar du prisökningen</h3>
<div class='mejl'><p>”Ni har varit med oss i flera år och det har betytt mycket. Från {prog.sasong} gör vi om hålsponsorskapet helt. Ni får
hålets namn, en ny skylt, hålets sida på hemsidan, egna inlägg, en partnervecka och en rapport efter säsongen. Det kostar mer,
{kr(prog.produkter['halsponsor']['pris'])} kr om året. Eftersom ni var med från början vill vi att höjningen kommer i steg:
{kr(trappa[0]) if trappa else ''} kr nästa år, och hålet är ert först.”</p></div>
<p class='liten'>Säg priset en gång, tydligt, och var sedan tyst. Den som pratar först efter priset förhandlar bort det.</p>

<h2>När de säger nej till hålet</h2>
<p>Ett nej till hålet är sällan ett nej till klubben. Erbjud nästa steg, från minst åtagande och uppåt:</p>
<ul>{stege_txt}</ul>
<p>Företagsdagen säljs till alla som säger ”vi vill träffa människor, inte synas”. Räknemall: {fdk.get('minsta_antal', 8)} gäster eller fler,
självkostnad per gäst + PRO:ns tid, plus {round(float(fdk.get('paslag', 0.3)) * 100)} % påslag. Exempel: {fd['deltagare']} gäster ger {kr(fd['pris'])} kr.</p>

<div class='hall'><h2>Dokumentera allt, samma dag</h2>
<p>Partneröversikten (Excel-filen) är klubbens enda lista. Skriv in varje kontakt samma dag:</p>
<ul>
 <li><b>Företag, kontaktperson, telefon, e-post.</b></li>
 <li><b>Produkt och hål</b> de är intresserade av.</li>
 <li><b>Status:</b> kontaktad, möte bokat, förslag skickat, reserverad, avtal, nej.</li>
 <li><b>Nästa steg och datum.</b> Ett intresse utan datum är inget intresse.</li></ul>
<p>Ett reserverat hål hålls i högst 14 dagar. Står det reserverat längre utan avtal släpps det.</p></div>

<h2 class='sid'>Förnyelsen börjar i oktober</h2>
<table><tr><th>När</th><th>Vad</th></tr>
<tr><td>Oktober</td><td>Årsrapporten skickas till partnern med ett tack och ett förslag till möte.</td></tr>
<tr><td>Början av november</td><td>Förnyelsemöte: gå igenom rapporten, fråga vad som var bra och vad som saknades.</td></tr>
<tr><td>Till 30 november</td><td>Förstahandsrätt till samma hål eller plats. Därefter säljs det fritt.</td></tr>
<tr><td>December</td><td>Avtal skrivs, logotyp bekräftas för nästa säsong.</td></tr></table>
<p>Frågor att ställa i förnyelsemötet: Vad märkte ni av ert hål? Vilka kunder tog ni med hit? Vill ni ha samma vecka nästa år?
Vill ni ta ett steg till, till exempel en tävling eller företagsdagen?</p>

<h2>Mejlutkast</h2>
<p class='liten'>Byt ut det som står inom hakparentes. Skicka från din egen adress, aldrig som massutskick.</p>
<h3>1. Första kontakt, nytt företag</h3>
<div class='mejl'><div class='amne'>Ämne: Ett hål på {e(k.bana)} med ert namn?</div>
<p>Hej [förnamn],</p>
<p>Jag är klubbchef på {e(k.namn)}. Från säsongen {prog.sasong} får våra hål namn efter de företag som vill stå bakom dem, och jag
tror att [företaget] skulle passa på ett av dem.</p>
<p>Det handlar om mer än en skylt: hålet bär ert namn på banan, i mobilen och i våra kanaler, ni får en egen vecka hos oss och en
rapport efter säsongen om vad som har synts.</p>
<p>Får jag visa hur det ser ut? Det tar en halvtimme, hos er eller över en kopp kaffe i klubbhuset. Passar [dag] eller [dag]?</p>
<p>Vänliga hälsningar<br>{sign}</p></div>

<h3>2. Uppföljning efter mötet</h3>
<div class='mejl'><div class='amne'>Ämne: Hål [nummer], som vi pratade om</div>
<p>Hej [förnamn],</p>
<p>Tack för i dag. Som utlovat skickar jag presentationen och prospektet för hål [nummer]. Jag har reserverat hålet åt er till
[datum, högst 14 dagar].</p>
<p>Kort sammanfattat: [företaget]-hålet, {kr(prog.produkter['halsponsor']['pris'])} kr per år, ett eller tre år. Med tre år är priset låst
och startkostnaden borta.</p>
<p>Jag ringer [dag] för att höra vad ni bestämt. Hör gärna av er innan om något är oklart.</p>
<p>Vänliga hälsningar<br>{sign}</p></div>

<h3>3. Uppföljning, inget svar</h3>
<div class='mejl'><div class='amne'>Ämne: Ska jag hålla hål [nummer] åt er?</div>
<p>Hej [förnamn],</p>
<p>Jag hör av mig om hål [nummer] eftersom reservationen går ut [datum]. Vill ni att jag håller det en vecka till, eller ska jag
släppa det till nästa intresserade? Ett kort svar räcker.</p>
<p>Vänliga hälsningar<br>{sign}</p></div>

<h3>4. Dagens hålsponsor, inför {prog.sasong}</h3>
<div class='mejl'><div class='amne'>Ämne: Ert hål på {e(k.bana)} {prog.sasong}</div>
<p>Hej [förnamn],</p>
<p>Tack för att ni har stått bakom hål [nummer]. Inför {prog.sasong} gör vi om hålsponsorskapet helt, och jag vill gärna visa er det
nya innan vi berättar om det för någon annan. Hålet är ert först, till {e((prog.cfg.get('befintliga') or {}).get('sista_dag', '30 november'))}.</p>
<p>Kan vi ses en halvtimme [dag] eller [dag]?</p>
<p>Vänliga hälsningar<br>{sign}</p></div>

<h3>5. Förnyelse efter säsongen</h3>
<div class='mejl'><div class='amne'>Ämne: [Företaget]-hålet, säsongen som gick</div>
<p>Hej [förnamn],</p>
<p>Säsongen är slut och här kommer er årsrapport: vad som visades, vad som mättes och vad vi genomförde, med bilder från ert hål
och er partnervecka.</p>
<p>Jag skulle gärna gå igenom den med er och höra vad ni vill göra nästa år. Ert hål är ert först, till
{e((prog.cfg.get('befintliga') or {}).get('sista_dag', '30 november'))}. Passar [dag] eller [dag]?</p>
<p>Vänliga hälsningar<br>{sign}</p></div>

<h3>6. Tack efter avtal</h3>
<div class='mejl'><div class='amne'>Ämne: Välkommen som partner till {e(k.namn)}</div>
<p>Hej [förnamn],</p>
<p>Välkomna! Från säsongen {prog.sasong} heter hål [nummer] [företaget]-hålet. Två saker behöver vi från er: logotypen som vektorfil
(SVG, PDF eller EPS) och en kort text om företaget till hålets sida. Ni får se och godkänna allt innan det visas.</p>
<p>Vänliga hälsningar<br>{sign}</p></div>

<h2>Efter påskrivet avtal</h2>
<ol>
 <li>Skriv in företaget i partneröversikten och ändra status till sålt.</li>
 <li>Skicka tackmejlet (utkast 6) och be om logotypen.</li>
 <li>Samla logotyperna i partneröversikten. Sista dag är i februari, för då gör TACADA säsongens leverans: plattor, hålsidor och inlägg i ett paket.</li>
 <li>Partnern godkänner sitt material. Plattan trycks i mars.</li>
 <li>Partnerveckan bokas i kalendern.</li></ol>
<p class='liten'>Frågor om materialet: TACADA. Frågor om avtalet: klubbchefen.</p>"""


# ------------------------------------------------------------------ D: årsrapport
def rapport(prog: Program, partner: dict, data: dict) -> str:
    """En partners årsrapport. data: {'matt': [...], 'uppskattat': [...], 'levererat': [...], 'foton': [...],
    'kommentar': str, 'nasta': [...]}; tomma listor visar fält som fylls i."""
    k = prog.klubb
    p = prog.produkter.get(partner.get("produkt", "halsponsor"), prog.produkter["halsponsor"])
    hal = next((h for h in prog.hal if h.nr == partner.get("hal")), None)
    namn = partner.get("foretag") or partner.get("namn") or "[Företaget]"
    titel = f"{namn}-hålet" if hal else f"{namn} · {p['namn']}"
    mall = data.get("mall", False)

    def tabell(rader, typ, tom):
        if not rader:
            rader = [{"vad": x, "varde": None, "kalla": ""} for x in tom]
        t = {"matt": ("Uppmätt", "t-matt"), "upp": ("Uppskattning", "t-upp"), "lev": ("Levererat", "t-lev")}[typ]
        ut = ""
        for r in rader:
            v = r.get("varde")
            varde = (f"<b style='font:400 15pt/1 var(--serif)'>{v}</b>" if v not in (None, "")
                     else "<span class='liten' style='color:#9AA8AB'>fylls i</span>")
            ut += (f"<tr><td>{e(r['vad'])}<span class='tag {t[1]}'>{t[0]}</span><br><span class='liten'>{e(r.get('kalla', ''))}</span></td>"
                   f"<td class='n' style='width:24%'>{varde}</td></tr>")
        return f"<table><tr><th>Vad</th><th class='n'>Värde</th></tr>{ut}</table>"

    r, kalla = prog.ronder()
    ytor = "".join(f"<li>{e(y)}</li>" for y in (p.get("ytor") or {}).get("fysiska", []) + (p.get("ytor") or {}).get("digitala", []))
    foton = data.get("foton") or [{"text": t} for t in ("Skylten vid tee", "Veckans inlägg under partnerveckan", "Hålets sida på hemsidan",
                                                       "Presentationsinlägget")]
    fotohtml = "".join(
        f"<div style='break-inside:avoid'><div style='height:150px;background:{'#E4EAE6' if not f.get('bild') else 'var(--djup)'};"
        f"display:flex;align-items:center;justify-content:center;border-radius:3px;overflow:hidden'>"
        + (f"<img src='{f['bild']}' style='width:100%;height:100%;object-fit:cover'>" if f.get("bild") else
           "<span class='liten'>Foto läggs in</span>")
        + f"</div><div class='liten' style='margin-top:4pt'>{e(f['text'])}</div></div>" for f in foton)
    nasta = data.get("nasta") or ["Samma hål och samma partnervecka nästa säsong (förstahandsrätt till 30 november).",
                                  "Tävlingspartner: ge en av klubbens tävlingar ert namn.",
                                  "Företagsdag för era kunder eller er personal."]
    kommentar = data.get("kommentar") or ""
    hal_bild = hal_i_ruta(hal.bild, 0, 0, 200, 300, max_px=900) if hal and hal.bild else ""
    return f"""
{"<div style='background:#B42820;color:#fff;font:600 8pt/1 var(--sans);letter-spacing:.16em;padding:7pt 10pt;margin-bottom:12pt'>MALL · INGA RIKTIGA VÄRDEN · " + e(namn).upper() + " ÄR ETT PÅHITTAT EXEMPEL</div>" if mall else ""}
<div style='display:flex;justify-content:space-between;align-items:center'>
 <div class='ey' style='margin:0'>Årsrapport · säsongen {prog.sasong}</div>
 <div style='display:flex;align-items:center;gap:10px'><span class='liten'>{e(k.namn)}</span><img src='{k.logga("ljus")}' style='width:36px;height:36px'></div></div>
<div style='display:flex;gap:22pt;margin-top:14pt'>
 <div style='flex:1'>
  <h1 style='font-size:34pt'>{e(titel)}</h1>
  <p class='lead'>{e(f'Hål {hal.nr} · par {hal.par} · ' if hal else '')}{e(p['namn'])} · {e(partner.get('avtal', 'avtal ' + str(prog.sasong)))}</p>
  <div class='ruta'><div class='ey'>Sammanfattning</div>
  <p style='margin:0'>{e(kommentar) if kommentar else "<span class='liten'>Klubbchefens sammanfattning av året skrivs här: vad som levererades, vad som stack ut och vad partnern fick ut av sin vecka.</span>"}</p></div></div>
 <div style='width:200px;height:300px;position:relative;background:var(--djup);border-radius:3px;flex:none'>{hal_bild}</div></div>

<h2>Avtalad exponering</h2>
<ul class='kol2'>{ytor}</ul>

<h2>Uppmätt</h2>
<p class='liten'>Räknat under säsongen ur hemsidans statistik, QR-koden och Meta (Instagram och Facebook). Visningar är antal gånger
något har visats, inte antal personer.</p>
{tabell(data.get('matt'), 'matt', ['Hålets sida på hemsidan, sidvisningar', 'varav via QR-koden på skylten', 'Klick till er hemsida',
                                    'Presentationsinlägget, visningar', 'Veckans partner-inlägget, visningar', 'Ert eget inlägg (om ni delar siffran)'])}

<h2>Uppskattat</h2>
<p class='liten'>Räknat ur klubbens ronder. Uppskattningar är inte mätningar och redovisas för sig.</p>
{tabell(data.get('uppskattat'), 'upp', [f'Passager vid skylten = ronder × andel som spelar hålet ({kalla}: {kr(r)} ronder)',
                                        'Ronder under er partnervecka (ur bokningssystemet)'])}

<h2>Levererat</h2>
{tabell(data.get('levererat'), 'lev', ['Sponsorplattan uppsatt (datum)', 'Hålets sida med logotyp publicerad (datum)',
                                       'Presentationsinlägget publicerat (datum)', 'Ert eget inlägg levererat (datum)',
                                       'Partnervecka genomförd (vecka)', 'Partnertävlingen (datum, deltog ja/nej)'])}

<h2>Bilder från era platser</h2>
<div style='display:grid;grid-template-columns:repeat(2,1fr);gap:12pt'>{fotohtml}</div>

<h2>Nästa säsong</h2>
<ul>{''.join(f'<li>{e(x)}</li>' for x in nasta)}</ul>
<p class='liten' style='margin-top:14pt'>{e(prog.villkor['flygfilm'])} Underlag: klubbens statistik och TACADA. Material: TACADA.</p>"""


__all__ = ["A3L", "A4", "A4L", "beslut", "beslutsunderlag", "html", "kalender", "manual", "oversikt", "pdf", "prislista", "rapport"]
