# Produktionsflödet steg för steg

| Steg | Vad | Kommando / verktyg | Klart när |
| --- | --- | --- | --- |
| 1. Underlag | Ladda ner ortofoto + markhöjdmodell för området i `klubb.yaml` från Geotorget till `data/<klubb>/orto/` och `data/<klubb>/hojd/`. Hämta scorekort och hålkartor. | Geotorget (ni loggar in) | Filerna ligger på plats |
| 2. Utsnitt | Klipp ut banan ur ortofotot. | `python -m golfholes utsnitt klubbar/<klubb> data/<klubb>/orto/*.tif` | `data/<klubb>/utsnitt/orto.jpg` + `.jgw` |
| 3. Digitalisera | Öppna `verktyg/ritverktyg.html` i webbläsaren, ladda bilden + .jgw, klicka ut tees, spellinje, green, fairway, bunkrar, vatten, skog. Kontrollrutan visar längd mot scorekort direkt. | Ritverktyget | `hal-NN.yaml` sparad i `klubbar/<klubb>/` |
| 4. Kontrollera | Avstånd, längd mot scorekort (±3 %), kamera för tee-vy. | `python -m golfholes rapport klubbar/<klubb>/hal-NN.yaml` | Alla tees "ok" |
| 5. "Så spelar du hålet" | Skriv Säkert/Chansa i hålfilen utifrån avstånden. Granskas av en golfare. | Text i `strategy:` | Granskad |
| 6. Klubbkontroll | Skicka hålbild + avstånd till klubben. | `python -m golfholes halbild …` | Skriftligt godkänt |
| 7. Skylt | Förhandsvisning + tryck-PDF per platta till Ecosign. | `python -m golfholes skylt …` | Malin har granskat, QR-kod äkta |
| 8. Webb | Digital banguide, sidan QR-koden pekar på. | `python -m golfholes webb klubbar/<klubb>` | Publicerad på klubbens/vår domän |
| 9. Film | Tee-vy och flygfilm i 3D. | (kommer – Blender på Mac Pro) | Filmer per tee och hål |

## Status
- [x] Geometri, avstånd, tee-kamera, längdkontroll
- [x] Grafisk hålbild från vektorer (grund för stilen Nordisk)
- [x] Skylt 70 × 100 cm, tre plattor, förhandsvisning + tryck-PDF per platta
- [x] Digital banguide: sida per hål med sponsor, tee-val och filmplats
- [x] Ritverktyg för att digitalisera hål från ortofoto (testat end-to-end på syntetiskt ortofoto)
- [x] Utsnitt ur Lantmäteriets GeoTIFF (testat på syntetiska rutor)
- [ ] Riktig QR-kod (kräver `segno`, installeras på Macen)
- [ ] Testa på Glasriket hål 3 med riktigt ortofoto (väntar på Geotorget)
- [ ] Höjddata i rapporten (uppför/nedför) – `Elevation` finns, kopplas in när vi har filerna
- [ ] Stilarna Signatur, Klassisk, Arv
- [ ] Tee-vy och flygfilm (3D, Mac Pro)
- [ ] Ecosigns tryckspecifikation in i `SignSpec` (mått, utfall, PDF/X)
