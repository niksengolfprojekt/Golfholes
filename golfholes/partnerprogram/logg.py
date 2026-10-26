"""Partneröversikten: klubbens enda lista över partners, säljkontakter, leveranser och mätvärden (xlsx).

  skapa(prog, fil)  → en tom översikt med alla platser ifyllda (hål, range, putting ...)
  las(fil)          → {"status": {plats: status}, "partners": {plats: {...}}, "rapport": {plats: data}}

Årsrapporten (golfholes.render.partner_dok.rapport) läser bara det som står här. Uppmätt, uppskattat och
levererat hålls isär hela vägen, och en tom cell blir "fylls i" i rapporten, aldrig en gissning.
"""
from __future__ import annotations

from pathlib import Path

from . import Program

PARTNERS = ["Plats", "Namn", "Pris (kr)", "Status", "Företag", "Kontaktperson", "Telefon", "E-post",
            "Avtal från", "Avtal till", "Partnervecka", "Nästa steg", "Datum nästa steg"]
KONTAKTER = ["Datum", "Företag", "Kontaktperson", "Produkt / hål", "Status", "Nästa steg", "Datum nästa steg", "Anteckning"]
LEVERANSER = ["Plats", "Vad", "Datum", "Foto (filnamn)", "Gjort av"]
MATVARDEN = ["Plats", "Vad", "Värde", "Typ", "Källa", "Period"]
RONDER = ["Månad", "Ronder", "Källa"]
TYPER = {"uppmätt": "matt", "uppskattat": "uppskattat", "uppskattning": "uppskattat"}
STATUS = ["ledig", "reserverad", "såld"]
KONTAKTSTATUS = ["kontaktad", "möte bokat", "förslag skickat", "reserverad", "avtal", "nej"]

INSTRUKTION = [
    "Partneröversikten är klubbens enda lista över partnerprogrammet. Skriv in allt samma dag.",
    "",
    "Partners: en rad per plats (hål, range, puttinggreen ...). Status är ledig, reserverad eller såld.",
    "  Reserverad = muntligt ja utan påskrivet avtal. Hålls högst 14 dagar.",
    "Kontakter: varje samtal, mejl och möte, också de som sa nej. Ett intresse utan datum är inget intresse.",
    "Leveranser: det klubben och TACADA har gjort för partnern, med datum (skylt uppe, hålsida publicerad ...).",
    "Mätvärden: siffror till årsrapporten. Typ är uppmätt (statistik från hemsidan, QR-koden eller Meta)",
    "  eller uppskattat (räknat ur ronder). Skriv alltid källan. Visningar är antal visningar, inte personer.",
    "Ronder: klubbens ronder per månad ur bokningssystemet. Används för uppskattningen vid skylten.",
    "",
    "Tom cell betyder att värdet saknas. Rapporten skriver då att det fylls i, den hittar aldrig på en siffra.",
]


def platser(prog: Program) -> list[tuple[str, str, int | None]]:
    """(plats-id, namn, pris) för allt som bara kan säljas en gång."""
    ut = [(f"hal-{h.nr:02d}", f"Hål {h.nr}" + (" (premium)" if h.premium else ""), h.pris) for h in prog.hal]
    for p in prog.aktiva():
        if p["niva"] != "hal" and p.get("max") == 1:
            ut.append((p["id"], p["namn"], p.get("pris")))
    return ut


