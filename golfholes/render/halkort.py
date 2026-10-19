"""Hålkort: den färdiga hålpresentationen, i en av klubbens valda layouter.

Varje layout är en fast mall: samma rutnät, typsnitt, storlekar och element för varje hål.
Det enda som ändras mellan hålen är innehållet i fälten (hålbild, siffror, texter).
Därför ser hål 1 och hål 18 alltid likadana ut, och klubben väljer layout en gång
med `layout:` i `klubb.yaml` (en siffra eller en lista om de köper flera).

  1 Hålkort    – SPIKAD (Eric 2026-10-16). Hålet till vänster, siffra och fakta till höger.
  2 Poster     – stort hål i mitten, stor antikvasiffra, längder i en rad längst ner.
  3 Mörk       – hålkortets rutnät på mörkgrön botten med mässingsdetaljer.
  4 Skärm      – liggande 16:9 för klubbhusskärm och webb, tre spalter.
  5 Banguide   – fickformat som en yardage book: Säkert/Chansa och rader för anteckningar.
  6 Sponsorhål – hålkortet med rubrik "[Sponsor]-hålet" och sponsorplatta.

Fälten har maxlängder (FIELD_LIMITS). `kontroll()` säger till om en text är för lång
för mallen, i stället för att mallen krymper texten och hålet ser annorlunda ut.
"""
from __future__ import annotations

import html
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
FONTS = ROOT / "assets" / "typsnitt"
ATTRIBUTION = "Underlag: Ortofoto och Markhöjdmodell ©Lantmäteriet, bearbetat, CC BY 4.0"
TYPBILD_NOTE = "Typbild som visar stilen. Färdigt material byggs på Lantmäteriets ortofoto och höjddata."

# Maxlängd per fält i tecken. Satt efter hål 14, den spikade layoutens referens, plus marginal.
FIELD_LIMITS = {"rubrik": 28, "beskrivning": 230, "rad": 520, "slutrad": 60, "sakert": 110, "chansa": 110}


@dataclass
class Sponsor:
    name: str
    url: str = ""
    logo: str | None = None   # SVG/PNG i en färg; saknas den sätts namnet som ordbild


@dataclass
class Halkort:
    club: str
    hole: int
    par: int
    index: int
    tees: list[tuple[str, int]]
    image: Path               # hålbild med genomskinlig bakgrund (PNG, RGBA)
    bana: str = ""
    rubrik: str = ""
    beskrivning: str = ""
    rad_rubrik: str = "Råd från pro:n"
    rad: list[str] = field(default_factory=list)
    slutrad: str = ""
    sakert: str = ""
    chansa: str = ""
    sponsor: Sponsor | None = None
    typbild: bool = False
    farg_mork: str = "#142219"   # bakgrund i mörk layout; klubbens mörkaste färg

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Halkort":
        path = Path(path)
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        sp = d.get("sponsor")
        return cls(
            club=d["club"], hole=int(d["hole"]), par=int(d["par"]), index=int(d["index"]),
            tees=[(str(t[0]), int(t[1])) for t in d["tees"]],
            image=(path.parent / d["bild"]).resolve(),
            bana=d.get("bana", ""), rubrik=d.get("rubrik", ""), beskrivning=d.get("beskrivning", ""),
            rad_rubrik=d.get("rad_rubrik", "Råd från pro:n"), rad=list(d.get("rad", [])),
            slutrad=d.get("slutrad", ""), sakert=d.get("strategi", {}).get("sakert", ""),
            chansa=d.get("strategi", {}).get("chansa", ""),
            sponsor=Sponsor(**sp) if sp else None, typbild=bool(d.get("typbild", False)),
            farg_mork=d.get("farg_mork", "#142219"),
        )

    def kontroll(self) -> list[str]:
        """Fält som inte ryms i mallen. Tom lista = allt ryms."""
        texts = {"rubrik": self.rubrik, "beskrivning": self.beskrivning, "rad": " ".join(self.rad),
                 "slutrad": self.slutrad, "sakert": self.sakert, "chansa": self.chansa}
        out = [f"{k}: {len(v)} tecken, mallen rymmer {FIELD_LIMITS[k]}"
               for k, v in texts.items() if len(v) > FIELD_LIMITS[k]]
        if not self.image.exists():
            out.append(f"bild saknas: {self.image}")
        if not 1 <= len(self.tees) <= 5:
            out.append(f"{len(self.tees)} tees, mallen rymmer 1–5")
        return out

    @property
    def credit(self) -> str:
        return TYPBILD_NOTE if self.typbild else ATTRIBUTION


