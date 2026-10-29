"""Fairway i toppskick: bruna fläckar hittas, frisk gräsmatta och spelprickar lämnas i fred."""
import numpy as np

from verktyg.fairway_frisk import brunvikt


def _ruta(farg, n=40):
    return np.full((n, n, 3), farg, np.float32)


def test_brunt_hittas_gront_inte():
    assert brunvikt(_ruta((150, 120, 50))).mean() > 0.9   # torr, orange-brun
    assert brunvikt(_ruta((110, 150, 50))).max() == 0     # frisk grön


def test_rod_spelprick_rors_inte():
    a = _ruta((150, 120, 50), 80)
    a[30:50, 30:50] = (220, 40, 50)  # röd prick på brun yta
    w = brunvikt(a)
    assert w[40, 40] == 0
    assert w[2, 2] > 0.9


def test_avstandsprick_hamnar_mitt_i_fairway():
    from golfholes.render.foto import _mitt_i_fairway
    linje = [(0.0, 0.0), (0.0, 300.0)]
    fairway = [[(2.0, 100.0), (32.0, 100.0), (32.0, 200.0), (2.0, 200.0)]]  # fairway till höger om linjen
    x, y = _mitt_i_fairway(linje, (0.0, 150.0), fairway)
    assert abs(x - 17.0) < 0.6 and y == 150.0
    assert _mitt_i_fairway(linje, (0.0, 150.0), []) == (0.0, 150.0)
