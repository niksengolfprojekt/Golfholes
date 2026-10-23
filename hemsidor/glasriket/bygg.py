"""Bygger Glasrikets GK:s hemsida: läser sidorna i sidor/, klubbens data (klubbar/glasriket/ och data/)
och skriver en färdig statisk sajt till public/ (det är den mappen som publiceras).

Hålsidorna 1–18 byggs ur klubb.yaml (par, index, tees och längder), hålkorten i
klubbar/glasriket/halkort/ och texterna i data/hal.yaml. Finns en färdig hålbild i
klubbar/glasriket/halbilder/hal-NN-malad.webp kommer den med automatiskt, med tees inritade.
Saknas bilden byggs hålsidan ändå – utan hålbild, med en varning. Aldrig en trasig bild.

Kör:                     python hemsidor/glasriket/bygg.py
Kontroll inför lansering: python hemsidor/glasriket/bygg.py --lansering-kontroll
Förhandsvisning utan server: python hemsidor/glasriket/bygg.py --forhandsvisning <mapp>
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from PIL import Image

ROT = Path(__file__).resolve().parent
REPO = ROT.parents[1]
KLUBB = REPO / "klubbar" / "glasriket"
SIDOR = ROT / "sidor"
DATA = ROT / "data"
TILLG = ROT / "tillgangar"
CACHE = ROT / "cache"
UT = ROT / "public"

# --- Inställningar (flaggor) som ändras när beslut fattas ---------------------------------
# Sajten är inte lanserad: alla sidor får noindex och robots.txt stänger ute sökmotorer.
LANSERAD = False
# Adressen sajten ska ligga på. Används i kanoniska länkar, sitemap och QR-länkarna på skyltarna.
DOMAN = "https://www.glasriketsgk.se"
# Bokningssystemet ("Boka starttid"). Klubben bokar i dag via Min Golf.
BOKNING_URL = "https://mingolf.golf.se/"
# Cookiefri besöksräknare (Plausible). None = avstängd, inget skript laddas.
# Sätt till domännamnet utan https, t.ex. "glasriketsgk.se", när sajten finns i Plausible.
PLAUSIBLE_DOMAN = None
# Värd för sajt och formulär. Netlify tar emot formulären (Netlify Forms) – står i integritetspolicyn.
VARD = "Netlify"
# Klubbens organisationsnummer i integritetspolicyn. None = raden visas inte.
ORGNR = None
# ------------------------------------------------------------------------------------------

ATTRIBUTION = "Underlag: Ortofoto och Markhöjdmodell ©Lantmäteriet, bearbetat, CC BY 4.0"
MENY = [
    ("banan/", "Banan"),
    ("greenfee/", "Greenfee och bokning"),
    ("bli-medlem/", "Bli medlem"),
    ("halsponsorer/", "Hålsponsorer"),
    ("kontakt/", "Kontakt"),
]
BILDHOJDER = (900, 1800)   # hålbildens två storlekar på sajten (px höjd)
KORTHOJD = 520             # småbilden på banöversikten

varningar: list[str] = []


def e(s) -> str:
    return html.escape(str(s), quote=True)


def kr(v: int) -> str:
    return f"{v:,}".replace(",", " ") + " kr"


def tee_namn(n: str) -> str:
    return " · ".join(t.strip() for t in re.split(r"[/·]", str(n)))


# ------------------------------------------------------------------ data
def las_yaml(p: Path):
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None


def las_hal() -> list[dict]:
    klubb = las_yaml(KLUBB / "klubb.yaml")
    texter = las_yaml(DATA / "hal.yaml") or {}
    hal = []
    for h in klubb["holes"]:
        n = int(h["hole"])
        kort = las_yaml(KLUBB / "halkort" / f"hal-{n:02d}.yaml") or {}
        txt = texter.get(n, {}) or {}
        if kort.get("tees"):
            tees = [(tee_namn(t[0]), int(t[1])) for t in kort["tees"]]
        else:
            tees = [(tee_namn(k), int(v)) for k, v in h["tees"].items()]
        tees.sort(key=lambda t: -t[1])
        hal.append({
            "nr": n, "par": int(h["par"]), "index": int(h["index"]), "tees": tees,
            "rubrik": kort.get("rubrik") or txt.get("rubrik", ""),
            "beskrivning": kort.get("beskrivning") or txt.get("beskrivning", ""),
            "rad": list(kort.get("rad") or txt.get("rad") or []),
            "slutrad": kort.get("slutrad") or txt.get("slutrad", ""),
            "obs": txt.get("obs", ""),
            "sponsor": kort.get("sponsor") or txt.get("sponsor") or h.get("sponsor"),
            "bild": None,
        })
    return hal


# ------------------------------------------------------------------ hålbilder
def _data_mapp() -> Path | None:
    """Lantmäteriets data ligger i repots data/ (checkas aldrig in). I en git-worktree letar vi i huvudmappen."""
    kandidater = [REPO / "data" / "glasriket"]
    try:
        gemensam = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--git-common-dir"],
                                  capture_output=True, text=True, check=True).stdout.strip()
        kandidater.append((REPO / gemensam).resolve().parent / "data" / "glasriket")
    except (OSError, subprocess.CalledProcessError):
        pass
    return next((k for k in kandidater if (k / "lantmateriet.json").exists()), None)


def _markerad(n: int, kalla: Path) -> Path:
    """Hålbilden med tees inritade (romb + namn), sparad i cache/ så att bygget går utan Lantmäteriets data.
    Nyckeln är bildens och hålfilens innehåll: ändras någon av dem ritas bilden om."""
    halfil = KLUBB / f"hal-{n:02d}.yaml"
    nyckel = hashlib.sha1(kalla.read_bytes() + (halfil.read_bytes() if halfil.exists() else b"")).hexdigest()[:10]
    cache = CACHE / f"hal-{n:02d}-{nyckel}.webp"
    if cache.exists():
        return cache
    ut = None
    data = _data_mapp()
    if halfil.exists() and data:
        try:
            sys.path.insert(0, str(REPO))
            from golfholes.hole import Hole
            from golfholes.render.foto import markera_halbild

            logg = json.loads((data / "lantmateriet.json").read_text(encoding="utf-8"))
            orto = data / Path(next(f["fil"] for f in logg["filer"] if f["katalog"] == "orto")).relative_to("data/glasriket")
            tmp = CACHE / f"hal-{n:02d}-tmp.png"
            CACHE.mkdir(exist_ok=True)
            bild, _ = markera_halbild(Hole.from_yaml(halfil), orto, kalla, tmp)
            if bild == tmp:
                ut = tmp
            else:
                varningar.append(f"Hål {n}: hålbilden passar inte hålfilen – tees ej inritade (bilden visas ändå)")
        except Exception as fel:  # noqa: BLE001 – bygget ska aldrig stoppa på en bild
            varningar.append(f"Hål {n}: kunde inte rita tees ({fel.__class__.__name__}: {fel}) – bilden visas utan tees")
    else:
        varningar.append(f"Hål {n}: Lantmäteriets data eller hålfil saknas här – bilden visas utan inritade tees")
    im = Image.open(ut or kalla).convert("RGBA")
    if im.height > BILDHOJDER[-1]:
        im = im.resize((round(im.width * BILDHOJDER[-1] / im.height), BILDHOJDER[-1]), Image.LANCZOS)
    for gammal in CACHE.glob(f"hal-{n:02d}-*.webp"):
        gammal.unlink()
    CACHE.mkdir(exist_ok=True)
    im.save(cache, quality=84, method=6)
    if ut:
        ut.unlink()
    return cache


def halbilder_bygg(hal: list[dict]) -> None:
    """Hålbilderna i tre storlekar till public/img/hal/. Filnamnen bär bildens nyckel, så en ny
    bild får en ny adress (ingen gammal bild i webbläsarens cache) och oförändrade bilder görs inte om."""
    mal = UT / "img" / "hal"
    mal.mkdir(parents=True, exist_ok=True)
    behall = set()
    for h in hal:
        n = h["nr"]
        kalla = KLUBB / "halbilder" / f"hal-{n:02d}-malad.webp"
        if not kalla.exists():
            varningar.append(f"Hål {n}: ingen färdig hålbild ännu (klubbar/glasriket/halbilder/hal-{n:02d}-malad.webp) – hålsidan byggs utan bild")
            continue
        try:
            cache = _markerad(n, kalla)
            im = Image.open(cache)
            im.load()
        except Exception as fel:  # noqa: BLE001
            varningar.append(f"Hål {n}: hålbilden går inte att läsa ({fel}) – hålsidan byggs utan bild")
            continue
        storlekar = []
        for hojd in (*BILDHOJDER, KORTHOJD):
            hojd = min(hojd, im.height)
            b = round(im.width * hojd / im.height)
            fil = mal / f"{cache.stem}-{hojd}.webp"
            if not fil.exists():
                im.resize((b, hojd), Image.LANCZOS).save(fil, quality=82, method=4)
            behall.add(fil.name)
            storlekar.append((fil.name, b, hojd))
        h["bild"] = {"stora": storlekar[:-1], "kort": storlekar[-1], "kvot": im.width / im.height}
    for fil in mal.glob("*"):
        if fil.name not in behall:
            fil.unlink()


# ------------------------------------------------------------------ sidmall
def las_sida(fil: Path):
    text = fil.read_text(encoding="utf-8")
    m = re.match(r"<!--(.*?)-->\s*", text, re.S)
    if not m:
        raise SystemExit(f"{fil.name}: saknar huvud med titel/sokvag")
    meta = {}
    for rad in m.group(1).strip().splitlines():
        k, _, v = rad.partition(":")
        meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def statistik_skript() -> str:
    if not PLAUSIBLE_DOMAN:
        return ""
    return (f'<script defer data-domain="{e(PLAUSIBLE_DOMAN)}" src="https://plausible.io/js/script.js"></script>\n'
            "<script>window.plausible=window.plausible||function(){(window.plausible.q=window.plausible.q||[]).push(arguments)}</script>\n")


def sida(meta: dict, kropp: str, f: dict) -> str:
    sokvag = meta["sokvag"]
    aktiv = sokvag.split("/")[0] + "/" if sokvag else ""
    meny = "".join(
        f'<li><a href="/{u}"{" aria-current=\"page\"" if aktiv == u else ""}>{n}</a></li>' for u, n in MENY)
    robots = "" if LANSERAD else '<meta name="robots" content="noindex, nofollow">\n'
    url = DOMAN + "/" + (sokvag if sokvag != "404" else "")
    bild = meta.get("bild", "img/hal-03-inspel-1600.webp")
    adress = ", ".join(f["adress"][1:])
    return f"""<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(meta["titel"])}</title>
