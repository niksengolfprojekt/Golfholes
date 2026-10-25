"""Kontroll av designregistret (hemsidor/designregister.yaml).

Varje sajt jämförs med alla sajter som står före den i registret. En sajt får inte ha
en förbjuden riktning, inte dela riktning eller toppbild med en tidigare sajt och måste
skilja sig på minst `minst_olika` av fälten i `jamfor`. Fält som inte är bedömda än
(`null` eller "ej-bedomd") hoppas över.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REGISTER = Path(__file__).resolve().parent.parent / "hemsidor" / "designregister.yaml"
OBEDOMD = (None, "", "ej-bedomd")
FARGAVSTAND = 60   # två huvudfärger närmare än så (RGB-avstånd) räknas som samma


def las(path: str | Path = REGISTER) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _falt(sajt: dict, namn: str):
    v = sajt
    for del_ in namn.split("."):
        v = v.get(del_) if isinstance(v, dict) else None
    return v


def _rgb(hexfarg: str) -> tuple[int, int, int]:
    h = hexfarg.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lika(namn: str, a, b) -> bool:
    if namn.startswith("palett") and isinstance(a, str) and isinstance(b, str) and a.startswith("#") and b.startswith("#"):
        return sum((x - y) ** 2 for x, y in zip(_rgb(a), _rgb(b))) ** 0.5 < FARGAVSTAND
    if isinstance(a, dict) and isinstance(b, dict):
        return sorted(map(str, a.values())) == sorted(map(str, b.values()))
    return str(a).strip().lower() == str(b).strip().lower()


def kontrollera(register: dict) -> tuple[list[str], list[str]]:
    """Returnerar (fel, varningar) som läsbara rader."""
    regler = register.get("regler", {})
    riktningar = register.get("riktningar", {})
    sajter = register.get("sajter", [])
    fel: list[str] = []
    varn: list[str] = []

    for i, s in enumerate(sajter):
        namn = s.get("namn", s.get("id"))
        r = s.get("riktning")
        if r in regler.get("forbjudna_riktningar", []):
            fel.append(f"{namn}: riktningen '{r}' är förbjuden ({riktningar.get(r, '')})")
        elif r not in OBEDOMD and r not in riktningar:
            fel.append(f"{namn}: okänd riktning '{r}' – lägg till den under `riktningar` först")
        if s.get("typ") == "klubb":
            if len(s.get("inventering") or []) < 8:
                varn.append(f"{namn}: inventeringen har {len(s.get('inventering') or [])} punkter, minst 8 behövs")
            for f in ("ide", "designfil"):
                if s.get(f) in OBEDOMD:
                    varn.append(f"{namn}: `{f}` saknas")

        for tidigare in sajter[:i]:
            tnamn = tidigare.get("namn", tidigare.get("id"))
            for f in regler.get("maste_skilja", []):
                a, b = _falt(s, f), _falt(tidigare, f)
                if a not in OBEDOMD and b not in OBEDOMD and _lika(f, a, b):
                    fel.append(f"{namn}: samma {f} som {tnamn} ('{a}')")
            jamforbara = olika = 0
            for f in regler.get("jamfor", []):
                a, b = _falt(s, f), _falt(tidigare, f)
                if a in OBEDOMD or b in OBEDOMD:
                    continue
                jamforbara += 1
                olika += not _lika(f, a, b)
            krav = regler.get("minst_olika", 0)
            if jamforbara >= krav and olika < krav:
                fel.append(f"{namn}: skiljer sig bara på {olika} av {jamforbara} punkter från {tnamn}, minst {krav} krävs")
    return fel, varn


def rapport(path: str | Path = REGISTER) -> int:
    reg = las(path)
    fel, varn = kontrollera(reg)
    print(f"Designregister: {len(reg.get('sajter', []))} sajter")
    for s in reg.get("sajter", []):
        print(f"  {s.get('namn')}: riktning {s.get('riktning')}, toppbild {s.get('toppbild')}, status {s.get('status')}")
    for rad in fel:
        print("FEL      " + rad)
    for rad in varn:
        print("VARNING  " + rad)
    print("Inga fel." if not fel else f"{len(fel)} fel – sajten är inte unik nog än.")
    return 1 if fel else 0
