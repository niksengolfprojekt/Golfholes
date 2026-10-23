"""Digital banguide: en mobilsida per hål + en översikt per klubb.

QR-koden på skylten pekar på hålets sida. Sidan visar sponsorn först,
låter golfaren välja tee och visar flygfilmen från den teen.
Filmerna läggs som `film-tee-<namn>.mp4` i hålets mapp när de är renderade.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import yaml

from ..hole import Hole
from .flat import render_flat
from ..statistik import matkod
from .sign import ATTRIBUTION

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{--paper:#f4f1e8;--ink:#2f3a2d;--soft:#6b7565;--line:#ddd7c6;--accent:#4f7a3f}
body{background:var(--paper);color:var(--ink);font-family:Inter,'Helvetica Neue',Arial,sans-serif;line-height:1.45}
main{max-width:640px;margin:0 auto;padding:16px 16px 48px}
.sponsor{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:#fff;margin-bottom:18px}
.sponsor small{color:var(--soft);letter-spacing:.12em;text-transform:uppercase;font-size:11px}
.sponsor strong{font-size:18px}
.sponsor a{color:var(--accent);font-weight:600;text-decoration:none;white-space:nowrap}
h1{font-family:'Cormorant Garamond',Lora,Georgia,serif;font-style:italic;font-weight:500;font-size:40px;line-height:1.05}
.meta{color:var(--soft);letter-spacing:.14em;text-transform:uppercase;font-size:12px;margin:4px 0 16px}
.tees{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.tees button{font:inherit;font-weight:600;border:1px solid var(--line);background:#fff;border-radius:999px;padding:8px 16px;cursor:pointer}
.tees button[aria-pressed=true]{background:var(--ink);color:#fff;border-color:var(--ink)}
.film{aspect-ratio:16/9;background:#dfe6d2;border-radius:12px;display:flex;align-items:center;justify-content:center;color:var(--soft);font-size:14px;overflow:hidden;margin-bottom:18px}
.film video{width:100%;height:100%;object-fit:cover}
.grid{display:grid;grid-template-columns:1fr;gap:18px}
@media(min-width:560px){.grid{grid-template-columns:45% 1fr}}
.hole svg{width:100%;height:auto;max-height:70vh;display:block}
table{width:100%;border-collapse:collapse;font-size:15px}
td{padding:7px 0;border-bottom:1px solid var(--line)}
td:last-child{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
h2{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--soft);margin:16px 0 4px}
.tip{font-family:Lora,Georgia,serif;margin-top:6px}
footer{margin-top:28px;font-size:11px;color:var(--soft)}
nav a{color:var(--accent);text-decoration:none;font-weight:600}
.list a{display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--line);color:var(--ink);text-decoration:none}
"""

JS = """
const data=JSON.parse(document.getElementById('d').textContent);
const rows=document.getElementById('rows'), film=document.getElementById('film'), lbl=document.getElementById('lbl');
function show(t){
  document.querySelectorAll('.tees button').forEach(b=>b.setAttribute('aria-pressed', b.dataset.t===t));
  const d=data.tees[t]; lbl.textContent=t;
  rows.innerHTML=d.rows.map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`).join('');
  film.innerHTML=`<video src="film-tee-${t}.mp4" controls playsinline muted autoplay onerror="this.parentNode.textContent='Flygfilmen från tee ${t} kommer snart'"></video>`;
}
document.querySelectorAll('.tees button').forEach(b=>b.onclick=()=>show(b.dataset.t));
show(data.default);
"""


def _e(s) -> str:
    return html.escape(str(s))


def _tee_rows(hole: Hole, tee_name: str) -> list[list[str]]:
    rows = [[f'{r["namn"] or r["typ"]}, {r["sida"]}', f'{r["till"]}–{r["carry"]} m'] for r in hole.hazard_distances(tee_name)]
    gd = hole.green_distances(tee_name)
    rows.append(["Green fram / mitt / bak", f'{gd["fram"]:.0f} / {gd["mitt"]:.0f} / {gd["bak"]:.0f} m'])
    return rows


def hole_page(hole: Hole, club: dict) -> str:
    sponsor = (club.get("sponsors") or {}).get(hole.number)
    back = hole.tee()
    tees = sorted(hole.tees, key=lambda t: -(t.length_m or 0))
    data = {"default": back.name, "tees": {t.name: {"rows": _tee_rows(hole, t.name)} for t in tees}}
    sp = ""
    if sponsor:
        url = sponsor.get("url", "")
        link = (f'<a href="https://{_e(url)}" rel="sponsored" data-hal="h{hole.number:02d}">Besök →</a>'
                if url else "")
        sp = (f'<div class="sponsor"><div><small>Hål {hole.number} sponsras av</small><br>'
              f'<strong>{_e(sponsor["name"])}</strong></div>{link}</div>')
    title = f'{sponsor["name"]}-hålet' if sponsor and sponsor.get("naming_rights") else f"Hål {hole.number}"
    tips = "".join(f'<p class="tip"><b><i>{_e(k.capitalize())}</i></b> – {_e(v)}</p>' for k, v in hole.strategy.items())
    tee_buttons = "".join(f'<button data-t="{_e(t.name)}">Tee {_e(t.name)} · {_e(t.length_m)} m</button>' for t in tees)
    index = f" · Index {hole.index}" if hole.index else ""
    return f"""<!doctype html><html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)} – {_e(club['club'])}</title><style>{CSS}</style>{matkod(club)}</head><body><main>
{sp}
<h1>{_e(title)}</h1><div class="meta">Hål {hole.number} · Par {hole.par}{index} · {_e(club['club'])}</div>
<div class="tees" role="group" aria-label="Välj tee">{tee_buttons}</div>
<div class="film" id="film"></div>
<div class="grid"><div class="hole">{render_flat(hole, width_px=420, fit=True, fade=True)}</div>
<div><h2>Avstånd från tee <span id="lbl"></span></h2><table id="rows"></table>
{'<h2>Så spelar du hålet</h2>' + tips if tips else ''}</div></div>
<footer><nav><a href="../">← Alla hål</a></nav><p style="margin-top:8px">{_e(ATTRIBUTION)}</p></footer>
</main><script type="application/json" id="d">{json.dumps(data, ensure_ascii=False)}</script><script>{JS}</script></body></html>"""


def club_page(club: dict, holes: list[Hole]) -> str:
    items = "".join(
        f'<a href="hal-{h.number:02d}/"><span>Hål {h.number}</span><span>Par {h.par} · {h.tee().length_m or ""} m</span></a>'
        for h in sorted(holes, key=lambda h: h.number)
    )
    return f"""<!doctype html><html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Banguide – {_e(club['club'])}</title>
<style>{CSS}</style></head><body><main><h1>{_e(club['club'])}</h1><div class="meta">Banguide</div>
<div class="list">{items}</div><footer><p>{_e(ATTRIBUTION)}</p></footer></main></body></html>"""


def build_site(club_dir: str | Path, out_dir: str | Path) -> list[Path]:
    club_dir, out = Path(club_dir), Path(out_dir)
    club = yaml.safe_load((club_dir / "klubb.yaml").read_text(encoding="utf-8"))
    holes = [Hole.from_yaml(p) for p in sorted(club_dir.glob("hal-*.yaml"))]
    written = []
    for h in holes:
        d = out / f"hal-{h.number:02d}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(hole_page(h, club), encoding="utf-8")
        written.append(d / "index.html")
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(club_page(club, holes), encoding="utf-8")
    written.append(out / "index.html")
    return written
