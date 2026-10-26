"""Hålsponsorskylt 70 × 100 cm i tre plattor – i klubbens stil (golfholes/stilar.py).

Skylten ritas tills vidare med en av de fyra kodritade ritmotorerna (THEMES 1–4), vald efter
klubbens stil (`Stil.ritmotor`). De är inte längre ett val för klubben.

1. Rubrikplatta  – "[Sponsor]-hålet" + hål och klubb. Byts när sponsorn byts.
2. Hålguide      – hålbild, längder, avstånd, "Så spelar du hålet". Byts aldrig.
3. Sponsorplatta – logga i en färg, QR-kod, webbadress. Byts årligen.

Stilarna (samma data, olika utseende):
  1 Signatur  – foto ovanifrån, mörk träram, linnefärgad bakgrund, klubbmärke i rubriken
  2 Klassisk  – akvarell, ljus ekram, mörkgrön kursiv antikva med eklöv
  3 Arv       – gravyr på pergament, valnötsram med guldlist, kartusch runt rubriken
  4 Nordisk   – mjuk illustration, smal svart ram, stor hålsiffra, guldbrun antikva

Måtten nedan är utgångsläge tills Ecosign lämnat sin tryckspecifikation.
Ger: en förhandsvisning av hela skylten + en tryck-PDF per platta (med utfall).
"""
from __future__ import annotations

import html
import math
import random
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..hole import Hole
from ..qr import qr_svg
from ..statistik import qr_lank
from .styles import make_view, render_green, render_hole, scope_ids

ATTRIBUTION = "Underlag: Ortofoto och Markhöjdmodell ©Lantmäteriet, bearbetat, CC BY 4.0"


@dataclass
class SignSpec:
    width_mm: float = 700
    header_mm: float = 150
    guide_mm: float = 640
    sponsor_mm: float = 190
    gap_mm: float = 10          # synligt mellanrum mellan plattorna i ramen
    bleed_mm: float = 3         # utfall per kant i tryckfilen


SERIF = "'Cormorant Garamond', 'Lora', 'Georgia', serif"
OLD_SERIF = "'IM Fell English', 'Baskerville', 'GFS Baskerville', 'Lora', serif"
SANS = "'Inter', 'Helvetica Neue', 'Arial', sans-serif"
CONDENSED = "'Avenir Next Condensed', 'Oswald', 'DejaVu Sans Condensed', 'Inter', sans-serif"


@dataclass(frozen=True)
class Theme:
    style: int
    paper: str            # plattornas bakgrund
    ink: str              # text och logga
    soft: str             # sekundär text
    accent: str           # rubrikfärg
    line: str             # tabellinjer
    title_font: str
    title_italic: bool
    title_caps: bool
    frame: str            # ramens färg/textur (bara i förhandsvisningen – ramen är Ecosigns)
    frame_line: str       # list innanför ramen
    frame_mm: float


THEMES = {
    1: Theme(1, "#ece6d8", "#2b2a27", "#6d685d", "#2b2a27", "#cfc6b2", CONDENSED, False, True,
             "repeating-linear-gradient(90deg,#3a271b 0 3mm,#432e20 3mm 5mm,#35241a 5mm 9mm)", "#1f150f", 28),
    2: Theme(2, "#fbfaf6", "#2f4a35", "#62705f", "#2f4a35", "#dcd9cc", SERIF, True, False,
             "repeating-linear-gradient(90deg,#cdae80 0 4mm,#d6b98c 4mm 6mm,#c7a676 6mm 11mm)", "#b8955f", 26),
    3: Theme(3, "#f1e5c9", "#4a3426", "#7a6250", "#4a3426", "#cdb98f", OLD_SERIF, False, False,
             "repeating-linear-gradient(90deg,#4a2f1f 0 3mm,#55372a 3mm 5mm,#432a1c 5mm 9mm)", "#c9a85a", 30),
    4: Theme(4, "#f7f5ef", "#2e2e2b", "#77736a", "#8a6a3a", "#dedad0", SERIF, False, False,
             "#1b1b1a", "#1b1b1a", 10),
}


def _e(s) -> str:
    return html.escape(str(s))