def _e(s) -> str:
    return html.escape(str(s))


def _font_css() -> str:
    f = FONTS.as_uri()
    return f"""
@font-face{{font-family:'Cormorant Garamond';src:url('{f}/CormorantGaramond.ttf');font-weight:300 700}}
@font-face{{font-family:'Cormorant Garamond';src:url('{f}/CormorantGaramond-Italic.ttf');font-weight:300 700;font-style:italic}}
@font-face{{font-family:'DM Sans';src:url('{f}/DMSans.ttf');font-weight:100 1000}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{overflow:hidden}}
body{{-webkit-font-smoothing:antialiased;font-kerning:normal;text-rendering:geometricPrecision}}
body *{{font-variant-numeric:lining-nums!important}}
.hole{{position:absolute;background-repeat:no-repeat}}
"""


def _page(css: str, body: str, w: int, h: int) -> str:
    return (f"<!doctype html><html lang='sv'><head><meta charset='utf-8'><style>{_font_css()}"
            f"body{{width:{w}px;height:{h}px;position:relative}}{css}</style></head><body>{body}</body></html>")


def _hole(c: Halkort, x: int, y: int, w: int, h: int, pos: str = "left top", feather: bool = False) -> str:
    """Hålbilden inpassad i en ruta. Skalas, beskärs aldrig: hela hålet syns alltid.
    feather: tona ut bildens kanter, för layouter där hålet inte går ut i sidans kant."""
    from PIL import Image

    with Image.open(c.image) as im:
        iw, ih = im.size
    k = min(w / iw, h / ih)
    fw, fh = iw * k, ih * k
    hx, vy = (pos.split() + ["top"])[:2]
    fx = x + {"left": 0, "center": (w - fw) / 2, "right": w - fw}[hx]
    fy = y + {"top": 0, "center": (h - fh) / 2, "bottom": h - fh}[vy]
    mask = ""
    if feather:
        g = "linear-gradient(to right,transparent 0,#000 14%,#000 86%,transparent 100%)"
        mask = f"-webkit-mask-image:{g};mask-image:{g};"
    return (f"<div class='hole' style='left:{fx:.1f}px;top:{fy:.1f}px;width:{fw:.1f}px;height:{fh:.1f}px;{mask}"
            f"background-image:url(\"{c.image.as_uri()}\");background-size:100% 100%'></div>")


def _paras(items: list[str], cls: str = "") -> str:
    return "".join(f"<p class='{cls}'>{_e(t)}</p>" for t in items if t)


def _tee_rows(c: Halkort) -> str:
    return "".join(f"<tr><td class='tn'>{_e(n)}</td><td class='tl'>{m}&nbsp;m</td></tr>" for n, m in c.tees)


