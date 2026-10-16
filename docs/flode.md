# Produktionsflödet steg för steg

| Steg | Vad | Kommando / verktyg | Klart när |
| --- | --- | --- | --- |
| 1. Underlag | Ladda ner ortofoto + markhöjdmodell för området i `klubb.yaml` från Geotorget till `data/<klubb>/orto/` och `data/<klubb>/hojd/`. Hämta scorekort och hålkartor. | Geotorget (ni loggar in) | Filerna ligger på plats |
| 2. Utsnitt | Klipp ut banan ur ortofotot. | `python -m golfholes utsnitt klubbar/<klubb> data/<klubb>/orto/*.tif` | `data/<klubb>/utsnitt/orto.jpg` + `.jgw` |
| 3. Digitalisera | Öppna `verktyg/ritverktyg.html` i webbläsaren, ladda bilden + .jgw, klicka ut tees, spellinje, green, fairway, bunkrar, vatten, skog. Kontrollrutan visar längd mot scorekort direkt. | Ritverktyget | `hal-NN.yaml` sparad i `klubbar/<klubb>/` |
| 4. Kontrollera | Avstånd, längd mot scorekort (±3 %), kamera för tee-vy. | `python -m golfholes rapport klubbar/<klubb>/hal-NN.yaml` | Alla tees "ok" |
| 5. "Så spelar du hålet" | Skriv Säkert/Chansa i hålfilen utifrån avstånden. Granskas av en golfare. | Text i `strategy:` | Granskad |
| 5b. Stilval | Klubben ser samma hål i alla fyra stilar och väljer 1–4. Valet skrivs in som `stil:` i `klubb.yaml`. | `python -m golfholes stilprov klubbar/<klubb>/hal-NN.yaml` | `stil:` satt |
| 5c. Layoutval | Klubben ser samma hål i alla layouter och väljer. Valet skrivs in som `layout:` i `klubb.yaml` (en siffra eller en lista). Texterna per hål ligger i `klubbar/<klubb>/halkort/hal-NN.yaml`; mallen säger till om en text är för lång. | `python -m golfholes layoutprov klubbar/<klubb>/halkort/hal-NN.yaml` | `layout:` satt |
| 6. Klubbkontroll | Skicka hålbild + avstånd till klubben. | `python -m golfholes halbild …` | Skriftligt godkänt |
| 7. Skylt | Förhandsvisning + tryck-PDF per platta till Ecosign. | `python -m golfholes skylt …` | Malin har granskat, QR-kod äkta |
| 8. Webb | Digital banguide, sidan QR-koden pekar på. | `python -m golfholes webb klubbar/<klubb>` | Publicerad på klubbens/vår domän |
| 9. Film | Tee-vy och flygfilm i 3D. | (kommer – Blender på Mac Pro) | Filmer per tee och hål |

## Status
- [x] Geometri, avstånd, tee-kamera, längdkontroll
- [x] Grafisk hålbild från vektorer (grund för stilen Nordisk)
- [x] Fyra stilar att välja 1–4 (Signatur, Klassisk, Arv, Nordisk) – hålbild, greenförstoring och hel skylt i varje stil, plus `stilprov` som visar alla fyra sida vid sida
- [x] Skylt 70 × 100 cm, tre plattor, förhandsvisning + tryck-PDF per platta
- [x] Digital banguide: sida per hål med sponsor, tee-val och filmplats
- [x] Ritverktyg för att digitalisera hål från ortofoto (testat end-to-end på syntetiskt ortofoto)
- [x] Utsnitt ur Lantmäteriets GeoTIFF (testat på syntetiska rutor)
- [x] Hålkort som fasta mallar: 1 Hålkort (spikad 2026-10-16), 2 Poster, 3 Mörk, 4 Skärm 16:9, 5 Banguide, 6 Sponsorhål. Samma mall för varje hål, maxlängd per textfält, `halkort` och `layoutprov`
- [x] Glasriket hål 14 och hål 3 som typbilder i mallen (AI-bild, inte exakt form – byts mot ortofoto)
- [ ] Hålkort från riktig hålbild: koppla `halbild` (ortofoto + masker) som bild i hålkortet, med avståndsmarkeringar ur hålfilen
- [ ] Tryck-PDF av hålkorten (mått bestäms när klubben valt format)
- [ ] Riktig QR-kod (kräver `segno`, installeras på Macen)
- [ ] Testa på Glasriket hål 3 med riktigt ortofoto (väntar på Geotorget)
- [ ] Höjddata i rapporten (uppför/nedför) – `Elevation` finns, kopplas in när vi har filerna
- [ ] Signatur med riktigt ortofoto (koden är klar, väntar på Geotorget – visar platshållare tills dess)
- [x] Texturrendering: Klassisk och Nordisk ritas med texturkit (gräs, vatten, lövverk, penseldrag) klippta efter exakta masker – demo-kit utklippt ur AI-skisserna
- [ ] Högupplösta texturkit för tryck (genereras som rena texturer, inte hela hål) + kit för Arv och Signatur-ljussättning
- [ ] Ritverktyget: fler lager som skisserna visar – gångvägar, broar, solitärträd, ruffkant
- [ ] Malin granskar de fyra stilarna (typsnitt, färger, ornament) – akvarell och gravyr är kodritade och mindre måleriska än AI-skisserna
- [ ] Webbsidorna i klubbens stil (använder ännu Nordisk)
- [ ] Klubbmärke (SVG) från klubben till rubriken i stil 1
- [ ] Tee-vy och flygfilm (3D, Mac Pro)
- [ ] Ecosigns tryckspecifikation in i `SignSpec` (mått, utfall, PDF/X)