<meta name="description" content="{e(meta["beskrivning"])}">
{robots}<link rel="canonical" href="{url}">
<meta property="og:title" content="{e(meta["titel"])}">
<meta property="og:description" content="{e(meta["beskrivning"])}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{DOMAN}/{bild}">
<meta property="og:locale" content="sv_SE">
<meta property="og:site_name" content="{e(f["namn"])}">
<meta name="theme-color" content="#10202E">
<link rel="icon" href="/favicon-32.png" sizes="32x32">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preload" href="/fonts/spectral-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/fonts/hanken-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/css/site.css">
{statistik_skript()}</head>
<body>
<a class="hoppa" href="#innehall">Till innehållet</a>
<header class="huvud">
  <div class="inne">
    <a class="marke" href="/" aria-label="{e(f["namn"])}, till startsidan">
      <img src="/img/sigill-96.png" width="48" height="48" alt="">
      <span>Glasrikets <em>Golfklubb</em></span>
    </a>
    <nav class="meny" aria-label="Huvudmeny"><ul>{meny}</ul></nav>
    <a class="knapp knapp-glod boka" href="{e(BOKNING_URL)}" rel="noopener">Boka starttid</a>
    <details class="mobilmeny"><summary aria-label="Meny"><span></span></summary><ul>{meny}<li><a href="{e(BOKNING_URL)}" rel="noopener">Boka starttid</a></li></ul></details>
  </div>
