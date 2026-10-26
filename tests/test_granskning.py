import shutil
from pathlib import Path

from golfholes.granskning import bygg

EKBACKA = Path(__file__).resolve().parent.parent / "klubbar" / "exempel-ekbacka"


def test_granskningssida_fragar_per_tee_och_ger_besked(tmp_path):
    klubb = tmp_path / "exempel-ekbacka"
    shutil.copytree(EKBACKA, klubb)
    (klubb / "granskning.yaml").write_text(
        "nyckel: test1234\nfragor:\n  7: ['Är greenen ombyggd?']\n  klubb: ['Har ni en ny klubbchef?']\n", encoding="utf-8")
    mal, _ = bygg(klubb, sajt=tmp_path / "sajt")
    assert mal == tmp_path / "sajt" / "granskning" / "exempel-ekbacka-test1234"
    s = (mal / "index.html").read_text(encoding="utf-8")
    assert 'data-netlify="true"' in s and 'name="granskning-exempel-ekbacka"' in s
    assert 'action="/granskning/exempel-ekbacka-test1234/tack/"' in s
    assert "noindex" in s and "Lantmäteriet" in s
    assert 'name="h07_besked"' in s and "Är greenen ombyggd?" in s and "Har ni en ny klubbchef?" in s
    assert s.count("ligger den där vi ritat den?") >= 1
    assert "AI" not in s.replace("MAIL", "")
    assert (mal / "tack" / "index.html").exists()


def test_nyckel_skapas_en_gang(tmp_path):
    klubb = tmp_path / "exempel-ekbacka"
    shutil.copytree(EKBACKA, klubb)
    (klubb / "granskning.yaml").unlink(missing_ok=True)
    forsta, _ = bygg(klubb, sajt=tmp_path / "sajt")
    andra, _ = bygg(klubb, sajt=tmp_path / "sajt")
    assert forsta == andra


def test_paket_stoppar_utan_bestallning_och_vid_saknad_grund():
    from golfholes.paket import kontrollera
    assert kontrollera({}) and "Fråga Eric" in kontrollera({})[0]
    assert kontrollera({"produkter": ["hemsida"]})          # hemsidan bygger på hålguiden
    assert kontrollera({"produkter": ["halguide", "hemsida"]}) == []
    assert kontrollera({"produkter": ["halguide", "tröjor"]})
