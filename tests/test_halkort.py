from pathlib import Path

from golfholes.render.halkort import FIELD_LIMITS, LAYOUTS, Halkort, parse_layout, render_html

ROOT = Path(__file__).parent.parent
HAL14 = ROOT / "klubbar" / "glasriket" / "halkort" / "hal-14.yaml"
HAL03 = ROOT / "klubbar" / "glasriket" / "halkort" / "hal-03.yaml"


def test_halkort_fits_every_layout():
    for f in (HAL14, HAL03):
        c = Halkort.from_yaml(f)
        assert c.kontroll() == [], f
        for n in LAYOUTS:
            page, w, h = render_html(c, n)
            assert f">{c.hole}<" in page and f"Index {c.index}" in page or f"<b>{c.index}</b>" in page
            assert w > 0 and h > 0


def test_same_template_for_every_hole():
    """Två olika hål ger exakt samma mall: bara innehållet skiljer."""
    a, b = Halkort.from_yaml(HAL14), Halkort.from_yaml(HAL03)
    for n in LAYOUTS:
        pa, pb = render_html(a, n)[0], render_html(b, n)[0]
        css = lambda p: p[p.index("<style>"):p.index("</style>")]
        assert css(pa) == css(pb), f"layout {n} har olika CSS för olika hål"


def test_too_long_text_is_flagged():
    c = Halkort.from_yaml(HAL14)
    c.beskrivning = "x" * (FIELD_LIMITS["beskrivning"] + 1)
    assert any(f.startswith("beskrivning") for f in c.kontroll())


def test_typbild_is_labelled():
    c = Halkort.from_yaml(HAL14)
    assert c.typbild and "Typbild" in render_html(c, 1)[0]


def test_parse_layout():
    assert parse_layout(1) == [1]
    assert parse_layout([1, "Skärm"]) == [1, 4]
