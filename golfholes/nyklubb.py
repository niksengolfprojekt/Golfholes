"""Ny klubb från start till leverans: samma steg i samma ordning varje gång, styrt av vad klubben köpt.

    python -m golfholes nyklubb klubbar/<klubb> --skapa "Klubbens namn"   → ny klubbmapp ur mallen
    python -m golfholes nyklubb klubbar/<klubb>                           → var står klubben? (ändrar inget)
    python -m golfholes nyklubb klubbar/<klubb> --kor                     → kör alla gratis kodsteg som är redo

Varje steg har en ägare:
    kod    – ett kommando i repot, gratis. `--kor` kör det när allt det bygger på är klart.
    claude – Claude gör det för hand (fröpunkter, hålkortstexter, profilförslag ...).
    ai     – AI-målning eller film. Kostar krediter: körs ALDRIG automatiskt, kräver Erics OK på beloppet.
    klubb  – väntar på klubben (scorekort, stilval, godkännande).
    eric   – väntar på Eric (paket, testhål, logga, kredittak, tryckprov).

Godkännanden som koden inte kan se själv skrivs i klubbar/<klubb>/godkant.yaml (datum + vem).
Bara de produkter som står under `paket: produkter:` i klubb.yaml får steg. Se docs/ny-klubb.md.
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml

from .paket import PRODUKTER, kontrollera

REPO = Path(__file__).resolve().parent.parent
MALL_GODKANT = """\
# Godkännanden som koden inte kan se själv (python -m golfholes nyklubb klubbar/{slug}).
# Skriv datum och vem, t.ex. "2026-11-12 Eric". Tomt = inte godkänt än.
paket_bekraftat:      # Eric: paket: i klubb.yaml stämmer med avtalet/beställningen
stil_vald:            # klubben: stil ur stilmenyn (eller Eric: stil A tills vidare)
kredittak:            # Eric: max OpenArt-krediter för klubben, t.ex. 6000
testhal_ok:           # Eric: första hålet godkänt innan resten målas
logga_vald:           # Eric (och klubben): vilken loggväg
profil_ok:            # Eric: färger, typsnitt, flagga, manual
hemsida_ok:           # Eric: hemsidan klar att visa klubben
some_ok:              # Eric: inläggen klara
sponsring_ok:         # Eric: prospekt och partnerprogram klara
granskning_skickad:   # Eric: granskningslänken skickad till klubbchefen
klubb_godkant_hal: [] # klubbchefen: hål som är godkända (svaren i Netlify Forms granskning-{slug})
tryckprov_ok:         # Eric: Ecosigns tryckprov godkänt (bara skyltar)
flygfilm_ok:          # Eric: flygfilm efter betalning och inom kredittaket
"""

MALL_KLUBB = """\
# {namn} – skapad {datum} med `python -m golfholes nyklubb`. Fyll i det som står TODO.
# Mall och förklaringar: klubbar/glasriket/klubb.yaml och docs/ny-klubb.md.
club: {namn}
web: TODO
contact: TODO
stil: A              # TODO klubbens val ur stilmenyn; A (kvällsljus) tills dess
layout: 3
kortnamn: TODO
filnamn: TODO
bana: TODO
# Vad klubben har köpt. Bara detta levereras (python -m golfholes paket klubbar/{slug}).
paket:
  avtal: TODO        # varifrån beställningen kommer, t.ex. "TACADA Direkt, signerat 2026-11-20"
  produkter: []      # halguide, grafisk_profil, hemsida, some_kit, halsponsring, skyltar, flygfilm, some_forvaltning
  # hal: [1, 10, 14] # bara för referensklubb
