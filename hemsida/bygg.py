"""Bygger tacada.se: läser sidorna i hemsida/sidor/, lägger på sidhuvud och sidfot,
och skriver färdiga filer till hemsida/public/ (det är den mappen som publiceras).

Kör:  python hemsida/bygg.py
Kontroll inför lansering:  python hemsida/bygg.py --lansering
"""
import re
import sys
from pathlib import Path

ROT = Path(__file__).resolve().parent
SIDOR = ROT / "sidor"
UT = ROT / "public"
DOMAN = "https://tacada.se"

# --- Inställningar som ändras när beslut fattas ----------------------------------
# Sajten är inte lanserad: alla sidor får noindex och robots.txt stänger ute sökmotorer.
LANSERAD = False
# Glasrikets styrelse beslutar 2026-12-08. Till dess nämns klubben inte på sajten,
# och referenssidan byggs inte. Sätt True först när klubben godkänt texten skriftligt.
REFERENS_GLASRIKET = False
# Bolagsuppgifter. None visas som en tydlig lucka och stoppar lansering.
BOLAG = {
    "namn": None,       # t.ex. "Niksen AB"
    "orgnr": None,
    "epost": None,      # t.ex. "hej@tacada.se"
    "telefon": None,
    "ort": None,
}
# ------------------------------------------------------------------------------------

MENY = [
    ("golfklubbar/", "Golfklubbar"),
    ("halsponsorer/", "Hålsponsorer"),
    ("studio/", "Studio"),
    ("om/", "Om oss"),
    ("kontakt/", "Kontakt"),
]

LUCKA = '<span class="lucka">[FYLL I: {}]</span>'


def bolag(nyckel, etikett):
    v = BOLAG.get(nyckel)
    return v if v else LUCKA.format(etikett)


def las_sida(fil):
    text = fil.read_text(encoding="utf-8")
    m = re.match(r"<!--(.*?)-->\s*", text, re.S)
    if not m:
        raise SystemExit(f"{fil.name}: saknar huvud med titel/sokvag")
    meta = {}
    for rad in m.group(1).strip().splitlines():
        k, _, v = rad.partition(":")
        meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def ersatt(text):
    text = text.replace("{{epost}}", bolag("epost", "e-post"))
    text = text.replace("{{telefon}}", bolag("telefon", "telefon"))
    text = text.replace("{{bolag}}", bolag("namn", "bolagsnamn"))
    text = text.replace("{{orgnr}}", bolag("orgnr", "org.nr"))
    text = text.replace("{{ort}}", bolag("ort", "ort"))
    return text


def bygg_sida(meta, kropp, ordmarke):
    sokvag = meta["sokvag"]
    meny = "".join(
        f'<li><a href="/{u}"{" aria-current=\"page\"" if sokvag == u else ""}>{n}</a></li>' for u, n in MENY
    )
    ljus = meta.get("huvud") == "ljus"
    robots = "" if LANSERAD else '<meta name="robots" content="noindex, nofollow">\n'
    url = DOMAN + "/" + sokvag
    sida = f"""<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{meta["titel"]}</title>
<meta name="description" content="{meta["beskrivning"]}">
{robots}<link rel="canonical" href="{url}">
<meta property="og:title" content="{meta["titel"]}">
<meta property="og:description" content="{meta["beskrivning"]}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{DOMAN}/img/start-morgon.webp">
<meta property="og:locale" content="sv_SE">
<meta name="theme-color" content="#183329">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon-32.png" sizes="32x32">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preload" href="/fonts/marcellus-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/fonts/inter-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/css/site.css">
</head>
<body>
<a class="hoppa" href="#innehall">Till innehållet</a>
<header class="huvud{" ljus" if ljus else ""}">
  <div class="inne">
    <a class="ordmarke" href="/" aria-label="TACADA, till startsidan">{ordmarke}</a>
    <nav class="meny" aria-label="Huvudmeny"><ul>{meny}</ul></nav>
    <details class="mobilmeny"><summary>Meny</summary><ul>{meny}</ul></details>
  </div>
</header>
<main id="innehall">
{kropp}
</main>
<footer class="fot">
  <div class="inne">
    <div class="topp">
      <div style="display:grid;gap:14px;align-content:start">
        <a class="ordmarke" href="/" aria-label="TACADA, till startsidan">{ordmarke}</a>
        <p>Vi skapar värde till varje hål.</p>
      </div>
      <div><h2>Områden</h2><ul><li><a href="/golfklubbar/">Courses</a></li><li><a href="/halsponsorer/">Partners</a></li><li><a href="/studio/">Studio</a></li><li><a href="/editions/">Editions</a></li></ul></div>
      <div><h2>Kontakt</h2><ul><li>{{{{epost}}}}</li><li>{{{{telefon}}}}</li><li><a href="/kontakt/">Boka en visning</a></li></ul></div>
      <div><h2>Bolag</h2><ul><li>{{{{bolag}}}}</li><li>Org.nr {{{{orgnr}}}}</li><li><a href="/integritet/">Integritetspolicy</a></li></ul></div>
    </div>
    <div class="kallor">
      <span>Underlag: Ortofoto och Markhöjdmodell ©Lantmäteriet, bearbetat, CC BY 4.0.</span>
      <span>Sajten använder inga kakor för spårning.</span>
    </div>
  </div>
</footer>
<script src="/js/site.js" defer></script>
</body>
</html>
"""
    return ersatt(sida)


