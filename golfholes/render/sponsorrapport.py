"""Sponsorrapportens sida (A4 stående): hålbild, sponsor, visningar per kanal och månad.

Siffrorna heter alltid VISNINGAR. Tee-skylten är en uppskattning och märks så.
"""
from __future__ import annotations

import base64
import html
import io
from pathlib import Path

import yaml

from ..statistik import HalStatistik, Sasongsrapport

ATTRIBUTION = "Underlag: Ortofoto och Markhöjdmodell ©Lantmäteriet, bearbetat, CC BY 4.0"
FONTS = Path(__file__).resolve().parents[2] / "assets" / "typsnitt"
MANADER = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
MANADER_LANG = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september",
                "oktober", "november", "december"]

INK, SOFT, LINE, PAPER, PLATE, ACCENT, BAR = "#1d2a22", "#5b665f", "#d9d6cc", "#f7f5ef", "#ffffff", "#2f5d46", "#3f7a5c"


def _e(s) -> str:
    return html.escape(str(s))


def tal(n: int) -> str:
    """Svenskt tusentalsavstånd: 24 000."""
    return f"{n:,}".replace(",", " ")


def _font_face(fam: str, fil: str, weight: int, style: str = "normal") -> str:
    p = FONTS / fil
    if not p.exists():
        return ""
    return (f"@font-face{{font-family:'{fam}';src:url('{p.as_uri()}');font-weight:{weight};"
            f"font-style:{style}}}")


