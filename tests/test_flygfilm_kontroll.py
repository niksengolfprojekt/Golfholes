"""Formkontrollen för flygfilmen: projektion och bakåtprojektion ska mötas."""
import math

import numpy as np
import pytest

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


def test_stig_tas_bort_bara_langs_linjen():
    from golfholes.render.flygfilm_kontroll import ta_bort_stig
    rng = np.random.default_rng(2)
    bild = np.clip(np.array([60, 90, 50]) + rng.normal(0, 5, (120, 200, 3)), 0, 255).astype(np.uint8)
    bild[:, 98:104] = (140, 130, 115)                    # grå "grusgång" rakt ner
    ut = ta_bort_stig(bild, [[12, -30, [[101, 0], [101, 119]]]])
    assert ut[:, 99:103].astype(int).mean(axis=(0, 1))[0] < 80    # ingen grusfärg kvar
    assert (ut[:, :80] == bild[:, :80]).all()                     # resten orört


def test_bakgrund_klubbens_morka_farg():
    from pathlib import Path
    from golfholes.render.flygfilm_kontroll import hexfarg, klubbens_bakgrund
    assert hexfarg("#10202E").tolist() == [16, 32, 46]
    assert klubbens_bakgrund(Path("klubbar/glasriket/hal-14.yaml")).tolist() == [16, 32, 46]


def test_steg_plan_jamnar_ryck():
    from golfholes.render.flygfilm_jamna import steg_plan
    # var 5:e steg dubbelt så långt (som Wan-klippen), 150 bilder -> 120
    m = np.array([2.0 if i % 5 == 4 else 1.0 for i in range(149)])
    s = steg_plan(m, 120)
    assert len(s) == 120 and abs(s[0]) < 1e-9 and abs(s[-1] - 149) < 1e-6
    C = np.concatenate([[0.0], np.cumsum(m + 1e-3)])
    steg = np.diff(np.interp(s, np.arange(150), C))
    mitt = steg[20:-20]
    assert mitt.std() / mitt.mean() < 0.02   # jämna steg, ingen puls


def test_steg_plan_foljer_bas():
    from golfholes.render.flygfilm_jamna import steg_plan
    m = np.ones(99)
    bas = np.linspace(0, 99, 50) ** 1.2 / 99 ** 0.2   # AI:n ligger efter i början
    s = steg_plan(m, 50, bas=bas)
    assert np.allclose(s, bas, atol=0.5) and np.all(np.diff(s) >= 0)


def test_synk_bas_hittar_forskjuten_takt():
    pytest.importorskip("cv2")
    from golfholes.render.flygfilm_jamna import synk_bas
    rng = np.random.default_rng(1)
    bild = (rng.random((120, 600, 3)) * 255).astype(np.uint8)
    bild = np.repeat(np.repeat(bild[::4, ::4], 4, 0), 4, 1)
    def ruta(x):
        return np.ascontiguousarray(bild[:, int(x):int(x) + 240])
    ai = np.array([ruta(3 * i) for i in range(80)])          # AI flyger 3 px/bild
    ra = np.array([ruta(3 * min(79, 1.5 * j)) for j in range(50)])   # den råa 1,5 gånger fortare
    v = synk_bas(ai, ra, sigma=2.0)
    assert abs(v[25] - 37.5) < 3 and abs(v[-1] - 73.5) < 4


def test_avstand_star_pa_tee_och_gar_bara_ned():
    from golfholes.render.flygfilm_avstand import avstand_per_ruta, synlighet
    hal = {"centerline": [[0.0, 0.0], [0.0, 300.0]], "tees": [{"name": "56", "point": [0.0, 0.0], "length_m": 330}]}
    kam = [{"e": 0.0, "n": 150.0}] * 3 + [{"e": 0.0, "n": n} for n in (0.0, 100.0, 90.0, 200.0)]
    m = avstand_per_ruta(hal, kam, "56", vid_tee=3)
    assert m[:4] == [330, 330, 330, 330]          # hänger över hålet: tee-längden
    assert m[4] == 220 and m[5] == 220 and m[6] == 110   # backar aldrig uppåt
    s = synlighet(48, 24, 0.5, 1.5)
    assert s[0] == 0 and s[24] == 1 and s[-1] == 0


def test_slag_hal14_landar_pa_fairway():
    import yaml
    from golfholes.render.flygfilm_tracer import slag_plan

    hal = yaml.safe_load(open("klubbar/glasriket/hal-14.yaml", encoding="utf-8"))
    slag = slag_plan(hal)
    assert [s.namn for s in slag] == ["Utslag", "Andra slaget", "Inspel"]
    assert sum(s.langd_m for s in slag) == 335

    def inne(p, poly):
        c, (x, y) = False, p
        for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
        return c
    for s in slag[:-1]:   # alla nedslag utom det sista (green) ska ligga på fairway
        assert any(inne(s.till, f) for f in hal["fairways"])
