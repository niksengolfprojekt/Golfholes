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
