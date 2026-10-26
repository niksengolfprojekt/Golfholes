"""Granskningssida för klubbchefen: en sida per klubb där varje fråga per hål ställs och klubben svarar direkt.

    python -m golfholes granskning klubbar/<klubb> [--hal 3,14]

Sidan byggs in i TACADA:s sajt (hemsida/public/granskning/<klubb>-<nyckel>/) och publiceras med den.
Svaren tas emot av Netlify Forms (formuläret heter granskning-<klubb>). Adressen innehåller en slumpad
nyckel och sidan indexeras aldrig, så bara den som får länken hittar den.

Frågorna räknas fram ur repot, samma för varje klubb:
- varje tee: ligger den där vi ritat den? (märkt "osäker" om längden avviker mer än 3 % eller
  fröfilen säger att teen är beräknad/uppskattad)
- out: stämmer linjerna vi ritat, eller finns out som vi inte vet om?
- hålets texter och pro:ns råd
- egna frågor per hål och för klubben i klubbar/<klubb>/granskning.yaml
- klubbfrågor: förra säsongens ronder (om de saknas), ändringar på banan efter flygfotot
Sist: godkänt / godkänt med ändringar / inte godkänt per hål, och klubbchefens namn som intyg.
"""
from __future__ import annotations

import html
import json
import os
import re
import secrets
import shutil
import sys
from datetime import date
from pathlib import Path

import yaml
from PIL import Image

from .hole import Hole

REPO = Path(__file__).resolve().parent.parent
SAJT = REPO / "hemsida" / "public"
BILDHOJD = 2800  # klubbchefen ska se hålen i den kvalitet de levereras
OSAKER_ORD = re.compile(r"beräkn|uppskatt|syns inte|osäker|bekräft", re.I)
SIDA = {"hoger": "högersidan", "vanster": "vänstersidan", "höger": "högersidan", "vänster": "vänstersidan"}


def e(s) -> str:
    return html.escape(str(s), quote=True)


def _installningar(klubbmapp: Path) -> dict:
    """klubbar/<klubb>/granskning.yaml: nyckeln i adressen + egna frågor. Skapas första gången."""
    fil = klubbmapp / "granskning.yaml"
    if fil.exists():
        return yaml.safe_load(fil.read_text(encoding="utf-8")) or {}
    nyckel = secrets.token_hex(4)
    fil.write_text(
        "# Granskningssidan för klubbchefen (python -m golfholes granskning klubbar/<klubb>).\n"
        "# nyckel: slumpad del av adressen – byt den om länken hamnat fel, så slutar den gamla fungera.\n"
        "# fragor: egna frågor per hål (nummer) och för hela klubben (klubb). En rad per fråga.\n"
        f"nyckel: {nyckel}\n"
        "fragor:\n"
        "  klubb: []\n",
        encoding="utf-8")
    return {"nyckel": nyckel, "fragor": {"klubb": []}}


def _osakra_tees(klubbmapp: Path, n: int) -> set[str]:
    """Teenamn som fröfilen själv kallar beräknade/uppskattade (kommentar på samma rad eller raden före)."""
    fro = klubbmapp / "utkast" / f"hal-{n:02d}.yaml"
    if not fro.exists():
        return set()
    rader = fro.read_text(encoding="utf-8").splitlines()
    ut = set()
    for i, rad in enumerate(rader):
        m = re.search(r"name:\s*'?\"?([^,'\"}]+)", rad)
        if not m:
            continue
        namn = m.group(1).strip()
        intill = rad + " " + (rader[i - 1] if i and rader[i - 1].lstrip().startswith("#") else "")
        if OSAKER_ORD.search(intill.split("#", 1)[1] if "#" in intill else ""):
            ut.add(namn)
    return ut


