"""Hemsidan byggs utan trasiga länkar, och Glasriket syns inte före styrelsens beslut."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("bygg", Path(__file__).resolve().parents[1] / "hemsida" / "bygg.py")
bygg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bygg)


def test_hemsidan_byggs_utan_fel():
    adresser = bygg.bygg()
    assert "https://tacada.se/golfklubbar/" in adresser
    assert bygg.kontrollera() == []


def test_glasriket_doljs_tills_styrelsen_sagt_ja():
    if bygg.REFERENS_GLASRIKET:
        return
    bygg.bygg()
    assert not (bygg.UT / "referenser" / "glasriket" / "index.html").exists()
    for html in bygg.UT.rglob("*.html"):
        if html.relative_to(bygg.UT).parts[0] == "granskning":  # klubbens egen hemliga granskningslänk
            continue
        assert "Glasriket" not in html.read_text(encoding="utf-8"), html


def test_inga_priser_fran_tacada():
    bygg.bygg()
    for html in bygg.UT.rglob("*.html"):
        text = html.read_text(encoding="utf-8")
        for pris in ("99 990", "224 945", "79 990", "39 990", "19 995"):
            assert pris not in text, (html, pris)


def test_inga_ai_stamplar():
    import re
    from pathlib import Path
    publik = Path(__file__).resolve().parents[1] / "hemsida" / "public"
    for fil in publik.rglob("*.html"):
        text = fil.read_text(encoding="utf-8")
        assert not re.search(r"\bAI\b", text), f"AI-stämpel i {fil}"
        assert 'class="ai"' not in text, f"AI-etikett i {fil}"
