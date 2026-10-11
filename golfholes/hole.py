"""Ett hål: geometri (från vektorkartan) + klubbens scorekortsdata.

All geometri är i SWEREF 99 TM (meter). Avstånd räknas längs spellinjen
(`centerline`), från vald tee, aldrig fågelvägen – så som golfare mäter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import geometry as g

# Svenska namn på hindertyper i rapporter och på skyltar.
HAZARD_LABELS = {
    "bunker": "Bunker",
    "water": "Vatten",
    "creek": "Bäck",
    "ob": "Out of bounds",
    "trees": "Skog",
}


@dataclass
class Hazard:
    kind: str
    name: str
    polygon: list[g.Point]


@dataclass
class Tee:
    name: str
    point: g.Point
    length_m: float | None = None  # längd enligt klubbens scorekort


@dataclass
class Hole:
    club: str
    number: int
    par: int
    index: int | None
    centerline: list[g.Point]
    green: list[g.Point]
    tees: list[Tee]
    hazards: list[Hazard] = field(default_factory=list)
    fairways: list[list[g.Point]] = field(default_factory=list)
    trees: list[list[g.Point]] = field(default_factory=list)  # skogs-/trädytor
    strategy: dict[str, str] = field(default_factory=dict)  # "säkert"/"chansa", granskas av golfare
    ortho: Path | None = None  # utsnitt (JPG) med world-fil bredvid – används av fotostilen
    source: str = ""

    # ---------- inläsning ----------
    @classmethod
    def from_yaml(cls, path: str | Path) -> "Hole":
        d = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        origin = tuple(d.get("origin", (0.0, 0.0)))

        def pts(seq):
            return [(origin[0] + p[0], origin[1] + p[1]) for p in seq]

        return cls(
            club=d["club"],
            number=int(d["hole"]),
            par=int(d["par"]),
            index=d.get("index"),
            centerline=pts(d["centerline"]),
            green=pts(d["green"]),
            tees=[Tee(t["name"], pts([t["point"]])[0], t.get("length_m")) for t in d["tees"]],
            hazards=[Hazard(h["kind"], h.get("name", ""), pts(h["polygon"])) for h in d.get("hazards") or []],
            fairways=[pts(f) for f in d.get("fairways") or []],
            trees=[pts(t) for t in d.get("trees") or []],
            strategy=d.get("strategy", {}) or {},
            ortho=(Path(path).parent / d["ortho"]).resolve() if d.get("ortho") else None,
            source=d.get("source", ""),
        )

    # ---------- avstånd ----------
    def tee(self, name: str | None = None) -> Tee:
        """Bakre tee om inget namn anges (den med längst avstånd till green)."""
        if name is None:
            return max(self.tees, key=lambda t: self.green_distances(t.name)["mitt"])
        for t in self.tees:
            if t.name == str(name):
                return t
        raise KeyError(f"Tee {name} finns inte på hål {self.number}")

    def _tee_station(self, tee: Tee) -> float:
        return g.project(self.centerline, tee.point)[0]

    def green_distances(self, tee_name: str) -> dict[str, float]:
        tee = next(t for t in self.tees if t.name == str(tee_name))
        s0 = self._tee_station(tee)
        front, back, _ = g.station_range(self.centerline, self.green)
        mid = g.project(self.centerline, g.centroid(self.green))[0]
        return {"fram": front - s0, "mitt": mid - s0, "bak": back - s0}

    def hazard_distances(self, tee_name: str | None = None) -> list[dict]:
        """Avstånd från tee till varje hinder: närmaste kant och bortre kant (carry)."""
        tee = self.tee(tee_name)
        s0 = self._tee_station(tee)
        rows = []
        for h in self.hazards:
            first, last, side = g.station_range(self.centerline, h.polygon)
            rows.append(
                {
                    "typ": HAZARD_LABELS.get(h.kind, h.kind),
                    "namn": h.name,
                    "sida": "vänster" if side < -3 else "höger" if side > 3 else "tvärs",
                    "till": round(first - s0),
                    "carry": round(last - s0),
                }
            )
        return sorted(rows, key=lambda r: r["till"])

    # ---------- kamera för tee-vy och film ----------
    def camera(self, tee_name: str | None = None, height_m: float = 1.6, aim_m: float = 150.0) -> dict:
        """Kamerans läge för tee-vyn.

        Står på teen i ögonhöjd och siktar mot punkten `aim_m` meter ut längs
        fairwayns mittlinje. Par 3, eller om green ligger närmare än siktpunkten:
        sikta på greenens mitt.
        """
        tee = self.tee(tee_name)
        s0 = self._tee_station(tee)
        green_mid = g.centroid(self.green)
        to_green = self.green_distances(tee.name)["mitt"]
        if self.par == 3 or to_green <= aim_m:
            target, mode = green_mid, "green"
        else:
            target, mode = g.point_along(self.centerline, s0 + aim_m), f"{aim_m:.0f} m längs mittlinjen"
        return {
            "tee": tee.name,
            "position": [round(tee.point[0], 2), round(tee.point[1], 2), height_m],
            "sikte": [round(target[0], 2), round(target[1], 2)],
            "riktning_grader": round(g.bearing(tee.point, target), 1),
            "siktar_mot": mode,
        }

    # ---------- kontroll ----------
    def check_lengths(self, tolerance: float = 0.03) -> list[dict]:
        """Jämför uppmätt längd (tee → mitten av green) med klubbens scorekort."""
        out = []
        for t in self.tees:
            measured = self.green_distances(t.name)["mitt"]
            row = {"tee": t.name, "uppmätt": round(measured), "scorekort": t.length_m}
            if t.length_m:
                diff = (measured - t.length_m) / t.length_m
                row["avvikelse_%"] = round(100 * diff, 1)
                row["ok"] = abs(diff) <= tolerance
            out.append(row)
        return out