def _css(spec: SignSpec, t: Theme) -> str:
    title_case = "uppercase" if t.title_caps else "none"
    return f"""
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:{t.paper};color:{t.ink};font-family:{SANS}}}
    .plate{{width:{spec.width_mm}mm;background:{t.paper};position:relative;overflow:hidden}}
    .title{{font-family:{t.title_font};font-style:{'italic' if t.title_italic else 'normal'};text-transform:{title_case};
            color:{t.accent};font-weight:{600 if t.title_caps else 500};line-height:1}}
    .caps{{font-size:9mm;letter-spacing:2.2mm;text-transform:uppercase;color:{t.soft}}}
    .header{{height:{spec.header_mm}mm;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5mm}}
    .header .title{{font-size:{30 if t.title_caps else 34}mm;letter-spacing:{'1.5mm' if t.title_caps else '-0.3mm'}}}
    .rule{{width:420mm;border-top:0.5mm solid {t.soft};opacity:.6}}
    .guide{{height:{spec.guide_mm}mm;display:flex;padding:22mm 26mm 18mm 26mm;gap:18mm}}
    .holeimg{{flex:0 0 350mm;height:100%;display:flex;align-items:center;justify-content:center;position:relative}}
    .holeimg>svg{{width:100%;height:100%}}
    .holeimg>svg.north{{position:absolute;right:4mm;top:4mm;width:22mm;height:30mm}}
    .col{{flex:1;display:flex;flex-direction:column;gap:9mm;padding-top:6mm}}
    .col .title{{font-size:30mm}}
    .numeral{{font-family:{SERIF};font-size:120mm;line-height:.8;color:{t.accent};font-weight:400}}
    .par{{font-size:9mm;letter-spacing:1.4mm;color:{t.soft};text-transform:uppercase}}
    table{{border-collapse:collapse;font-size:10.5mm;width:100%}}
    td{{padding:2.6mm 0;border-bottom:0.4mm solid {t.line}}}
    td.n{{text-align:right;font-variant-numeric:tabular-nums}}
    h3{{font-size:7mm;letter-spacing:1.6mm;text-transform:uppercase;color:{t.soft};font-weight:600;margin-bottom:1mm}}
    .tip{{font-family:{SERIF};font-size:10.5mm;line-height:1.25;margin-top:2.5mm}}
    .tip b{{font-style:italic}}
    .greenbox{{margin-top:auto;display:flex;align-items:center;gap:6mm}}
    .greenbox svg{{width:78mm;height:78mm;flex:0 0 78mm}}
    .greenbox .caps{{font-size:6.5mm;letter-spacing:1.4mm}}
    .attr{{position:absolute;left:26mm;bottom:6mm;font-size:4.5mm;color:{t.soft}}}
    .sponsor{{height:{spec.sponsor_mm}mm;display:flex;align-items:center;justify-content:space-between;padding:0 40mm}}
    .sp-left{{display:flex;flex-direction:column;align-items:center;gap:6mm;flex:1}}
    .logo{{height:70mm;width:360mm;display:flex;align-items:center;justify-content:center;color:{t.ink}}}
    .logo svg{{max-height:100%;max-width:100%}}
    .logo svg *{{fill:{t.ink} !important;stroke:none}}  /* loggan alltid i en färg */
    .logo .name{{font-family:{t.title_font if t.style != 4 else SANS};font-weight:700;font-size:40mm;letter-spacing:1mm}}
    .url{{font-size:9mm;color:{t.soft}}}
    .qr{{display:flex;flex-direction:column;align-items:center;gap:4mm}}
    .qrbox{{width:125mm;height:125mm;background:#fff;padding:6mm}}
    .qrbox svg{{width:100%;height:100%;display:block}}
    .qrlabel{{font-size:7.5mm;letter-spacing:1mm;color:{t.soft}}}
    /* stil 1: klubbmärke till vänster i rubriken */
    .header.emblem{{flex-direction:row;justify-content:flex-start;gap:16mm;padding:0 40mm}}
    .header.emblem .txt{{display:flex;flex-direction:column;gap:5mm}}
    .header.emblem .rule{{width:100%}}
    .emb{{width:105mm;height:105mm;flex:0 0 105mm}}
    .emb svg{{width:100%;height:100%}}
    /* stil 3: pergament med ojämna kanter och kartusch */
    .sheet{{position:absolute;inset:7mm;background:{t.paper}}}
    .s3 .plate{{background:#d8c398}}
    .s3 .plate>*:not(.sheet):not(.cartouche):not(.attr){{position:relative}}
    .s3 .attr{{z-index:1}}
    .cartouche{{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:600mm;height:120mm}}
    """


