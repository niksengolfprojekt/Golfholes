"""Sponsorstatistik och partnerexport – med påhittade TESTDATA i tests/fixtures/testklubb/."""
import json
import shutil
import zipfile
from pathlib import Path

import yaml

from golfholes.partnerexport import exportera, lank_med_utm, svg_en_farg
from golfholes.render.sponsorrapport import sida_html, tal
from golfholes.statistik import matkod, qr_lank, sammanstall

ROOT = Path(__file__).parent.parent
KLUBB = ROOT / "tests" / "fixtures" / "testklubb"
KALLA = KLUBB / "statistik" / "2027"


def _kanaler(r, nr=14):
    h = next(h for h in r.hal if h.hal == nr)
    return h, {k.namn: k for k in h.kanaler}


def test_sammanstallning_per_kanal():
    r = sammanstall(KLUBB, 2027, KALLA)
    assert r.testdata and r.klubb == "Ekbacka Golfklubb"
    h, k = _kanaler(r)
    assert h.sponsor["name"] == "Nordvik" and h.par == 4
    # Hålsidan: 512 + 604 + 689 + 14 (sidan med ?q= räknas också som hålsidan)
    assert k["Hålsidan på webben"].visningar == 1819
    assert k["Hålsidan på webben"].klick == 37
    # QR: mätkodens egenskap q går före sidnamnet med ?q= (juli: 240, inte 14)
    assert k["varav via QR-koden på skylten"].visningar == 163 + 217 + 240
    # Partner: bara rätt klubb och säsong 2027
    assert k["Digital partnerkanal"].visningar == 2310 + 2875 + 3120
    assert k["Digital partnerkanal"].klick == 41 + 55 + 62
    # Tee-skylten = ronder × andel (1,0), märkt uppskattning
    assert k["Tee-skylten"].visningar == 24000 and k["Tee-skylten"].uppskattning
    # QR ingår redan i hålsidan och räknas inte två gånger; tee-uppskattningen ligger utanför
    assert h.digitala_visningar == 1819 + 8305
    assert h.manader() == {"2027-05": 512 + 2310, "2027-06": 604 + 2875, "2027-07": 703 + 3120}


def test_plausible_zip_och_saknade_ronder(tmp_path):
    klubb = tmp_path / "klubb"
    shutil.copytree(KLUBB, klubb)
    c = yaml.safe_load((klubb / "klubb.yaml").read_text(encoding="utf-8"))
    del c["ronder_per_ar"]
    (klubb / "klubb.yaml").write_text(yaml.safe_dump(c, allow_unicode=True), encoding="utf-8")
    pl = klubb / "statistik" / "2027" / "plausible"
    with zipfile.ZipFile(pl / "plausible-2027-08.zip", "w") as z:
        z.writestr("pages.csv", "name,visitors,pageviews\n/hal-14/,10,20\n")
    r = sammanstall(klubb, 2027, klubb / "statistik" / "2027")
    h, k = _kanaler(r)
    assert k["Hålsidan på webben"].manader["2027-08"] == 20
    assert "Tee-skylten" not in k and "ronder" in h.saknas
    assert any("ronder" in v for v in r.varningar)


def test_sida_visar_visningar_testdata_och_aldrig_personer():
    r = sammanstall(KLUBB, 2027, KALLA)
    h, _ = _kanaler(r)
    page = sida_html(r, h, KLUBB)
    assert "Nordvik-hålet" in page and "TESTDATA" in page
    assert "uppskattning" in page and "Visningar" in page
    assert tal(24000) in page and tal(10124) in page
    low = page.lower()
    for ord_ in ("personer såg", "besökare", "unika", "människor"):
        assert ord_ not in low
    assert "inte antal personer" in low  # förklaringen i sidfoten
    assert "gamebook" not in low


def test_qr_lank_och_matkod():
    club = {"web_base": "https://exempel.se/ekbacka/", "statistik": {"plausible_doman": "exempel.se"}}
    assert qr_lank(club, 3) == "https://exempel.se/ekbacka/hal-03/?q=h03"
    # klubbhemsidorna: hålsidan under /banan/ (samma adress som hemsidor/glasriket bygger)
    assert qr_lank({"web": "https://www.glasriketsgk.se"}, 3) == "https://www.glasriketsgk.se/banan/hal-03/?q=h03"
    mall = {"web": "https://x.se", "sponsring": {"halsida": "https://y.se/hal/{hal}/"}}
    assert qr_lank(mall, 7) == "https://y.se/hal/7/?q=h07"
    kod = matkod(club)
    assert 'data-domain="exempel.se"' in kod and "props:q?{q:q}" in kod and "Sponsorklick" in kod
    assert matkod({}) == ""


def test_partnerexport(tmp_path):
    filer, varningar = exportera(KLUBB, tmp_path)
    d = json.loads((tmp_path / "hal-14.json").read_text(encoding="utf-8"))
    assert d["klubb"] == "Ekbacka Golfklubb" and d["bana"] == "Ekbackabanan" and d["hal"] == 14 and d["par"] == 4
    sp = d["sponsor"]
    assert sp["namn"] == "Nordvik" and sp["halnamn"] == "Nordvik-hålet"
    assert sp["lank"] == ("https://nordvik.se/?utm_source=partnerapp&utm_medium=halsponsor"
                          "&utm_campaign=testklubb-hal-14")
    assert sp["giltig_fran"] == "2027-04-01" and sp["giltig_till"] == "2027-10-31"
    svg = (tmp_path / sp["logga_svg"]).read_text(encoding="utf-8")
    assert "#3b8fb5" not in svg and "#1d4e6b" not in svg  # en färg
    # Hål 13 saknar sponsor men exporteras med par
    d13 = json.loads((tmp_path / "hal-13.json").read_text(encoding="utf-8"))
    assert d13["sponsor"] is None and d13["par"] == 3
    # Ingen geometri eller hålbild i exporten
    with zipfile.ZipFile(tmp_path / "testklubb-partnerexport.zip") as z:
        namn = z.namelist()
    assert "hal-14.json" in namn and sp["logga_svg"] in namn
    assert not any(n.endswith((".webp", ".jpg", ".yaml")) for n in namn)
    text = json.dumps(d).lower()
    for f in ("centerline", "green", "tees", "origin", "bild"):
        assert f not in text


def test_utm_behaller_egna_parametrar_och_svg_en_farg():
    assert lank_med_utm("https://a.se/x?id=5&utm_source=gammal", "k", 2) == (
        "https://a.se/x?id=5&utm_source=partnerapp&utm_medium=halsponsor&utm_campaign=k-hal-02")
    assert lank_med_utm("", "k", 2) is None
    s = svg_en_farg('<svg><rect fill="red" style="stroke:#00f;fill:none"/></svg>', "#111111")
    assert 'fill="#111111"' in s and "stroke:#111111" in s and "fill:none" in s


if __name__ == "__main__":
    import inspect
    import tempfile

    for n, f in list(globals().items()):
        if n.startswith("test_"):
            if "tmp_path" in inspect.signature(f).parameters:
                with tempfile.TemporaryDirectory() as t:
                    f(Path(t))
            else:
                f()
            print("ok", n)