# ---------------------------------------------------------------- 1 Hålkort (spikad)
def layout_halkort(c: Halkort, dark: bool = False) -> tuple[str, int, int]:
    W, H = 848, 1264
    if dark:
        m = c.farg_mork
        bg = (f"radial-gradient(ellipse at 35% 45%,color-mix(in srgb,{m} 94%,#fff) 0%,{m} 70%,"
              f"color-mix(in srgb,{m} 80%,#000) 100%)")
        ink, body, head, rule, num = "#efe7d6", "rgba(239,231,214,.74)", "#c8a96b", "rgba(200,169,107,.55)", "#efe7d6"
        num_font = "'Cormorant Garamond',serif;font-weight:500"
        sans = "'DM Sans',sans-serif"
        caps = "letter-spacing:.16em"
        last = "#efe7d6"
    else:
        bg = "#fbf4ec"
        ink, body, head, rule, num = "#2d2a27", "#57524c", "#2d2a27", "#2d2a27", "#2d2a27"
        num_font = "'DejaVu Sans',sans-serif;font-weight:700"
        sans = "'DejaVu Sans',sans-serif"
        caps = "letter-spacing:.01em"
        last = "#2d2a27"
    sponsor_css = sponsor_html = top_css = top_html = ""
    if c.sponsor:
        top_html = f"<div class='hdr'>{_e(c.sponsor.name)}-hålet</div>"
        top_css = (f".hdr{{position:absolute;left:517px;width:300px;top:56px;text-align:center;font:600 15px {sans};"
                   f"letter-spacing:.24em;text-transform:uppercase;color:{head}}}")
        logo = (f"<img src='{Path(c.sponsor.logo).resolve().as_uri()}' style='max-width:180px;max-height:56px'>"
                if c.sponsor.logo else f"<div class='wm'>{_e(c.sponsor.name)}</div>")
        sponsor_html = (f"<div class='sp'><div class='spl'>Hålet presenteras av</div>{logo}"
                        f"<div class='spu'>{_e(c.sponsor.url)}</div></div>")
        sponsor_css = (f".sp{{position:absolute;left:517px;width:300px;bottom:70px;border-top:1px solid {rule};"
                       f"padding-top:22px;text-align:center}}"
                       f".spl{{font:500 12px {sans};letter-spacing:.2em;text-transform:uppercase;color:{body};margin-bottom:12px}}"
                       f".wm{{font:600 34px 'Cormorant Garamond',serif;letter-spacing:.14em;text-transform:uppercase;color:{ink}}}"
                       f".spu{{font:400 14px {sans};color:{body};margin-top:8px}}")
    pro = c.rad[:2] if c.sponsor else c.rad   # sponsorplattan tar plats: bara de två första råden
    css = f"""
body{{background:{bg}}}
.num{{position:absolute;left:517px;width:300px;top:{92 if c.sponsor else 98}px;text-align:center;font-family:{num_font};
  font-size:{160 if dark else 146}px;line-height:1;color:{num};letter-spacing:{'0' if dark else '-.01em'}}}
.par{{position:absolute;left:517px;width:300px;top:251px;text-align:center;font:700 29px {sans};color:{ink};
  text-transform:uppercase;{caps}}}
.tees{{position:absolute;left:517px;width:300px;top:302px;border-top:1px solid {rule};border-bottom:1px solid {rule};
  padding:11px 0 13px}}
.tees table{{margin:0 auto;border-collapse:collapse;font:400 20.5px {sans};color:{ink}}}
.tees td{{padding:0;line-height:1.54}}
.tn{{text-align:right;padding-right:14px!important;min-width:44px}}
.txt{{position:absolute;left:517px;width:300px;top:{450 if c.sponsor else 452}px;color:{body};font:400 17px/1.5 {sans}}}
.txt h2{{font:700 18px {sans};color:{head};text-transform:uppercase;{caps};margin-bottom:4px}}
.txt h2+p{{margin-top:0}}
.txt p{{margin-top:9px}}
.txt .blk{{margin-bottom:24px}}
.txt .last{{color:{last}}}
.cr{{position:absolute;left:34px;bottom:22px;font:400 10px {sans};color:{body};opacity:.75}}
{top_css}{sponsor_css}
"""
    body_html = f"""
{_hole(c, 0, 72, 600, 1060)}
{top_html}
<div class='num'>{c.hole}</div>
<div class='par'>Par {c.par} · Index {c.index}</div>
<div class='tees'><table>{_tee_rows(c)}</table></div>
<div class='txt'>
  <div class='blk'><h2>{_e(c.rubrik)}</h2><p>{_e(c.beskrivning)}</p></div>
  <div class='blk'><h2>{_e(c.rad_rubrik)}</h2>{_paras(pro)}{"" if c.sponsor else f"<p class='last'>{_e(c.slutrad)}</p>"}</div>
</div>
{sponsor_html}
<div class='cr'>{_e(c.credit)}</div>
"""
    return _page(css, body_html, W, H), W, H