# ---------------------------------------------------------------- ornament
def _emblem(club: dict, base: Path, t: Theme) -> str:
    """Klubbens märke om det finns (klubb.yaml: logo), annars en rund platshållare med initialer."""
    if club.get("logo") and (base / club["logo"]).exists():
        return (base / club["logo"]).read_text(encoding="utf-8")
    initials = "".join(w[0] for w in club["club"].replace("Golfklubb", "GK").split() if w[:1].isalpha())[:3].upper()
    return (f'<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="47" fill="none" stroke="{t.ink}" stroke-width="2.5"/>'
            f'<circle cx="50" cy="50" r="40" fill="none" stroke="{t.ink}" stroke-width=".8"/>'
            f'<text x="50" y="58" text-anchor="middle" font-family="{SERIF}" font-size="24" fill="{t.ink}">{_e(initials)}</text></svg>')


def _oak_leaf(color: str) -> str:
    return (f'<svg viewBox="0 0 120 40" style="width:60mm;height:20mm">'
            f'<path d="M5 20 H45 M75 20 H115" stroke="{color}" stroke-width="1" opacity=".6"/>'
            f'<path d="M60 4 C55 8 52 10 54 14 C49 13 47 16 50 19 C46 20 46 24 51 25 C48 28 50 32 55 30 C56 34 58 36 60 37 '
            f'C62 36 64 34 65 30 C70 32 72 28 69 25 C74 24 74 20 70 19 C73 16 71 13 66 14 C68 10 65 8 60 4Z" fill="{color}" opacity=".85"/>'
            f'<path d="M60 8 V38" stroke="#fbfaf6" stroke-width=".8"/></svg>')


def _cartouche(color: str) -> str:
    """Ornamental kartusch (ram med rullade ändar) bakom rubriken i stil 3."""
    return (f'<svg class="cartouche" viewBox="0 0 600 120" preserveAspectRatio="none">'
            f'<g fill="none" stroke="{color}">'
            f'<path d="M60 12 H540 Q560 12 566 30 Q590 30 590 60 Q590 90 566 90 Q560 108 540 108 H60 Q40 108 34 90 Q10 90 10 60 Q10 30 34 30 Q40 12 60 12Z" stroke-width="2"/>'
            f'<path d="M66 20 H534 Q550 20 554 36 Q578 38 578 60 Q578 82 554 84 Q550 100 534 100 H66 Q50 100 46 84 Q22 82 22 60 Q22 38 46 36 Q50 20 66 20Z" stroke-width=".8"/>'
            f'<path d="M34 30 Q46 46 34 60 Q46 74 34 90 M566 30 Q554 46 566 60 Q554 74 566 90" stroke-width="1.2"/>'
            f'<circle cx="300" cy="12" r="4" fill="{color}"/><circle cx="300" cy="108" r="4" fill="{color}"/></g></svg>')


def _north_arrow(angle_deg: float, color: str) -> str:
    """Liten nordpil, vriden så att den pekar mot verklig norr i den roterade hålbilden."""
    return (f'<svg class="north" viewBox="0 0 40 56"><g transform="rotate({-angle_deg:.1f} 20 30)">'
            f'<path d="M20 8 L28 40 L20 33 L12 40Z" fill="{color}"/></g>'
            f'<text x="20" y="7" text-anchor="middle" font-size="9" font-family="{SANS}" fill="{color}">N</text></svg>')


