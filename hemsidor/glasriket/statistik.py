"""Hålsponsorernas siffror: besök per hålsida och QR-besök per hål, hämtat från Plausible.

Ger en CSV med en rad per hål (sidvisningar, besökare, QR-besök) för en period, som underlag
till sponsorrapporten efter säsongen. Siffrorna är besök, inte personer.

Förutsättningar (görs en gång, när sajten har en domän):
  1. Lägg till sajten i Plausible och sätt PLAUSIBLE_DOMAN i bygg.py. Bygg och publicera.
  2. I Plausible: Site settings → Goals → lägg till Custom event "QR-besök".
     Site settings → Custom properties → lägg till "hal".
  3. Skapa en Stats API-nyckel (Account settings → API keys) och lägg den som hemlighet
     PLAUSIBLE_API_KEY i miljön (aldrig i repot).
  4. QR-koderna på skyltarna pekar på adresserna i qr-lankar.csv (…/banan/hal-NN/?q=hNN).

Kör:  python hemsidor/glasriket/statistik.py 2027-04-01 2027-10-31  > sponsorstatistik-2027.csv
"""
import csv
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from bygg import PLAUSIBLE_DOMAN  # noqa: E402

API = "https://plausible.io/api/v2/query"


def fraga(nyckel: str, kropp: dict) -> list:
    req = urllib.request.Request(API, data=json.dumps(kropp).encode(), method="POST", headers={
        "Authorization": f"Bearer {nyckel}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as svar:
        return json.load(svar)["results"]


def main(fran: str, till: str) -> None:
    nyckel = os.environ.get("PLAUSIBLE_API_KEY")
    if not PLAUSIBLE_DOMAN or not nyckel:
        raise SystemExit("Sätt PLAUSIBLE_DOMAN i bygg.py och miljövariabeln PLAUSIBLE_API_KEY först.")
    period = [fran, till]
    sidor = fraga(nyckel, {
        "site_id": PLAUSIBLE_DOMAN, "date_range": period, "metrics": ["pageviews", "visitors"],
        "dimensions": ["event:page"], "filters": [["contains", "event:page", ["/banan/hal-"]]],
    })
    qr = fraga(nyckel, {
        "site_id": PLAUSIBLE_DOMAN, "date_range": period, "metrics": ["events"],
        "dimensions": ["event:props:hal"], "filters": [["is", "event:goal", ["QR-besök"]]],
    })
    per_hal = {n: {"sidvisningar": 0, "besokare": 0, "qr_besok": 0} for n in range(1, 19)}
    for r in sidor:
        sida = r["dimensions"][0]
        try:
            n = int(sida.split("/banan/hal-")[1].strip("/")[:2])
        except (IndexError, ValueError):
            continue
        if n in per_hal:
            per_hal[n]["sidvisningar"] += r["metrics"][0]
            per_hal[n]["besokare"] += r["metrics"][1]
    for r in qr:
        hal = r["dimensions"][0]
        if hal.startswith("h") and hal[1:].isdigit() and int(hal[1:]) in per_hal:
            per_hal[int(hal[1:])]["qr_besok"] += r["metrics"][0]
    ut = csv.writer(sys.stdout)
    ut.writerow(["hal", "sidvisningar", "besokare", "qr_besok", "period"])
    for n, v in per_hal.items():
        ut.writerow([n, v["sidvisningar"], v["besokare"], v["qr_besok"], f"{fran}–{till}"])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