def _data_uri_bild(p: Path, max_h: int = 1400) -> str:
    from PIL import Image

    im = Image.open(p).convert("RGB")
    if im.height > max_h:
        im = im.resize((round(im.width * max_h / im.height), max_h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def halbild(club_dir: Path, h: HalStatistik, testdata: bool) -> tuple[str, str]:
    """(HTML för hålbilden, märkning under bilden). Tom sträng om inget underlag finns."""
    nr = h.hal
    kandidater = []
    if h.sponsor.get("halbild"):
        kandidater.append(club_dir / h.sponsor["halbild"])
    kort = club_dir / "halkort" / f"hal-{nr:02d}.yaml"
    if kort.exists():
        bild = (yaml.safe_load(kort.read_text(encoding="utf-8")) or {}).get("bild")
        if bild:
            kandidater.append((kort.parent / bild).resolve())
    kandidater += [club_dir / "halbilder" / f"hal-{nr:02d}-malad.webp", club_dir / "halbilder" / f"hal-{nr:02d}-foto.webp"]
    for p in kandidater:
        if p.exists():
            ai = "malad" in p.name
            mark = ("Hålbild: AI-målad på Lantmäteriets ortofoto. " if ai else "Hålbild ur Lantmäteriets ortofoto. ") + ATTRIBUTION
            return f"<img src='{_data_uri_bild(p)}' alt='Hål {nr}'>", mark
    geo = club_dir / f"hal-{nr:02d}.yaml"
    if geo.exists():
        from ..hole import Hole
        from .flat import render_flat

        svg = render_flat(Hole.from_yaml(geo), width_px=420, fit=True, fade=True, north_arrow=False)
        mark = "Påhittat demohål." if testdata else ATTRIBUTION
        return f"<div class='svg'>{svg}</div>", mark
    return "", ""


def _logga(club_dir: Path, sp: dict) -> str:
    lp = sp.get("logo")
    if lp and (club_dir / lp).exists():
        p = club_dir / lp
        mime = "image/svg+xml" if p.suffix.lower() == ".svg" else f"image/{p.suffix.lower().lstrip('.')}"
        return f"<img src='data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}' alt='{_e(sp['name'])}'>"
    return f"<div class='wordmark'>{_e(sp['name'])}</div>"


def _period(manader: list[str], sasong: int) -> str:
    if not manader:
        return f"säsongen {sasong}"
    a, b = int(manader[0][5:]) - 1, int(manader[-1][5:]) - 1
    return f"{MANADER_LANG[a]} {sasong}" if a == b else f"{MANADER_LANG[a]}–{MANADER_LANG[b]} {sasong}"


def _stapelgraf(manader: dict[str, int]) -> str:
    if not manader:
        return ""
    hi = max(manader.values()) or 1
    w, h, pad_b, pad_t = 420, 150, 28, 24
    n = len(manader)
    slot = w / n
    bw = min(64, slot * 0.5)
    parts = [f"<svg viewBox='0 0 {w} {h}' xmlns='http://www.w3.org/2000/svg' role='img' "
             f"aria-label='Digitala visningar per månad'>",
             f"<line x1='0' x2='{w}' y1='{h - pad_b}' y2='{h - pad_b}' stroke='{LINE}' stroke-width='1'/>"]
    for i, (m, v) in enumerate(manader.items()):
        bh = (h - pad_b - pad_t) * v / hi
        x = i * slot + (slot - bw) / 2
        y = h - pad_b - bh
        r = min(4, bh / 2)
        parts.append(f"<path d='M{x:.1f},{h - pad_b} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
                     f"H{x + bw - r:.1f} Q{x + bw:.1f},{y:.1f} {x + bw:.1f},{y + r:.1f} V{h - pad_b} Z' fill='{BAR}'>"
                     f"<title>{MANADER_LANG[int(m[5:]) - 1]}: {tal(v)} visningar</title></path>")
        parts.append(f"<text x='{x + bw / 2:.1f}' y='{y - 6:.1f}' text-anchor='middle' class='bv'>{tal(v)}</text>")
        parts.append(f"<text x='{x + bw / 2:.1f}' y='{h - 8}' text-anchor='middle' class='bm'>{MANADER[int(m[5:]) - 1]}</text>")
    parts.append("</svg>")
    return "".join(parts)


def _matt(k) -> str:
    if k.uppskattning:
        return "Uppskattning: klubbens ronder × andel som spelar hålet"
    if k.kalla == "plausible":
        return "Sidvisningar av hålets sida"
    if k.kalla == "qr":
        return "Sidvisningar efter skanning av QR-koden"
    return "Visningar av hålet med sponsorns logga"


def sida_html(r: Sasongsrapport, h: HalStatistik, club_dir: Path) -> str:
    club = yaml.safe_load((club_dir / "klubb.yaml").read_text(encoding="utf-8")) or {}
    fonts = club.get("typsnitt") or {}
    serif, sans = fonts.get("siffror", "Spectral"), fonts.get("text", "Hanken Grotesk")
    faces = "".join([
        _font_face("Spectral", "Spectral-Regular.ttf", 400), _font_face("Spectral", "Spectral-Medium.ttf", 500),
        _font_face("Spectral", "Spectral-Italic.ttf", 400, "italic"),
        _font_face("Hanken Grotesk", "HankenGrotesk-Regular.ttf", 400),
        _font_face("Hanken Grotesk", "HankenGrotesk-Medium.ttf", 500),
        _font_face("Hanken Grotesk", "HankenGrotesk-SemiBold.ttf", 600)])
    sp = h.sponsor
    namn = sp.get("name", "")
    rubrik = f"{namn}-hålet" if sp.get("naming_rights", True) else f"Hål {h.hal}"
    meta = " · ".join(x for x in [f"Hål {h.hal}", f"Par {h.par}" if h.par else "", r.klubb, r.bana or ""] if x)
    manader = h.manader()
    period = _period(list(manader), r.sasong)
    bild, bildmark = halbild(club_dir, h, r.testdata)
    tee = next((k for k in h.kanaler if k.uppskattning), None)

    rader = []
    for k in h.kanaler:
        cls = " class='sub'" if k.kalla == "qr" else ""
        est = " <span class='tag'>uppskattning</span>" if k.uppskattning else ""
        klick = "–" if k.klick is None else tal(k.klick)
        rader.append(f"<tr{cls}><td>{_e(k.namn)}{est}<div class='how'>{_e(_matt(k))}</div></td>"
                     f"<td class='n'>{'≈ ' if k.uppskattning else ''}{tal(k.visningar)}</td><td class='n'>{klick}</td></tr>")
    saknas_txt = {"webb": "hålsidan på webben", "partner": "digitala partnerkanaler", "ronder": "tee-skylten (klubbens ronder)"}
    saknas = [saknas_txt[s] for s in h.saknas]
    saknas_html = (f"<p class='missing'>Ingen siffra för {', '.join(saknas)} den här säsongen.</p>" if saknas else "")
    test_band = ("<div class='testband'>TESTDATA · påhittade siffror och påhittad sponsor · inte en riktig rapport</div>"
                 if r.testdata else "")
    tee_txt = ""
    if tee:
        ronder = tee.visningar
        tee_txt = (f"<div class='tile'><div class='cap'>Tee-skylten</div><div class='big2'>≈ {tal(ronder)}</div>"
                   f"<div class='lbl'>visningar · uppskattning</div></div>")
    graf = _stapelgraf(manader)
    return f"""<!doctype html><html lang="sv"><head><meta charset="utf-8"><style>
{faces}
@page{{size:210mm 297mm;margin:0}}
*{{box-sizing:border-box}}
html,body{{margin:0;padding:0;background:{PAPER}}}
body{{width:794px;height:1123px;overflow:hidden;font-family:'{sans}','Hanken Grotesk',Arial,sans-serif;color:{INK};
  -webkit-print-color-adjust:exact;print-color-adjust:exact;position:relative}}
.testband{{background:#b3261e;color:#fff;font-weight:600;font-size:12px;letter-spacing:.14em;text-align:center;padding:7px 0;text-transform:uppercase}}
.wrap{{padding:40px 52px 0}}
.top{{display:flex;justify-content:space-between;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:{SOFT};
  border-bottom:1px solid {LINE};padding-bottom:12px}}
h1{{font-family:'{serif}',Spectral,Georgia,serif;font-weight:500;font-size:50px;line-height:1.05;margin:26px 0 6px;letter-spacing:-.01em}}
.meta{{font-size:15px;color:{SOFT}}}
.main{{display:grid;grid-template-columns:262px 1fr;gap:34px;margin-top:26px}}
.hole{{height:500px;border-radius:6px;overflow:hidden;position:relative}}
.hole img{{width:100%;height:100%;object-fit:contain;display:block;mix-blend-mode:multiply}}
.hole .svg{{width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:#eef0e6}}
.hole .svg svg{{height:100%;width:auto;max-width:100%}}
.cap{{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:{SOFT};font-weight:600}}
.big{{font-family:'{serif}',Spectral,Georgia,serif;font-size:76px;line-height:1;margin:10px 0 6px;font-weight:500;letter-spacing:-.02em}}
.big2{{font-family:'{serif}',Spectral,Georgia,serif;font-size:38px;line-height:1;margin:8px 0 4px;font-weight:500}}
.lbl{{font-size:14px;color:{SOFT}}}
.hero{{padding-bottom:22px;border-bottom:1px solid {LINE}}}
.row{{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:22px}}
.plate{{background:{PLATE};border:1px solid {LINE};border-radius:6px;display:flex;align-items:center;justify-content:center;height:96px;padding:16px 20px}}
.plate img{{max-width:100%;max-height:60px}}
.wordmark{{font-weight:600;font-size:24px;letter-spacing:.12em;text-transform:uppercase}}
.chart{{margin-top:22px}}
.chart svg{{width:100%;height:auto;display:block;margin-top:8px}}
.bv{{font:600 14px '{sans}',Arial,sans-serif;fill:{INK}}}
.bm{{font:500 14px '{sans}',Arial,sans-serif;fill:{SOFT}}}
table{{width:100%;border-collapse:collapse;margin-top:28px;font-size:14px}}
th{{text-align:left;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:{SOFT};font-weight:600;padding:0 0 8px;border-bottom:1px solid {INK}}}
th.n,td.n{{text-align:right;width:110px}}
td{{padding:10px 0;border-bottom:1px solid {LINE};vertical-align:top}}
td.n{{font-variant-numeric:tabular-nums;font-weight:600;font-size:16px}}
tr.sub td:first-child{{padding-left:18px}}
tr.sub td{{color:{SOFT}}}
tr.sub td.n{{font-weight:500}}
.how{{font-size:12px;color:{SOFT};margin-top:2px}}
.tag{{display:inline-block;font-size:10px;letter-spacing:.1em;text-transform:uppercase;border:1px solid {SOFT};color:{SOFT};border-radius:3px;padding:1px 5px;margin-left:6px;vertical-align:2px}}
.missing{{font-size:13px;color:{SOFT};margin:12px 0 0}}
.foot{{position:absolute;left:52px;right:52px;bottom:34px;font-size:11px;line-height:1.5;color:{SOFT};border-top:1px solid {LINE};padding-top:12px}}
.foot b{{color:{INK};font-weight:600}}
</style></head><body>
{test_band}
<div class="wrap">
<div class="top"><span>Sponsorrapport · Säsong {r.sasong}</span><span>{_e(r.klubb)}</span></div>
<h1>{_e(rubrik)}</h1><div class="meta">{_e(meta)}</div>
<div class="main">
  <div class="hole">{bild}</div>
  <div>
    <div class="hero"><div class="cap">Digitala visningar</div><div class="big">{tal(h.digitala_visningar)}</div>
      <div class="lbl">på hålsidan och i digitala partnerkanaler, {_e(period)}</div></div>
    <div class="row">{tee_txt}<div><div class="cap" style="margin-bottom:8px">Hålsponsor</div><div class="plate">{_logga(club_dir, sp)}</div></div></div>
    {f'<div class="chart"><div class="cap">Digitala visningar per månad</div>{graf}</div>' if graf else ''}
  </div>
</div>
<table><thead><tr><th>Kanal</th><th class="n">Visningar</th><th class="n">Klick</th></tr></thead><tbody>{''.join(rader)}</tbody></table>
{saknas_html}
</div>
<div class="foot"><b>Visningar</b> är antal gånger hålet och sponsorn har visats – inte antal personer.
Tee-skylten är en uppskattning: klubbens ronder {r.sasong} × andelen ronder som spelar hålet.
{_e(bildmark)}</div>
</body></html>"""
