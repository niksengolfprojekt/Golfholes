"""Social Media Kit: inlägg i 4:5 (1080 × 1350) ur `klubbar/<klubb>/some/inlagg.yaml`.

  python -m golfholes inlagg klubbar/<klubb>   → NN-<id>.png per inlägg, texter.md, översikt.jpg

Samma mallar för varje klubb: färger, typsnitt, logga och hashtaggar kommer ur klubb.yaml,
hålets fakta ur hålkortet och bilden är hålkortets hålbild med tees och T-flagga (hela hålet
syns alltid). Inlägg vars hål saknar hålbild hoppas över och kommer med nästa körning.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .halkort import Halkort
from .klubbmaterial import ATTRIBUTION, Klubb, Webblasare, css, e, hal_i_ruta, halkort_markerat, kontaktark

W, H = 1080, 1350
TYPER = ("nystart", "serie", "sponsorer", "hal", "bli_sponsor")

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1350px;overflow:hidden}
.pg{position:relative;width:1080px;height:1350px;overflow:hidden;background:var(--kristall);color:var(--djup)}
.pg.mork{background:var(--djup);color:var(--kristall)}
.abs{position:absolute}
.top{position:absolute;left:64px;right:64px;top:58px;display:flex;align-items:center;justify-content:space-between}
.klubb{display:flex;align-items:center;gap:16px;font:600 16px/1 var(--sans);letter-spacing:.22em;text-transform:uppercase;color:var(--glas)}
.mork .klubb{color:var(--is)}
.klubb img{width:58px;height:58px}
.ey{font:600 19px/1 var(--sans);letter-spacing:.22em;text-transform:uppercase;color:var(--glod-m)}
.mork .ey{color:var(--glod)}
.h{font:400 60px/1.06 var(--serif);letter-spacing:-.01em;text-wrap:balance}
.t{font:400 29px/1.42 var(--sans);color:#2C3D44;text-wrap:pretty}
.mork .t{color:#D3E3E0}
.src{position:absolute;left:64px;right:64px;bottom:30px;font:400 14px/1.3 var(--sans);color:#5B6E73}
.mork .src{color:var(--is);opacity:.8}
.rad{border-left:3px solid var(--glod-m);padding:2px 0 2px 24px}
.mork .rad{border-color:var(--glod)}
.rad .l{font:600 15px/1 var(--sans);letter-spacing:.2em;text-transform:uppercase;color:var(--glas)}
.mork .rad .l{color:var(--is)}
.rad .q{font:italic 400 33px/1.24 var(--serif);margin-top:12px;text-wrap:pretty}
.logo{border:2px dashed var(--glas);color:var(--glas);display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:6px;font:600 16px/1 var(--sans);letter-spacing:.18em;text-transform:uppercase}
.logo small{font:400 14px/1 var(--sans);letter-spacing:.02em;text-transform:none;opacity:.8}
"""


def _sida(k: Klubb, kropp: str) -> str:
    return (f"<!doctype html><html lang='sv'><head><meta charset='utf-8'><style>{css(k)}{CSS}</style></head>"
            f"<body>{kropp}</body></html>")


def _topp(k: Klubb, etikett: str, mork: bool) -> str:
    ey = f"<div class='ey'>{e(etikett)}</div>" if etikett else ""
    return (f"<div class='top'><div class='klubb'><img src='{k.logga('mork' if mork else 'ljus')}'>{e(k.namn)}</div>"
            f"{ey}</div>")


def _langder(c: Halkort) -> str:
    m = sorted(l for _, l in c.tees)
    return f"{m[0]} m" if m[0] == m[-1] else f"{m[0]}–{m[-1]} m"


# ------------------------------------------------------------------ mallar
def m_hal(k: Klubb, p: dict, c: Halkort, raw: dict) -> str:
    mork = bool(p.get("mork"))
    rubrik = p.get("rubrik") or c.rubrik
    rad = p.get("rad") or raw.get("kortrad") or c.slutrad
    return f"""<div class='pg{' mork' if mork else ''}'>{_topp(k, p.get('etikett', 'Hål för hål'), mork)}
{hal_i_ruta(c.image, 36, 150, 500, 1130)}
<div class='abs' style='left:580px;right:64px;top:150px;bottom:80px;display:flex;flex-direction:column;justify-content:center'>
 <div style='font:400 250px/.78 var(--serif);letter-spacing:-.04em;margin-left:-8px'>{c.hole}</div>
 <div class='ey' style='margin-top:34px'>Par {c.par} · Index {c.index} · {_langder(c)}</div>
 <div class='h' style='margin-top:26px'>{e(rubrik)}</div>
 <div class='t' style='margin-top:22px'>{e(p.get('text', ''))}</div>
 <div class='rad' style='margin-top:40px'><div class='l'>Pro:ns råd</div><div class='q'>{e(rad)}</div></div></div>
<div class='src'>{ATTRIBUTION}</div></div>"""


