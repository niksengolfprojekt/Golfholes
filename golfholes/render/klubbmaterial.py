"""Gemensamt för klubbens säljmaterial (hålsponsorprospekt och inlägg i sociala medier).

Allt klubbspecifikt läses ur `klubbar/<klubb>/klubb.yaml`: färger och typsnitt (`profil`),
loggor, sponsorpris och hålsidans adress (`sponsring`), kontonamn och hashtaggar (`some`).
Hålens texter kommer från hålkorten (`halkort/hal-NN.yaml`) och hålbilden är hålkortets
målade bild med alla tees och den vinröda T-flaggan inritade (`halkort.markera`).
Ny klubb = ny mapp med samma filer, samma kommandon.
"""
from __future__ import annotations

import base64
import html
import io
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .. import statistik
from .halkort import ATTRIBUTION, Halkort, _font_css, markera

# Uppskattning av ronder när klubben inte har lämnat sin egen siffra.
RIKSSNITT_RONDER = 25833
RIKSSNITT_KALLA = "snittet för svenska golfklubbar 2025 enligt Svenska Golfförbundet"

STANDARDFARGER = {"djup": "#10202E", "sjo": "#1D4756", "glas": "#3F7F86", "is": "#9CC9C3",
                  "kristall": "#EEF3EC", "glod": "#D9A441", "glod_mork": "#8A6220"}


def e(s) -> str:
    return html.escape(str(s), quote=True)


def kr(n: int) -> str:
    """10000 -> '10 000' (hårt mellanslag som tusentalsavgränsare)."""
    return f"{int(n):,}".replace(",", " ")


@dataclass
class Klubb:
    mapp: Path
    namn: str
    kortnamn: str
    filnamn: str
    bana: str
    web: str
    farger: dict
    rubrik: str = "Spectral"
    brodtext: str = "Hanken Grotesk"
    loggor: dict = field(default_factory=dict)
    sponsring: dict = field(default_factory=dict)
    some: dict = field(default_factory=dict)

    @classmethod
    def from_dir(cls, mapp: str | Path) -> "Klubb":
        mapp = Path(mapp)
        d = yaml.safe_load((mapp / "klubb.yaml").read_text(encoding="utf-8")) or {}
        prof = d.get("profil") or {}
        loggor = {k: mapp / v for k, v in (("ljus", prof.get("logga_pa_ljust")), ("mork", prof.get("logga_pa_morkt")),
                                           ("farg", prof.get("logga_farg"))) if v}
        return cls(
            mapp=mapp, namn=d.get("club", mapp.name), kortnamn=d.get("kortnamn", d.get("club", mapp.name)),
            filnamn=d.get("filnamn", mapp.name.capitalize()), bana=d.get("bana", ""), web=d.get("web", ""),
            farger={**STANDARDFARGER, **(prof.get("farger") or {})},
            rubrik=prof.get("rubrik", "Spectral"), brodtext=prof.get("brodtext", "Hanken Grotesk"),
            loggor=loggor, sponsring=d.get("sponsring") or {}, some=d.get("some") or {},
        )

    # -- sponsring
    @property
    def sasong(self) -> int:
        return int(self.sponsring.get("sasong", 2027))

    def halsida(self, hal: int) -> str:
        """Hålsidans adress (som den skrivs ut i text)."""
        return statistik.halsida({"web": self.web, "sponsring": self.sponsring}, hal)

    def qr_lank(self, hal: int) -> str:
        """Adressen i QR-koden: hålsidan med ?q=hNN, så att besöket räknas som QR-besök."""
        return statistik.qr_lank({"web": self.web, "sponsring": self.sponsring}, hal)

    def ronder(self) -> tuple[int, str]:
        """(ronder per år, källa). Klubbens egen siffra går före riksgenomsnittet."""
        egen = self.sponsring.get("ronder_per_ar")
        if egen:
            return int(egen), f"{self.kortnamn}s egen siffra"
        return RIKSSNITT_RONDER, RIKSSNITT_KALLA

    def status(self, hal: int) -> str:
        """Hålets sponsorstatus ur `sponsring.status`: "ledig", "bokad" eller "såld" (saknas = ledig)."""
        st = self.sponsring.get("status") or {}
        v = str(st.get(hal, st.get(str(hal), "ledig")) or "ledig").strip().lower()
        if v in ("ledig", "ledigt", "fri"):
            return "ledig"
        if v in ("bokad", "bokat"):
            return "bokad"
        if v in ("såld", "sålt", "sald", "salt"):
            return "såld"
        raise ValueError(f"sponsring.status för hål {hal}: {v!r} (skriv ledig, bokad eller såld)")

    def logga(self, bakgrund: str = "ljus") -> str:
        p = self.loggor.get(bakgrund)
        return data_uri(p, 600) if p and p.exists() else ""

    # -- halkort
    def halkort(self) -> dict[int, Path]:
        """Hålnummer -> hålkortsfil, för de hål som har en hålbild."""
        ut = {}
        for f in sorted((self.mapp / "halkort").glob("hal-*.yaml")):
            c = Halkort.from_yaml(f)
            if c.image.exists():
                ut[c.hole] = f
        return ut


