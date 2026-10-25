"""Export till digitala partnerkanaler: en JSON per hål med sponsorn, loggor och en zip.

Partnern ritar hålen själv. Exporten innehåller därför INGA hålbilder och ingen geometri –
bara klubb, bana, hål, par och sponsorns uppgifter. Formatet beskrivs i docs/partnerexport.md.
"""
from __future__ import annotations

import base64
import json
import re
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml

FORMAT_VERSION = "1.0"
LOGGA_FARG = "#1d2a22"      # loggan i en färg
PLATTA_FARG = "#f6f4ee"     # ljus platta bakom loggan
PLATTA_PX = (1200, 600)


def _slug(s: str) -> str:
    s = s.lower().replace("å", "a").replace("ä", "a").replace("ö", "o").replace("é", "e")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def lank_med_utm(url: str, klubb_slug: str, hal: int) -> str | None:
    """Sponsorns länk med utm-parametrar, så att sponsorn ser trafiken i sin egen statistik."""
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    d = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(d.query, keep_blank_values=True) if not k.startswith("utm_")]
    q += [("utm_source", "partnerapp"), ("utm_medium", "halsponsor"), ("utm_campaign", f"{klubb_slug}-hal-{hal:02d}")]
    return urlunsplit((d.scheme, d.netloc, d.path or "/", urlencode(q), d.fragment))


def svg_en_farg(svg: str, farg: str = LOGGA_FARG) -> str:
    """Byter alla färger i en SVG mot en färg (fill/stroke/stop-color, attribut och style)."""
    def byt(m: re.Match) -> str:
        v = m.group(2).strip().lower()
        return m.group(0) if v in ("none", "transparent") or v.startswith("url(") else f"{m.group(1)}{farg}"

    svg = re.sub(r'((?:fill|stroke|stop-color|color)\s*=\s*["\'])([^"\']+)(?=["\'])', byt, svg)
    svg = re.sub(r"((?:fill|stroke|stop-color|color)\s*:\s*)([^;\"'}]+)", byt, svg)
    if "<svg" in svg and not re.search(r"<svg[^>]*\sfill=", svg):
        svg = re.sub(r"<svg\b", f'<svg fill="{farg}"', svg, count=1)
    return svg


def _png_ur_svg(svg: str, ut: Path) -> Path | None:
    """Loggan på en ljus platta som PNG via Chromium. None om Chromium saknas."""
    try:
        from .render.export import to_png
    except ImportError:
        return None
    w, h = PLATTA_PX
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode()
    page = (f"<!doctype html><html><head><meta charset='utf-8'><style>html,body{{margin:0}}"
            f"body{{width:{w}px;height:{h}px;background:{PLATTA_FARG};display:flex;align-items:center;justify-content:center}}"
            f"img{{max-width:{int(w * .72)}px;max-height:{int(h * .5)}px}}</style></head><body><img src='{uri}'></body></html>")
    try:
        return to_png(page, ut, w, h, scale=1)
    except Exception:  # noqa: BLE001 – Chromium saknas eller startar inte
        return None


