import numpy as np
from PIL import Image

from verktyg.kant_tvatt import randmask


def test_randmask_hittar_vagrata_rander_men_inte_skog():
    rng = np.random.default_rng(1)
    a = rng.integers(0, 255, (400, 400)).astype(np.uint8)  # brusig "skog"
    for y in range(0, 400, 6):  # vågräta ränder i vänsterkanten
        a[y:y + 3, :120] = 200
        a[y + 3:y + 6, :120] = 40
    m = randmask(Image.fromarray(a).convert("RGB"))
    assert m is not None
    assert m[200, 40, 0] > 0.9
    assert m[200, 330, 0] < 0.1


def test_randmask_ingen_rand_ger_none():
    rng = np.random.default_rng(2)
    a = rng.integers(0, 255, (300, 300, 3)).astype(np.uint8)
    assert randmask(Image.fromarray(a)) is None