# ---------------------------------------------------------------- 2 Poster
def layout_poster(c: Halkort) -> tuple[str, int, int]:
    W, H = 800, 1120
    cols = "".join(f"<div class='tc'><div class='tv'>{m}<span> m</span></div><div class='tk'>Tee {_e(n)}</div></div>"
                   for n, m in c.tees)
    css = """
body{background:#f6f0e5}
.club{position:absolute;left:0;right:0;top:46px;text-align:center;font:500 11.5px 'DM Sans';letter-spacing:.34em;
  text-transform:uppercase;color:#7a6e5f}
.num{position:absolute;left:60px;top:84px;font:300 230px/0.8 'Cormorant Garamond';color:#2b3a30;letter-spacing:-.02em}
.parx{position:absolute;left:66px;top:290px;font:italic 400 25px 'Cormorant Garamond';color:#5d5247}
.rub{position:absolute;left:0;right:0;top:902px;text-align:center;font:italic 400 31px 'Cormorant Garamond';color:#2b3a30}
.band{position:absolute;left:80px;right:80px;top:958px;border-top:1px solid #b9a988;display:flex;justify-content:center;gap:0}
.tc{flex:1;text-align:center;padding-top:20px;max-width:200px}
.tc+.tc{border-left:1px solid #d9cdb4}
.tv{font:500 38px/1 'Cormorant Garamond';color:#2b3a30}
.tv span{font-size:22px}
.tk{font:500 10.5px 'DM Sans';letter-spacing:.24em;text-transform:uppercase;color:#8a7d6b;margin-top:8px}
.cr{position:absolute;left:0;right:0;bottom:22px;text-align:center;font:400 9.5px 'DM Sans';color:#a3978a}
"""
    body = f"""
<div class='club'>{_e(c.club)}{(' · ' + _e(c.bana)) if c.bana else ''}</div>
{_hole(c, 196, 70, 520, 820, 'center top', feather=True)}
<div class='num'>{c.hole}</div>
<div class='parx'>Par {c.par} · Index {c.index}</div>
<div class='rub'>{_e(c.rubrik)}</div>
<div class='band'>{cols}</div>
<div class='cr'>{_e(c.credit)}</div>
"""
    return _page(css, body, W, H), W, H


# ---------------------------------------------------------------- 4 Skärm 16:9
def layout_skarm(c: Halkort) -> tuple[str, int, int]:
    W, H = 1920, 1080
    css = """
body{background:#f7f1e8}
.l{position:absolute;left:130px;top:150px;width:470px}
.club{font:500 15px 'DM Sans';letter-spacing:.3em;text-transform:uppercase;color:#7a6e5f}
.hal{font:500 16px 'DM Sans';letter-spacing:.3em;text-transform:uppercase;color:#7a6e5f;margin-top:64px}
.num{font:400 300px/0.78 'Cormorant Garamond';color:#24342a;margin-top:16px;letter-spacing:-.02em}
.parx{font:italic 400 36px 'Cormorant Garamond';color:#5d5247;margin-top:26px}
.tt{margin-top:44px;border-top:1px solid #b9a988;width:330px}
.tt div{display:flex;justify-content:space-between;padding:13px 0;border-bottom:1px solid #e0d6c3;
  font:400 28px 'Cormorant Garamond';color:#24342a}
.tt span{font:500 13px 'DM Sans';letter-spacing:.22em;text-transform:uppercase;color:#8a7d6b;align-self:center}
.r{position:absolute;left:1330px;top:138px;width:470px;color:#4f4942;font:400 21px/1.6 'DM Sans'}
.r h2{font:italic 400 42px/1.15 'Cormorant Garamond';color:#24342a;margin-bottom:18px}
.r h3{font:600 13.5px 'DM Sans';letter-spacing:.24em;text-transform:uppercase;color:#8a6a3a;margin:40px 0 10px}
.r p+p{margin-top:12px}
.cr{position:absolute;right:120px;bottom:40px;font:400 12px 'DM Sans';color:#a3978a}
"""
    teerows = "".join(f"<div><span>Tee {_e(n)}</span>{m} m</div>" for n, m in c.tees)
    body = f"""
<div class='l'><div class='club'>{_e(c.club)}</div><div class='hal'>Hål</div><div class='num'>{c.hole}</div>
<div class='parx'>Par {c.par} · Index {c.index}</div><div class='tt'>{teerows}</div></div>
{_hole(c, 690, 40, 580, 1000, 'center center', feather=True)}
<div class='r'><h2>{_e(c.rubrik)}</h2><p>{_e(c.beskrivning)}</p><h3>{_e(c.rad_rubrik)}</h3>{_paras(c.rad[:2])}</div>
<div class='cr'>{_e(c.credit)}</div>
"""
    return _page(css, body, W, H), W, H


