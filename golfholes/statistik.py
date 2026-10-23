"""Statistik för hålsponsorer: visningar per hål, kanal och säsong.

Tre källor (se docs/statistik.md för hur de samlas in):

  a) Plausible – CSV-export per månad från klubbens webbplats.
     `pages.csv` ger sidvisningar per hålsida (/hal-03/ …).
     QR-besök: skylten länkar till /hal-NN/?q=hNN. Webbplatsens mätkod skickar `q` som
     egen egenskap, så exporten har en tabell (property, value, visitors, events) med
     raderna q = h03 osv. Saknas den tabellen räknas sidor vars namn innehåller ?q=hNN.
  b) Partnerkanaler – CSV med kolumnerna klubb, bana, hal, manad, visningar, klick.
     En fil per kanal. Kanalen namnges aldrig i sponsorns rapport (bara "Digital partnerkanal").
  c) Tee-skylten – klubbens ronder (`ronder_per_ar` i klubb.yaml) × andel som spelar hålet.
     Alltid märkt "uppskattning".

Alla siffror är VISNINGAR (antal gånger hålet/loggan visats), aldrig personer.

Mappstruktur för en säsong (standard data/<klubb>/statistik/<säsong>/):

  plausible/2027-05/pages.csv          (uppackad export för maj)
  plausible/2027-05/custom_props.csv
  plausible/plausible-2027-06.zip      (eller exporten som zip, månaden i filnamnet)
  partner/<kanal>.csv
  TESTDATA.txt                         (finns filen märks rapporten TESTDATA)
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

MANAD_RE = re.compile(r"(20\d\d)-(0[1-9]|1[0-2])")
HALSIDA_RE = re.compile(r"/hal-?(\d{1,2})(?:/|\?|$)", re.IGNORECASE)
Q_RE = re.compile(r"[?&]q=h(\d{1,2})\b", re.IGNORECASE)
Q_VARDE_RE = re.compile(r"^h(\d{1,2})$", re.IGNORECASE)


# ---------------------------------------------------------------- länkar

def qr_lank(club: dict, hole_nr: int) -> str:
    """Länken som QR-koden på tee-skylten pekar på: hålsidan med ?q=hNN."""
    base = str(club.get("web_base") or club.get("web") or "").rstrip("/")
    return f"{base}/hal-{hole_nr:02d}/?q=h{hole_nr:02d}"


def matkod(club: dict) -> str:
    """Plausible-mätkoden för hålsidorna (tom om klubben inte har `statistik.plausible_doman`).

    Sidan räknas utan frågesträng (så /hal-03/ blir en rad i pages.csv) och `q` från QR-länken
    skickas som egen egenskap. Klick på sponsorns länk skickas som händelsen Sponsorklick
    med egenskapen hal = hNN.
    """
    doman = (club.get("statistik") or {}).get("plausible_doman")
    if not doman:
        return ""
    return (f'<script defer data-domain="{doman}" src="https://plausible.io/js/script.manual.js"></script>'
            "<script>window.plausible=window.plausible||function(){(window.plausible.q=window.plausible.q||[]).push(arguments)};"
            "(function(){var q=new URLSearchParams(location.search).get('q');"
            "plausible('pageview',{u:location.origin+location.pathname,props:q?{q:q}:{}});"
            "document.addEventListener('click',function(e){var a=e.target.closest('a[data-hal]');"
            "if(a)plausible('Sponsorklick',{props:{hal:a.dataset.hal}});});})();</script>")


# ---------------------------------------------------------------- datamodell

@dataclass
class Kanal:
    namn: str
    visningar: int = 0
    klick: int | None = None
    kalla: str = ""
    uppskattning: bool = False
    manader: dict[str, int] = field(default_factory=dict)

    def lagg_till(self, manad: str | None, visningar: int, klick: int | None = None) -> None:
        self.visningar += visningar
        if klick is not None:
            self.klick = (self.klick or 0) + klick
        if manad:
            self.manader[manad] = self.manader.get(manad, 0) + visningar


@dataclass
class HalStatistik:
    hal: int
    par: int | None
    sponsor: dict
    kanaler: list[Kanal]
    saknas: list[str]

    @property
    def digitala_visningar(self) -> int:
        """Uppmätta visningar: hålsidan + partnerkanaler (QR ingår redan i hålsidan)."""
        return sum(k.visningar for k in self.kanaler if not k.uppskattning and k.kalla != "qr")

    def manader(self) -> dict[str, int]:
        ut: dict[str, int] = {}
        for k in self.kanaler:
            if k.uppskattning or k.kalla == "qr":
                continue
            for m, v in k.manader.items():
                ut[m] = ut.get(m, 0) + v
        return dict(sorted(ut.items()))


@dataclass
class Sasongsrapport:
    klubb: str
    bana: str | None
    sasong: int
    testdata: bool
    hal: list[HalStatistik]
    varningar: list[str]


# ---------------------------------------------------------------- läsning

def _tal(v) -> int:
    s = str(v or "").strip().replace(" ", "").replace(" ", "")
    if not s:
        return 0
    try:
        return int(round(float(s.replace(",", "."))))
    except ValueError:
        return 0


def _norm(s: str) -> str:
    return (s or "").strip().lower().replace("å", "a").replace("ä", "a").replace("ö", "o")


def _csv_rader(text: str) -> list[dict]:
    text = text.lstrip("﻿")
    try:
        dialekt = csv.Sniffer().sniff(text.splitlines()[0] if text else ",", delimiters=",;\t")
    except csv.Error:
        dialekt = csv.excel
    return [{_norm(k): v for k, v in r.items() if k} for r in csv.DictReader(io.StringIO(text), dialect=dialekt)]


def _plausible_filer(mapp: Path) -> list[tuple[str | None, str, str]]:
    """(månad, filnamn, text) för alla CSV i plausible-mappen, uppackade eller i zip."""
    ut: list[tuple[str | None, str, str]] = []
    if not mapp.exists():
        return ut
    for p in sorted(mapp.rglob("*")):
        m = MANAD_RE.search(str(p.relative_to(mapp)))
        manad = f"{m.group(1)}-{m.group(2)}" if m else None
        if p.suffix.lower() == ".csv":
            ut.append((manad, p.name.lower(), p.read_text(encoding="utf-8-sig")))
        elif p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    if n.lower().endswith(".csv"):
                        ut.append((manad, Path(n).name.lower(), z.read(n).decode("utf-8-sig")))
    return ut


def las_plausible(mapp: Path, sasong: int, varningar: list[str]) -> tuple[dict, dict, dict]:
    """Returnerar (sidvisningar, qr, sponsorklick) som {hål: {månad: antal}}."""
    sidor: dict[int, dict[str, int]] = {}
    qr_props: dict[int, dict[str, int]] = {}
    klick: dict[int, dict[str, int]] = {}
    qr_sidor: dict[int, dict[str, int]] = {}
    manader_med_props: set[str] = set()
    for manad, namn, text in _plausible_filer(mapp):
        if manad is None:
            varningar.append(f"Plausible-filen {namn} saknar månad (ÅÅÅÅ-MM) i mapp- eller filnamn – hoppas över.")
            continue
        if not manad.startswith(str(sasong)):
            continue
        rader = _csv_rader(text)
        if not rader:
            continue
        kol = set(rader[0])
        if {"property", "value"} <= kol:
            for r in rader:
                prop = _norm(r.get("property"))
                mq = Q_VARDE_RE.match((r.get("value") or "").strip())
                if prop == "hal" and mq:
                    antal = _tal(r.get("events") if r.get("events") not in (None, "") else r.get("visitors"))
                    d = klick.setdefault(int(mq.group(1)), {})
                    d[manad] = d.get(manad, 0) + antal
                    continue
                if prop != "q":
                    continue
                if mq:
                    manader_med_props.add(manad)
                    antal = _tal(r.get("events") if r.get("events") not in (None, "") else r.get("visitors"))
                    d = qr_props.setdefault(int(mq.group(1)), {})
                    d[manad] = d.get(manad, 0) + antal
        elif "name" in kol and ("pageviews" in kol or "visitors" in kol):
            if namn.startswith(("entry", "exit")):
                continue  # ingångs-/utgångssidor är delmängder av pages.csv
            for r in rader:
                sida = r.get("name") or ""
                mh = HALSIDA_RE.search(sida)
                if not mh:
                    continue
                antal = _tal(r.get("pageviews") if r.get("pageviews") not in (None, "") else r.get("visitors"))
                nr = int(mh.group(1))
                d = sidor.setdefault(nr, {})
                d[manad] = d.get(manad, 0) + antal
                mq = Q_RE.search(sida)
                if mq:
                    d = qr_sidor.setdefault(int(mq.group(1)), {})
                    d[manad] = d.get(manad, 0) + antal
    # QR: mätkodens egenskap q går före sidnamn med ?q= (som Plausible normalt tar bort).
    qr: dict[int, dict[str, int]] = {}
    for nr in set(qr_props) | set(qr_sidor):
        for m in set(qr_props.get(nr, {})) | set(qr_sidor.get(nr, {})):
            v = qr_props.get(nr, {}).get(m) if m in manader_med_props else qr_sidor.get(nr, {}).get(m)
            if v:
                qr.setdefault(nr, {})[m] = v
    return sidor, qr, klick


def las_partner(mapp: Path, klubb: str, bana: str | None, sasong: int, varningar: list[str]) -> list[tuple[str, dict]]:
    """[(filnamn, {hål: {månad: (visningar, klick)}})] – en post per partnerfil."""
    ut = []
    if not mapp.exists():
        return ut
    for p in sorted(mapp.glob("*.csv")):
        rader = _csv_rader(p.read_text(encoding="utf-8-sig"))
        saknade = {"klubb", "hal", "manad", "visningar"} - set(rader[0] if rader else {})
        if saknade:
            varningar.append(f"{p.name}: saknar kolumnerna {', '.join(sorted(saknade))} – hoppas över.")
            continue
        per_hal: dict[int, dict[str, tuple[int, int]]] = {}
        for r in rader:
            if _norm(r.get("klubb")) != _norm(klubb):
                continue
            if bana and r.get("bana") and _norm(r.get("bana")) != _norm(bana):
                continue
            mm = MANAD_RE.search(r.get("manad") or "")
            if not mm or mm.group(1) != str(sasong):
                continue
            manad = f"{mm.group(1)}-{mm.group(2)}"
            nr = _tal(r.get("hal"))
            v, k = per_hal.setdefault(nr, {}).get(manad, (0, 0))
            per_hal[nr][manad] = (v + _tal(r.get("visningar")), k + _tal(r.get("klick")))
        ut.append((p.name, per_hal))
    return ut


def _ronder(club: dict, sasong: int) -> int | None:
    r = club.get("ronder_per_ar")
    if isinstance(r, dict):
        v = r.get(sasong, r.get(str(sasong)))
        return _tal(v) if v is not None else None
    return _tal(r) if r is not None else None


def _par(club: dict, club_dir: Path, nr: int) -> int | None:
    for h in club.get("holes") or []:
        if int(h.get("hole", 0)) == nr and h.get("par"):
            return int(h["par"])
    f = club_dir / f"hal-{nr:02d}.yaml"
    if f.exists():
        return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("par")
    return None


def kallmapp(club_dir: Path, sasong: int) -> Path:
    """Standardplats för säsongens exporter: data/<klubb>/statistik/<säsong>/, annars klubbmappen."""
    for p in (Path("data") / club_dir.name / "statistik" / str(sasong), club_dir / "statistik" / str(sasong)):
        if p.exists():
            return p
    return Path("data") / club_dir.name / "statistik" / str(sasong)


def sammanstall(club_dir: str | Path, sasong: int, kalla: str | Path | None = None) -> Sasongsrapport:
    club_dir = Path(club_dir)
    club = yaml.safe_load((club_dir / "klubb.yaml").read_text(encoding="utf-8")) or {}
    kalla = Path(kalla) if kalla else kallmapp(club_dir, sasong)
    varningar: list[str] = []
    if not kalla.exists():
        varningar.append(f"Ingen statistik hittad i {kalla}.")
    sponsors = {int(k): v for k, v in (club.get("sponsors") or {}).items() if v}
    if not sponsors:
        varningar.append("klubb.yaml har inga sponsorer (fältet sponsors) – ingen rapport att göra.")
    bana = club.get("bana")
    sidor, qr, klick = las_plausible(kalla / "plausible", sasong, varningar)
    partner = las_partner(kalla / "partner", club["club"], bana, sasong, varningar)
    ronder = _ronder(club, sasong)
    andel = float((club.get("statistik") or {}).get("andel_spelar_halet", 1.0))
    if ronder is None:
        varningar.append(f"Klubbens ronder för {sasong} saknas (ronder_per_ar i klubb.yaml) – tee-skylten räknas inte.")
    flera_partner = len(partner) > 1
    hal = []
    for nr, sp in sorted(sponsors.items()):
        kanaler: list[Kanal] = []
        saknas: list[str] = []
        if ronder is not None:
            k = Kanal("Tee-skylten", kalla="ronder", uppskattning=True)
            k.lagg_till(None, int(round(ronder * andel)))
            kanaler.append(k)
        else:
            saknas.append("ronder")
        if nr in sidor:
            k = Kanal("Hålsidan på webben", kalla="plausible")
            for m, v in sorted(sidor[nr].items()):
                k.lagg_till(m, v)
            if nr in klick:
                k.klick = sum(klick[nr].values())
            kanaler.append(k)
            if nr in qr:
                kq = Kanal("varav via QR-koden på skylten", kalla="qr")
                for m, v in sorted(qr[nr].items()):
                    kq.lagg_till(m, v)
                kanaler.append(kq)
        else:
            saknas.append("webb")
        for i, (fil, per_hal) in enumerate(partner, 1):
            if nr not in per_hal:
                continue
            k = Kanal("Digital partnerkanal" + (f" {i}" if flera_partner else ""), kalla=f"partner:{fil}")
            for m, (v, kl) in sorted(per_hal[nr].items()):
                k.lagg_till(m, v, kl)
            kanaler.append(k)
        if not any(k.kalla.startswith("partner") for k in kanaler):
            saknas.append("partner")
        hal.append(HalStatistik(nr, _par(club, club_dir, nr), sp, kanaler, saknas))
    testdata = bool(club.get("testdata")) or (kalla / "TESTDATA.txt").exists()
    return Sasongsrapport(club["club"], bana, sasong, testdata, hal, varningar)


# ---------------------------------------------------------------- utdata

def _slug(s: str) -> str:
    s = _norm(s).replace("é", "e")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "sponsor"


def skriv_csv(r: Sasongsrapport, ut: Path) -> Path:
    ut.parent.mkdir(parents=True, exist_ok=True)
    with ut.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["klubb", "sasong", "hal", "sponsor", "kanal", "visningar", "klick", "uppskattning", "testdata"])
        for h in r.hal:
            for k in h.kanaler:
                w.writerow([r.klubb, r.sasong, h.hal, h.sponsor.get("name"), k.namn, k.visningar,
                            "" if k.klick is None else k.klick, "ja" if k.uppskattning else "nej",
                            "ja" if r.testdata else "nej"])
    return ut


def bygg_rapport(club_dir: str | Path, sasong: int, out_dir: str | Path, kalla: str | Path | None = None,
                 pdf: bool = True) -> tuple[Sasongsrapport, list[Path]]:
    """En sida per sponsor (PNG + PDF) och en sammanställning (CSV)."""
    from .render.sponsorrapport import sida_html

    club_dir, out = Path(club_dir), Path(out_dir)
    r = sammanstall(club_dir, sasong, kalla)
    filer = [skriv_csv(r, out / f"sammanstallning-{sasong}.csv")]
    if not r.hal:
        return r, filer
    from .render.export import to_pdf, to_png

    for h in r.hal:
        html = sida_html(r, h, club_dir)
        bas = out / f"hal-{h.hal:02d}-{_slug(h.sponsor.get('name', ''))}-{sasong}"
        filer.append(to_png(html, bas.with_suffix(".png"), 794, 1123))
        if pdf:
            filer.append(to_pdf(html, bas.with_suffix(".pdf"), 210, 297))
    return r, filer