def _orto(klubbmapp: Path) -> Path | None:
    """Klubbens ortofoto: Lantmäteriets ruta i data/<klubb>/, annars det sparade utsnittet
    (verktyg/orto_utsnitt, GOLF_LM pekar på mappen). None om inget finns här."""
    slug = klubbmapp.name
    logg = REPO / "data" / slug / "lantmateriet.json"
    if not list((REPO / "data" / slug / "orto").glob("*.tif")):
        os.environ.setdefault("GOLF_KLUBB", slug)
        try:
            sys.path.insert(0, str(REPO))
            import verktyg.orto_utsnitt  # noqa: F401 – läser utsnittet i stället för rutan
        except Exception:  # noqa: BLE001 – utan utsnitt används hemsidans bild
            return None
    if not logg.exists():
        return None
    fil = Path(next(f["fil"] for f in json.loads(logg.read_text(encoding="utf-8"))["filer"] if f["katalog"] == "orto"))
    fil = fil if fil.is_absolute() else REPO / fil
    return fil if fil.exists() else None


def _bild(klubbmapp: Path, n: int, mal: Path, botten: str) -> tuple[str | None, str | None]:
    """Hålbilden i den kvalitet klubben ska få, med dagens tees inritade. Ritas ur den målade
    bilden och hålfilen; finns inte ortofotot här tas hemsidans (mindre) bild, med varning."""
    malad = next((klubbmapp / "halbilder" / namn for namn in (f"hal-{n:02d}-malad.webp", f"hal-{n:02d}-foto.webp")
                  if (klubbmapp / "halbilder" / namn).exists()), None)
    halfil = klubbmapp / f"hal-{n:02d}.yaml"
    kalla, varning = None, None
    orto = _orto(klubbmapp) if malad and halfil.exists() else None
    if orto:
        from .render.foto import markera_halbild

        tmp = mal / f"hal-{n:02d}-tmp.png"
        mal.mkdir(parents=True, exist_ok=True)
        bild, _ = markera_halbild(Hole.from_yaml(halfil), orto, malad, tmp, halfil=halfil)
        if bild == tmp:
            kalla = tmp
        else:
            varning = f"Hål {n}: bilden passar inte hålfilen – tees ej inritade"
    if not kalla:
        cache = sorted((REPO / "hemsidor" / klubbmapp.name / "cache").glob(f"hal-{n:02d}-*.webp"))
        if cache:
            kalla, varning = cache[-1], varning or f"Hål {n}: ortofotot saknas här – hemsidans mindre bild används"
        elif malad:
            kalla, varning = malad, f"Hål {n}: bilden saknar inritade tees (hämta Lantmäteriets data först)"
    if not kalla:
        return None, f"Hål {n}: ingen hålbild – frågorna ställs utan bild"
    rgba = Image.open(kalla).convert("RGBA")
    im = Image.new("RGB", rgba.size, botten)
    im.paste(rgba, (0, 0), rgba)
    if im.height > BILDHOJD:
        im = im.resize((round(im.width * BILDHOJD / im.height), BILDHOJD), Image.LANCZOS)
    mal.mkdir(parents=True, exist_ok=True)
    fil = mal / f"hal-{n:02d}.webp"
    im.save(fil, quality=88, method=6)
    if kalla.name.endswith("-tmp.png"):
        kalla.unlink()
    return fil.name, varning


def _val(namn: str, alternativ: list[str], kravs: bool = False) -> str:
    return '<div class="val">' + "".join(
        f'<label><input type="radio" name="{e(namn)}" value="{e(a)}"{" required" if kravs and i == 0 else ""}> {e(a)}</label>'
        for i, a in enumerate(alternativ)) + "</div>"


def _fritext(namn: str, platshallare: str = "Skriv här om något ska ändras") -> str:
    return f'<textarea name="{e(namn)}" rows="2" placeholder="{e(platshallare)}"></textarea>'