def bygg():
    ordmarke = (ROT / "mallar" / "ordmarke.svg").read_text(encoding="utf-8")
    ordmarke = re.sub(r"<title>.*?</title>", "", ordmarke)
    ordmarke = ordmarke.replace("<svg ", '<svg aria-hidden="true" focusable="false" ', 1)
    adresser = []
    for fil in sorted(SIDOR.glob("*.html")):
        meta, kropp = las_sida(fil)
        if meta.get("villkor") == "referens_glasriket" and not REFERENS_GLASRIKET:
            mal = UT / meta["sokvag"] / "index.html"
            if mal.exists():
                mal.unlink()
            continue
        sokvag = meta["sokvag"]
        mal = UT / "404.html" if sokvag == "404" else UT / sokvag / "index.html"
        mal.parent.mkdir(parents=True, exist_ok=True)
        mal.write_text(bygg_sida(meta, kropp, ordmarke), encoding="utf-8")
        if sokvag != "404" and meta.get("karta", "ja") == "ja":
            adresser.append(DOMAN + "/" + sokvag)
    (UT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{a}</loc></url>\n" for a in adresser)
        + "</urlset>\n",
        encoding="utf-8",
    )
    robots = (
        f"User-agent: *\nAllow: /\nSitemap: {DOMAN}/sitemap.xml\n" if LANSERAD else "User-agent: *\nDisallow: /\n"
    )
    (UT / "robots.txt").write_text(robots, encoding="utf-8")
    return adresser


def kontrollera(lansering=False):
    """Hittar trasiga interna länkar, bilder utan alt-text och – inför lansering – luckor."""
    fel = []
    for html in UT.rglob("*.html"):
        text = html.read_text(encoding="utf-8")
        namn = html.relative_to(UT)
        for img in re.findall(r"<img\b[^>]*>", text):
            if 'alt="' not in img:
                fel.append(f"{namn}: bild utan alt-text: {img[:80]}")
        for lank in re.findall(r'(?:href|src)="(/[^"#?]*)', text):
            mal = UT / lank.lstrip("/")
            if lank.endswith("/"):
                mal = mal / "index.html"
            if not mal.exists():
                fel.append(f"{namn}: trasig länk {lank}")
        for bild in re.findall(r"url\((/img/[^)]+)\)", text):
            if not (UT / bild.lstrip("/")).exists():
                fel.append(f"{namn}: bild saknas {bild}")
        if "Glasriket" in text and not REFERENS_GLASRIKET:
            fel.append(f"{namn}: nämner Glasriket före styrelsens beslut")
        if lansering:
            if "[FYLL I" in text:
                fel.append(f"{namn}: luckor kvar: " + ", ".join(sorted(set(re.findall(r"\[FYLL I: ([^\]]+)\]", text)))))
            if "noindex" in text:
                fel.append(f"{namn}: noindex kvar (sätt LANSERAD = True)")
    return fel


def forhandsvisning(mal):
    """Kopierar sajten med relativa länkar, så att den kan visas utan webbserver (t.ex. som Artifact)."""
    import shutil
    mal = Path(mal)
    if mal.exists():
        shutil.rmtree(mal)
    shutil.copytree(UT, mal)
    for html in mal.rglob("*.html"):
        djup = len(html.relative_to(mal).parts) - 1
        rel = "../" * djup

        def lank(m):
            attr, vag = m.group(1), m.group(2)
            if vag == "" or vag.endswith("/"):
                vag += "index.html"
            return f'{attr}="{rel}{vag}'

        text = html.read_text(encoding="utf-8")
        text = re.sub(r'(href|src|srcset|action)="/([^"]*?)(?=["#?])', lank, text)
        text = text.replace("url(/img/", f"url({rel}img/")
        html.write_text(text, encoding="utf-8")
    css = mal / "css" / "site.css"
    css.write_text(css.read_text(encoding="utf-8").replace("url(/fonts/", "url(../fonts/"), encoding="utf-8")
    return mal


if __name__ == "__main__":
    adresser = bygg()
    fel = kontrollera(lansering="--lansering" in sys.argv)
    print(f"Byggde {len(adresser)} sidor till {UT}")
    if "--forhandsvisning" in sys.argv:
        print("Förhandsvisning:", forhandsvisning(sys.argv[sys.argv.index("--forhandsvisning") + 1]))
    for f in fel:
        print("FEL:", f)
    sys.exit(1 if fel else 0)