def m_nystart(k: Klubb, p: dict, kort: list[Halkort]) -> str:
    n = len(kort)
    cw = (W - 2 * 50) / max(n, 1)
    bilder = "".join(hal_i_ruta(c.image, 50 + i * cw, 150, cw - 10, 700) for i, c in enumerate(kort))
    nummer = "".join(f"<div class='abs ey' style='left:{50 + i * cw:.0f}px;width:{cw - 10:.0f}px;top:866px;text-align:center'>Hål {c.hole}</div>"
                     for i, c in enumerate(kort))
    return f"""<div class='pg'>{_topp(k, p.get('etikett', ''), False)}{bilder}{nummer}
<div class='abs' style='left:64px;right:64px;top:940px'>
 <div class='h' style='font-size:74px'>{e(p.get('rubrik', ''))}</div>
 <div class='t' style='margin-top:24px;max-width:860px'>{e(p.get('text', ''))}</div></div>
<div class='src'>{ATTRIBUTION}</div></div>"""


def m_serie(k: Klubb, p: dict, kort: list[Halkort]) -> str:
    n = len(kort)
    kol = (n + 1) // 2
    x0, y0, bw, rh = 44, 440, W - 88, 390
    cw = bw / max(kol, 1)
    celler = ""
    for i, c in enumerate(kort):
        x, y = x0 + (i % kol) * cw, y0 + (i // kol) * (rh + 22)
        celler += hal_i_ruta(c.image, x + 3, y, cw - 6, rh - 40, "center bottom", max_px=1200)
        celler += (f"<div class='abs' style='left:{x:.0f}px;width:{cw:.0f}px;top:{y + rh - 30}px;text-align:center;"
                   f"font:400 26px/1 var(--serif)'>{c.hole}</div>")
    return f"""<div class='pg'>{_topp(k, p.get('etikett', ''), False)}
<div class='abs' style='left:64px;right:64px;top:180px'>
 <div class='h' style='font-size:84px'>{e(p.get('rubrik', ''))}</div>
 <div class='t' style='margin-top:26px;max-width:860px'>{e(p.get('text', ''))}</div></div>
{celler}<div class='src'>{ATTRIBUTION}</div></div>"""


def m_sponsorer(k: Klubb, p: dict) -> str:
    celler = "".join(
        f"<div style='aspect-ratio:1;border:1.5px solid var(--glas);border-radius:50%;display:flex;align-items:center;"
        f"justify-content:center;font:400 46px/1 var(--serif)'>{i}</div>" for i in range(1, 19))
    return f"""<div class='pg mork'>{_topp(k, p.get('etikett', ''), True)}
<div class='abs' style='left:72px;right:72px;top:150px;bottom:90px;display:flex;flex-direction:column;justify-content:center'>
 <div class='h' style='font-size:92px'>{e(p.get('rubrik', ''))}</div>
 <div class='t' style='margin-top:30px;max-width:860px'>{e(p.get('text', ''))}</div>
 <div style='display:grid;grid-template-columns:repeat(6,1fr);gap:28px;margin-top:76px;color:var(--kristall)'>{celler}</div></div></div>"""


def m_bli_sponsor(k: Klubb, p: dict, c: Halkort) -> str:
    kontakt = k.sponsring.get("kontakt", k.web)
    return f"""<div class='pg'>{_topp(k, p.get('etikett', ''), False)}
{hal_i_ruta(c.image, 36, 150, 480, 1130)}
<div class='abs' style='left:560px;right:64px;top:150px;bottom:80px;display:flex;flex-direction:column;justify-content:center'>
 <div class='h' style='font-size:76px'>{e(p.get('rubrik', ''))}</div>
 <div class='t' style='margin-top:26px'>{e(p.get('text', ''))}</div>
 <div style='margin-top:48px;background:var(--djup);padding:12px;box-shadow:0 20px 40px rgba(16,32,46,.22)'>
  <div style='height:84px;display:flex;align-items:center;justify-content:center;font:400 34px/1 var(--serif);color:var(--kristall)'>[Ert företag]-hålet</div>
  <div style='background:var(--kristall);padding:22px'><div style='font:600 13px/1 var(--sans);letter-spacing:.22em;color:var(--glas);margin-bottom:14px'>PRESENTERAS AV</div>
   <div class='logo' style='height:110px'>Er logotyp här<small>i en färg</small></div></div></div>
 <div style='margin-top:44px;font:600 16px/1 var(--sans);letter-spacing:.2em;text-transform:uppercase;color:var(--glod-m)'>Prata med kansliet</div>
 <div style='margin-top:14px;font:500 27px/1.35 var(--sans)'>{e(kontakt)}</div></div>
<div class='src'>Hål {c.hole} på {e(k.bana)}. {ATTRIBUTION}</div></div>"""


# ------------------------------------------------------------------ bygg
def las(klubbmapp: Path) -> list[dict]:
    d = yaml.safe_load((Path(klubbmapp) / "some" / "inlagg.yaml").read_text(encoding="utf-8")) or {}
    poster = d.get("inlagg") or []
    for p in poster:
        if p.get("typ") not in TYPER:
            raise ValueError(f"{p.get('id')}: okänd typ {p.get('typ')!r} (finns: {', '.join(TYPER)})")
    return poster


def html_for(k: Klubb, p: dict, kort: dict[int, Path], markerat) -> str | None:
    """HTML för ett inlägg, eller None om hålet saknar hålbild (kommer med senare)."""
    typ = p["typ"]
    if typ in ("hal", "bli_sponsor"):
        f = kort.get(int(p["hal"]))
        if not f:
            return None
        raw = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        c = markerat(f)
        return _sida(k, m_hal(k, p, c, raw) if typ == "hal" else m_bli_sponsor(k, p, c))
    if typ == "nystart":
        return _sida(k, m_nystart(k, p, [markerat(kort[h]) for h in p.get("hal", []) if h in kort]))
    if typ == "serie":
        return _sida(k, m_serie(k, p, [markerat(f) for _, f in sorted(kort.items())]))
    return _sida(k, m_sponsorer(k, p))


def texter_md(k: Klubb, gjorda: list[tuple[str, dict]], vantar: list[dict]) -> str:
    bas = " ".join(k.some.get("hashtags", []))
    rader = [f"# {k.namn} – inlägg och bildtexter", "",
             f"{len(gjorda)} inlägg i 4:5 (1080 × 1350). Bildtexten skrivs under inlägget, hashtaggarna sist.",
             "Lantmäteriets källtext står redan på bilderna. Publiceras först när klubben har godkänt hålen.", ""]
    for fil, p in gjorda:
        rubrik = p.get("rubrik") or f"Hål {p.get('hal')}"
        rader += [f"## {fil[:2]} · {rubrik}", "", f"Bild: `{fil}`", "",
                  " ".join((p.get("bildtext") or "").split()), "",
                  " ".join([*k.some.get("hashtags", []), *p.get("hashtags", [])]) or bas, ""]
    if vantar:
        rader += ["## Väntar på hålbild", "",
                  *[f"- {p['id']} (hål {p.get('hal')}) – kommer med när hålbilden finns och kommandot körs igen" for p in vantar], ""]
    return "\n".join(rader)


def bygg_kit(klubbmapp: Path, ut: Path) -> dict:
    klubbmapp, ut = Path(klubbmapp), Path(ut)
    k = Klubb.from_dir(klubbmapp)
    poster = las(klubbmapp)
    kort = k.halkort()
    cache: dict[Path, Halkort] = {}

    def markerat(f: Path) -> Halkort:
        if f not in cache:
            cache[f] = halkort_markerat(f)
        return cache[f]

    gjorda, vantar, bilder = [], [], []
    ut.mkdir(parents=True, exist_ok=True)
    with Webblasare() as wb:
        for p in poster:
            sida = html_for(k, p, kort, markerat)
            if sida is None:
                vantar.append(p)
                print(f"  väntar: {p['id']} (hål {p.get('hal')} saknar hålbild)")
                continue
            fil = f"{len(gjorda) + 1:02d}-{p['id']}.png"
            bilder.append(wb.png(sida, W, H, ut / fil))
            gjorda.append((fil, p))
            print(f"  {ut / fil}")
    (ut / "texter.md").write_text(texter_md(k, gjorda, vantar), encoding="utf-8")
    if bilder:
        kontaktark(bilder, ut / "översikt.jpg", 5, 2600, etiketter=[f for f, _ in gjorda])
    print(f"{len(gjorda)} inlägg, {len(vantar)} väntar på hålbild. Texter: {ut / 'texter.md'}")
    return {"inlagg": [ut / f for f, _ in gjorda], "vantar": [p["id"] for p in vantar], "texter": ut / "texter.md"}