def _fraga(rubrik: str, falt: str, alternativ: list[str], hjalp: str = "", osaker: bool = False) -> str:
    flagga = '<span class="osaker">Vi är osäkra här</span>' if osaker else ""
    return (f'<fieldset class="fraga{" ar-osaker" if osaker else ""}"><legend>{e(rubrik)} {flagga}</legend>'
            + (f"<p class=\"hjalp\">{e(hjalp)}</p>" if hjalp else "")
            + _val(falt, alternativ) + _fritext(falt + "_kommentar") + "</fieldset>")


def _hal_sektion(klubbmapp: Path, n: int, extra: list[str], bildmapp: Path, varningar: list[str], botten: str) -> str:
    hole = Hole.from_yaml(klubbmapp / f"hal-{n:02d}.yaml")
    rad = yaml.safe_load((klubbmapp / f"hal-{n:02d}.yaml").read_text(encoding="utf-8"))
    kortfil = klubbmapp / "halkort" / f"hal-{n:02d}.yaml"
    kort = yaml.safe_load(kortfil.read_text(encoding="utf-8")) if kortfil.exists() else {}
    bild, varning = _bild(klubbmapp, n, bildmapp, botten)
    if varning:
        varningar.append(varning)
    osakra = _osakra_tees(klubbmapp, n)
    p = f"h{n:02d}"
    delar = []

    for r in hole.check_lengths():
        osaker = r["tee"] in osakra or (r.get("ok") is False)
        langd = f"Vi mäter {r['uppmätt']} m till mitten av greenen"
        if r["scorekort"]:
            langd += f", scorekortet säger {r['scorekort']} m."
        falt = f"{p}_tee_{re.sub(r'[^0-9a-z]+', '-', r['tee'].lower())}"
        delar.append(_fraga(f"Tee {r['tee']}: ligger den där vi ritat den?", falt,
                            ["Ja", "Nej, se kommentar"], langd, osaker))

    ob = rad.get("ob") or []
    if ob:
        text = "; ".join(f"längs {SIDA.get(o.get('sida'), o.get('sida', ''))}"
                         + (f" från {o['fran_m']} till {o['till_m']} m från bakre tee" if "fran_m" in o else "")
                         for o in ob)
        delar.append(_fraga("Out: stämmer linjerna på bilden?", f"{p}_out", ["Ja", "Nej, se kommentar"],
                            f"Vi har ritat out {text}."))
    else:
        delar.append(_fraga("Out: finns det out på hålet?", f"{p}_out",
                            ["Nej, ingen out", "Ja, se kommentar"], "Vi har inte ritat någon out på det här hålet."))

    if kort:
        texter = [kort.get("rubrik", ""), kort.get("beskrivning", "")] + list(kort.get("rad") or []) + [kort.get("slutrad", "")]
        visas = "".join(f"<p>{e(t)}</p>" for t in texter if t)
        delar.append(f'<div class="texter"><h4>Texterna på hålkortet</h4>{visas}</div>'
                     + _fraga("Stämmer texterna och pro:ns råd?", f"{p}_text", ["Ja", "Ändra, se kommentar"]))

    for i, fraga in enumerate(extra, 1):
        delar.append(_fraga(fraga, f"{p}_extra{i}", ["Ja", "Nej, se kommentar"]))

    status = ('<fieldset class="fraga status"><legend>Ert besked för hål ' f"{n}</legend>"
              + _val(f"{p}_besked", ["Godkänt", "Godkänt med ändringarna ovan", "Inte godkänt"], kravs=True)
              + "</fieldset>")
    bildhtml = ((f'<figure><a href="{e(bild)}" target="_blank" rel="noopener"><img src="{e(bild)}" '
                 f'alt="Hål {n} ovanifrån med tees utmärkta" loading="lazy"></a>'
                 '<figcaption>Tryck på bilden för att se den i full storlek.</figcaption></figure>')
                if bild else "")
    tees = " · ".join(f"{t.name}: {t.length_m} m" for t in hole.tees if t.length_m)
    return (f'<section class="hal" id="hal-{n}"><div class="halhuvud"><h3>Hål {n}</h3>'
            f'<p>Par {hole.par}{f" · Index {hole.index}" if hole.index else ""} · {e(tees)}</p></div>'
            f'<div class="halkropp">{bildhtml}<div class="fragor">{"".join(delar)}{status}</div></div></section>')