tees: []             # [{{namn: "58", farg: gul}}, ...] som klubben skriver dem
bbox_sweref99tm: null   # TODO {{e_min, n_min, e_max, n_max}} runt banan + 100 m
holes: []            # TODO scorekortet: - {{hole: 1, par: 4, index: 5, tees: {{"58": 352}}, geometry: null}}
"""


@dataclass
class Klubb:
    mapp: Path
    data: dict
    godkant: dict

    @property
    def slug(self) -> str:
        return self.mapp.name

    @property
    def produkter(self) -> list[str]:
        return list((self.data.get("paket") or {}).get("produkter") or [])

    @property
    def hal(self) -> list[int]:
        valda = (self.data.get("paket") or {}).get("hal")
        if valda:
            return [int(h) for h in valda]
        return [int(h["hole"]) for h in (self.data.get("holes") or []) if "hole" in h]

    def ok(self, nyckel: str) -> bool:
        v = self.godkant.get(nyckel)
        return bool(v) and str(v).strip().upper() != "TODO"

    def ut(self, *delar: str) -> Path:
        return REPO / "output" / self.slug / Path(*delar)


@dataclass
class Steg:
    id: str
    avsnitt: str                 # avsnitt i docs/ny-klubb.md
    titel: str
    vem: str                     # kod | claude | ai | klubb | eric
    klart: Callable[[Klubb], bool]
    kraver: tuple = ()
    kommando: list[str] | None = None   # bara för vem == "kod"
    hal: int | None = None
    status: str = field(default="", compare=False)


def las(mapp: Path) -> Klubb:
    mapp = Path(mapp)
    data = yaml.safe_load((mapp / "klubb.yaml").read_text(encoding="utf-8")) or {}
    gfil = mapp / "godkant.yaml"
    godkant = (yaml.safe_load(gfil.read_text(encoding="utf-8")) or {}) if gfil.exists() else {}
    return Klubb(mapp, data, godkant)


def _har(p: Path, monster: str = "*") -> bool:
    return p.exists() and any(p.glob(monster))


def _todo(v) -> bool:
    return v in (None, "", [], {}) or "TODO" in str(v)


def _langd_ok(k: Klubb, n: int) -> bool:
    fil = k.mapp / f"hal-{n:02d}.yaml"
    if not fil.exists():
        return False
    from .hole import Hole
    try:
        rader = Hole.from_yaml(fil).check_lengths()
    except Exception:
        return False
    return all(r.get("ok", True) for r in rader)


def _scorekort_ok(k: Klubb) -> bool:
    holes = {int(h["hole"]): h for h in (k.data.get("holes") or []) if "hole" in h}
    return bool(k.hal) and all(n in holes and holes[n].get("par") and holes[n].get("tees") for n in k.hal)


def _malad(k: Klubb, n: int) -> bool:
    return any(p for p in (k.mapp / "halbilder").glob(f"hal-{n:02d}-*.webp")
               if "lyft" not in p.name and "foto" not in p.name) if (k.mapp / "halbilder").exists() else False


def plan(k: Klubb) -> list[Steg]:
    """Alla steg för klubben, i ordning, bara för det som är beställt."""
    m, s = str(k.mapp), k.slug
    py = [sys.executable, "-m", "golfholes"]
    steg = [
        Steg("paket", "0", "Paketet ifyllt och bekräftat mot avtalet", "eric",
             lambda k: not kontrollera(k.data.get("paket") or {}) and k.ok("paket_bekraftat")),
        Steg("scorekort", "1", "Scorekort: par, index och längd per tee för hålen som ska göras", "klubb",
             _scorekort_ok, ("paket",)),
    ]
    if "halguide" not in k.produkter:
        return steg + _ovriga(k, py)
    steg += [
        Steg("bbox", "1", "Banans yta i SWEREF 99 TM (bbox_sweref99tm)", "claude",
             lambda k: not _todo(k.data.get("bbox_sweref99tm")), ("paket",)),
        Steg("hamta", "1", "Ortofoto och höjdmodell från Lantmäteriet", "kod",
             lambda k: (REPO / "data" / k.slug / "lantmateriet.json").exists(), ("bbox",),
             py + ["hamta", m]),
        Steg("stil", "2", "Stil vald ur stilmenyn", "klubb", lambda k: k.ok("stil_vald"), ("paket",)),
        Steg("kredittak", "2", "Kredittak för AI-målningen", "eric", lambda k: k.ok("kredittak"), ("paket",)),
    ]
    forsta = k.hal[0] if k.hal else None
    for n in k.hal:
        h = f"{n:02d}"
        efter_test = () if n == forsta else ("testhal",)
        steg += [
            Steg(f"fro-{h}", "2", f"Hål {n}: fröpunkter (tees mot klubbens bild, green, riktning)", "claude",
                 lambda k, n=n: (k.mapp / "utkast" / f"hal-{n:02d}.yaml").exists(), ("hamta", "scorekort") + efter_test,
                 hal=n),
            Steg(f"utkast-{h}", "2", f"Hål {n}: hålfil ur ortofotot", "kod",
                 lambda k, n=n: (k.mapp / f"hal-{n:02d}.yaml").exists(), (f"fro-{h}",),
                 py + ["utkast", f"{m}/utkast/hal-{h}.yaml"], hal=n),
            Steg(f"langd-{h}", "2", f"Hål {n}: varje tee inom ±3 % (rapport)", "claude",
                 lambda k, n=n: _langd_ok(k, n), (f"utkast-{h}",), hal=n),
            Steg(f"aiunderlag-{h}", "2", f"Hål {n}: underlag för AI-målning", "kod",
                 lambda k, n=n: _malad(k, n)
                 or (k.mapp / "typbilder" / "ai-underlag" / f"hal-{n:02d}-underlag.jpg").exists(),
                 (f"langd-{h}",), py + ["aiunderlag", f"{m}/hal-{h}.yaml"], hal=n),
            Steg(f"malning-{h}", "2", f"Hål {n}: AI-målning + aibild (formpoäng ≥ 0,7)", "ai",
                 lambda k, n=n: _malad(k, n), (f"aiunderlag-{h}", "stil", "kredittak"), hal=n),
            Steg(f"korttext-{h}", "2", f"Hål {n}: hålkortets texter (halkort/hal-{h}.yaml)", "claude",
                 lambda k, n=n: (k.mapp / "halkort" / f"hal-{n:02d}.yaml").exists(), (f"malning-{h}",), hal=n),
            Steg(f"halkort-{h}", "2", f"Hål {n}: hålkort (PNG)", "kod",
                 lambda k, n=n: _har(k.ut("halkort"), f"hal-{n:02d}-layout*.png"), (f"korttext-{h}", "hamta"),
                 py + ["halkort", f"{m}/halkort/hal-{h}.yaml"], hal=n),
        ]
    if forsta is not None:
        steg.append(Steg("testhal", "2", f"Testhålet (hål {forsta}) godkänt av Eric innan resten görs", "eric",
                         lambda k: k.ok("testhal_ok"), (f"halkort-{forsta:02d}",)))
    return steg + _ovriga(k, py)


def _ovriga(k: Klubb, py: list[str]) -> list[Steg]:
    m, p = str(k.mapp), set(k.produkter)
    alla_kort = tuple(f"halkort-{n:02d}" for n in k.hal) if "halguide" in p else ()
    steg: list[Steg] = []
    if "grafisk_profil" in p:
        steg += [
            Steg("logga", "3", "Loggvägar (3–4) visade, en vald", "eric", lambda k: k.ok("logga_vald"), ("paket",)),
            Steg("profil", "3", "Profil, typsnitt och flagga i klubb.yaml + manual-PDF", "claude",
                 lambda k: all(not _todo(k.data.get(x)) for x in ("profil", "typsnitt", "flagga")), ("logga",)),
            Steg("profil-ok", "3", "Grafiska profilen godkänd", "eric", lambda k: k.ok("profil_ok"), ("profil",)),
        ]
    if "hemsida" in p:
        steg += [
            Steg("designregister", "4", "Egen designriktning i hemsidor/designregister.yaml (unik)", "claude",
                 lambda k: f"id: {k.slug}" in (REPO / "hemsidor" / "designregister.yaml").read_text(encoding="utf-8"),
                 alla_kort),
            Steg("webb", "4", "Digital banguide / hålsidor", "kod", lambda k: _har(k.ut("webb")),
                 ("designregister",) + alla_kort, py + ["webb", m]),
            Steg("hemsida-ok", "4", "Hemsidan godkänd (smakgranskning först)", "eric",
                 lambda k: k.ok("hemsida_ok"), ("webb",)),
        ]
    if "some_kit" in p:
        steg += [
            Steg("inlaggtext", "5", "Inläggstexter i some/inlagg.yaml", "claude",
                 lambda k: (k.mapp / "some" / "inlagg.yaml").exists(), alla_kort),
            Steg("inlagg", "5", "Inlägg 4:5 för sociala medier", "kod", lambda k: _har(k.ut("inlagg")),
                 ("inlaggtext",), py + ["inlagg", m]),
            Steg("some-ok", "5", "Inläggen godkända", "eric", lambda k: k.ok("some_ok"), ("inlagg",)),
        ]
    if "halsponsring" in p:
        steg += [
            Steg("sponsring", "6", "Sponsring i klubb.yaml (pris, tillval) + partnerprogram.yaml", "claude",
                 lambda k: not _todo(k.data.get("sponsring")) and (k.mapp / "partnerprogram.yaml").exists(),
                 alla_kort),
            Steg("prospekt", "6", "Säljpresentation för alla hål (prospekt --gemensam)", "kod",
                 lambda k: _har(k.ut("prospekt")), ("sponsring",), py + ["prospekt", m, "--gemensam"]),
            Steg("partnerprogram", "6", "Partnerprogrammet (presentation, manual, rapporter ...)", "kod",
                 lambda k: _har(k.ut("partnerprogram")), ("sponsring",), py + ["partnerprogram", m]),
            Steg("sponsring-ok", "6", "Sponsormaterialet godkänt", "eric", lambda k: k.ok("sponsring_ok"),
                 ("prospekt", "partnerprogram")),
        ]
    if "halguide" in p:
        steg += [
            Steg("granskningsfil", "8", "Egna frågor till klubbchefen (granskning.yaml)", "claude",
                 lambda k: (k.mapp / "granskning.yaml").exists(), alla_kort),
            Steg("granskning", "8", "Granskningssidan för klubbchefen", "kod",
                 lambda k: _har(REPO / "hemsida" / "public" / "granskning", f"{k.slug}-*"),
                 ("granskningsfil",), py + ["granskning", m]),
            Steg("granskning-skickad", "8", "Granskningslänken skickad till klubbchefen", "eric",
                 lambda k: k.ok("granskning_skickad"), ("granskning",)),
            Steg("klubb-godkant", "8", "Klubbchefen har godkänt alla hål", "klubb",
                 lambda k: set(k.hal) <= {int(x) for x in (k.godkant.get("klubb_godkant_hal") or [])},
                 ("granskning-skickad",)),
        ]
    if "skyltar" in p:
        steg.append(Steg("tryckprov", "8", "Tryckprov från Ecosign godkänt innan skyltar beställs", "eric",
                         lambda k: k.ok("tryckprov_ok"), ("klubb-godkant",)))
    if "flygfilm" in p:
        steg.append(Steg("flygfilm", "7", "Flygfilm: efter betalning, Erics OK och inom kredittaket", "ai",
                         lambda k: k.ok("flygfilm_ok") and _har(k.ut("flygfilm")), ("klubb-godkant",)))
    return steg


STATUS = {
    "klar": "✓ klart",
    "vantar": "· väntar på tidigare steg",
    "kod": "▶ kan köras nu (gratis)",
    "claude": "✱ Claude gör nu",
    "ai": "€ kräver Erics OK på krediter",
    "klubb": "? väntar på klubben",
    "eric": "! väntar på Eric",
}


def bedom(steg: list[Steg], k: Klubb) -> list[Steg]:
    klara = set()
    for st in steg:
        if st.klart(k):
            klara.add(st.id)
    finns = {st.id for st in steg}
    for st in steg:
        if st.id in klara:
            st.status = "klar"
        elif any(d in finns and d not in klara for d in st.kraver):
            st.status = "vantar"
        else:
            st.status = st.vem
    return steg


def kor(mapp: Path, max_varv: int = 50) -> tuple[list[Steg], list[tuple[Steg, int]]]:
    """Kör gratis kodsteg som är redo, om och om igen tills inget nytt går. Aldrig AI, aldrig godkännanden."""
    gjorda: list[tuple[Steg, int]] = []
    forsokta: set[str] = set()
    for _ in range(max_varv):
        k = las(mapp)
        redo = [st for st in bedom(plan(k), k) if st.status == "kod" and st.id not in forsokta]
        if not redo:
            break
        for st in redo:
            forsokta.add(st.id)
            print(f"\n▶ {st.titel}\n  {' '.join(st.kommando[1:])}", flush=True)
            r = subprocess.run(st.kommando, cwd=REPO)
            gjorda.append((st, r.returncode))
    k = las(mapp)
    return bedom(plan(k), k), gjorda


def skapa(mapp: Path, namn: str, datum: str) -> list[Path]:
    mapp = Path(mapp)
    if (mapp / "klubb.yaml").exists():
        raise SystemExit(f"{mapp}/klubb.yaml finns redan – skriver inte över.")
    for d in ("utkast", "halkort", "halbilder", "typbilder/ai-underlag", "some", "profil", "loggor"):
        (mapp / d).mkdir(parents=True, exist_ok=True)
    filer = [mapp / "klubb.yaml", mapp / "godkant.yaml"]
    filer[0].write_text(MALL_KLUBB.format(namn=namn, slug=mapp.name, datum=datum), encoding="utf-8")
    filer[1].write_text(MALL_GODKANT.format(slug=mapp.name), encoding="utf-8")
    return filer


def utskrift(k: Klubb, steg: list[Steg]) -> str:
    rader = [f"{k.data.get('club', k.slug)} – {', '.join(k.produkter) or 'inget paket'}"
             + (f" – hål {', '.join(map(str, k.hal))}" if "halguide" in k.produkter else ""), ""]
    avsnitt = None
    for st in steg:
        if st.avsnitt != avsnitt:
            avsnitt = st.avsnitt
            rader.append(f"Avsnitt {avsnitt}")
        rader.append(f"  {STATUS[st.status]:<32} {st.titel}")
    klara = sum(st.status == "klar" for st in steg)
    rader += ["", f"{klara} av {len(steg)} steg klara."]
    for rubrik, typ in (("Nästa för Claude", "claude"), ("Kan köras nu (--kor)", "kod"),
                        ("Väntar på Eric", "eric"), ("Kräver krediter (Erics OK)", "ai"),
                        ("Väntar på klubben", "klubb")):
        lista = [st.titel for st in steg if st.status == typ]
        if lista:
            rader.append(f"{rubrik}:")
            rader += [f"  - {t}" for t in lista]
    ej = [PRODUKTER[x].namn.split(":")[0] for x in PRODUKTER if x not in k.produkter]
    if ej:
        rader.append("Inte beställt (görs inte): " + ", ".join(ej))
    for f in kontrollera(k.data.get("paket") or {}):
        rader.append(f"STOPP: {f}")
    return "\n".join(rader)
