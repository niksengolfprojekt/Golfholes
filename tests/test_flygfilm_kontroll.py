"""Formkontrollen för flygfilmen: projektion och bakåtprojektion ska mötas."""
import math

import numpy as np

from golfholes.render.flygfilm_kontroll import Projektion


def _data(pitch):
    z = (np.zeros((60, 60)) + 100.0).tolist()  # plan mark på 100 m, 2 m-rutor
    return {"kameror": [{"e": 50.0, "n": 50.0, "z": 300.0, "yaw": math.radians(90), "pitch": pitch}],
            "mark": {"e0": 0.0, "n1": 120.0, "res": 2.0, "z": z}}


def test_rakt_ner_mitt_i_bild():
    p = Projektion(_data(-math.pi / 2 + 1e-3))
    x, y, fram = p.px(0, [50.0], [50.0])
    assert fram[0] and abs(x[0] - 640) < 2 and abs(y[0] - 360) < 2
    # norrut (yaw 90°) ligger uppåt i bilden
    _, y2, _ = p.px(0, [50.0], [70.0])
    assert y2[0] < y[0]


def test_fram_och_tillbaka():
    p = Projektion(_data(math.radians(-50)))
    X, Y = np.array([[300.0, 900.0]]), np.array([[500.0, 650.0]])
    e, n = p.mark_under(0, X, Y)
    x, y, _ = p.px(0, e.ravel(), n.ravel())
    assert np.allclose(x, X.ravel() + 0.5, atol=1.0) and np.allclose(y, Y.ravel() + 0.5, atol=1.0)


def test_ai_delar_hela_sekunder_och_hopkopplade():
    from golfholes.render.flygfilm_kontroll import ai_delar, vikter
    h = [600.0] * 24 + list(np.geomspace(600, 5, 96)) + [5.0] * 200 + list(np.geomspace(5, 600, 96)) + [600.0] * 24
    mal, pap = vikter(h)
    assert mal[0] == 1 and mal[200] == 0 and pap[200] == 0
    delar = ai_delar(h)
    assert all((b - a) % 24 == 0 and (b - a) <= 6 * 24 for a, b in delar)
    assert all(delar[j][1] == delar[j + 1][0] for j in range(len(delar) - 1))
    assert mal[delar[0][0]] < 1 and mal[delar[0][0] - 1] >= 0.999 and mal[delar[-1][1]] > 0.99


def test_fargmatcha_flyttar_medel_och_spridning():
    from golfholes.render.flygfilm_kontroll import _medel_std, fargmatcha
    rng = np.random.default_rng(1)
    a = rng.normal(100, 10, (4, 20, 20, 3)).clip(0, 255).astype(np.uint8)
    b = rng.normal(150, 30, (4, 20, 20, 3)).clip(0, 255).astype(np.uint8)
    ut = fargmatcha(a, _medel_std(a), _medel_std(b))
    m, s = _medel_std(ut)
    mb, sb = _medel_std(b)
    assert np.allclose(m, mb, atol=2) and np.allclose(s, sb, atol=2)
    assert np.allclose(fargmatcha(a, _medel_std(a), _medel_std(b), 0.0), a, atol=0.01)


def test_tvatt_tar_bort_paahittad_sand_bara_i_omradet():
    from golfholes.render.flygfilm_kontroll import tvatta_bild
    rng = np.random.default_rng(0)
    bild = np.clip(np.array([90, 120, 70]) + rng.normal(0, 6, (200, 300, 3)), 0, 255).astype(np.uint8)
    bild[40:60, 50:90] = (225, 210, 185)       # påhittad bunker inne i området
    bild[150:170, 200:240] = (225, 210, 185)   # sand utanför området: ska vara kvar
    ut, n = tvatta_bild(bild, (0, 300, 0, 100))
    assert n > 0
    assert ut[45:55, 60:80].astype(int).mean(axis=(0, 1))[0] < 130     # ingen sandfärg kvar
    assert (ut[150:170, 200:240] == bild[150:170, 200:240]).all()