def bygg(klubbmapp: Path, hal: list[int] | None = None, sajt: Path = SAJT) -> tuple[Path, list[str]]:
    klubb = yaml.safe_load((klubbmapp / "klubb.yaml").read_text(encoding="utf-8"))
    inst = _installningar(klubbmapp)
    slug = klubbmapp.name
    mal = sajt / "granskning" / f"{slug}-{inst['nyckel']}"
    if mal.exists():
        shutil.rmtree(mal)
    mal.mkdir(parents=True)
    fragor = inst.get("fragor") or {}
    nummer = hal or sorted(int(f.stem[4:]) for f in klubbmapp.glob("hal-[0-9][0-9].yaml"))
    varningar: list[str] = []
    botten = ((klubb.get("profil") or {}).get("farger") or {}).get("djup", "#101F2B")  # bildens botten = hålkortets
    sektioner = "".join(_hal_sektion(klubbmapp, n, list(fragor.get(n) or fragor.get(str(n)) or []), mal, varningar, botten)
                        for n in nummer)

    namn = klubb.get("kortnamn") or klubb.get("club", slug)
    klubbfragor = []
    if not (klubb.get("sponsring") or {}).get("ronder_per_ar"):
        klubbfragor.append('<fieldset class="fraga"><legend>Hur många ronder spelades på banan förra säsongen?</legend>'
                           '<p class="hjalp">Medlemsronder och greenfeeronder tillsammans. Siffran visar sponsorerna hur många som passerar deras hål.</p>'
                           '<input type="number" name="klubb_ronder" min="0" inputmode="numeric"></fieldset>')
    orto = (klubb.get("lantmateriet") or {}).get("ortofoto", "")
    klubbfragor.append(_fraga("Har något på banan ändrats sedan flygfotot togs?", "klubb_andringar",
                              ["Nej", "Ja, se kommentar"],
                              "Till exempel nya bunkrar, flyttade tees eller nya gångvägar." + (" Flygfotot är från sommaren 2025." if "2025" in str(orto) else "")))
    for i, f in enumerate(fragor.get("klubb") or [], 1):
        klubbfragor.append(_fraga(f, f"klubb_extra{i}", ["Ja", "Nej, se kommentar"]))

    form = f"granskning-{slug}"
    sida = MALL.format(
        titel=e(f"{namn} – granskning av hålen"), klubb=e(namn), form=e(form), tack=e(f"/{mal.relative_to(sajt).as_posix()}/tack/"), antal=len(nummer),
        meny="".join(f'<a href="#hal-{n}">{n}</a>' for n in nummer),
        sektioner=sektioner, klubbfragor="".join(klubbfragor), datum=date.today().isoformat())
    (mal / "index.html").write_text(sida, encoding="utf-8")
    tack = mal / "tack"
    tack.mkdir()
    (tack / "index.html").write_text(TACK.format(klubb=e(namn)), encoding="utf-8")
    return mal, varningar