def css(k: Klubb) -> str:
    """Typsnitt (inbäddade) + klubbens färger som CSS-variabler."""
    f = k.farger
    return _font_css() + (
        f":root{{--djup:{f['djup']};--sjo:{f['sjo']};--glas:{f['glas']};--is:{f['is']};--kristall:{f['kristall']};"
        f"--glod:{f['glod']};--glod-m:{f['glod_mork']};--serif:'{k.rubrik}',Georgia,serif;"
        f"--sans:'{k.brodtext}',Arial,sans-serif}}"
        "body{font-family:var(--sans);font-variant-numeric:lining-nums;color:var(--djup)}"
    )


_URI_CACHE: dict[tuple, str] = {}


def data_uri(p: Path, max_px: int | None = None) -> str:
    """Bild som data-URI (Chromium laddar inte file:// i set_content). max_px krymper
    längsta sidan, så att PDF:erna inte blir onödigt stora."""
    key = (str(p), max_px, p.stat().st_mtime)
    if key in _URI_CACHE:
        return _URI_CACHE[key]
    from PIL import Image

    with Image.open(p) as im:
        im.load()
        if max_px and max(im.size) > max_px:
            im.thumbnail((max_px, max_px), Image.LANCZOS)
        buf = io.BytesIO()
        if im.mode in ("RGBA", "LA", "P"):
            im.convert("RGBA").save(buf, "WEBP", quality=90, method=4)
            mime = "image/webp"
        else:
            im.convert("RGB").save(buf, "JPEG", quality=90)
            mime = "image/jpeg"
    _URI_CACHE[key] = f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode()
    return _URI_CACHE[key]


def halkort_markerat(fil: Path) -> Halkort:
    """Hålkortet med hålbilden där alla tees och T-flaggan är inritade. Den markerade bilden
    sparas i output/ och återanvänds så länge varken hålbild eller hålfil har ändrats."""
    c = Halkort.from_yaml(fil)
    if not c.halfil:
        return c
    from dataclasses import replace

    from .halkort import ROOT

    sparad = ROOT / "output" / c.halfil.parent.name / "halbilder" / f"{c.image.stem}-markerad.png"
    if sparad.exists() and sparad.stat().st_mtime > max(c.image.stat().st_mtime, c.halfil.stat().st_mtime):
        return replace(c, image=sparad, halfil=None)
    return markera(c)