def skapa(prog: Program, fil: Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    rubrik = Font(bold=True, color="FFFFFF")
    fyll = PatternFill("solid", fgColor=prog.klubb.farger.get("djup", "#10202E").lstrip("#")[:6])

    def blad(namn, kolumner, bredd=18):
        ws = wb.create_sheet(namn)
        ws.append(kolumner)
        for i, c in enumerate(ws[1], 1):
            c.font, c.fill = rubrik, fyll
            ws.column_dimensions[c.column_letter].width = bredd if i > 1 else 14
        ws.freeze_panes = "A2"
        return ws

    ins = wb.active
    ins.title = "Instruktion"
    ins.column_dimensions["A"].width = 110
    ins.append([f"{prog.klubb.namn} · partneröversikt {prog.sasong}"])
    ins["A1"].font = Font(bold=True, size=14)
    for rad in INSTRUKTION:
        ins.append([rad])

    ws = blad("Partners", PARTNERS)
    for pid, namn, pris in platser(prog):
        st = prog.klubb.status(int(pid[4:])) if pid.startswith("hal-") else (prog.cfg.get("status") or {}).get(pid, "ledig")
        ws.append([pid, namn, pris, {"bokad": "reserverad"}.get(st, st)] + [None] * (len(PARTNERS) - 4))
    dv = DataValidation(type="list", formula1='"' + ",".join(STATUS) + '"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add(f"D2:D{ws.max_row}")

    kt = blad("Kontakter", KONTAKTER)
    dv2 = DataValidation(type="list", formula1='"' + ",".join(KONTAKTSTATUS) + '"', allow_blank=True)
    kt.add_data_validation(dv2)
    dv2.add("E2:E1000")

    lev = blad("Leveranser", LEVERANSER, 28)
    for pid, _, _ in platser(prog)[:1]:
        lev.append([pid, "Exempel: sponsorplattan uppsatt (radera raden)", None, None, None])

    mv = blad("Mätvärden", MATVARDEN, 24)
    dv3 = DataValidation(type="list", formula1='"uppmätt,uppskattat"', allow_blank=False)
    mv.add_data_validation(dv3)
    dv3.add("D2:D2000")

    ro = blad("Ronder", RONDER)
    for m in ("april", "maj", "juni", "juli", "augusti", "september", "oktober"):
        ro.append([m, None, "bokningssystemet"])

    fil = Path(fil)
    fil.parent.mkdir(parents=True, exist_ok=True)
    wb.save(fil)
    return fil


def _rader(ws, kolumner):
    for rad in ws.iter_rows(min_row=2, values_only=True):
        if not any(v not in (None, "") for v in rad):
            continue
        yield dict(zip(kolumner, rad))


def las(fil: Path) -> dict:
    from openpyxl import load_workbook

    wb = load_workbook(fil, data_only=True)
    status, partners, rapport = {}, {}, {}
    for r in _rader(wb["Partners"], PARTNERS):
        pid = str(r["Plats"])
        st = (r["Status"] or "ledig").strip().lower()
        if st not in STATUS:
            raise SystemExit(f"{fil}: Partners, {pid}: okänd status {st!r} (skriv {', '.join(STATUS)})")
        status[pid] = {"reserverad": "bokad"}.get(st, st)
        if r["Företag"]:
            partners[pid] = {"foretag": r["Företag"], "kontakt": r["Kontaktperson"] or "",
                             "avtal_till": _datum(r["Avtal till"]), "vecka": r["Partnervecka"],
                             "nasta": r["Nästa steg"] or ""}
    for r in _rader(wb["Leveranser"], LEVERANSER):
        if str(r["Vad"] or "").startswith("Exempel:"):
            continue
        d = rapport.setdefault(str(r["Plats"]), {"matt": [], "uppskattat": [], "levererat": [], "foton": []})
        d["levererat"].append({"vad": r["Vad"], "varde": _datum(r["Datum"]), "kalla": r["Gjort av"] or ""})
        if r["Foto (filnamn)"]:
            d["foton"].append({"text": r["Vad"], "fil": r["Foto (filnamn)"]})
    for r in _rader(wb["Mätvärden"], MATVARDEN):
        typ = TYPER.get(str(r["Typ"] or "").strip().lower())
        if not typ:
            raise SystemExit(f"{fil}: Mätvärden, {r['Plats']}: Typ måste vara uppmätt eller uppskattat")
        if not r["Källa"]:
            raise SystemExit(f"{fil}: Mätvärden, {r['Plats']} {r['Vad']!r}: källa saknas")
        d = rapport.setdefault(str(r["Plats"]), {"matt": [], "uppskattat": [], "levererat": [], "foton": []})
        kalla = r["Källa"] + (f", {r['Period']}" if r["Period"] else "")
        d[typ].append({"vad": r["Vad"], "varde": _tal(r["Värde"]), "kalla": kalla})
    ronder = [r for r in _rader(wb["Ronder"], RONDER) if r["Ronder"] not in (None, "")]
    return {"status": status, "partners": partners, "rapport": rapport,
            "ronder": sum(int(r["Ronder"]) for r in ronder) if ronder else None}


def _datum(v):
    return v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else (v or "")


def _tal(v):
    if isinstance(v, (int, float)):
        return f"{v:,.0f}".replace(",", " ")
    return v
