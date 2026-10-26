"""Vad klubben har köpt. Vi levererar det klubben beställt och inget mer.

    python -m golfholes paket klubbar/<klubb>

I klubb.yaml:
    paket:
      avtal: "TACADA Direkt, signerat 2026-11-02"     # varifrån beställningen kommer (avtal, mejl)
      produkter: [halguide, grafisk_profil, hemsida, some_kit, halsponsring]
      hal: [1, 10, 14]                                 # bara för referensklubb: vilka hål (annars alla)

Kommandot skriver ut vilka steg i docs/ny-klubb.md som ska göras och vilka som inte ska göras,
och stoppar om en produkt saknar något den bygger på eller om paketet inte är ifyllt.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Produkt:
    namn: str
    steg: str            # avsnitt i docs/ny-klubb.md
    kraver: tuple = ()   # produkter som måste ingå för att den här ska gå att leverera


PRODUKTER: dict[str, Produkt] = {
    "halguide": Produkt("Hålguide: hålbilder och hålkort för varje hål", "1, 2"),
    "grafisk_profil": Produkt("Grafisk profil: förnyad logga, färger, typsnitt och manual", "3"),
    "hemsida": Produkt("Ny hemsida med en sida per hål", "4", ("halguide",)),
    "some_kit": Produkt("Social Media Kit: fästa inlägg, hål för hål, ikoner", "5", ("halguide",)),
    "halsponsring": Produkt("Hålsponsring: säljpresentation, partnerprogram och sponsorstatistik", "6", ("halguide",)),
    "skyltar": Produkt("Hålskyltar 70 × 100 cm hos Ecosign (tillval)", "6", ("halguide", "halsponsring")),
    "flygfilm": Produkt("Flygfilm per hål med nedräkning och slagkurvor (tillval)", "7", ("halguide",)),
    "some_forvaltning": Produkt("SoMe-förvaltning per månad (tillval)", "5", ("some_kit",)),
}

# Referensklubb: 3 hål som hålkort, för ett bokat möte. Inget annat.
REFERENSKLUBB = ("halguide",)


def las(klubbmapp: Path) -> dict:
    klubb = yaml.safe_load((klubbmapp / "klubb.yaml").read_text(encoding="utf-8")) or {}
    return klubb.get("paket") or {}


def kontrollera(paket: dict) -> list[str]:
    """Fel som stoppar arbetet: inget paket, okända produkter, saknade förutsättningar."""
    produkter = list(paket.get("produkter") or [])
    if not produkter:
        return ["Inget paket i klubb.yaml (paket: produkter: [...]). Fråga Eric vad klubben har köpt innan något görs."]
    fel = [f"Okänd produkt: {p} (finns: {', '.join(PRODUKTER)})" for p in produkter if p not in PRODUKTER]
    for p in produkter:
        for k in (PRODUKTER[p].kraver if p in PRODUKTER else ()):
            if k not in produkter:
                fel.append(f"{PRODUKTER[p].namn} bygger på {PRODUKTER[k].namn.split(':')[0].lower()}, som inte är beställd")
    return fel


def sammanfattning(klubbmapp: Path) -> tuple[list[str], list[str], list[str]]:
    """(ska göras, ska inte göras, fel)."""
    paket = las(klubbmapp)
    valda = [p for p in (paket.get("produkter") or []) if p in PRODUKTER]
    gor = [f"{PRODUKTER[p].namn} (avsnitt {PRODUKTER[p].steg})" for p in valda]
    if paket.get("hal"):
        gor.append("Bara hål " + ", ".join(str(h) for h in paket["hal"]))
    gor_inte = [PRODUKTER[p].namn for p in PRODUKTER if p not in valda]
    return gor, gor_inte, kontrollera(paket)