</header>
<main id="innehall">
{kropp}
</main>
<footer class="fot">
  <div class="inne">
    <div class="fot-topp">
      <div class="fot-marke">
        <img src="/img/sigill-mork-192.png" width="96" height="96" alt="Glasrikets Golfklubbs sigill" loading="lazy">
        <p>Ängs- och skogsbana i naturreservatet Fylleryd, Växjö.</p>
      </div>
      <div><h2>Hitta hit</h2><ul><li>{e(f["adress"][0])}</li><li>{e(adress)}</li><li><a href="{e(f["karta"])}" rel="noopener">Vägbeskrivning</a></li></ul></div>
      <div><h2>Kontakt</h2><ul><li><a href="mailto:{f["epost"]}">{f["epost"]}</a></li><li><a href="tel:{f["telefon"].replace(" ", "").replace("-", "")}">{f["telefon"]}</a></li><li>Swish {f["swish"]}</li></ul></div>
      <div><h2>Följ oss</h2><ul><li><a href="{e(f["instagram"])}" rel="noopener">Instagram</a></li><li><a href="{e(f["facebook"])}" rel="noopener">Facebook</a></li><li><a href="/integritet/">Integritetspolicy</a></li></ul></div>
    </div>
    <div class="kallor">
      <span>{ATTRIBUTION}.</span>
      <span>Vissa bilder är visualiseringar.</span>
      <span>Webbplatsen använder inga kakor.</span>
    </div>
  </div>
