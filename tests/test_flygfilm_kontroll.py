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
