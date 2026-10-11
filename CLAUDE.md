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
- En datagrund per klubb, fyra stilar: 1 Signatur (foto ovanifrån), 2 Klassisk (akvarell), 3 Arv (gravyr), 4 Nordisk (mjuk 3D-illustration). Klubben väljer med `stil: 1–4` i `klubb.yaml`; koden i `golfholes/render/styles.py` (hålbild) och `sign.py` (`THEMES`, skylt).
- Tee-vy: kamera på tee, 1,6 m höjd, sikte 150 m ut längs mittlinjen (par 3: mot green). Flygfilm: 5 m höjd längs hålet, avslutas i hålbild ovanifrån med sponsorlogga.
- Skylt 70 × 100 cm, tre plattor: rubrik ("[Sponsor]-hålet"), hålguide (byts aldrig), sponsorplatta med logga i en färg + QR-kod. Tillverkas av Ecosign.
- Pilotklubb: Glasrikets GK, hål 3.

- Hålbilder i målad stil: exakta masker från hålfilen + texturkit i `assets/texturer/<stil>/` (`golfholes/render/texture.py`). AI/skisser får bara leverera texturer, aldrig former.

## Miljö
- Molnmiljön saknar ofta paketindex: kärnkoden använder bara standardbiblioteket, PyYAML och Pillow (+ numpy för texturrenderingen, med vektorstil som reserv). Tyngre bibliotek (rasterio, shapely, Blender) körs på ägarens Mac Pro.
- Kör `python -m golfholes rapport <fil>` och testerna efter varje ändring.
- I molnet saknas pytest: kör testfunktionerna direkt med python om pytest inte finns.
- QR-koden är en tydlig platshållare om `segno` saknas – trycks aldrig så.
- Status och nästa steg: `docs/flode.md`. Uppdatera den när något blir klart.
