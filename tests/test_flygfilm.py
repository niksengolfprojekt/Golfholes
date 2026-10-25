"""Flygfilmens kamera och rendering på en påhittad testterräng (ingen Lantmäteriet-data behövs)."""
import math

import numpy as np

from golfholes.hole import Hole, Tee
from golfholes.render.flygfilm import Kamera, Scen, _blockmax, kamerabana, korridor, rendera


def _scen():
    res, w, h = 0.5, 1200, 1200          # 600 × 600 m, övre vänstra hörn (0, 600)
    mark = np.full((h, w), 100.0, np.float32) + np.linspace(0, 6, h, dtype=np.float32)[:, None]
    H = mark.copy()
    H[100:140, 500:700] += 20.0           # en skogsridå bortom green
    rgb = np.zeros((h, w, 3), np.uint8)
    rgb[...] = (90, 140, 80)
    rgb[100:140, 500:700] = (30, 60, 35)
    return Scen(rgb, H, mark, 0.0, 600.0, res, [(b, _blockmax(H, b)) for b in (4, 16, 64)], res)


def _hal():
    return Hole(club="Testklubb", number=1, par=4, index=1,
                centerline=[(300.0, 100.0), (300.0, 400.0)],
                green=[(295.0, 395.0), (305.0, 395.0), (305.0, 405.0), (295.0, 405.0)],
                tees=[Tee("58", (300.0, 100.0), 300)])


def test_kameran_flyger_5_m_over_marken_och_slutar_rakt_ovanifran():
    sc, hal = _scen(), _hal()
    kams, info = kamerabana(hal, sc, fps=10, sekunder=6, slut_s=2)
    assert len(kams) == 60 and info["ruta_slut_flygning"] == 40
    for k in kams[:40]:
        y = (sc.n0 - k.n) / sc.res
        mark = sc.mark[int(y), int((k.e - sc.e0) / sc.res)]
        assert abs(k.z - mark - 5.0) < 0.3
        assert -0.3 < k.pitch < 0.05                     # blicken framåt, lätt nedåt
    assert kams[39].n > kams[0].n + 250                    # flyger mot green (norrut)
    sist = kams[-1]
    assert sist.pitch < -math.radians(89) and abs(sist.yaw - math.pi / 2) < 0.01   # rakt ner, green överst
    assert sist.z > 300 and sist.urklipp == 1.0


def test_rendering_visar_mark_under_horisonten_och_himmel_ovanfor():
    sc = _scen()
    im = rendera(sc, Kamera(300.0, 150.0, 105.5, math.pi / 2, -0.05), 160, 90)
    assert im.shape == (90, 160, 3)
    assert im[85, 80, 1] > im[85, 80, 0]                  # gräs nedtill
    assert im[2, 80, 2] > im[2, 80, 1] > 100              # himmel upptill
    topp = rendera(sc, Kamera(300.0, 300.0, 500.0, math.pi / 2, -math.pi / 2 + 1e-3), 160, 90)
    assert (topp[45, 80].astype(int) - (90, 140, 80)).__abs__().max() < 40


def test_korridoren_tacker_green_och_tees():
    linje, bredd = korridor(_hal())
    assert bredd >= 30 and tuple(np.round(linje[0])) == (300, 100) and round(linje[-1][1]) == 400


def test_oversikt_borjar_och_slutar_ovanifran_och_flyger_lugnt_5_m_over_marken():
    from golfholes.render.flygfilm import kamerabana_oversikt
    sc, hal = _scen(), _hal()
    fps = 10
    kams, info = kamerabana_oversikt(hal, sc, fps=fps, tee="58")
    assert info["sekunder"] >= 20
    for k in (kams[0], kams[-1]):
        assert k.pitch < -math.radians(89) and abs(k.yaw - math.pi / 2) < 0.01 and k.z > 300
    assert abs(kams[0].z - kams[-1].z) < 0.5 and abs(kams[0].n - kams[-1].n) < 0.5   # samma vy
    f0, f1 = info["faser_s"]["ned"][1], info["faser_s"]["upp"][0]
    mitt = [k for i, k in enumerate(kams) if f0 <= i / fps <= f1]
    for k in mitt:
        mark = sc.mark[int((sc.n0 - k.n) / sc.res), int((k.e - sc.e0) / sc.res)]
        assert abs(k.z - mark - 5.0) < 0.3
    # flygningen börjar 15 m bakom tee (300, 100), när kameran är på väg ner
    start = kams[round(info["faser_s"]["flygning"][0] * fps)]
    assert abs(start.e - 300) < 2 and 80 < start.n < 92 and start.z > 110
    assert mitt[0].n < 115 and mitt[-1].n > 340
    # inga ryck: upplevd fart (m/s delat med höjden över mark) ändras mjukt mellan rutor
    P = np.array([[k.e, k.n, k.z] for k in kams])
    v = np.linalg.norm(np.diff(P, axis=0), axis=1) * fps
    upplevd = v / np.maximum(np.array(info["hojd_over_mark_m"][:-1]), 5.0)
    assert upplevd.max() < 6 and np.abs(np.diff(upplevd)).max() < 0.5
    # norr-sydlig rörelse byter riktning högst två gånger (ner mot tee, fram, tillbaka till mitten)
    dn = np.sign(np.round(np.diff(P[:, 1]), 2))
    dn = dn[dn != 0]
    assert np.count_nonzero(np.diff(dn)) <= 2
    assert max(v[int(f0 * fps):int(f1 * fps)]) < 30                         # lugn flygning


def test_standardtee_valjer_56():
    from golfholes.render.flygfilm import standardtee
    hal = _hal()
    hal.tees = [Tee("60", (300.0, 90.0), 310), Tee("52/56", (300.0, 100.0), 300)]
    assert standardtee(hal) == "52/56" and standardtee(hal, "60") == "60"
