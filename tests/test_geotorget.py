import pytest

from golfholes.geotorget import Ruta, bbox_wgs84, inloggning, senaste
from golfholes.sweref import sweref99tm_to_wgs84, wgs84_to_sweref99tm


def test_sweref_round_trip():
    lat, lon = 56.8982474, 14.8680174  # Glasrikets GK enligt OpenStreetMap
    e, n = wgs84_to_sweref99tm(lat, lon)
    lat2, lon2 = sweref99tm_to_wgs84(e, n)
    assert abs(lat2 - lat) < 1e-8 and abs(lon2 - lon) < 1e-8


def test_bbox_wgs84_covers_club_area():
    b = {"e_min": 491366, "n_min": 6305290, "e_max": 492427, "n_max": 6306850}
    min_lon, min_lat, max_lon, max_lat = bbox_wgs84(b)
    assert min_lon < 14.868 < max_lon and min_lat < 56.898 < max_lat


def _r(id_, samling, datum):
    return Ruta("orto", id_, samling, datum, f"https://x/{id_}.tif", {})


def test_senaste_picks_newest_colour_photo():
    rutor = [_r("o1_25_mr23", "orto-e2-2023", "2023-04-20"),
             _r("o1_25_mr25", "orto-e2-2025", "2025-07-01"),
             _r("o2_25_mr25", "orto-e2-2025", "2025-07-01"),
             _r("o1_25_im26", "orto-e2-2026", "2026-05-01"),          # IR, ska bort
             _r("o05e1i_c27", "orto-historiska-2020", "2027-01-01")]  # historisk, ska bort
    assert [r.id for r in senaste(rutor)] == ["o1_25_mr25", "o2_25_mr25"]


def test_inloggning_kraver_miljovariabler(monkeypatch):
    monkeypatch.delenv("LM_ANVANDARE", raising=False)
    monkeypatch.delenv("LM_LOSENORD", raising=False)
    with pytest.raises(SystemExit):
        inloggning()