def _png_ur_bitmap(src: Path, ut: Path) -> Path:
    """PNG-logga → en färg (loggans alfa/mörka delar) på ljus platta, med Pillow."""
    from PIL import Image, ImageOps

    im = Image.open(src).convert("RGBA")
    alfa = im.getchannel("A")
    if alfa.getextrema() == (255, 255):  # ingen genomskinlighet: mörka pixlar = logga
        alfa = ImageOps.invert(im.convert("L"))
    w, h = PLATTA_PX
    alfa.thumbnail((int(w * .72), int(h * .5)), Image.LANCZOS)
    platta = Image.new("RGB", (w, h), PLATTA_FARG)
    farg = Image.new("RGB", alfa.size, LOGGA_FARG)
    platta.paste(farg, ((w - alfa.width) // 2, (h - alfa.height) // 2), alfa)
    ut.parent.mkdir(parents=True, exist_ok=True)
    platta.save(ut)
    return ut


def _par(club: dict, club_dir: Path, nr: int) -> int | None:
    for h in club.get("holes") or []:
        if int(h.get("hole", 0)) == nr and h.get("par"):
            return int(h["par"])
    for f in (club_dir / f"hal-{nr:02d}.yaml", club_dir / "halkort" / f"hal-{nr:02d}.yaml"):
        if f.exists():
            p = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("par")
            if p:
                return int(p)
    return None


def _datum(v) -> str | None:
    if v is None or v == "":
        return None
    return v.isoformat() if isinstance(v, date) else str(v)


def exportera(club_dir: str | Path, out_dir: str | Path) -> tuple[list[Path], list[str]]:
    """Skriver hal-NN.json, loggor/ och en zip. Returnerar (filer, varningar)."""
    club_dir, out = Path(club_dir), Path(out_dir)
    club = yaml.safe_load((club_dir / "klubb.yaml").read_text(encoding="utf-8")) or {}
    slug = _slug(club_dir.name)
    varningar: list[str] = []
    bana = club.get("bana")
    if not bana:
        varningar.append("klubb.yaml saknar `bana` (banans namn) – fältet blir null.")
    sponsors = {int(k): v for k, v in (club.get("sponsors") or {}).items() if v}
    hal_nr = sorted({int(h["hole"]) for h in club.get("holes") or [] if h.get("hole")} | set(sponsors))
    if not sponsors:
        varningar.append("klubb.yaml har inga sponsorer (fältet sponsors) – alla hål exporteras utan sponsor.")
    out.mkdir(parents=True, exist_ok=True)
    for gammal in list(out.glob("hal-*.json")) + list((out / "loggor").glob("*")):
        gammal.unlink()
    filer: list[Path] = []
    for nr in hal_nr:
        sp = sponsors.get(nr)
        sponsor = None
        if sp:
            namn = sp.get("name") or sp.get("namn")
            sponsor = {"namn": namn,
                       "halnamn": f"{namn}-hålet" if sp.get("naming_rights", True) else None,
                       "logga_svg": None, "logga_png": None,
                       "lank": lank_med_utm(sp.get("url", ""), slug, nr),
                       "giltig_fran": _datum(sp.get("giltig_fran")), "giltig_till": _datum(sp.get("giltig_till"))}
            stam = f"loggor/hal-{nr:02d}-{_slug(namn)}"
            logo = club_dir / sp["logo"] if sp.get("logo") else None
            if logo and logo.exists():
                if logo.suffix.lower() == ".svg":
                    svg = svg_en_farg(logo.read_text(encoding="utf-8"))
                    (out / "loggor").mkdir(parents=True, exist_ok=True)
                    (out / f"{stam}.svg").write_text(svg, encoding="utf-8")
                    sponsor["logga_svg"] = f"{stam}.svg"
                    if _png_ur_svg(svg, out / f"{stam}.png"):
                        sponsor["logga_png"] = f"{stam}.png"
                    else:
                        varningar.append(f"Hål {nr}: PNG-loggan kunde inte ritas (Chromium saknas) – bara SVG.")
                else:
                    _png_ur_bitmap(logo, out / f"{stam}.png")
                    sponsor["logga_png"] = f"{stam}.png"
                    varningar.append(f"Hål {nr}: {namn} har bara bitmapslogga – be om SVG.")
            else:
                varningar.append(f"Hål {nr}: {namn} saknar logga (fältet logo) – logga_svg och logga_png blir null.")
            if not sponsor["lank"]:
                varningar.append(f"Hål {nr}: {namn} saknar webbadress (fältet url).")
            if not (sponsor["giltig_fran"] and sponsor["giltig_till"]):
                varningar.append(f"Hål {nr}: {namn} saknar avtalsperiod (giltig_fran/giltig_till).")
        par = _par(club, club_dir, nr)
        if par is None:
            varningar.append(f"Hål {nr}: par saknas.")
        post = {"format": f"tacada-halsponsor/{FORMAT_VERSION}", "exporterad": date.today().isoformat(),
                "klubb": club.get("club"), "bana": bana, "hal": nr, "par": par, "sponsor": sponsor}
        if club.get("testdata"):
            post["testdata"] = True
        f = out / f"hal-{nr:02d}.json"
        f.write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        filer.append(f)
    zp = out / f"{slug}-partnerexport.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob("*")):
            if p.is_file() and p != zp and p.suffix != ".zip":
                z.write(p, p.relative_to(out).as_posix())
    filer.append(zp)
    return filer, varningar