# ---------------------------------------------------------------- 5 Banguide (fickformat)
def layout_banguide(c: Halkort) -> tuple[str, int, int]:
    W, H = 794, 1123
    pills = "".join(f"<div class='pill'><b>{_e(n)}</b>{m} m</div>" for n, m in c.tees)
    css = """
body{background:#faf6ee}
.top{position:absolute;left:0;right:0;top:0;height:150px;background:#1f3a2e;color:#f3ecdf}
.num{position:absolute;left:52px;top:18px;font:500 112px/1 'Cormorant Garamond';color:#f3ecdf}
.kv{position:absolute;left:200px;top:46px;display:flex;gap:34px}
.kv div{font:500 10.5px 'DM Sans';letter-spacing:.24em;text-transform:uppercase;color:#c8b48a}
.kv b{display:block;font:500 34px/1.1 'Cormorant Garamond';letter-spacing:0;color:#f3ecdf;margin-top:4px}
.pills{position:absolute;right:44px;top:50px;display:flex;flex-direction:column;gap:6px;align-items:flex-end}
.pill{font:400 14px 'DM Sans';color:#f3ecdf;border:1px solid rgba(243,236,223,.35);border-radius:20px;padding:3px 12px}
.pill b{font-weight:600;color:#c8b48a;margin-right:8px}
.club{position:absolute;left:52px;top:166px;font:500 10.5px 'DM Sans';letter-spacing:.28em;text-transform:uppercase;color:#8a7d6b}
.c{position:absolute;left:506px;top:214px;width:250px}
.c h2{font:italic 400 27px/1.15 'Cormorant Garamond';color:#1f3a2e;margin-bottom:12px}
.c .d{font:400 13.5px/1.6 'DM Sans';color:#4f4942}
.box{margin-top:24px;padding:16px 18px;border-radius:6px;font:400 13.5px/1.55 'DM Sans';color:#3e3a35}
.box h3{font:600 11px 'DM Sans';letter-spacing:.22em;text-transform:uppercase;margin-bottom:6px}
.s{background:#e6eddf}.s h3{color:#3f6b45}
.ch{background:#f3e5cf}.ch h3{color:#9a6328}
.notes{margin-top:30px}
.notes h3{font:600 11px 'DM Sans';letter-spacing:.22em;text-transform:uppercase;color:#8a7d6b;margin-bottom:4px}
.notes div{height:34px;border-bottom:1px solid #d9cdb4}
.cr{position:absolute;left:52px;bottom:20px;font:400 9px 'DM Sans';color:#a3978a}
"""
    body = f"""
<div class='top'><div class='num'>{c.hole}</div>
<div class='kv'><div>Par<b>{c.par}</b></div><div>Index<b>{c.index}</b></div></div>
<div class='pills'>{pills}</div></div>
<div class='club'>{_e(c.club)}</div>
{_hole(c, 22, 200, 470, 880, 'left top', feather=True)}
<div class='c'><h2>{_e(c.rubrik)}</h2><div class='d'>{_e(c.beskrivning)}</div>
<div class='box s'><h3>Säkert</h3>{_e(c.sakert)}</div>
<div class='box ch'><h3>Chansa</h3>{_e(c.chansa)}</div>
<div class='notes'><h3>Anteckningar</h3><div></div><div></div><div></div><div></div></div></div>
<div class='cr'>{_e(c.credit)}</div>
"""
    return _page(css, body, W, H), W, H


def _sponsorhal(c: Halkort):
    if c.sponsor is None:
        c = Halkort(**{**c.__dict__, "sponsor": Sponsor("Nordvik", "nordvik.se")})   # påhittad demosponsor
    return layout_halkort(c)


LAYOUTS = {
    1: ("Hålkort", layout_halkort),
    2: ("Poster", layout_poster),
    3: ("Mörk", lambda c: layout_halkort(c, dark=True)),
    4: ("Skärm", layout_skarm),
    5: ("Banguide", layout_banguide),
    6: ("Sponsorhål", _sponsorhal),
}


