"""nyklubb: samma steg varje gång, bara det som är beställt, aldrig krediter utan Erics OK."""
from pathlib import Path
import tempfile

import yaml

from golfholes import nyklubb as ny

ROOT = Path(__file__).parent.parent


def _klubb(produkter, hal=None, godkant=None):
    d = Path(tempfile.mkdtemp()) / "testklubb"
    ny.skapa(d, "Testklubb GK", "2026-11-01")
    data = yaml.safe_load((d / "klubb.yaml").read_text(encoding="utf-8"))
    data["paket"] = {"avtal": "test", "produkter": produkter, **({"hal": hal} if hal else {})}
    data["holes"] = [{"hole": n, "par": 4, "tees": {"58": 350}} for n in range(1, 19)]
    data["bbox_sweref99tm"] = {"e_min": 0, "n_min": 0, "e_max": 1, "n_max": 1}
    (d / "klubb.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    if godkant:
        (d / "godkant.yaml").write_text(yaml.safe_dump(godkant), encoding="utf-8")
    k = ny.las(d)
    return k, ny.bedom(ny.plan(k), k)


def test_skapa_skriver_inte_over():
    d = Path(tempfile.mkdtemp()) / "x"
    ny.skapa(d, "X GK", "2026-11-01")
    try:
        ny.skapa(d, "X GK", "2026-11-01")
    except SystemExit:
        return
    raise AssertionError("skapa skrev över en befintlig klubb.yaml")


def test_utan_paket_stoppar_allt():
    d = Path(tempfile.mkdtemp()) / "tom"
    ny.skapa(d, "Tom GK", "2026-11-01")
    k = ny.las(d)
    steg = ny.bedom(ny.plan(k), k)
    assert [s.id for s in steg] == ["paket", "scorekort"]
    assert "STOPP" in ny.utskrift(k, steg)


def test_bara_bestallda_produkter_far_steg():
    _, steg = _klubb(["halguide"], hal=[1, 10])
    ids = {s.id for s in steg}
    assert {"fro-01", "fro-10", "testhal", "granskning"} <= ids
    assert not any(i.startswith(("webb", "inlagg", "prospekt", "profil", "flygfilm", "tryckprov")) for i in ids)
    assert "fro-02" not in ids


def test_hela_paketet_har_alla_avsnitt():
    _, steg = _klubb(["halguide", "grafisk_profil", "hemsida", "some_kit", "halsponsring", "skyltar", "flygfilm"])
    assert {s.avsnitt for s in steg} >= {"0", "1", "2", "3", "4", "5", "6", "7", "8"}
    assert len([s for s in steg if s.id.startswith("fro-")]) == 18


def test_ai_kors_aldrig_automatiskt_och_resten_vantar_pa_testhalet():
    _, steg = _klubb(["halguide", "flygfilm"], hal=[3, 14])
    for s in steg:
        if s.vem in ("ai", "eric", "klubb", "claude"):
            assert s.kommando is None, s.id
        if s.vem == "kod":
            assert s.kommando and "golfholes" in s.kommando
    fro14 = next(s for s in steg if s.id == "fro-14")
    assert "testhal" in fro14.kraver
    assert "testhal" not in next(s for s in steg if s.id == "fro-03").kraver


def test_godkannanden_lases_ur_godkant_yaml():
    _, steg = _klubb(["halguide"], hal=[1], godkant={"paket_bekraftat": "2026-11-01 Eric"})
    st = {s.id: s.status for s in steg}
    assert st["paket"] == "klar" and st["scorekort"] == "klar"
    assert st["stil"] == "klubb" and st["kredittak"] == "eric"
    assert st["hamta"] == "kod" and st["malning-01"] == "vantar"


def test_alvesta_har_plan():
    k = ny.las(ROOT / "klubbar" / "alvesta")
    steg = ny.bedom(ny.plan(k), k)
    st = {s.id: s.status for s in steg}
    assert st["paket"] == "klar" and st["malning-01"] == "klar" and st["malning-10"] == "klar"


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