</footer>
<script src="/js/site.js" defer></script>
</body>
</html>
"""


# ------------------------------------------------------------------ byggstenar
def bildtagg(h: dict, storlek: str = "stor", lazy: bool = True, klass: str = "") -> str:
    b = h["bild"]
    if not b:
        return ""
    alt = f"Hål {h['nr']} ovanifrån, par {h['par']}, med tees utmärkta"
    if storlek == "kort":
        namn, w, hh = b["kort"]
        return (f'<img class="{klass}" src="/img/hal/{namn}" width="{w}" height="{hh}" alt="{e(alt)}"'
                f'{" loading=\"lazy\"" if lazy else ""} decoding="async">')
    srcset = ", ".join(f"/img/hal/{n} {w}w" for n, w, _ in b["stora"])
    namn, w, hh = b["stora"][0]
    return (f'<img class="{klass}" src="/img/hal/{namn}" srcset="{srcset}" sizes="(min-width: 900px) 34vw, 60vw"'
            f' width="{w}" height="{hh}" alt="{e(alt)}"{" loading=\"lazy\"" if lazy else ""} decoding="async">')


def langst(h: dict) -> int:
    return max(m for _, m in h["tees"])


def halkort_lista(hal: list[dict]) -> str:
    kort = []
    for h in hal:
        bild = (f'<div class="hk-bild">{bildtagg(h, "kort")}</div>' if h["bild"]
                else f'<div class="hk-bild hk-tom" aria-hidden="true"><span>{h["nr"]}</span></div>')
        kort.append(
            f'<li><a class="hk" href="/banan/hal-{h["nr"]:02d}/">{bild}'
            f'<div class="hk-text"><span class="hk-nr">Hål {h["nr"]}</span>'
            f'<span class="hk-fakta">Par {h["par"]} · {langst(h)} m</span>'
            f'<span class="hk-rubrik">{e(h["rubrik"])}</span></div></a></li>')
    return f'<ul class="hk-lista">{"".join(kort)}</ul>'


def utvalda_hal(hal: list[dict], antal: int = 4) -> str:
    med = [h for h in hal if h["bild"]]
    # signaturhålet och det svåraste först, sedan i ordning
    ordning = sorted(med, key=lambda h: (h["nr"] not in (17, 14), h["nr"]))[:antal]
    return halkort_lista(sorted(ordning, key=lambda h: h["nr"]))


def tee_tabell(h: dict) -> str:
    rader = "".join(f'<tr><th scope="row">{e(n)}</th><td>{m}&nbsp;m</td></tr>' for n, m in h["tees"])
    return f'<table class="tees"><caption>Tee och längd</caption><tbody>{rader}</tbody></table>'


def hal_sida(h: dict, hal: list[dict], f: dict, oversikt: str) -> tuple[dict, str]:
    n = h["nr"]
    fore = hal[(n - 2) % 18]
    nasta = hal[n % 18]
    sponsor = ""
    if h["sponsor"]:
        sp = h["sponsor"]
        logga = ""
        kalla = (KLUBB / sp["logo"]) if sp.get("logo") else None
        if kalla and kalla.exists():
            mal = UT / "img" / "sponsorer" / f"hal-{n:02d}{kalla.suffix.lower()}"
            mal.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(kalla, mal)
            logga = f'<img src="/img/sponsorer/{mal.name}" alt="{e(sp["name"])}" class="sponsor-logga" loading="lazy">'
        elif kalla:
            varningar.append(f"Hål {n}: sponsorns logga saknas ({kalla}) – namnet visas utan logga")
        namn = (f'<a href="{e(sp["url"])}" rel="noopener" data-hal="h{n:02d}">{e(sp["name"])}</a>'
                if sp.get("url") else e(sp["name"]))
        sponsor = f'<aside class="sponsor"><span class="over">Hålsponsor</span>{logga}<p class="sponsor-namn">{namn}-hålet</p></aside>'
    rad = "".join(f"<li>{e(r)}</li>" for r in h["rad"])
    rad_block = ""
    if rad or h["slutrad"]:
        rad_block = (f'<section class="rad"><h2>Råd från pro:n</h2>{f"<ul>{rad}</ul>" if rad else ""}'
                     f'{f"<p class=\"slutrad\">{e(h["slutrad"])}</p>" if h["slutrad"] else ""}</section>')
    obs = f'<div class="obs"><strong>Observera</strong><p>{e(h["obs"])}</p></div>' if h["obs"] else ""
    if h["bild"]:
        prickar = ('<p class="prickar"><span class="prick prick-rod"></span>100 m kvar till greenens mitt'
                   '<span class="prick prick-gul"></span>150 m</p>') if h["par"] > 3 else ""
        bild = (f'<figure class="hal-bild">{bildtagg(h, lazy=False)}{prickar}'
                f'<figcaption>{ATTRIBUTION}</figcaption></figure>')
    else:
        bild = (f'<figure class="hal-bild hal-bild-oversikt"><a href="/banan/">{oversikt}</a>'
                f'<figcaption>Hål {n} på banöversikten. {ATTRIBUTION}</figcaption></figure>')
    rubrik = f'<p class="hal-rubrik">{e(h["rubrik"])}</p>' if h["rubrik"] else ""
    beskr = f'<p class="ingress">{e(h["beskrivning"])}</p>' if h["beskrivning"] else ""
    kropp = f"""<div class="hal">
  <div class="inne hal-grid">
    <div class="hal-huvud">
      <nav class="smula" aria-label="Brödsmulor"><a href="/banan/">Banan</a> <span aria-hidden="true">/</span> Hål {n}</nav>
      {sponsor}
      <div class="hal-titel">
        <h1 class="hal-nr"><span class="visuellt-dold">Hål </span>{n}</h1>
        <p class="hal-par">Par {h["par"]}<br>Index {h["index"]}</p>
      </div>
    </div>
    {bild}
    <div class="hal-text">
      {tee_tabell(h)}
      {rubrik}
      {beskr}
      {rad_block}
      {obs}
      <nav class="hal-nav" aria-label="Fler hål">
        <a href="/banan/hal-{fore["nr"]:02d}/" rel="prev"><span>Föregående</span>Hål {fore["nr"]}</a>
        <a href="/banan/hal-{nasta["nr"]:02d}/" rel="next"><span>Nästa</span>Hål {nasta["nr"]}</a>
      </nav>
    </div>
  </div>
