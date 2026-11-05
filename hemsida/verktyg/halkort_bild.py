"""Ritar hålkortet för det påhittade hål 7 (startsidan och Hålsponsorer) och lägger det på
klubbhusskärmen. Ingen riktig klubb: allt kommer från den påhittade banan.

Kör:  python hemsida/verktyg/halkort_bild.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROT = Path(__file__).resolve().parents[2]
IMG = ROT / "hemsida" / "public" / "img"
TYP = ROT / "assets" / "typsnitt"
INTER = Path("/mnt/project-files/tacada/grafisk-profil/kalla")
ELFENBEN, TALLGRON, MORKBRONS, KOL, DAMPAD, LINJE = "#F7F1E6", "#183329", "#7F6640", "#292D28", "#5C5F57", "#D8CDB9"


def typ(namn, storlek):
    for p in (TYP / namn, INTER / namn):
        if p.exists():
            return ImageFont.truetype(str(p), storlek)
    return ImageFont.load_default()


def kort(B=1600, H=1000):
    k = Image.new("RGB", (B, H), ELFENBEN)
    d = ImageDraw.Draw(k)
    hal = Image.open(IMG / "hal" / "hal-07.webp").convert("RGBA")
    hh = int(H * .9); hal = hal.resize((round(hal.width * hh / hal.height), hh), Image.LANCZOS)
    k.paste(hal, (int(B * .2) - hal.width // 2, (H - hh) // 2), hal)
    x = int(B * .42)
    d.text((x, H * .08), "TACADA · HÅLGUIDE", font=typ("Inter-600.ttf", 20), fill=MORKBRONS)
    d.text((x - 6, H * .13), "7", font=typ("Marcellus-Regular.ttf", 230), fill=TALLGRON)
    d.text((x, H * .42), "PAR 4 · INDEX 5", font=typ("Inter-600.ttf", 26), fill=MORKBRONS)
    y = H * .5
    for farg, tee, m in (("#EEE9DF", "Vit", "372 m"), ("#E1C34A", "Gul", "341 m"), ("#2F5FA7", "Blå", "298 m")):
        d.ellipse((x, y + 6, x + 22, y + 28), fill=farg, outline="#999")
        d.text((x + 36, y), tee, font=typ("Inter-500.ttf", 26), fill=KOL)
        d.text((x + 200, y), m, font=typ("Inter-600.ttf", 26), fill=KOL)
        y += 44
    d.line((x, y + 14, B * .92, y + 14), fill=LINJE, width=2)
    d.text((x, y + 36), "PRO:NS RÅD", font=typ("Inter-600.ttf", 20), fill=MORKBRONS)
    rad = ["Rakt och smalt mellan tallarna. Sikta mot",
           "vänsterkanten av fairway, bollen rullar in",
           "mot mitten. Bunkern till höger tar alla",
           "utslag som drar iväg."]
    for i, r in enumerate(rad):
        d.text((x, y + 72 + i * 38), r, font=typ("Inter-400.ttf", 26), fill=DAMPAD)
    return k


def main():
    k = kort()
    k.resize((1200, 750), Image.LANCZOS).save(IMG / "exempel-halkort.webp", quality=88)
    # Klubbhusskärmen: kortet in i tv-rutan (rak bild, rutan är nästan rektangulär).
    rum = Image.open(IMG / "klubbhus-skarm.webp").convert("RGB")
    x0, y0, x1, y1 = 475, 223, 726, 365
    rum.paste(k.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
    rum.save(IMG / "klubbhus-skarm.webp", quality=86)


if __name__ == "__main__":
    main()
