"""Formpoängen för AI-målningar: en trogen målning ska slå en som flyttat formen."""
import numpy as np
from PIL import Image

from golfholes.render.foto import formpoang


class _Hal:
    fairways = [[(20, 20), (60, 20), (60, 140), (20, 140)]]
    green = [(30, 150), (50, 150), (50, 170), (30, 170)]


def _bild(dx=0):
    a = np.full((200, 100, 3), 60, np.uint8)
    a[20:140, 20 + dx:60 + dx] = 170   # fairway ljus
    a[150:170, 30 + dx:50 + dx] = 200  # green ljusast
    im = Image.fromarray(a).convert("RGBA")
    im.putalpha(255)
    return im


def test_formpoang_skiljer_trogen_fran_flyttad():
    px = lambda e, n: (e, n)
    bas = _bild()
    trogen = formpoang(bas, _bild(), _Hal(), px)
    flyttad = formpoang(bas, _bild(dx=30), _Hal(), px)
    assert trogen["likhet"] > 0.99
    assert trogen["poang"] > 0.8 > flyttad["poang"] + 0.2
