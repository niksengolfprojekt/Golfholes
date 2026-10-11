# Produktionsflödet steg för steg

| Steg | Vad | Vem | Klart när |
| --- | --- | --- | --- |
| 1. Underlag | Ladda ner ortofoto (16 cm) + markhöjdmodell (1 m) för klubbens område från Geotorget. Hämta scorekort och hålkartor. | Ni (inloggning) + Claude | Filerna ligger i `data/<klubb>/`, området i `klubb.yaml` |
| 2. Vektorisera | Rita ut tees, spellinje, green, bunkrar, vatten per hål. Först med AI-segmentering, sedan manuell kontroll mot klubbens hålkarta. | Claude, ni granskar | Ett `hal-NN.yaml` per hål |
| 3. Räkna | Avstånd till hinder och green, längd mot scorekort, kamera för tee-vy. | Koden (`python -m golfholes rapport`) | Alla hål "ok" i längdkontrollen |
| 4. Klubbkontroll | Skicka utkast per hål till klubben/greenkeeper. Rätta tee-lägen, nya bunkrar, OB. | Ni | Klubben har godkänt skriftligt |
| 5. Rendera | Hålbild i vald stil, tee-vy och flygfilm. | Koden; filmer på Mac Pro | Bilder och filmer per hål |
| 6. Mallar | Skylt (tre plattor), digital banguide, tryckfiler. Sponsorlogga + QR. | Koden + Malin granskar | Tryckfärdiga PDF:er till Ecosign, webbsidor publicerade |

## Status
- [x] Grundstruktur, geometri, avstånd, kamera, längdkontroll (exempelhål)
- [ ] Nedladdning och utsnitt av Lantmäteriets data (väntar på Geotorget)
- [ ] Vektorisering från ortofoto
- [ ] Hålbild i stilen Nordisk/grafisk direkt från vektorer (först – mest automatiserbar)
- [ ] Tee-vy och flygfilm (3D, Mac Pro)
- [ ] Skyltmall 70 × 100 cm och digital banguide