</div>"""
    sp_txt = f" {h['sponsor']['name']}-hålet." if h["sponsor"] else ""
    meta = {
        "titel": f"Hål {n} · Par {h['par']} · {f['kortnamn']}",
        "beskrivning": f"Hål {n} på Glasrikets GK: par {h['par']}, {langst(h)} meter från längsta tee."
                       + (f" {h['rubrik']}." if h["rubrik"] else "") + sp_txt,
        "sokvag": f"banan/hal-{n:02d}/",
    }
    if h["bild"]:
        meta["bild"] = f"img/hal/{h['bild']['stora'][0][0]}"
    return meta, kropp


def greenfee_tabell(rader) -> str:
    r = "".join(f"<tr><th scope=\"row\">{e(a)}</th><td>{e(b)}</td><td>{kr(c)}</td></tr>" for a, b, c in rader)
    return f'<table class="pris"><thead><tr><th scope="col">Spelare</th><th scope="col">Dag</th><th scope="col">Pris</th></tr></thead><tbody>{r}</tbody></table>'


def medlemskort(f: dict) -> str:
    kort = "".join(
        f'<li class="mk"><h3>{e(m["namn"])}</h3><p class="mk-villkor">{e(m["villkor"])}</p>'
        f'<p class="mk-pris">{kr(m["pris"])}<span>/år</span></p><p class="mk-ingar">{e(m["ingar"])}</p></li>'
        for m in f["medlemskap"]["former"])
    return f'<ul class="mk-lista">{kort}</ul>'


def tider(t: dict) -> str:
    r = "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in t["tider"])
    return f'<h3>{e(t["rubrik"])}</h3><dl class="tider">{r}</dl><p class="liten">{e(t["not"])}</p>'


def ersatt(text: str, f: dict, hal: list[dict], oversikt: str) -> str:
    gf = f["greenfee"]
    bana = f["bana"]
    total = sum(langst(h) for h in hal)
    par = sum(h["par"] for h in hal)
    med_bild = [h for h in hal if h["bild"]]
    ex = next((h for h in med_bild if h["nr"] == 17), med_bild[0] if med_bild else hal[16])
    ord_ = {
        "exempel_bild": bildtagg(ex, "kort") if ex["bild"] else "",
        "exempel_nr": str(ex["nr"]), "exempel_nr2": f"{ex['nr']:02d}", "exempel_par": str(ex["par"]),
        "exempel_index": str(ex["index"]), "exempel_rubrik": e(ex["rubrik"]),
        "bokning_url": e(BOKNING_URL),
        "epost": f["epost"],
        "telefon": f["telefon"],
        "telefon_lank": f["telefon"].replace(" ", "").replace("-", ""),
        "swish": f["swish"],
        "adress_rad1": e(f["adress"][0]), "adress_rad2": e(f["adress"][1]), "adress_rad3": e(f["adress"][2]),
        "karta": e(f["karta"]),
        "instagram": e(f["instagram"]), "facebook": e(f["facebook"]),
        "par": str(par), "total": f"{total:,}".replace(",", " "),
        "antal_hal": str(len(hal)),
        "bana_plats": e(bana["plats"]),
        "bana_karaktar": e(bana["karaktar"]),
        "bandesigner": e(bana["bandesigner"]), "banarkitekt": e(bana["banarkitekt"]),
        "sasong": e(bana["sasong"]), "pay_play": e(bana["pay_play"]),
        "utvalda_hal": utvalda_hal(hal),
        "alla_hal": halkort_lista(hal),
        "oversikt": oversikt,
        "gf_ar": str(gf["giltig"]),
        "gf_krav": e(gf["krav"]),
        "gf_stora": greenfee_tabell(gf["stora"]),
        "gf_nio_not": e(gf["nio"]["not"]), "gf_nio": greenfee_tabell(gf["nio"]["rader"]),
        "gf_pp_not": e(gf["pay_play"]["not"]), "gf_pp": greenfee_tabell(gf["pay_play"]["rader"]),
        "gf_fran": kr(min(r[2] for r in gf["stora"] if r[0] == "Senior")),
        "gf_betalning": e(gf["betalning"]),
        "gf_rabatt": e(gf["samarbete"]["rabatt"]),
        "gf_klubbar": e(", ".join(gf["samarbete"]["klubbar"][:-1]) + " och " + gf["samarbete"]["klubbar"][-1]),
        "gf_golfhaftet": e(gf["golfhaftet"]),
        "bokning_period": e(gf["bokning"]["period"]),
        "bokning_regler": "".join(f"<li>{e(r)}</li>" for r in gf["bokning"]["regler"]),
        "mk_ar": str(f["medlemskap"]["giltig"]),
        "mk_not": e(f["medlemskap"]["not"]),
        "mk_kort": medlemskort(f),
        "mk_val": "".join(f"<option>{e(m['namn'])}</option>" for m in f["medlemskap"]["former"]),
        "mk_fran": kr(min(m["pris"] for m in f["medlemskap"]["former"] if m["namn"].startswith("Senior"))),
        "mk_delbetalning": e(f["medlemskap"]["delbetalning"]),
        "mk_friskvard": e(f["medlemskap"]["friskvard"]),
        "mk_aktivitet": e(f["medlemskap"]["aktivitet"]),
        "mk_spelratt": e(f["medlemskap"]["spelratt"]),
        "hal_val": "".join(f"<option>Hål {h['nr']} (par {h['par']})</option>" for h in hal),
        "tider_reception": tider(f["oppettider"]["reception"]),
        "tider_kansli": tider(f["oppettider"]["kansli"]),
        "restaurang_tel": f["restaurang"]["telefon"], "restaurang_not": e(f["restaurang"]["not"]),
        "proshop_namn": e(f["proshop"]["namn"]), "proshop_url": e(f["proshop"]["url"]),
        "vard": e(VARD),
        "orgnr": f" (org.nr {e(ORGNR)})" if ORGNR else "",
        "statistik": ("Vi räknar besök med Plausible, som inte använder kakor och inte sparar några personuppgifter "
                      "eller IP-adresser. Statistiken visar bara hur många som besöker sidorna, till exempel hur många "
                      "som når en hålsida via QR-koden på teeskylten.") if PLAUSIBLE_DOMAN else
                     "Webbplatsen samlar i dag ingen besöksstatistik.",
        "attribution": ATTRIBUTION,
        "hamtad": str(f["hamtad"]),
    }

    def byt(m):
        k = m.group(1)
        if k not in ord_:
            raise SystemExit(f"Okänt fält {{{{{k}}}}}")
        return ord_[k]

    return re.sub(r"\{\{(\w+)\}\}", byt, text)


# ------------------------------------------------------------------ bygget
def bygg() -> list[str]:
    f = las_yaml(DATA / "klubbfakta.yaml")
    hal = las_hal()
    for p in ("css", "js", "fonts"):
        if (UT / p).exists():
            shutil.rmtree(UT / p)
    for p in (UT / "img").glob("*") if (UT / "img").exists() else []:
        if p.is_file():
            p.unlink()
    UT.mkdir(exist_ok=True)
    for p in TILLG.iterdir():
        if p.is_dir():
            shutil.copytree(p, UT / p.name, dirs_exist_ok=True)
        else:
            shutil.copy2(p, UT / p.name)
    halbilder_bygg(hal)
    oversikt = ('<img class="oversikt" src="/img/oversikt-1200.webp" srcset="/img/oversikt-1200.webp 800w, '
                '/img/oversikt-2000.webp 1334w" sizes="(min-width: 900px) 40vw, 92vw" width="800" height="1200" '
                'alt="Banöversikt över Glasrikets 18-hålsbana ovanifrån, med hålens nummer" loading="lazy" decoding="async">')
    # gamla sidor bort (utom bilder och tillgångar som skrivs om ovan)
    for gammal in UT.rglob("*.html"):
        gammal.unlink()
    adresser = []
    sidor = [las_sida(fil) for fil in sorted(SIDOR.glob("*.html"))]
    sidor += [hal_sida(h, hal, f, oversikt) for h in hal]
    for meta, kropp in sidor:
        sokvag = meta["sokvag"]
        mal = UT / "404.html" if sokvag == "404" else UT / sokvag / "index.html"
        mal.parent.mkdir(parents=True, exist_ok=True)
        mal.write_text(sida(meta, ersatt(kropp, f, hal, oversikt), f), encoding="utf-8")
        if sokvag != "404" and meta.get("karta", "ja") == "ja":
            adresser.append(DOMAN + "/" + sokvag)
    (UT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{a}</loc></url>\n" for a in adresser) + "</urlset>\n", encoding="utf-8")
    (UT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {DOMAN}/sitemap.xml\n" if LANSERAD else "User-agent: *\nDisallow: /\n",
        encoding="utf-8")
    # QR-länkarna till teeskyltarna: ?q=hNN räknas som QR-besök när besöksräknaren är på.
    # Samma funktion som skylten, prospektet och sponsorstatistiken använder (golfholes/statistik.py).
    sys.path.insert(0, str(REPO))
    from golfholes.statistik import qr_lank
    klubb_web = (las_yaml(KLUBB / "klubb.yaml") or {}).get("web", "").rstrip("/")
    if klubb_web != DOMAN.rstrip("/"):
        varningar.append(f"DOMAN ({DOMAN}) och web i klubb.yaml ({klubb_web}) skiljer sig – QR-koderna på skyltarna pekar på klubb.yaml")
    (ROT / "qr-lankar.csv").write_text(
        "hal,adress\n" + "".join(f"{h['nr']},{qr_lank({'web': DOMAN}, h['nr'])}\n" for h in hal),
        encoding="utf-8")
    return adresser


def kontrollera(lansering: bool = False) -> list[str]:
    """Trasiga interna länkar, bilder utan alt-text, förbjudna ord och – inför lansering – flaggorna."""
    fel = []
    noindex = 0
    for fil in UT.rglob("*.html"):
        text = fil.read_text(encoding="utf-8")
        namn = fil.relative_to(UT)
        for img in re.findall(r"<img\b[^>]*>", text):
            if 'alt="' not in img:
                fel.append(f"{namn}: bild utan alt-text: {img[:80]}")
        for lank in re.findall(r'(?:href|src)="(/[^"#?]*)', text):
            mal = UT / lank.lstrip("/")
            if lank.endswith("/"):
                mal = mal / "index.html"
            if not mal.exists():
                fel.append(f"{namn}: trasig länk {lank}")
        for srcset in re.findall(r'srcset="([^"]+)"', text):
            for bit in srcset.split(","):
                vag = bit.strip().split(" ")[0]
                if vag.startswith("/") and not (UT / vag.lstrip("/")).exists():
                    fel.append(f"{namn}: bild saknas {vag}")
        for ord_ in ("GameBook", "Emtec", "[FYLL I", "Lorem", "TODO", "{{"):
            if ord_.lower() in text.lower():
                fel.append(f"{namn}: innehåller förbjudet ord/platshållare: {ord_}")
        if re.search(r"\bAI\b", text):
            fel.append(f"{namn}: ordet AI får inte stå på sajten (inga AI-stämplar)")
        if "Lantmäteriet" not in text:
            fel.append(f"{namn}: saknar Lantmäteriets källtext")
        if lansering and "noindex" in text:
            noindex += 1
    if noindex:
        fel.append(f"noindex kvar på {noindex} sidor (sätt LANSERAD = True)")
    if lansering:
        if not LANSERAD:
            fel.append("LANSERAD är False")
        if not PLAUSIBLE_DOMAN:
            fel.append("PLAUSIBLE_DOMAN saknas – QR-besök och sidvisningar räknas inte (sponsorstatistiken)")
        if not BOKNING_URL.startswith("https://"):
            fel.append("BOKNING_URL saknas eller är inte https")
    return fel


def forhandsvisning(mal) -> Path:
    """Kopia med relativa länkar, så att sajten kan visas utan webbserver."""
    mal = Path(mal)
    if mal.exists():
        shutil.rmtree(mal)
    shutil.copytree(UT, mal)
    for fil in mal.rglob("*.html"):
        rel = "../" * (len(fil.relative_to(mal).parts) - 1)

        def lank(m):
            attr, vag = m.group(1), m.group(2)
            if vag == "" or vag.endswith("/"):
                vag += "index.html"
            return f'{attr}="{rel}{vag}'

        text = fil.read_text(encoding="utf-8")
        text = re.sub(r'(href|src|action)="/([^"]*?)(?=["#?])', lank, text)
        text = re.sub(r'srcset="([^"]+)"', lambda m: 'srcset="' + m.group(1).replace("/img/", rel + "img/") + '"', text)
        fil.write_text(text, encoding="utf-8")
    css = mal / "css" / "site.css"
    css.write_text(css.read_text(encoding="utf-8").replace("url(/fonts/", "url(../fonts/"), encoding="utf-8")
    return mal


if __name__ == "__main__":
    adresser = bygg()
    fel = kontrollera(lansering="--lansering-kontroll" in sys.argv)
    print(f"Byggde {len(adresser)} sidor till {UT}")
    for v in varningar:
        print("VARNING:", v)
    if "--forhandsvisning" in sys.argv:
        print("Förhandsvisning:", forhandsvisning(sys.argv[sys.argv.index("--forhandsvisning") + 1]))
    for f_ in fel:
        print("FEL:", f_)
    if "--lansering-kontroll" in sys.argv and not fel:
        print("Klar att lansera.")
    sys.exit(1 if fel else 0)