def parse_layout(v) -> list[int]:
    vals = v if isinstance(v, list) else [v]
    out = []
    for x in vals:
        if isinstance(x, str) and not x.isdigit():
            x = next(k for k, (n, _) in LAYOUTS.items() if n.lower() == x.lower())
        out.append(int(x))
    return out


def render_html(c: Halkort, layout: int) -> tuple[str, int, int]:
    return LAYOUTS[layout][1](c)


# ---------------------------------------------------------------- PNG
_CHROME_UI = 200   # extra fönsterhöjd som beskärs bort


def _chromium() -> str | None:
    for p in ("/opt/pw-browsers/chromium", shutil.which("chromium"), shutil.which("google-chrome"),
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if p and Path(p).exists():
            return p
    return None


def to_png(page: str, w: int, h: int, out: str | Path, scale: float = 2.0) -> Path:
    """HTML → PNG. Playwright om det finns (Macen), annars Chromium direkt."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        from .export import to_png as pw_png
        return pw_png(page, out, w, h, scale)
    except ImportError:
        pass
    chrome = _chromium()
    if not chrome:
        raise RuntimeError("Varken Playwright eller Chromium hittades – kan inte göra PNG.")
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "sida.html"
        src.write_text(page, encoding="utf-8")
        subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        "--allow-file-access-from-files", f"--force-device-scale-factor={scale}",
                        f"--window-size={w},{h + _CHROME_UI}", "--virtual-time-budget=4000",
                        f"--screenshot={out.resolve()}", src.as_uri()],
                       check=True, capture_output=True, timeout=120)
    # Chromium räknar fönsterhöjden inklusive en osynlig verktygsrad: beskär till exakt sidstorlek.
    from PIL import Image
    with Image.open(out) as im:
        im.crop((0, 0, round(w * scale), round(h * scale))).save(out)
    return out


def render(c: Halkort, layout: int, out: str | Path, scale: float = 2.0) -> Path:
    page, w, h = render_html(c, layout)
    return to_png(page, w, h, out, scale)


def build_layout_samples(c: Halkort, out_dir: str | Path, scale: float = 2.0) -> dict[str, Path]:
    """Samma hål i alla layouter, plus en översiktsbild med alla sida vid sida."""
    from PIL import Image, ImageDraw, ImageFont

    out_dir = Path(out_dir)
    files: dict[str, Path] = {}
    for n, (name, _) in LAYOUTS.items():
        files[f"{n} {name}"] = render(c, n, out_dir / f"hal-{c.hole:02d}-layout{n}-{name.lower()}.png", scale)
    # Översikt: stående layouter i en rad, skärmlayouten under
    thumbs = {k: Image.open(v).convert("RGB") for k, v in files.items()}
    th = 900
    portrait = [k for k, im in thumbs.items() if im.height > im.width]
    land = [k for k in thumbs if k not in portrait]
    pad, label = 40, 70
    row_w = sum(round(thumbs[k].width * th / thumbs[k].height) for k in portrait) + pad * (len(portrait) + 1)
    land_h = sum(round(thumbs[k].height * (row_w - 2 * pad) / thumbs[k].width) + label + pad for k in land)
    sheet = Image.new("RGB", (row_w, th + label + 2 * pad + land_h), "#e9e4da")
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(FONTS / "DMSans.ttf"), 30)
    x = pad
    for k in portrait:
        im = thumbs[k].resize((round(thumbs[k].width * th / thumbs[k].height), th), Image.LANCZOS)
        d.text((x, pad), k, font=font, fill="#3a3530")
        sheet.paste(im, (x, pad + label))
        x += im.width + pad
    y = th + label + 2 * pad
    for k in land:
        w = row_w - 2 * pad
        im = thumbs[k].resize((w, round(thumbs[k].height * w / thumbs[k].width)), Image.LANCZOS)
        d.text((pad, y), k, font=font, fill="#3a3530")
        sheet.paste(im, (pad, y + label))
        y += im.height + label + pad
    files["översikt"] = out_dir / f"hal-{c.hole:02d}-alla-layouter.jpg"
    sheet.save(files["översikt"], quality=90)
    return files
