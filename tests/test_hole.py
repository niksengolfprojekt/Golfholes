from pathlib import Path

from golfholes import Hole
from golfholes.sweref import wgs84_to_sweref99tm

EXAMPLE = Path(__file__).parent.parent / "klubbar" / "exempel-ekbacka" / "hal-07.yaml"


def test_lengths_match_scorecard():
    hole = Hole.from_yaml(EXAMPLE)
    assert all(r["ok"] for r in hole.check_lengths())


def test_back_tee_is_longest():
    hole = Hole.from_yaml(EXAMPLE)
    assert hole.tee().name == "58"


def test_hazard_distances_and_sides():
    rows = {r["namn"]: r for r in Hole.from_yaml(EXAMPLE).hazard_distances("58")}
    assert rows["Bäcken"]["carry"] == 170
    assert rows["Dammen"]["sida"] == "höger"
    assert rows["Fairwaybunker"]["sida"] == "vänster"


def test_camera_aims_150m_along_centerline():
    cam = Hole.from_yaml(EXAMPLE).camera("58")
    assert cam["position"][2] == 1.6
    assert abs(cam["sikte"][1] - (6300000 + 150)) < 0.01


def test_par3_aims_at_green():
    hole = Hole.from_yaml(EXAMPLE)
    hole.par = 3
    assert hole.camera("58")["siktar_mot"] == "green"


def test_sweref_known_point():
    # Regressionsvärde (Glasrikets GK:s nordöstra hörn enligt OSM). Stäm av mot
    # Lantmäteriets koordinattransformation när vi har en officiell kontrollpunkt.
    e, n = wgs84_to_sweref99tm(56.9043906, 14.8740077)
    assert abs(e - 492327) < 2 and abs(n - 6306750) < 2
