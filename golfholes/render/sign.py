"""Hålsponsorskylt 70 × 100 cm i tre plattor.

1. Rubrikplatta  – "[Sponsor]-hålet" + hål och klubb. Byts när sponsorn byts.
2. Hålguide      – hålbild, längder, avstånd, "Så spelar du hålet". Byts aldrig.
3. Sponsorplatta – logga i en färg, QR-kod, webbadress. Byts årligen.

Måtten nedan är utgångsläge tills Ecosign lämnat sin tryckspecifikation.
Ger: en förhandsvisning av hela skylten + en tryck-PDF per platta (med utfall).
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..hole import Hole
from ..qr import qr_svg
from .flat import PALETTE, render_flat

ATTRIBUTION = "Underlag: Ortofoto och Markhöjdmodell ©Lantmäteriet, bearbetat, CC BY 4.0"


@dataclass
class SignSpec:
    width_mm: float = 700
    header_mm: float = 150
    guide_mm: float = 640
    sponsor_mm: float = 190
    gap_mm: float = 10          # synligt mellanrum mellan plattorna i ramen
    bleed_mm: float = 3         # utfall per kant i tryckfilen


# Stil "Nordisk": typsnitt med reserver som finns på de flesta datorer.
SERIF = "'Cormorant Garamond', 'Lora', 'Georgia', serif"
SANS = "'Inter', 'Helvetica Neue', 'Arial', sans-serif"
INK = "#3f4a3c"
SOFT = "#6b7565"
PAPER = PALETTE["paper"]


def _e(s) -> str:
    return html.escape(str(s))


def _css(spec: SignSpec) -> str:
    return f"""
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:{PAPER};color:{INK};font-family:{SANS}}}
    .plate{{width:{spec.width_mm}mm;background:{PAPER};position:relative;overflow:hidden}}
    .header{{height:{spec.header_mm}mm;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5mm}}
    .header h1{{font-family:{SERIF};font-style:italic;font-weight:500;font-size:34mm;line-height:1;letter-spacing:-0.3mm}}
    .rule{{width:420mm;border-top:0.5mm solid {SOFT};opacity:.6}}
    .caps{{font-size:9mm;letter-spacing:2.2mm;text-transform:uppercase;color:{SOFT}}}
    .guide{{height:{spec.guide_mm}mm;display:flex;padding:22mm 26mm 18mm 26mm;gap:20mm}}
    .holeimg{{flex:0 0 340mm;height:100%;display:flex;align-items:center;justify-content:center}}
    .holeimg svg{{width:100%;height:100%}}
    .col{{flex:1;display:flex;flex-direction:column;gap:12mm;padding-top:10mm}}
    .col h2{{font-family:{SERIF};font-style:italic;font-weight:500;font-size:34mm;line-height:1}}
    .par{{font-size:9mm;letter-spacing:1.4mm;color:{SOFT};text-transform:uppercase}}
    table{{border-collapse:collapse;font-size:11mm;width:100%}}
    td{{padding:3mm 0;border-bottom:0.4mm solid #d9d4c4}}
    td.n{{text-align:right;font-variant-numeric:tabular-nums}}
    h3{{font-size:7.5mm;letter-spacing:1.6mm;text-transform:uppercase;color:{SOFT};font-weight:600;margin-bottom:1mm}}
    .tip{{font-family:{SERIF};font-size:11mm;line-height:1.3;margin-top:3mm}}
    .tip b{{font-style:italic}}
    .attr{{position:absolute;left:26mm;bottom:6mm;font-size:4.5mm;color:{SOFT}}}
    .sponsor{{height:{spec.sponsor_mm}mm;display:flex;align-items:center;justify-content:space-between;padding:0 40mm}}
    .sp-left{{display:flex;flex-direction:column;align-items:center;gap:6mm;flex:1}}
    .logo{{height:70mm;width:360mm;display:flex;align-items:center;justify-content:center}}
    .logo .name{{font-family:{SANS};font-weight:800;font-size:40mm;letter-spacing:1mm;color:{INK}}}
    .logo img{{max-height:100%;max-width:100%}}
    .url{{font-size:9mm;color:{SOFT}}}
    .qr{{display:flex;flex-direction:column;align-items:center;gap:4mm}}
    .qrbox{{width:125mm;height:125mm;background:#fff;padding:6mm}}
    .qrbox svg{{width:100%;height:100%;display:block}}
    .qrlabel{{font-size:7.5mm;letter-spacing:1mm;color:{SOFT}}}
    """


def _header(hole: Hole, club: dict, sponsor: dict | None) -> str:
    title = f"{sponsor['name']}-hålet" if sponsor and sponsor.get("naming_rights") else f"Hål {hole.number}"
    return (f'<div class="plate header"><h1>{_e(title)}</h1><div class="rule"></div>'
            f'<div class="caps">Hål {hole.number} · {_e(club["club"])}</div></div>')


def _guide(hole: Hole) -> str:
    back = hole.tee()
    tees = sorted(hole.tees, key=lambda t: -(t.length_m or 0))
    tee_rows = "".join(f'<tr><td>Tee {_e(t.name)}</td><td class="n">{_e(t.length_m)} m</td></tr>' for t in tees)
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
    svg = render_flat(hole, width_px=600, fit=True, fade=True)
    index = f" · Index {hole.index}" if hole.index else ""
    return (f'<div class="plate guide"><div class="holeimg">{svg}</div><div class="col">'
            f'<h2>Hål {hole.number}</h2><div class="par">Par {hole.par}{index}</div>'
            f'<table>{tee_rows}</table>'
            f'<div><h3>Avstånd från tee {_e(back.name)}</h3><table>{dist_rows}</table></div>'
            f'{tips}</div><div class="attr">{_e(ATTRIBUTION)}</div></div>')


def _sponsor(hole: Hole, club: dict, sponsor: dict | None, base: Path) -> tuple[str, bool]:
    url = f"{club.get('web_base', '').rstrip('/')}/hal-{hole.number:02d}"
    qr, real = qr_svg(url)
    if sponsor and sponsor.get("logo"):
        logo_svg = (base / sponsor["logo"]).read_text(encoding="utf-8")
        logo = logo_svg
    elif sponsor:
        logo = f'<div class="name">{_e(sponsor["name"].upper())}</div>'
    else:
        logo = '<div class="name" style="opacity:.35">DIN LOGGA HÄR</div>'
    site = _e(sponsor.get("url", "")) if sponsor else ""
    return (f'<div class="plate sponsor"><div class="sp-left"><div class="caps">Hålsponsor</div>'
            f'<div class="logo">{logo}</div><div class="url">{site}</div></div>'
            f'<div class="qr"><div class="qrbox">{qr}</div><div class="qrlabel">Flyg genom hålet</div></div></div>'), real


def build_sign(hole_file: str | Path, out_dir: str | Path, spec: SignSpec | None = None, pdf: bool = True) -> dict:
    """Bygger förhandsvisning (PNG) och tryckfiler (PDF per platta)."""
    from .export import to_pdf, to_png

    spec = spec or SignSpec()
    hole_file = Path(hole_file)
    base = hole_file.parent
    hole = Hole.from_yaml(hole_file)
    club = yaml.safe_load((base / "klubb.yaml").read_text(encoding="utf-8"))
    sponsor = (club.get("sponsors") or {}).get(hole.number)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    header, guide = _header(hole, club, sponsor), _guide(hole)
    sponsor_html, qr_real = _sponsor(hole, club, sponsor, base)
    css = _css(spec)

    # Förhandsvisning: tre plattor i en mörk ram, i skala.
    frame = 24
    preview = f"""<!doctype html><html><head><meta charset="utf-8"><style>{css}
      body{{background:#2b2f2a;padding:{frame}mm;width:{spec.width_mm + 2 * frame}mm}}
      .stack{{display:flex;flex-direction:column;gap:{spec.gap_mm}mm;background:#2b2f2a}}
      .plate{{box-shadow:0 0 0 1.2mm #c9b88f}}</style></head>
      <body><div class="stack">{header}{guide}{sponsor_html}</div></body></html>"""
    total_mm = spec.header_mm + spec.guide_mm + spec.sponsor_mm + 2 * spec.gap_mm + 2 * frame
    css_px_per_mm = 96 / 25.4  # så räknar webbläsaren mm
    files = {"forhandsvisning": to_png(preview, out / f"skylt-hal-{hole.number:02d}.png",
                                       (spec.width_mm + 2 * frame) * css_px_per_mm, total_mm * css_px_per_mm,
                                       scale=0.35)}  # ca 1 000 px bred förhandsvisning

    if pdf:
        b = spec.bleed_mm
        for name, part, h in (("1-rubrik", header, spec.header_mm), ("2-halguide", guide, spec.guide_mm),
                              ("3-sponsor", sponsor_html, spec.sponsor_mm)):
            page = f"""<!doctype html><html><head><meta charset="utf-8"><style>{css}
              body{{padding:{b}mm;width:{spec.width_mm + 2 * b}mm;height:{h + 2 * b}mm}}</style></head>
              <body>{part}</body></html>"""
            files[name] = to_pdf(page, out / f"hal-{hole.number:02d}-{name}.pdf", spec.width_mm + 2 * b, h + 2 * b)
    files["qr_akta"] = qr_real
    return files