def _torn_edge(seed: int) -> str:
    """Clip-path med ojämna, rivna kanter för pergamentet i stil 3."""
    rnd = random.Random(seed)
    pts = []
    for side in range(4):
        for i in range(40):
            f = i / 40 * 100
            j = rnd.uniform(0, 1.2)
            pts.append({0: (f, j), 1: (100 - j, f), 2: (100 - f, 100 - j), 3: (j, 100 - f)}[side])
    return "polygon(" + ",".join(f"{x:.2f}% {y:.2f}%" for x, y in pts) + ")"


# ---------------------------------------------------------------- plattor
def _wrap(t: Theme, cls: str, inner: str, seed: int) -> str:
    sheet = f'<div class="sheet" style="clip-path:{_torn_edge(seed)}"></div>' if t.style == 3 else ""
    return f'<div class="plate {cls}">{sheet}{inner}</div>'


def _header(hole: Hole, club: dict, sponsor: dict | None, t: Theme, base: Path) -> str:
    title = f"{sponsor['name']}-hålet" if sponsor and sponsor.get("naming_rights") else f"Hål {hole.number}"
    sub = f'<div class="caps">Hål {hole.number} · {_e(club["club"])}</div>'
    h1 = f'<h1 class="title">{_e(title)}</h1>'
    if t.style == 1:
        inner = f'<div class="emb">{_emblem(club, base, t)}</div><div class="txt">{h1}<div class="rule"></div>{sub}</div>'
        return _wrap(t, "header emblem", inner, 1)
    if t.style == 2:
        return _wrap(t, "header", f'{h1}{_oak_leaf(t.accent)}{sub}', 1)
    if t.style == 3:
        return _wrap(t, "header", f'{_cartouche(t.ink)}{h1}{sub}', 1)
    return _wrap(t, "header", f'{h1}<div class="rule"></div>{sub}', 1)


def _guide(hole: Hole, t: Theme) -> str:
    back = hole.tee()
    tees = sorted(hole.tees, key=lambda x: -(x.length_m or 0))
    tee_rows = "".join(f'<tr><td>Tee {_e(x.name)}</td><td class="n">{_e(x.length_m)} m</td></tr>' for x in tees)
    dist_rows = "".join(
        f'<tr><td>{_e(r["typ"] if not r["namn"] else r["namn"])}, {_e(r["sida"])}</td>'
        f'<td class="n">{r["till"]}–{r["carry"]} m</td></tr>'
        for r in hole.hazard_distances(back.name)
    )
    gd = hole.green_distances(back.name)
    dist_rows += f'<tr><td>Green fram / mitt / bak</td><td class="n">{gd["fram"]:.0f} / {gd["mitt"]:.0f} / {gd["bak"]:.0f} m</td></tr>'
    tips = ""
    if hole.strategy:
        tips = '<div><h3>Så spelar du hålet</h3>' + "".join(
            f'<p class="tip"><b>{_e(k.capitalize())}</b> – {_e(v)}</p>' for k, v in hole.strategy.items()
        ) + "</div>"
    svg = scope_ids(render_hole(hole, t.style, width_px=600), "h")
    green = scope_ids(render_green(hole, t.style, size_px=300), "g")
    north = _north_arrow(make_view(hole, back, 600).angle, t.ink) if t.style in (1, 2, 4) else ""  # Arv har kompassros
    index = f" · Index {hole.index}" if hole.index else ""
    heading = (f'<div class="numeral">{hole.number}</div>' if t.style == 4
               else f'<h2 class="title">Hål {hole.number}</h2>')
    inner = (f'<div class="holeimg">{svg}{north}</div><div class="col">'
             f'{heading}<div class="par">Par {hole.par}{index}</div>'
             f'<table>{tee_rows}</table>'
             f'<div><h3>Avstånd från tee {_e(back.name)}</h3><table>{dist_rows}</table></div>'
             f'{tips}<div class="greenbox">{green}<div class="caps">Green</div></div></div>'
             f'<div class="attr">{_e(ATTRIBUTION)}</div>')
    return _wrap(t, "guide", inner, 2)


