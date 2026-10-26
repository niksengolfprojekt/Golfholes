# Instruktioner för Claude i det här repot

## Vad projektet är
Grafiska hålpresentationer och hålsponsorskyltar för svenska golfklubbar. Ägarna är säljare och designer, inte utvecklare: de kontrollerar resultat och säljer. Claude skriver och underhåller koden. Förklara alltid på svenska, i vanliga ord.

## Grundregler
- **Aldrig påhittad geometri.** Allt i en riktig klubbs `hal-NN.yaml` kommer från Lantmäteriets ortofoto/höjdmodell, klubbens egna uppgifter eller GPS-mätning. AI-bilder får bara användas för stil, aldrig för var saker ligger.
- Koordinatsystem: SWEREF 99 TM (EPSG:3006), meter. Avstånd längs `centerline`, från vald tee.
- Längdkontroll mot scorekortet ska vara inom ±3 % innan ett hål går vidare.
- Varje hål godkänns av klubben innan leverans.
- Rådata (GeoTIFF m.m.) läggs under `data/` och checkas inte in.
- Attribution på allt färdigt material: "Underlag: Ortofoto och Markhöjdmodell ©Lantmäteriet, bearbetat, CC BY 4.0".
- Påhittade klubbar och sponsorer (t.ex. "Ekbacka Golfklubb", "Nordvik") används i demo; riktiga sponsorers loggor bara med tillstånd.

## Produktbeslut (2026-10-11)
- En datagrund per klubb. Klubbens hålbildsstil anges i `klubb.yaml` som `stil:` med ett av de sex namnen nedan (t.ex. `stil: Gravyr`); tabellen `STILAR` i `golfholes/stilar.py` har AI-prompt och stilprov per stil. Glasriket har `stil: foto` (standardprompten). Gamla `stil: 1–4` läses med varning. De kodritade ritmotorerna i `golfholes/render/styles.py` och `sign.py` (`THEMES`) är bara reserv tills hålet är målat.
- Tee-vy: kamera på tee, 1,6 m höjd, sikte 150 m ut längs mittlinjen (par 3: mot green). Flygfilm: 5 m höjd längs hålet, avslutas i hålbild ovanifrån med sponsorlogga. Rå film ur data: `python -m golfholes flygfilm <hålfil>` (`golfholes/render/flygfilm.py`); AI byter sedan bara yta (video-till-video).
- Skylt 70 × 100 cm, tre plattor: rubrik ("[Sponsor]-hålet"), hålguide (byts aldrig), sponsorplatta med logga i en färg + QR-kod. Tillverkas av Ecosign.
- Pilotklubb: Glasrikets GK, hål 3.

- Stilmenyn på hemsidan (beslut 2026-10-22): klubben väljer stil innan vi gör deras hål bland sex AI-målade stilar: Akvarell, Sommarakvarell, Gravyr, Mjuk 3D, Arkitektskiss, Papperssnitt (prov: `klubbar/glasriket/typbilder/stilar/`). Bort: Blå gravyr, Platt grafisk, Screentryck, Foto höst, Vinterskymning och kodens fyra (Signatur, Klassisk, Arv, Nordisk). Inkopplat i koden 2026-10-23 (`stilprov`, `aiprompt`, `aiunderlag`, `aibild`, `halkort`, `webb` följer klubbens stil).
- Hålbilder i målad stil: exakta masker från hålfilen + texturkit i `assets/texturer/<stil>/` (`golfholes/render/texture.py`). AI/skisser får bara leverera texturer, aldrig former.

## Miljö
- Molnmiljön saknar ofta paketindex: kärnkoden använder bara standardbiblioteket, PyYAML och Pillow (+ numpy för texturrenderingen, med vektorstil som reserv). Tyngre bibliotek (rasterio, shapely, Blender) körs på ägarens Mac Pro.
- Kör `python -m golfholes rapport <fil>` och testerna efter varje ändring.
- I molnet saknas pytest: kör testfunktionerna direkt med python om pytest inte finns.
- QR-koden är en tydlig platshållare om `segno` saknas – trycks aldrig så.
- Status och nästa steg: `docs/flode.md`. Uppdatera den när något blir klart.
