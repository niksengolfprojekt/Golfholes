from golfholes.designregister import kontrollera, las

REGLER = {
    "maste_skilja": ["riktning", "toppbild"],
    "jamfor": ["typsnitt", "palett.huvud", "halbildstil", "halkortslayout"],
    "minst_olika": 3,
    "forbjudna_riktningar": ["standardmall"],
}
RIKTNINGAR = {"standardmall": "", "delad-scen": "", "kartan-forst": ""}


def sajt(**f):
    bas = {"namn": "A", "typ": "foretag", "riktning": "delad-scen", "toppbild": "fast-halbild",
           "typsnitt": {"rubrik": "Spectral", "text": "Hanken"}, "palett": {"huvud": "#10202E"},
           "halbildstil": "akvarell", "halkortslayout": 1}
    bas.update(f)
    return bas


def reg(*sajter):
    return {"regler": REGLER, "riktningar": RIKTNINGAR, "sajter": list(sajter)}


def test_registret_gar_att_lasa():
    r = las()
    assert r["sajter"] and r["gemensamt"]
    for s in r["sajter"]:
        assert s["riktning"] in r["riktningar"] or s["riktning"] in ("ej-bedomd", None)


def test_forbjuden_riktning_stoppas():
    fel, _ = kontrollera(reg(sajt(riktning="standardmall")))
    assert any("förbjuden" in f for f in fel)


def test_samma_riktning_som_tidigare_stoppas():
    fel, _ = kontrollera(reg(sajt(), sajt(namn="B", toppbild="kartan", typsnitt={"rubrik": "X", "text": "Y"},
                                          palett={"huvud": "#B7955E"}, halbildstil="gravyr", halkortslayout=3)))
    assert fel == ["B: samma riktning som A ('delad-scen')"]


def test_for_lika_detaljer_stoppas_och_nara_farger_raknas_som_lika():
    b = sajt(namn="B", riktning="kartan-forst", toppbild="karta", palett={"huvud": "#14243A"}, halkortslayout=3)
    fel, _ = kontrollera(reg(sajt(), b))
    assert fel == ["B: skiljer sig bara på 1 av 4 punkter från A, minst 3 krävs"]


def test_unik_sajt_godkanns():
    b = sajt(namn="B", riktning="kartan-forst", toppbild="karta", typsnitt={"rubrik": "Marcellus", "text": "Inter"},
             palett={"huvud": "#571F30"}, halbildstil="gravyr", halkortslayout=3)
    assert kontrollera(reg(sajt(), b))[0] == []


def test_obedomda_falt_hoppas_over():
    b = sajt(namn="B", riktning="ej-bedomd", toppbild="ej-bedomd")
    fel, _ = kontrollera(reg(sajt(), b))
    assert not any("samma" in f for f in fel)
