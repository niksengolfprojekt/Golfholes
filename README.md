# Golfholes

Från Lantmäteriets data till exakta hålbilder, avstånd, tee-vyer och hålsponsorskyltar för golfklubbar.

En datagrund per klubb – klubbens valda stil ovanpå (sex målade stilar). Allt mäts i SWEREF 99 TM (meter) och alla avstånd räknas längs spellinjen, så som golfare mäter.

## Flödet

1. **Underlag** – Lantmäteriets ortofoto + markhöjdmodell (Geotorget), klubbens scorekort och hålkartor.
2. **Vektorisera** – fairway, green, bunkrar, vatten, tees och spellinje per hål → `klubbar/<klubb>/hal-NN.yaml`.
3. **Räkna och kontrollera** – avstånd till hinder och green, längd mot scorekort (±3 %), kamera för tee-vyn.
4. **Klubben godkänner** varje hål.
5. **Rendera** hålbild i vald stil, tee-vy och flygfilm (rå film ur data med `flygfilm`, ytan byts sedan av AI).
6. **Mallar** – skylt 70 × 100 cm (tre plattor), digital banguide, tryckfiler.

Mer i [docs/flode.md](docs/flode.md).

## Kom igång

Installation på Mac: se [docs/mac.md](docs/mac.md).

```bash
python -m golfholes rapport klubbar/exempel-ekbacka/hal-07.yaml   # avstånd + kontroll
python -m golfholes halbild klubbar/exempel-ekbacka/hal-07.yaml   # hålbild
python -m golfholes stilprov klubbar/exempel-ekbacka            # de sex stilarna – klubben väljer en
python -m golfholes skylt   klubbar/exempel-ekbacka/hal-07.yaml   # skylt 70 × 100 cm i klubbens stil (--stil Gravyr för att prova)
python -m golfholes flygfilm klubbar/glasriket/hal-14.yaml --data data/glasriket   # rå flygfilm (MP4)
python -m golfholes webb    klubbar/exempel-ekbacka               # digital banguide
python -m pytest
```

Ritverktyget för att digitalisera hål från ortofoto: öppna `verktyg/ritverktyg.html` i webbläsaren.

## Stilar

Klubben väljer en stil i `klubb.yaml` med `stil:` och ett av namnen (Erics beslut 2026-10-22):

**Akvarell · Sommarakvarell · Gravyr · Mjuk 3D · Arkitektskiss · Papperssnitt**

Tabellen `STILAR` i `golfholes/stilar.py` har AI-prompt och stilprov per stil. AI:n byter bara ytan på hålets
eget fotounderlag; `aibild` kontrollerar att formen är kvar. Glasriket har sin egen fotostil (`stil: foto`).
Gamla `stil: 1–4` läses med en varning. De fyra kodritade ritmotorerna i `render/styles.py` är bara reserv
tills hålet är målat.

## Struktur

| Mapp | Innehåll |
| --- | --- |
| `golfholes/` | Koden: geometri, avstånd, kamera, kontroll, Lantmäteriet-utsnitt |
| `golfholes/render/` | Hålbild, skylt, webbsidor |
| `verktyg/` | Ritverktyget (öppnas i webbläsaren) |
| `klubbar/<klubb>/` | En mapp per klubb: `klubb.yaml` + ett `hal-NN.yaml` per hål |
| `klubbar/exempel-ekbacka/` | Påhittat exempelhål för demo och tester |
| `tests/` | Tester |
| `docs/` | Beskrivning av flödet |
| `data/` | Rådata från Lantmäteriet (läggs inte i git – för stora filer) |

## Attribution på färdigt material

> Underlag: Ortofoto och Markhöjdmodell ©Lantmäteriet, bearbetat, CC BY 4.0
