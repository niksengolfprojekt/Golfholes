# Produktionsflödet steg för steg

| Steg | Vad | Kommando / verktyg | Klart när |
| --- | --- | --- | --- |
| 1. Underlag | Se vilka bildår som finns, hämta nyaste ortofoto + markhöjdmodell för området i `klubb.yaml` direkt från Lantmäteriets API (gör utsnittet automatiskt). Hämta scorekort och hålkartor. | `python -m golfholes sok klubbar/<klubb>` (öppet) och `python -m golfholes hamta klubbar/<klubb>` (kräver Geotorget-inloggningen som nätverkshemlighet för `dl1.lantmateriet.se` i molnmiljön, eller miljövariablerna `LM_ANVANDARE`/`LM_LOSENORD`) | `data/<klubb>/lantmateriet.json` + utsnitt |
| 2. Utsnitt | Klipp ut banan ur ortofotot. | `python -m golfholes utsnitt klubbar/<klubb> data/<klubb>/orto/*.tif` | `data/<klubb>/utsnitt/orto.jpg` + `.jgw` |
| 3. Utkast | Sätt fröpunkter per hål i `klubbar/<klubb>/utkast/hal-NN.yaml` mot klubbens hålkarta: tees (namn + längd från scorekortet), en punkt mitt på green och en eller flera i fairway. Koden växer ut green och fairway ur fotot (trollstav), hittar skog, vatten och bunkrar och räknar fram spellinjen genom fairwayns mitt. Ligger greenen i skugga kan kanten ritas in som `green_polygon`. | `python -m golfholes utkast klubbar/<klubb>/utkast/hal-NN.yaml` | `hal-NN.yaml` + kontrollbild `data/<klubb>/utkast/hal-NN_kontroll.jpg` |
| 3b. Rätta | Öppna `verktyg/ritverktyg.html`, ladda `orto.jpg` + `.jgw` + `hal-NN_ritverktyg.json`. Dra hörnpunkter, Alt+klick tar bort falska ytor (grus vid tee, skuggor längs vägar), rita till det som saknas. Kontrollrutan visar längd mot scorekort direkt. | Ritverktyget | `hal-NN.yaml` sparad i `klubbar/<klubb>/` |
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
- [x] Hålkort från riktig hålbild: `fotobild` gör stil 1 Foto höst ur ortofotot längs hålets spelytor (höstfärger, skuggor utjämnade, prickar 100/150 m och flagga ritade av koden) – Glasriket hål 3 i hålkort layout 1, 2026-10-19. Outlinje ritas först när klubben gett den.
- [x] AI-målad hålbild i förlagans stil (2026-10-19): `aiunderlag` gör fotounderlaget (9:16, utan markeringar), AI:n målar om ytan (OpenArt Nano Banana 2.1, bara bilden som referens – med förlagan som andra bild flyttade AI:n green och ritade nya tees), `aibild` lägger målningen på hålets exakta siluett, ritar prickar och flagga och gör en kontrollbild med hålfilens konturer. Ge `aibild` flera målningar så väljer koden den med bäst formpoäng (likhet med fotot + tydliga fairwaykanter); under 0,7 varnar den – då har AI:n ritat om hålet. Underlag och målning i 4K. Nästa hål målas med hål 3 som stilprov (`typbilder/ai-underlag/stilprov-hal-03.png`) så att alla hål ser lika ut. Glasriket hål 3: `klubbar/glasriket/halbilder/hal-03-malad.webp`
- [x] Spelkorridoren: `utkast` ritar aldrig skog i bandet längs spellinjen och från varje tee (`spelfri_m`, 12 m)
- [x] Spelarvy, layout 7 (2026-10-22): stående mobilformat för webb/app med siffror på hålbilden (200/150/100 m kvar till greenens mitt), spellinje och fågelväg per tee, förstorad green vriden mot inspelet med djup och bredd, greenbunkrar och Säkert/Chansa. Bara mått ur hålfilen; inga lutningspilar (höjdmodellen är för grov för greener) och inga servicesymboler förrän klubben gett platserna. `python -m golfholes halkort … --layout 7`. Prov: Glasriket hål 14
- [ ] Tryck-PDF av hålkorten (mått bestäms när klubben valt format)
- [ ] Riktig QR-kod (kräver `segno`, installeras på Macen)
- [x] Utkast ur ortofoto (`utkast`): trollstav för green/fairway, automatisk skog/vatten/bunker, spellinje genom fairwayns mitt, rättning i ritverktyget – provat på Glasriket hål 3 2026-10-19 (två av tre tees inom ±3 %, tee 44 syns inte på fotot)
- [x] Sök och hämta direkt från Lantmäteriets STAC-API (`sok`, `hamta`) – testat skarpt 2026-10-19: Glasrikets ortofoto 2025 och markhöjdmodell hämtade med nätverkshemligheten, utsnitt + höjd + reliefbild klara
- [x] Testa på Glasriket hål 3 med riktigt ortofoto (gjort 2026-10-19 med inloggningen som nätverkshemlighet). OBS 2026-10-22: molnmiljön nekar nu `api.lantmateriet.se` och `dl1.lantmateriet.se` (403 i proxyn) – båda måste finnas under Allowed domains i miljöns nätverksinställning. `data/` följer inte med till en ny session, så underlaget måste hämtas om.
- [ ] Höjddata i rapporten (uppför/nedför) – `Elevation` finns, kopplas in när vi har filerna
- [ ] Signatur med riktigt ortofoto (koden är klar; visar platshållare när `data/<klubb>/` saknas i sessionen)
- [ ] Glasriket hål 5: alla tre tees 3,2–3,4 % korta mot scorekortet (gräns ±3 %) och målningens formpoäng är 0,53 (under 0,7) – Eric har godkänt målningen. 2026-10-23: falsk vattenyta vid 491690/6305494 borttagen ur hålfilen (laserdata: mark + granar), kortet omgjort med nuvarande kod (tees markerade, T-flagga). Tees ska bekräftas av klubben.
- [ ] **Glasriket, status 18 hål (2026-10-23):** hålfil, målad hålbild och hålkort (layout 1) finns för alla 18. Längdkontroll ok utom hål 3 (alla tre tees), hål 5 (alla tre tees) och hål 11 (en tee). Rättat efter granskning 2026-10-23: hål 1 (greenbunkern flyttad till synlig sand, formpoäng 0,90), hål 2 (stenar retuscherade ur underlaget, formpoäng 0,73), hål 4 (skugga som såg ut som damm + brun fläck retuscherade, formpoäng 0,92). Kort i `/mnt/project-files/glasriket/halkort-v3/kort/`.
- [x] Texturrendering: Klassisk och Nordisk ritas med texturkit (gräs, vatten, lövverk, penseldrag) klippta efter exakta masker – demo-kit utklippt ur AI-skisserna
- [ ] Högupplösta texturkit för tryck (genereras som rena texturer, inte hela hål) + kit för Arv och Signatur-ljussättning
- [ ] Ritverktyget: fler lager som skisserna visar – gångvägar, broar, solitärträd, ruffkant
- [ ] Malin granskar de fyra stilarna (typsnitt, färger, ornament) – akvarell och gravyr är kodritade och mindre måleriska än AI-skisserna
- [x] Stilprov av hålbilden, Glasriket hål 14: akvarell, gravyr, mjuk 3D, platt grafisk och arkitektskiss (AI-målade på typbilden, med originalets siluett så formen är exakt densamma). Bilder i `klubbar/glasriket/typbilder/stilar/`. De visar målbilden för texturkiten; riktiga hål målas från ortofotots masker.
- [x] Andra omgången stilprov med egna färgskalor: blå gravyr, screentryck, sommarakvarell, vinterskymning
- [ ] Spelinformationen (prickar, flagga, outlinje) ritas av koden ovanpå stilen så den är lika och läsbar i alla stilar
- [x] Eric spikade fem hålbildsstilar för sajten (2026-10-17): 1 Foto höst, 2 Blå gravyr, 3 Sommarakvarell, 4 Screentryck, 5 Papperssnitt (bäst i mörkt hålkort). Regel i alla: fairway ljusast, ruff mörkare, skog mörkast. Översikt: `/mnt/project-files/hallayouter/stilar/hal-14-SPIKADE-fem-stilar.jpg`
- [x] Klubbens färger: `verktyg/klubbfarg.py` byter stilens färger mot klubbens tonskala (5 färger, mörk till ljus) och ritar prickar och flagga ovanpå. Mörka hålkortet tar `farg_mork` från hålfilen. Prov i tre paletter: `/mnt/project-files/hallayouter/klubbfarger/`
- [x] Stilmenyn spikad 2026-10-22: Akvarell, Sommarakvarell, Gravyr, Mjuk 3D, Arkitektskiss, Papperssnitt. Ersätter Erics fem från 2026-10-17 och kodens fyra.
- [ ] Koppla de sex stilarna till `stil:` i koden (i dag 1–4 kodritade, ska bort) – stilprov per stil som AI-stilreferens
- [ ] Webbsidorna i klubbens stil (använder ännu Nordisk)
- [ ] Klubbmärke (SVG) från klubben till rubriken i stil 1
- [ ] Tee-vy och flygfilm (3D, Mac Pro)
- [x] Ögonhöjdsvy ur data (`golfholes/render/perspektiv.py`): höjdmodell + ortofoto + skogsmassa, spellinjen hålls öppen. AI (OpenArt) målar vyn till foto. Glasriket hål 3, 5, 14: `/mnt/project-files/glasriket/ogonhojd/` – väntar på Erics godkännande. Visas som "Visualisering", aldrig som foto.
- [ ] Ecosigns tryckspecifikation in i `SignSpec` (mått, utfall, PDF/X)
