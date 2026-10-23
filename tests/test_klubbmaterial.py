"""Hålsponsorprospekt och inlägg: mallarna läser klubbens fält och följer reglerna."""
import re
from pathlib import Path

from golfholes.render import inlagg, prospekt
from golfholes.render.halkort import ATTRIBUTION, Halkort
from golfholes.render.klubbmaterial import Klubb, kr

ROOT = Path(__file__).parent.parent
GLAS = ROOT / "klubbar" / "glasriket"


def _utan_ai(html: str) -> bool:
    text = re.sub(r"<[^>]+>|data:[^'\"]+", " ", html)
    return re.search(r"\bAI\b", text) is None


def test_klubbens_falt_laeses_ur_klubb_yaml():
    k = Klubb.from_dir(GLAS)
    assert k.farger["djup"] == "#10202E" and k.farger["glod"] == "#D9A441"
    assert k.sponsring["pris_per_hal"] == 10000
    assert k.halsida(3) == "https://www.glasriketsgk.se/banan/hal-03/"
    assert k.qr_lank(3) == "https://www.glasriketsgk.se/banan/hal-03/?q=h03"
    assert all(p.exists() for p in k.loggor.values())
    assert kr(10000) == "10 000"


def test_prospekt_sex_sidor_med_pris_kalla_och_avsandare():
    k = Klubb.from_dir(GLAS)
    c = Halkort.from_yaml(GLAS / "halkort" / "hal-14.yaml")
    sidor, akta = prospekt.sidor(k, c, {"kortrad": "Spela hålet som ett par 5."})
    assert len(sidor) == prospekt.SIDOR
    allt = "".join(sidor)
    assert "10 000" in allt and "Material: TACADA" in allt and k.namn in allt
    assert ATTRIBUTION in sidor[0] and "Er logotyp här" in allt
    assert "visningar" in allt and "Uppskattning" in allt
    assert _utan_ai(allt)
    try:
        import segno  # noqa: F401
        assert akta, "QR-koden ska vara äkta när segno finns"
    except ImportError:
        assert not akta


def test_prospekt_pris_kommer_fran_klubben():
    k = Klubb.from_dir(GLAS)
    k.sponsring = {**k.sponsring, "pris_per_hal": 12500}
    c = Halkort.from_yaml(GLAS / "halkort" / "hal-03.yaml")
    assert "12 500" in "".join(prospekt.sidor(k, c)[0])


def test_inlaggslistan_ger_tjugo_inlagg():
    k = Klubb.from_dir(GLAS)
    poster = inlagg.las(GLAS)
    kort = k.halkort()
    klara = [p for p in poster if p["typ"] not in ("hal", "bli_sponsor") or int(p["hal"]) in kort]
    assert len(klara) >= 20
    for p in poster:
        assert p.get("bildtext"), p["id"]


def test_inlagg_visar_hela_halet_med_kalla_och_utan_ai():
    k = Klubb.from_dir(GLAS)
    kort = k.halkort()
    poster = {p["id"]: p for p in inlagg.las(GLAS)}
    for pid in ("hal-14", "bli-halsponsor", "fast-hal-for-hal"):
        html = inlagg.html_for(k, poster[pid], kort, Halkort.from_yaml)
        assert html and ATTRIBUTION in html and _utan_ai(html), pid
        assert "class='hal'" in html
    # hål utan hålbild hoppas över och kommer med nästa körning
    saknas = next((p for p in poster.values() if p["typ"] == "hal" and int(p["hal"]) not in kort), None)
    if saknas:
        assert inlagg.html_for(k, saknas, kort, Halkort.from_yaml) is None


def test_texter_md_har_bildtext_och_hashtags():
    k = Klubb.from_dir(GLAS)
    p = next(p for p in inlagg.las(GLAS) if p["id"] == "hal-17")
    md = inlagg.texter_md(k, [("01-hal-17.png", p)], [])
    assert "#glasriketsgk" in md and "#signaturhål" in md and "128 meter" in md
    assert "personer" not in md
