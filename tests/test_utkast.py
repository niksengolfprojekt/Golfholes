"""Utkast ur ortofoto: ytor, polygoner, trollstav och spellinje på syntetiska bilder."""
import numpy as np

from golfholes.utkast import Fonster, area, etiketter, fyll_hal, matt, polygoner, ringar, spellinje, trollstav


def _fonster(rgbn, res=0.5):
    return Fonster(rgbn.astype(np.float32), e0=500000.0, n0=6300000.0, res=res)


def test_etiketter_och_hal():
    m = np.zeros((20, 20), bool)
    m[2:8, 2:8] = True
    m[4, 4] = False          # hål
    m[12:15, 12:18] = True   # egen yta
    lab, n = etiketter(m)
    assert n == 2 and lab[2, 2] != lab[12, 12]
    assert fyll_hal(m)[4, 4] and fyll_hal(m).sum() == 36 + 18


def test_ring_runt_kvadrat_har_ratt_area():
    m = np.zeros((10, 10), bool)
    m[2:6, 3:8] = True
    r = max(ringar(m), key=area)
    assert area(r) == 20


def test_polygon_i_sweref():
    m = np.zeros((40, 40), bool)
    m[10:30, 10:30] = True   # 10 × 10 m vid 0,5 m/px
    f = _fonster(np.zeros((40, 40, 4)))
    (p,) = polygoner(m, f, min_m2=4)
    es, ns = [q[0] for q in p], [q[1] for q in p]
    assert 500004.5 <= min(es) <= 500005.5 and 500014.5 <= max(es) <= 500015.5
    assert 6299984.5 <= min(ns) <= 6299985.5 and 6299994.5 <= max(ns) <= 6299995.5


def test_trollstav_stannar_vid_ruffen():
    rng = np.random.default_rng(3)
    bild = np.empty((80, 80, 4))
    bild[:] = (85, 100, 88, 145)                     # ruff
    bild += rng.normal(0, 8, bild.shape)             # ruffen är ojämn
    yy, xx = np.mgrid[:80, :80]
    green = (yy - 40) ** 2 + (xx - 40) ** 2 < 15 ** 2
    bild[green] = (110, 132, 105, 176)               # jämn, ljus green
    yta = trollstav(matt(_fonster(bild)), 40, 40, tol=1.2)
    traff = (yta & green).sum() / green.sum()
    spill = (yta & ~green).sum() / green.sum()
    assert traff > 0.85 and spill < 0.15


def test_spellinje_gar_via_fairway_till_greenens_bakkant():
    f = _fonster(np.zeros((200, 100, 4)), res=1.0)
    fairway = np.zeros((200, 100), bool)
    fairway[80:140, 30:50] = True                    # mitt ~ (500040, 6299890)
    green = np.zeros((200, 100), bool)
    green[20:40, 60:80] = True                       # mitt ~ (500070, 6299970)
    linje = spellinje((500040.0, 6299810.0), (500070.0, 6299970.0), fairway, green, f, par=4)
    assert len(linje) == 4
    assert abs(linje[1][0] - 500040) < 1 and abs(linje[1][1] - 6299890) < 1
    assert abs(linje[2][0] - 500070) < 1 and abs(linje[2][1] - 6299970) < 1
    assert linje[3][1] > linje[2][1] + 5            # förlängd förbi mitten