def bildstorlek(p: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(p) as im:
        return im.size


def hal_i_ruta(bild: Path, x: float, y: float, w: float, h: float, ankare: str = "center center",
               max_px: int = 2400, extra: str = "") -> str:
    """Hela hålet inpassat i en ruta: skalas, beskärs aldrig."""
    iw, ih = bildstorlek(bild)
    k = min(w / iw, h / ih)
    fw, fh = iw * k, ih * k
    hx, vy = (ankare.split() + ["center"])[:2]
    fx = x + {"left": 0, "center": (w - fw) / 2, "right": w - fw}[hx]
    fy = y + {"top": 0, "center": (h - fh) / 2, "bottom": h - fh}[vy]
    return (f"<img class='hal' src='{data_uri(bild, max_px)}' style='position:absolute;left:{fx:.1f}px;"
            f"top:{fy:.1f}px;width:{fw:.1f}px;height:{fh:.1f}px;{extra}'>")


def qr(url: str, farg: str) -> tuple[str, bool]:
    from ..qr import qr_svg

    import re

    svg, akta = qr_svg(url, dark=farg)
    m = re.search(r'<svg[^>]*?width="([\d.]+)" height="([\d.]+)"', svg)
    if m:  # segno ger fast storlek utan viewBox: gör den skalbar
        w, h = m.groups()
        svg = svg.replace(f'width="{w}" height="{h}"', f'viewBox="0 0 {w} {h}" shape-rendering="crispEdges"', 1)
    return svg.replace("<svg ", "<svg style='width:100%;height:100%;display:block' ", 1), akta


class Webblasare:
    """En Chromium-session för många sidor (Playwright). PNG per sida och PDF av flera."""

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as err:  # pragma: no cover
            raise SystemExit("Playwright saknas: pip install playwright && playwright install chromium") from err
        self._pw = sync_playwright().start()
        self._b = self._pw.chromium.launch()
        return self

    def __exit__(self, *exc):
        self._b.close()
        self._pw.stop()

    def png(self, sida: str, w: int, h: int, ut: Path, skala: float = 1.0) -> Path:
        ut = Path(ut)
        ut.parent.mkdir(parents=True, exist_ok=True)
        pg = self._b.new_page(viewport={"width": w, "height": h}, device_scale_factor=skala)
        pg.set_content(sida, wait_until="load")
        pg.evaluate("document.fonts.ready")
        pg.screenshot(path=str(ut), clip={"x": 0, "y": 0, "width": w, "height": h})
        pg.close()
        return ut

    def pdf(self, sida: str, w: int, h: int, ut: Path) -> Path:
        ut = Path(ut)
        ut.parent.mkdir(parents=True, exist_ok=True)
        pg = self._b.new_page(viewport={"width": w, "height": h})
        pg.set_content(sida, wait_until="load")
        pg.evaluate("document.fonts.ready")
        pg.pdf(path=str(ut), width=f"{w}px", height=f"{h}px", print_background=True,
               margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        pg.close()
        return ut


def kontaktark(bilder: list[Path], ut: Path, kolumner: int, bredd: int = 2400, bakgrund: str = "#E4EAE6",
               etiketter: list[str] | None = None, marg: int = 30) -> Path:
    """Översiktsbild: alla bilder i ett rutnät (samma storlek för samma slags bild)."""
    from PIL import Image, ImageDraw, ImageFont

    from .halkort import FONTS

    ims = [Image.open(b).convert("RGB") for b in bilder]
    cw = (bredd - marg * (kolumner + 1)) // kolumner
    ch = round(cw * ims[0].height / ims[0].width)
    lab = 44 if etiketter else 0
    rader = (len(ims) + kolumner - 1) // kolumner
    ark = Image.new("RGB", (bredd, marg + rader * (ch + lab + marg)), bakgrund)
    d = ImageDraw.Draw(ark)
    font = ImageFont.truetype(str(FONTS / "HankenGrotesk-Medium.ttf"), 24)
    for i, im in enumerate(ims):
        x = marg + (i % kolumner) * (cw + marg)
        y = marg + (i // kolumner) * (ch + lab + marg)
        if etiketter:
            d.text((x, y + 8), etiketter[i], font=font, fill="#2A3A40")
        ark.paste(im.resize((cw, ch), Image.LANCZOS), (x, y + lab))
    ut.parent.mkdir(parents=True, exist_ok=True)
    ark.save(ut, quality=88)
    return ut


__all__ = ["ATTRIBUTION", "Klubb", "Webblasare", "css", "data_uri", "e", "hal_i_ruta", "halkort_markerat",
           "kontaktark", "kr", "qr"]
