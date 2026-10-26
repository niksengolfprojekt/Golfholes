"""Formpoängen för AI-målningar: en trogen målning ska slå en som flyttat formen."""
from pathlib import Path

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


def test_greenens_matt_ur_halfilen():
    """Spelarvyns green: djup längs inspelet och bredd tvärs det, i hela meter."""
    from golfholes.hole import Hole
    from golfholes.render.foto import _matt_green

    m = _matt_green(Hole.from_yaml(Path(__file__).parent.parent / "klubbar" / "glasriket" / "hal-14.yaml"))
    assert (m["djup"], m["bredd"]) == (33, 31)
    assert m["fram"] < 0 < m["bak"] and m["hoger"] < 0 < m["vanster"]


def _hal_med(**kw):
    from golfholes.hole import Hole, Tee

    d = dict(club="Testklubb", number=1, par=4, index=1,
             centerline=[(0.0, 0.0), (0.0, 300.0)], green=[(-10.0, 290.0), (10.0, 290.0), (10.0, 310.0), (-10.0, 310.0)],
             tees=[Tee("56", (0.0, 0.0), 300)])
    d.update(kw)
    return Hole(**d)


def test_flaggan_i_puttytans_mitt_aven_om_polygonen_korsar_sig():
    """En självkorsande greenpolygon (Glasriket hål 15) gav en tyngdpunkt i kanten."""
    from golfholes.render.foto import flaggpunkt

    ok = _hal_med()
    x, y = flaggpunkt(ok)
    assert abs(x) < 0.2 and abs(y - 300) < 0.2
    korsad = _hal_med(green=[(-10.0, 290.0), (10.0, 290.0), (10.0, 310.0), (-10.0, 310.0), (-10.0, 290.0),
                             (-10.0, 300.0), (-10.0, 290.0)])
    x, y = flaggpunkt(korsad)
    assert abs(x) < 1 and abs(y - 300) < 1
    assert flaggpunkt(_hal_med(flagga_punkt=(3.0, 298.0))) == (3.0, 298.0)


def test_outlinjen_foljer_tradlinjen_pa_ratt_sida():
    """Skog 30–80 m till vänster om linjen (norrut = väster är vänster): outlinjen hamnar i
    trädlinjen 31 m ut på vänstersidan och bara på den angivna sträckan."""
    from golfholes.render.foto import ob_linjer

    skog = [(-80.0, 50.0), (-30.0, 50.0), (-30.0, 250.0), (-80.0, 250.0)]
    h = _hal_med(trees=[skog], ob=[{"sida": "vanster", "fran_m": 60, "till_m": 200}])
    linjer = ob_linjer(h)
    assert len(linjer) == 1
    xs = [p[0] for p in linjer[0]]
    ys = [p[1] for p in linjer[0]]
    assert all(-32.5 < x < -29.5 for x in xs)
    assert 58 <= min(ys) and max(ys) <= 202
    assert ob_linjer(_hal_med(trees=[skog], ob=[{"sida": "hoger", "fran_m": 60, "till_m": 200}])) == []


def test_klubbens_flagga_ur_klubb_yaml(tmp_path):
    from golfholes.render.foto import _flagga, flaggstil

    assert flaggstil(tmp_path) is None  # ingen klubb.yaml: T-flaggan
    logga = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    logga.paste((255, 255, 255, 255), (5, 5, 35, 35))
    logga.save(tmp_path / "logga.png")
    (tmp_path / "klubb.yaml").write_text('flagga: {logga: logga.png, farg: "#1D4756"}\n', encoding="utf-8")
    stil = flaggstil(tmp_path)
    assert stil["farg"] == (0x1D, 0x47, 0x56)
    bild = Image.new("RGBA", (300, 300), (90, 140, 60, 255))
    _flagga(bild, 100, 200, 3.0, stil)
    a = np.asarray(bild)[..., :3].astype(int)
    duk = (abs(a[..., 0] - 0x1D) < 25) & (abs(a[..., 2] - 0x56) < 30) & (a[..., 1] < 100)
    vitt = (a > 200).all(-1)
    assert duk.sum() > 500 and vitt.sum() > 100  # duk i klubbens färg med ljus logga
