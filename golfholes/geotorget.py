"""Söker och hämtar Lantmäteriets ortofoto och markhöjdmodell direkt via deras STAC-API.

Sökningen är öppen för alla. Nedladdningen kräver Geotorget-inloggning, som läses
från miljövariablerna LM_ANVANDARE och LM_LOSENORD. De sätts i projektets
inställningar (miljövariabler), aldrig i chatten och aldrig i en fil i repot.

Typiskt flöde:
    python -m golfholes sok klubbar/glasriket          # vad finns, vilka år
    python -m golfholes hamta klubbar/glasriket        # senaste ortofoto + höjdmodell
    → data/glasriket/orto/*.tif, data/glasriket/hojd/*.tif, data/glasriket/lantmateriet.json
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from .sweref import sweref99tm_to_wgs84

STAC = {
    "orto": "https://api.lantmateriet.se/stac-bild/v1",
    "hojd": "https://api.lantmateriet.se/stac-hojd/v1",
}
HOJD_SAMLING = "dtm-cog"  # Markhöjdmodell 1 m. "dsm-skoglig-copc" (laserdata skog) hämtas inte.
ATTRIBUTION = "Underlag: Ortofoto och Markhöjdmodell ©Lantmäteriet, bearbetat, CC BY 4.0"
USER_AGENT = "golfholes/0.1 (TACADA Courses)"


@dataclass
class Ruta:
    katalog: str      # "orto" eller "hojd"
    id: str           # t.ex. "o63050_4900_25_mr25"
    samling: str      # t.ex. "orto-e2-2025"
    datum: str        # fotodatum / skanningsdatum
    url: str          # själva GeoTIFF:en (kräver inloggning)
    extra: dict       # övriga filer (metadata, miniatyr), öppna

    @property
    def ar(self) -> int:
        return int(self.datum[:4])


def bbox_wgs84(b: dict) -> tuple[float, float, float, float]:
    """bbox_sweref99tm ur klubb.yaml → (min_lon, min_lat, max_lon, max_lat)."""
    hörn = [sweref99tm_to_wgs84(e, n) for e in (b["e_min"], b["e_max"]) for n in (b["n_min"], b["n_max"])]
    lats, lons = [h[0] for h in hörn], [h[1] for h in hörn]
    return min(lons), min(lats), max(lons), max(lats)


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def sok(katalog: str, bbox: tuple[float, float, float, float]) -> list[Ruta]:
    """Alla rutor (alla år) som täcker bbox i en katalog. Kräver ingen inloggning."""
    url = f"{STAC[katalog]}/search?" + urllib.parse.urlencode(
        {"bbox": ",".join(f"{v:.6f}" for v in bbox), "limit": 100})
    rutor: list[Ruta] = []
    while url:
        d = _get_json(url)
        for f in d.get("features", []):
            if katalog == "hojd" and f["collection"] != HOJD_SAMLING:
                continue
            assets = f["assets"]
            rutor.append(Ruta(katalog, f["id"], f["collection"], f["properties"]["datetime"][:10],
                              assets["data"]["href"],
                              {k: a["href"] for k, a in assets.items() if k != "data"}))
        url = next((l["href"] for l in d.get("links", []) if l.get("rel") == "next"), None)
    return rutor


def ar_fargbild(r: Ruta) -> bool:
    """Vanligt färgortofoto: inte historiskt svartvitt och inte IR (suffix som börjar på 'i')."""
    if r.katalog != "orto":
        return True
    return not r.samling.startswith("orto-historiska") and not r.id.rsplit("_", 1)[-1].startswith("i")


def senaste(rutor: list[Ruta]) -> list[Ruta]:
    """Alla rutor från den nyaste samlingen (samma flygning/år), bara färgbilder."""
    rutor = [r for r in rutor if ar_fargbild(r)]
    if not rutor:
        return []
    nyast = max(rutor, key=lambda r: r.datum).samling
    return sorted((r for r in rutor if r.samling == nyast), key=lambda r: r.id)


def inloggning() -> str:
    anv, lös = os.environ.get("LM_ANVANDARE"), os.environ.get("LM_LOSENORD")
    if not anv or not lös:
        raise SystemExit(
            "Inloggning saknas: sätt miljövariablerna LM_ANVANDARE och LM_LOSENORD "
            "(Geotorget-användarnamn och lösenord) i projektinställningarna. "
            "Klistra aldrig in dem i chatten.")
    return "Basic " + base64.b64encode(f"{anv}:{lös}".encode()).decode()


def ladda_ner(url: str, mål: Path, auth: str | None) -> Path:
    """Hämtar en fil i bitar till mål. Fortsätter där den slutade om den avbröts."""
    mål.parent.mkdir(parents=True, exist_ok=True)
    del_fil = mål.with_suffix(mål.suffix + ".part")
    huvud = {"User-Agent": USER_AGENT}
    if auth:
        huvud["Authorization"] = auth
    start = del_fil.stat().st_size if del_fil.exists() else 0
    if start:
        huvud["Range"] = f"bytes={start}-"
    req = urllib.request.Request(url, headers=huvud)
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(del_fil, "ab" if start and r.status == 206 else "wb") as ut:
            while chunk := r.read(1 << 20):
                ut.write(chunk)
    except urllib.error.HTTPError as e:
        if e.code == 416 and start:  # redan komplett
            pass
        elif e.code in (401, 403):
            raise SystemExit(
                f"Lantmäteriet nekade nedladdningen ({e.code}). Kontrollera LM_ANVANDARE/LM_LOSENORD "
                "och att kontot har godkända villkor för ortofoto och markhöjdmodell på Geotorget.") from e
        else:
            raise
    del_fil.replace(mål)
    return mål


def hamta(bbox: tuple[float, float, float, float], data_dir: Path, ar: int | None = None,
          katalog: tuple[str, ...] = ("orto", "hojd")) -> dict:
    """Laddar ner nyaste (eller valt års) ortofoto och höjdmodell för bbox till data_dir.

    Skriver data_dir/lantmateriet.json med vilka filer, bildår och attribution.
    Filer som redan finns hoppas över.
    """
    auth = inloggning()
    logg: dict = {"attribution": ATTRIBUTION, "bbox_wgs84": bbox, "filer": []}
    for kat in katalog:
        rutor = sok(kat, bbox)
        if kat == "orto" and ar:
            rutor = [r for r in rutor if r.ar == ar]
        valda = senaste(rutor)
        if not valda:
            raise SystemExit(f"Hittade inga {kat}-rutor för området" + (f" år {ar}" if ar else "") + ".")
        for r in valda:
            mål = data_dir / kat / Path(urllib.parse.urlparse(r.url).path).name
            if not mål.exists():
                print(f"  hämtar {mål.name} ({r.samling}, {r.datum}) …", flush=True)
                ladda_ner(r.url, mål, auth)
            else:
                print(f"  finns redan: {mål.name}")
            logg["filer"].append({**asdict(r), "fil": str(mål)})
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "lantmateriet.json").write_text(json.dumps(logg, ensure_ascii=False, indent=2), encoding="utf-8")
    return logg
