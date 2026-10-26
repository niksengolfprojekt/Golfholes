"""Partnerprogrammet: en klubbs hela sponsorutbud, priser, leveranser och uppföljning.

  python -m golfholes partnerprogram klubbar/<klubb> [--ut mapp] [--bara deck,prospekt,...]

Standardbiblioteket (standard.yaml) håller produkterna, texterna och leveranslogiken som är lika för alla
klubbar. Klubbens `partnerprogram.yaml` väljer aktiva produkter, sätter priser, premiumhål och partnerveckor.
Klubbfakta (namn, profil, loggor, hål, status per hål) kommer ur `klubb.yaml` som för övrigt säljmaterial.

Den här modulen är bara data och räkning: produkterna med klubbens ändringar, hålen med pris och status,
partnerveckorna, räkneexemplen och kontrollerna som stoppar produkter klubben inte kan leverera.
Materialet ritas i golfholes/render/partner_*.py.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..render.klubbmaterial import Klubb

STANDARD = Path(__file__).with_name("standard.yaml")
LISTOR = {"aktiva": "aktiv", "tillagg": "tillagg", "vilande": "vilande", "framtid": "framtid"}
MARKERA = None   # tester kan byta ut halkort_markerat (som kräver ortofotot)
HALSTATUS = {"ledig": "Ledigt", "bokad": "Reserverat", "såld": "Sålt"}


def _formatera(v, ord: dict):
    """Fyll i {klammer} i alla strängar (rekursivt). Okända nycklar lämnas orörda."""
    if isinstance(v, str):
        try:
            return v.format_map(_Saknas(ord))
        except (ValueError, IndexError):
            return v
    if isinstance(v, list):
        return [_formatera(x, ord) for x in v]
    if isinstance(v, dict):
        return {k: _formatera(x, ord) for k, x in v.items()}
    return v


class _Saknas(dict):
    def __missing__(self, k):
        return "{" + k + "}"


def _slå_ihop(bas: dict, andring: dict) -> dict:
    ut = copy.deepcopy(bas)
    for k, v in (andring or {}).items():
        ut[k] = _slå_ihop(ut[k], v) if isinstance(v, dict) and isinstance(ut.get(k), dict) else v
    return ut


@dataclass
class Hal:
    nr: int
    par: int
    index: int | None
    langder: list[int]
    status: str            # ledig | bokad | såld
    pris: int
    premium: dict | None   # {namn, extra, yta} eller None
    rubrik: str = ""
    bild: Path | None = None
    beskrivning: str = ""
    tees: list = field(default_factory=list)

    @property
    def produkt(self) -> str:
        return "premiumhal" if self.premium else "halsponsor"

    @property
    def langd(self) -> str:
        if not self.langder:
            return ""
        a, b = min(self.langder), max(self.langder)
        return f"{a} m" if a == b else f"{a}–{b} m"


@dataclass
class Program:
    klubb: Klubb
    cfg: dict
    produkter: dict                     # id -> produkt (med klubbens ändringar, ifyllt)
    nivaer: dict
    villkor: dict
    vecka: dict                         # standardens partnervecka (ytor)
    administration: list
    hal: list[Hal] = field(default_factory=list)

    # ---------------------------------------------------------------- läsning
    @classmethod
    def from_dir(cls, mapp: str | Path) -> "Program":
        mapp = Path(mapp)
        k = Klubb.from_dir(mapp)
        fil = mapp / "partnerprogram.yaml"
        if not fil.exists():
            raise SystemExit(f"{fil} saknas. Kopiera klubbar/glasriket/partnerprogram.yaml och ändra.")
        cfg = yaml.safe_load(fil.read_text(encoding="utf-8")) or {}
        std = yaml.safe_load(STANDARD.read_text(encoding="utf-8"))
        val = cfg.get("produkter") or {}
        andringar = val.get("andringar") or {}
        modell = cls._modell(cfg)
        ord = {"kortnamn": k.kortnamn, "klubb": k.namn, "bana": k.bana or k.kortnamn, "sasong": cfg.get("sasong", k.sasong),
               "golfvecka": cfg.get("golfvecka", "Klubbens största vecka")}
        produkter = {}
        for nyckel, status in LISTOR.items():
            for pid in val.get(nyckel) or []:
                if pid not in std["produkter"]:
                    raise SystemExit(f"partnerprogram.yaml: okänd produkt {pid!r} (finns: {', '.join(std['produkter'])})")
                p = _slå_ihop(std["produkter"][pid], andringar.get(pid) or {})
                p["id"], p["status"] = pid, status
                if not (cfg.get("partnerveckor") or {}).get("skarm") and p.get("ytor"):
                    # Utan bekräftad skärm i klubbhuset lovas ingen yta på skärmen.
                    p["ytor"] = {typ: [y for y in lista if "skärm" not in y]
                                 for typ, lista in p["ytor"].items()}
                produkter[pid] = _formatera(p, ord)
        if "halsponsor" in produkter:
            produkter["halsponsor"]["pris"] = modell["halpris"]
        if "premiumhal" in produkter:
            produkter["premiumhal"]["pris"] = modell["premiumpris"]
        prog = cls(klubb=k, cfg=cfg, produkter=produkter, nivaer=std["nivaer"],
                   villkor=_formatera(_slå_ihop(std["villkor"], cfg.get("villkor") or {}), ord),
                   vecka=std["partnervecka"], administration=std["administration"])
        prog.hal = prog._hal(modell)
        return prog

    @staticmethod
    def _modell(cfg: dict) -> dict:
        m = cfg.get("prismodeller") or {"differentierad": {"namn": "Två priser", "halpris": 20000, "premiumpris": 25000}}
        namn = cfg.get("prismodell") or next(iter(m))
        if namn not in m:
            raise SystemExit(f"partnerprogram.yaml: prismodell {namn!r} finns inte i prismodeller")
        return m[namn]

    def _hal(self, modell: dict) -> list[Hal]:
        from ..render.halkort import Halkort
        from ..render.klubbmaterial import halkort_markerat

        d = yaml.safe_load((self.klubb.mapp / "klubb.yaml").read_text(encoding="utf-8")) or {}
        kort = self.klubb.halkort()
        prem = {int(n): v for n, v in (self.cfg.get("premiumhal") or {}).items()}
        ut = []
        for h in d.get("holes") or []:
            nr = int(h["hole"])
            p = prem.get(nr)
            bild, rubrik, beskr, tees = None, "", "", []
            if nr in kort:
                c = Halkort.from_yaml(kort[nr])
                rubrik, beskr, tees = c.rubrik, c.beskrivning, list(c.tees)
                bild = (MARKERA or halkort_markerat)(kort[nr]).image
            ut.append(Hal(nr=nr, par=int(h.get("par") or 0), index=h.get("index"),
                          langder=sorted(int(m) for m in (h.get("tees") or {}).values()),
                          status=self.klubb.status(nr), pris=modell["premiumpris"] if p else modell["halpris"],
                          premium=p, rubrik=rubrik, bild=bild, beskrivning=beskr, tees=tees))
        for nr, p in prem.items():
            if not p.get("extra"):
                raise SystemExit(f"Premiumhål {nr} saknar `extra`: ett premiumhål måste ha en verklig extra yta.")
        return ut

    # ---------------------------------------------------------------- urval
    def aktiva(self) -> list[dict]:
        return [p for p in self.produkter.values() if p["status"] == "aktiv"]

    def med_status(self, status: str) -> list[dict]:
        return [p for p in self.produkter.values() if p["status"] == status]

    def per_niva(self) -> dict[str, list[dict]]:
        ut = {n: [] for n in self.nivaer}
        for p in self.aktiva():
            ut.setdefault(p["niva"], []).append(p)
        return ut

    @property
    def sasong(self) -> int:
        return int(self.cfg.get("sasong", self.klubb.sasong))

    def kontakt(self) -> dict:
        c = self.cfg.get("kontakt") or {}
        return {"namn": c.get("namn", "Kansliet"), "epost": c.get("epost", ""), "telefon": c.get("telefon", "")}

    def ronder(self) -> tuple[int, str]:
        r = self.cfg.get("ronder") or {}
        if r.get("antal"):
            ar = f" ({r['ar']})" if r.get("ar") else ""
            return int(r["antal"]), f"{r.get('kalla', 'klubbens egen siffra')}{ar}"
        return self.klubb.ronder()

    # ---------------------------------------------------------------- partnerveckor
    def veckokandidater(self) -> list[tuple[str, str]]:
        """(nyckel, namn) för allt som ger en egen partnervecka, i kalenderns ordning: hålen, sedan övriga."""
        ut = []
        for h in self.hal:
            ut.append((f"hal-{h.nr:02d}", f"Hål {h.nr}"))
        for p in self.aktiva():
            if p.get("partnervecka") and p["niva"] == "verksamhet":
                ut.append((p["id"], p["namn"]))
        return ut

    def partnerveckor(self) -> dict:
        """Förslag på vecka per partner. Reserverade veckor (t.ex. golfveckan) går till sin produkt."""
        pv = self.cfg.get("partnerveckor") or {}
        forsta, sista = int(pv.get("forsta", 18)), int(pv.get("sista", 41))
        res = {int(v): p for v, p in (pv.get("reserverade") or {}).items()}
        lediga = [v for v in range(forsta, sista + 1) if v not in res]
        kand = self.veckokandidater()
        plan = {v: (p, self.produkter.get(p, {}).get("namn", p)) for v, p in res.items()}
        for v, k in zip(lediga, kand):
            plan[v] = k
        over = kand[len(lediga):]
        return {"plan": dict(sorted(plan.items())), "lediga": len(lediga), "behov": len(kand), "over": over,
                "forsta": forsta, "sista": sista}

    # ---------------------------------------------------------------- ekonomi
    def scenarier(self) -> list[dict]:
        """Räkneexemplen från uppdraget + prismodellerna. Inga prognoser."""
        i = self.cfg.get("idag") or {}
        rader = []
        if i.get("salda_hal"):
            rader.append({"text": f"Idag: {i['salda_hal']} × {kr(i['pris'])} kr", "antal": i["salda_hal"],
                          "pris": i["pris"], "summa": i["salda_hal"] * i["pris"], "idag": True})
        for n, p in ((10, 15000), (12, 20000), (15, 20000), (18, 20000), (18, 25000)):
            rader.append({"text": f"{n} × {kr(p)} kr", "antal": n, "pris": p, "summa": n * p})
        return rader

    def modeller(self) -> list[dict]:
        """Alla 18 hål sålda i varje prismodell."""
        prem = len(self.cfg.get("premiumhal") or {})
        n = len(self.hal)
        ut = []
        for nyckel, m in (self.cfg.get("prismodeller") or {}).items():
            summa = (n - prem) * m["halpris"] + prem * m["premiumpris"]
            ut.append({"nyckel": nyckel, "namn": m["namn"], "halpris": m["halpris"], "premiumpris": m["premiumpris"],
                       "summa": summa, "vald": nyckel == self.cfg.get("prismodell")})
        return ut

    def befintliga_trappa(self) -> list[int]:
        return list((self.cfg.get("befintliga") or {}).get("trappa") or [])

    def produktekonomi(self) -> list[dict]:
        """Per aktiv produkt: pris, klubbens kostnad, arbetstid och vad som blir kvar."""
        ut = []
        for p in self.aktiva():
            pris, kost, tid = p.get("pris"), p.get("kostnad_kr"), p.get("tid_h") or 0
            netto = pris - (kost or 0) if pris else None
            ut.append({"id": p["id"], "namn": p["namn"], "pris": pris, "enhet": p.get("prisenhet", ""),
                       "kostnad": kost, "kostnad_text": p.get("kostnad_text", ""), "tid_h": tid, "netto": netto,
                       "per_timme": round(netto / tid) if netto and tid else None, "max": p.get("max"),
                       "startkostnad": p.get("startkostnad") or 0})
        return ut

    def helt_program(self) -> dict:
        """Räkneexempel: allt i det aktiva erbjudandet sålt en gång (tävlingar: de som har ett pris)."""
        hal = sum(h.pris for h in self.hal)
        ovr = []
        for p in self.aktiva():
            if p["niva"] == "hal" or not p.get("pris"):
                continue
            if p["id"] == "tavling":
                antal = sum(1 for t in self.cfg.get("tavlingar") or [] if "Ingen egen partner" not in t.get("text", "")
                            and t.get("namn") != "Golfveckan")
                ovr.append((f"{p['namn']} ({antal} tävlingar)", antal * p["pris"]))
            else:
                ovr.append((p["namn"], p["pris"]))
        return {"hal": hal, "ovrigt": ovr, "summa": hal + sum(b for _, b in ovr)}

    def foretagsdag(self, deltagare: int) -> dict:
        fd = self.cfg.get("foretagsdag") or {}
        pd = fd.get("per_deltagare") or {}
        n = max(deltagare, int(fd.get("minsta_antal", 8)))
        sjalv = n * sum(pd.values()) + int(fd.get("pro_fast", 0))
        pris = int(math.ceil(sjalv * (1 + float(fd.get("paslag", 0.3))) / 500.0) * 500)
        return {"deltagare": n, "sjalvkostnad": sjalv, "pris": pris, "per_person": round(pris / n)}

    def klubbens_tid(self, avtal: int) -> float:
        """Klubbens arbetstimmar per år för ett program med `avtal` avtal (snitt av produkterna)."""
        snitt = sum(p.get("tid_h") or 0 for p in self.aktiva()) / max(len(self.aktiva()), 1)
        adm = 0.0
        for a in self.administration:
            adm += a.get("tid_h", 0) + a.get("tid_h_per_avtal", 0) * avtal
        return round(snitt * avtal + adm, 1)

    def uppskattning_tee(self, andel: float = 1.0) -> int:
        r, _ = self.ronder()
        return int(round(r * andel, -2))

    # ---------------------------------------------------------------- kontroller
    def kontroller(self) -> list[tuple[str, str]]:
        """(nivå, text). nivå 'stopp' = materialet får inte byggas; 'beslut' = klubben måste bekräfta."""
        ut = []
        v = self.partnerveckor()
        if v["over"]:
            ut.append(("stopp", f"Partnerveckorna räcker inte: {v['behov']} behövs, {v['lediga']} finns. "
                                 f"Förläng säsongen eller låt två partners dela vecka."))
        for p in self.aktiva():
            if p.get("forutsattning"):
                ut.append(("beslut", f"{p['namn']}: {p['forutsattning']}"))
            if p["status"] == "aktiv" and p.get("pris") is None and p.get("prisenhet") != "offert":
                ut.append(("stopp", f"{p['namn']} saknar pris."))
        for p in self.med_status("framtid"):
            if any(p["id"] == q for q in (self.cfg.get("produkter") or {}).get("aktiva") or []):
                ut.append(("stopp", f"{p['namn']} är en framtida produkt och får inte vara aktiv."))
        if not (self.cfg.get("partnerveckor") or {}).get("skarm"):
            ut.append(("info", "Ingen skärm i klubbhuset är bekräftad: partnerveckan använder bara entréskylten och de digitala ytorna."))
        return ut


def kr(n) -> str:
    return f"{int(n):,}".replace(",", " ")


__all__ = ["Hal", "HALSTATUS", "Program", "kr"]