def _sponsor(hole: Hole, club: dict, sponsor: dict | None, base: Path, t: Theme) -> tuple[str, bool]:
    url = qr_lank(club, hole.number)  # /hal-NN/?q=hNN – räknas som QR-besök i sponsorrapporten
    qr, real = qr_svg(url)
    if sponsor and sponsor.get("logo"):
        logo = (base / sponsor["logo"]).read_text(encoding="utf-8")
    elif sponsor:
        logo = f'<div class="name">{_e(sponsor["name"].upper())}</div>'
    else:
        logo = '<div class="name" style="opacity:.35">DIN LOGGA HÄR</div>'
    site = _e(sponsor.get("url", "")) if sponsor else ""
    inner = (f'<div class="sp-left"><div class="caps">Hålsponsor</div>'
             f'<div class="logo">{logo}</div><div class="url">{site}</div></div>'
             f'<div class="qr"><div class="qrbox">{qr}</div><div class="qrlabel">Flyg genom hålet</div></div>')
    return _wrap(t, "sponsor", inner, 3), real


def club_style(club: dict):
    """Klubbens stil i klubb.yaml (ett av de sex namnen; gamla 1–4 läses med varning)."""
    from ..stilar import las_stil

    return las_stil(club.get("stil", club.get("style")))


def build_sign(hole_file: str | Path, out_dir: str | Path, spec: SignSpec | None = None, pdf: bool = True,
               style: int | str | None = None) -> dict:
    """Bygger förhandsvisning (PNG) och tryckfiler (PDF per platta) i vald stil.

    `style` = None → klubbens val i klubb.yaml. Annars ett stilnamn (t.ex. "Gravyr").
    """
    from ..stilar import las_stil
    from .export import to_pdf, to_png

    spec = spec or SignSpec()
    hole_file = Path(hole_file)
    base = hole_file.parent
    hole = Hole.from_yaml(hole_file)
    club = yaml.safe_load((base / "klubb.yaml").read_text(encoding="utf-8"))
    stil = las_stil(style) if style is not None else club_style(club)
    st = stil.ritmotor
    t = THEMES[st]
    sponsor = (club.get("sponsors") or {}).get(hole.number)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    header, guide = _header(hole, club, sponsor, t, base), _guide(hole, t)
    sponsor_html, qr_real = _sponsor(hole, club, sponsor, base, t)
    css = _css(spec, t)
    body_cls = f"s{st}"

    # Förhandsvisning: tre plattor i stilens ram, i skala.
    f = t.frame_mm
    preview = f"""<!doctype html><html><head><meta charset="utf-8"><style>{css}
      body{{background:{t.frame};padding:{f}mm;width:{spec.width_mm + 2 * f}mm}}
      .stack{{display:flex;flex-direction:column;gap:{spec.gap_mm}mm;outline:1.2mm solid {t.frame_line};outline-offset:3mm}}
      </style></head><body class="{body_cls}"><div class="stack">{header}{guide}{sponsor_html}</div></body></html>"""
    total_mm = spec.header_mm + spec.guide_mm + spec.sponsor_mm + 2 * spec.gap_mm + 2 * f
    css_px_per_mm = 96 / 25.4  # så räknar webbläsaren mm
    name = stil.nyckel
    files = {"stil": stil.namn,
             "forhandsvisning": to_png(preview, out / f"skylt-hal-{hole.number:02d}-{name}.png",
                                       (spec.width_mm + 2 * f) * css_px_per_mm, total_mm * css_px_per_mm,
                                       scale=0.35)}  # ca 1 000 px bred förhandsvisning

    if pdf:
        b = spec.bleed_mm
        for pname, part, h in (("1-rubrik", header, spec.header_mm), ("2-halguide", guide, spec.guide_mm),
                               ("3-sponsor", sponsor_html, spec.sponsor_mm)):
            page = f"""<!doctype html><html><head><meta charset="utf-8"><style>{css}
              body{{padding:{b}mm;width:{spec.width_mm + 2 * b}mm;height:{h + 2 * b}mm;background:{t.paper}}}</style></head>
              <body class="{body_cls}">{part}</body></html>"""
            files[pname] = to_pdf(page, out / f"hal-{hole.number:02d}-{name}-{pname}.pdf", spec.width_mm + 2 * b, h + 2 * b)
    files["qr_akta"] = qr_real
    return files