MALL = """<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{titel}</title>
<link rel="preload" href="/fonts/marcellus-latin.woff2" as="font" type="font/woff2" crossorigin>
<style>
@font-face{{font-family:"Marcellus";src:url(/fonts/marcellus-latin.woff2) format("woff2");font-display:swap}}
@font-face{{font-family:"Inter";src:url(/fonts/inter-latin.woff2) format("woff2");font-weight:100 900;font-display:swap}}
:root{{--tallgron:#183329;--elfenben:#F3EDE2;--sand:#EAE2D3;--brons:#B7955E;--morkbrons:#7F6640;--natt:#101F2B;
--kol:#292D28;--linje:#D8CDB9;--dampad:#5C5F57;--rubrik:"Marcellus",Georgia,serif;--text:"Inter",system-ui,sans-serif}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--elfenben);color:var(--kol);font:17px/1.55 var(--text)}}
header{{background:var(--tallgron);color:var(--elfenben);padding:40px 16px 32px}}
header .inre,main{{max-width:1040px;margin:0 auto}}
.marke{{font:15px var(--rubrik);letter-spacing:.3em;color:var(--brons)}}
h1,h2,h3{{font-family:var(--rubrik);font-weight:400;margin:0}}
h1{{font-size:clamp(30px,6vw,46px);line-height:1.15;margin:14px 0 12px}}
header p{{max-width:640px;margin:0;color:#d9dcd3}}
nav.hal-meny{{position:sticky;top:0;z-index:2;background:var(--sand);border-bottom:1px solid var(--linje);
display:flex;gap:6px;overflow-x:auto;padding:10px 16px}}
nav.hal-meny a{{flex:0 0 auto;min-width:40px;height:40px;display:grid;place-items:center;border-radius:20px;
border:1px solid var(--linje);color:var(--tallgron);text-decoration:none;font-weight:600;background:var(--elfenben)}}
main{{padding:8px 16px 64px}}
.hal{{border-bottom:1px solid var(--linje);padding:40px 0;scroll-margin-top:60px}}
.halhuvud{{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 18px;margin-bottom:20px}}
.halhuvud h3{{font-size:34px;color:var(--tallgron)}}
.halhuvud p{{margin:0;color:var(--dampad)}}
.halkropp{{display:grid;grid-template-columns:minmax(0,340px) minmax(0,1fr);gap:32px;align-items:start}}
figure{{margin:0;position:sticky;top:76px}}
figure img{{width:100%;height:auto;display:block;border-radius:6px;background:var(--natt)}}
figcaption{{font-size:.8rem;opacity:.7;margin-top:6px}}
@media (max-width:760px){{.halkropp{{grid-template-columns:1fr}} figure{{position:static;max-width:340px}}}}
fieldset{{border:0;margin:0 0 22px;padding:0}}
legend{{font-weight:600;font-size:18px;padding:0;margin-bottom:6px}}
.hjalp{{margin:0 0 8px;color:var(--dampad)}}
.osaker{{display:inline-block;margin-left:6px;font-size:13px;font-weight:600;color:#fff;background:var(--morkbrons);
border-radius:12px;padding:2px 10px;vertical-align:2px}}
.val{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px}}
.val label{{display:flex;align-items:center;gap:8px;min-height:44px;padding:8px 14px;border:1px solid var(--linje);
border-radius:8px;background:#fff;cursor:pointer}}
.val label:has(input:checked){{border-color:var(--tallgron);box-shadow:inset 0 0 0 1px var(--tallgron)}}
textarea,input[type=text],input[type=email],input[type=number]{{width:100%;font:inherit;padding:10px 12px;
border:1px solid var(--linje);border-radius:8px;background:#fff}}
.texter{{background:var(--sand);border-radius:8px;padding:16px 18px;margin-bottom:12px}}
.texter h4{{margin:0 0 8px;font-size:14px;letter-spacing:.08em;text-transform:uppercase;color:var(--dampad)}}
.texter p{{margin:0 0 8px}}
.status{{background:#fff;border:1px solid var(--linje);border-radius:8px;padding:16px 18px}}
.klubb,.intyg{{padding:40px 0}}
.klubb h2,.intyg h2{{font-size:30px;color:var(--tallgron);margin-bottom:18px}}
.intyg label.kryss{{display:flex;gap:10px;align-items:flex-start;margin:16px 0}}
.rad{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}
.rad label{{display:block;font-weight:600}}
button{{font:600 17px var(--text);color:var(--elfenben);background:var(--tallgron);border:0;border-radius:8px;
padding:14px 28px;min-height:48px;cursor:pointer}}
.sparat{{color:var(--dampad);font-size:14px;margin-left:12px}}
footer{{max-width:1040px;margin:0 auto;padding:0 16px 40px;color:var(--dampad);font-size:14px}}
.dold{{display:none}}
</style>
</head>
<body>
<header><div class="inre">
<div class="marke">TACADA</div>
<h1>{klubb}: stämmer hålen?</h1>
<p>Här är era {antal} hål som vi ritat dem. Svara på frågorna under varje hål och ge ert besked. Era svar sparas i den här webbläsaren medan ni fyller i, så ni kan ta en paus och fortsätta senare. Inget trycks eller publiceras innan ni har godkänt hålet.</p>
</div></header>
<nav class="hal-meny" aria-label="Hål">{meny}</nav>
<main>
<form name="{form}" method="POST" action="{tack}" data-netlify="true" netlify-honeypot="bot-falt" id="granskning">
<input type="hidden" name="form-name" value="{form}">
<p class="dold"><label>Fyll inte i: <input name="bot-falt"></label></p>
{sektioner}
<section class="klubb"><h2>Om banan</h2>{klubbfragor}</section>
<section class="intyg"><h2>Ert godkännande</h2>
<div class="rad">
<label>Namn<input type="text" name="namn" required autocomplete="name"></label>
<label>Roll i klubben<input type="text" name="roll" required placeholder="T.ex. klubbchef"></label>
<label>E-post<input type="email" name="epost" required autocomplete="email"></label>
</div>
<label class="kryss"><input type="checkbox" name="intyg" value="ja" required> Jag har gått igenom hålen och ger beskeden ovan för klubbens räkning.</label>
<button type="submit">Skicka svaren</button><span class="sparat" id="sparat"></span>
</section>
</form>
</main>
<footer>Underlag: Ortofoto och Markhöjdmodell ©Lantmäteriet, bearbetat, CC BY 4.0 · Sidan byggd {datum}</footer>
<script>
(function(){{
  var f=document.getElementById("granskning"), k="tacada-{form}", s=document.getElementById("sparat");
  function las(){{try{{return JSON.parse(localStorage.getItem(k)||"{{}}")}}catch(x){{return {{}}}}}}
  var d=las();
  Array.prototype.forEach.call(f.elements,function(el){{
    if(!el.name||!(el.name in d)||el.type==="hidden")return;
    if(el.type==="radio")el.checked=(el.value===d[el.name]);
    else if(el.type==="checkbox")el.checked=!!d[el.name];
    else el.value=d[el.name];
  }});
  f.addEventListener("input",function(){{
    var u={{}};
    Array.prototype.forEach.call(f.elements,function(el){{
      if(!el.name||el.type==="hidden"||el.name==="bot-falt")return;
      if(el.type==="radio"){{if(el.checked)u[el.name]=el.value}}
      else if(el.type==="checkbox")u[el.name]=el.checked;
      else if(el.value)u[el.name]=el.value;
    }});
    try{{localStorage.setItem(k,JSON.stringify(u));s.textContent="Sparat i webbläsaren"}}catch(x){{}}
  }});
  f.addEventListener("submit",function(){{try{{localStorage.removeItem(k)}}catch(x){{}}}});
}})();
</script>
</body>
</html>
"""

TACK = """<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>Tack</title>
<style>body{{margin:0;background:#F3EDE2;color:#292D28;font:18px/1.6 system-ui,sans-serif;display:grid;place-items:center;min-height:100vh;padding:16px}}
h1{{font:400 36px Georgia,serif;color:#183329;margin:0 0 12px}}</style></head>
<body><div><h1>Tack!</h1><p>Vi har fått {klubb}s svar och återkommer med ändringarna innan något trycks eller publiceras.</p></div></body></html>
"""
