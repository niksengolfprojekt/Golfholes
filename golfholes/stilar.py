"""Klubbens hålbildsstil – de sex AI-målade stilarna i stilmenyn (Eric 2026-10-22).

Klubben väljer en stil innan vi gör deras hål och skriver den i `klubb.yaml`:

    stil: Akvarell        # eller Sommarakvarell, Gravyr, Mjuk 3D, Arkitektskiss, Papperssnitt

Alla stilar målas på samma sätt: koden gör fotounderlaget ur Lantmäteriets ortofoto
(`aiunderlag`), AI:n byter BARA ytan med stilens prompt nedan, och `aibild` lägger
målningen på hålets exakta form och kontrollerar formpoängen. Promptarna bygger på
standardprompten i docs/halproduktion.md: samma "keep every edge"-regler, bara ytan
skiljer. Stilprovet (bildfilen) visar klubben hur stilen ser ut – det ges ALDRIG till
AI:n som referens (då ritar den om hålet efter provets hål).

`foto` är Glasrikets egen stil (standardprompten, retuscherat flygfoto). Den finns kvar
för pilotklubben men är inte med i menyn för nya klubbar.

De gamla kodritade stilarna 1–4 (Signatur, Klassisk, Arv, Nordisk) är inte längre ett
val. En gammal siffra i klubb.yaml läses fortfarande, med en varning, och översätts till
närmaste nya stil.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROVMAPP = ROOT / "klubbar" / "glasriket" / "typbilder" / "stilar"

# Gemensamma regler – ordagrant samma krav som standardprompten i docs/halproduktion.md.
_START = ("Edit this image. This is a surface repaint of a real aerial photograph of a golf hole, not a redraw. "
          "Keep the image at exactly the same framing, scale and position: every pixel of every edge must stay "
          "where it is. ")
_REGLER = (" Keep the tonal order: fairway lightest, rough a step darker, woodland darkest, so the hole reads at a "
           "glance. Do not straighten, smooth, enlarge or reshape any fairway, green, bunker, shoreline, path or "
           "tree group. Do not add or remove anything: no new bunkers, ponds, paths, buildings or trees. No people, "
           "no text, no flags, no markers. Keep the cream background and its soft edge exactly as they are.")

# Standardprompten (Glasrikets fotostil) – kopia av docs/halproduktion.md, ändras bara där.
FOTO_PROMPT = (
    "Edit this image. This is a light retouching job on a real aerial photograph, not a redraw. Keep the image at "
    "exactly the same framing, scale and position: every pixel of every edge must stay where it is. Only improve the "
    "surfaces: make the grass a fresh, even late-summer green with subtle mowing stripes on the fairway and a smooth "
    "putting green, give any water a clean deep blue with soft reflections, make the tree crowns crisp and natural "
    "with gentle shadows (keep the golden autumn birches golden), clean up the sand in the bunkers and the gravel "
    "paths. Remove the hazy yellow cast so colours are clear and sunny. Do not straighten, smooth, enlarge or reshape "
    "any fairway, green, bunker, shoreline, path or tree group. Do not add or remove anything. No text, no flags, no "
    "markers. Keep the cream background and its soft edge exactly as they are.")


@dataclass(frozen=True)
class Stil:
    nyckel: str        # filnamn och kommandorad, t.ex. "mjuk-3d"
    namn: str          # som på hemsidan, t.ex. "Mjuk 3D"
    yta: str           # vad AI:n gör med ytan (engelska, går in i prompten)
    prov: str          # stilprovets bildfil (relativt repot)
    ritmotor: int      # kodritad reserv för skylt/halbild tills målningen finns: 1 foto, 2 akvarell, 3 gravyr, 4 platt
    i_menyn: bool = True

    @property
    def prompt(self) -> str:
        if self.nyckel == "foto":
            return FOTO_PROMPT
        return _START + "Only change the surfaces into " + self.yta + _REGLER

    @property
    def provbild(self) -> Path:
        return ROOT / self.prov


STILAR: dict[str, Stil] = {s.nyckel: s for s in (
    Stil("akvarell", "Akvarell",
         "a fine hand-painted watercolour illustration: soft transparent washes on warm cream paper, pale "
         "sage-green fairway with faint mowing stripes, a smooth slightly brighter green, golden-yellow autumn "
         "birches and darker conifers painted as loose round dabs with gentle wet edges, warm pale sand in the "
         "bunkers, any water a calm blue-grey wash.",
         "klubbar/glasriket/typbilder/stilar/hal-14-1-akvarell.webp", 2),
    Stil("sommarakvarell", "Sommarakvarell",
         "a bright summer watercolour illustration: fresh lime and spring-green washes on cream paper, a luminous "
         "yellow-green fairway with soft mowing stripes, a vivid smooth green, lush summer foliage in layered greens "
         "with cool blue-green shadows, clean white-cream sand in the bunkers, any water a clear summer blue.",
         "klubbar/glasriket/typbilder/stilar/hal-14-8-sommarakvarell.webp", 2),
    Stil("gravyr", "Gravyr",
         "a classic copperplate engraving printed in warm sepia ink on aged parchment: fine parallel hatching for "
         "the mowing stripes, stippled and cross-hatched tree crowns with crisp ink outlines, the green in fine "
         "concentric line work, bunkers left pale with dotted sand, any water in horizontal engraved lines. "
         "Monochrome sepia only.",
         "klubbar/glasriket/typbilder/stilar/hal-14-2-gravyr.webp", 3),
    Stil("mjuk-3d", "Mjuk 3D",
         "a soft 3D illustration like a polished clay miniature model seen from above: smooth matte surfaces, a "
         "rich green fairway with clean broad mowing stripes, a soft rounded green, trees as rounded puffy clay "
         "crowns in warm amber, orange and deep green with soft ambient-occlusion shadows, bunkers as smooth pale "
         "sand hollows, any water a smooth glossy teal.",
         "klubbar/glasriket/typbilder/stilar/hal-14-3-mjuk-3d.webp", 4),
    Stil("arkitektskiss", "Arkitektskiss",
         "an architect's presentation sketch: fine black ink lines over light pencil on white-cream paper, with "
         "pale watercolour wash only as a hint: a very pale green fairway with ruled mowing lines, tree crowns "
         "drawn as loose scalloped ink outlines with a pale yellow-green wash, bunkers outlined in ink with pale "
         "sand, any water in pale blue wash. Mostly paper white, airy and precise.",
         "klubbar/glasriket/typbilder/stilar/hal-14-5-skiss.webp", 3),
    Stil("papperssnitt", "Papperssnitt",
         "a layered cut-paper artwork: flat sheets of matte coloured paper stacked with soft drop shadows between "
         "the layers, a light sage fairway layer with subtle stripes, a slightly lighter green layer, woodland as "
         "deep forest-green paper with clean cut edges and small round cut-out tree crowns, bunkers as cream paper "
         "cut-outs, any water as a smooth blue-grey paper layer.",
         "klubbar/glasriket/typbilder/stilar/hal-14-10-papperssnitt.webp", 4),
    Stil("foto", "Foto (Glasriket)", "", "klubbar/glasriket/halbilder/hal-14-malad.webp", 1, i_menyn=False),
)}

MENY = [s for s in STILAR.values() if s.i_menyn]
STANDARD = "foto"   # klubb utan `stil:` = pilotklubbens fotostil, tills klubben valt

# Gamla siffror (före 2026-10-22) → närmaste nya stil.
GAMLA = {1: "foto", 2: "akvarell", 3: "gravyr", 4: "mjuk-3d"}
_GAMLA_NAMN = {"signatur": 1, "klassisk": 2, "arv": 3, "nordisk": 4}


def _nyckel(text: str) -> str:
    return text.strip().lower().replace(" ", "-").replace("_", "-")


def las_stil(value, varna: bool = True) -> Stil:
    """Klubbens `stil:`: ett av de sex namnen (stora/små bokstäver spelar ingen roll).
    Gamla 1–4 eller Signatur/Klassisk/Arv/Nordisk läses med en varning."""
    if value is None or str(value).strip() == "":
        return STILAR[STANDARD]
    text = str(value)
    gammal = None
    if text.strip().isdigit():
        gammal = int(text)
    elif _nyckel(text) in _GAMLA_NAMN:
        gammal = _GAMLA_NAMN[_nyckel(text)]
    if gammal is not None:
        if gammal not in GAMLA:
            raise ValueError(f"Okänd stil {value!r}. Välj en av: " + ", ".join(s.namn for s in MENY))
        ny = STILAR[GAMLA[gammal]]
        if varna:
            print(f"VARNING: `stil: {value}` är den gamla kodstilen (1–4, borttagen 2026-10-22). Läses som "
                  f"\"{ny.namn}\". Skriv ett av de sex namnen i klubb.yaml: " + ", ".join(s.namn for s in MENY),
                  file=sys.stderr)
        return ny
    k = _nyckel(text)
    for s in STILAR.values():
        if k in (s.nyckel, _nyckel(s.namn)):
            return s
    raise ValueError(f"Okänd stil {value!r}. Välj en av: " + ", ".join(s.namn for s in MENY))


def klubbens_stil(club_dir: str | Path, stil: str | None = None) -> Stil:
    """`stil` (kommandoraden) går före klubbens val i klubb.yaml."""
    if stil is not None:
        return las_stil(stil)
    f = Path(club_dir) / "klubb.yaml"
    club = yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}
    return las_stil((club or {}).get("stil", (club or {}).get("style")))


def malad_bild(club_dir: str | Path, nummer: int, stil: Stil) -> Path:
    """Den målade hålbilden i stilen. Fotostilen behåller sitt gamla namn (hal-NN-malad.webp)."""
    namn = f"hal-{nummer:02d}-malad.webp" if stil.nyckel == "foto" else f"hal-{nummer:02d}-malad-{stil.nyckel}.webp"
    return Path(club_dir) / "halbilder" / namn


def stilprov(out_dir: str | Path, hojd_px: int = 900) -> dict:
    """De sex stilarna sida vid sida, alla i SAMMA storlek, med namn – det klubben väljer från.
    Plus stilar.md med AI-prompten per stil (internt, aldrig till klubben)."""
    from PIL import Image, ImageDraw, ImageFont

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    bilder = []
    for s in MENY:
        im = Image.open(s.provbild).convert("RGBA")
        bilder.append((s, im.resize((round(im.width * hojd_px / im.height), hojd_px), Image.LANCZOS)))
    bredd = max(im.width for _, im in bilder)
    pad, text = 40, 70
    blad = Image.new("RGB", (pad + len(bilder) * (bredd + pad), hojd_px + text + 2 * pad), "#f4f1e8")
    d = ImageDraw.Draw(blad)
    fontfil = ROOT / "assets" / "typsnitt" / "HankenGrotesk-SemiBold.ttf"
    try:
        font = ImageFont.truetype(str(fontfil), 30) if fontfil.exists() else ImageFont.load_default(30)
    except OSError:
        font = ImageFont.load_default()
    filer = {}
    for i, (s, im) in enumerate(bilder):
        x = pad + i * (bredd + pad)
        bak = Image.new("RGBA", im.size, (244, 241, 232, 255))
        blad.paste(Image.alpha_composite(bak, im).convert("RGB"), (x + (bredd - im.width) // 2, pad))
        d.text((x + bredd / 2, pad + hojd_px + text / 2), s.namn, fill="#2b2a27", font=font, anchor="mm")
        filer[s.namn] = s.provbild
    alla = out / "alla-sex-stilar.jpg"
    blad.save(alla, quality=90)
    md = ["# Stilmenyn – AI-prompt per stil (internt)", "",
          "Stilprovet visar klubben stilen. AI:n får bara hålets eget underlag (`aiunderlag`) och prompten nedan,",
          "aldrig stilprovet. Formpoängen från `aibild` ska vara minst 0,7.", ""]
    for s in MENY:
        md += [f"## {s.namn} (`stil: {s.namn}`)", "", f"Stilprov: `{s.prov}`", "", s.prompt, ""]
    (out / "stilar.md").write_text("\n".join(md), encoding="utf-8")
    return {"alla": alla, "promptar": out / "stilar.md", **filer}
