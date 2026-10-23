# Hålproduktion – samma styrning för varje hål och varje klubb

Ett hål i taget, från klubbens scorekort och hålkarta till godkänt hålkort. Varje hålagent följer
exakt dessa steg. Inga egna genvägar, ingen påhittad geometri.

## Indata per klubb (finns innan start)
- `klubbar/<klubb>/klubb.yaml`: par, index och längd per tee (scorekortet).
- Klubbens hålkartor och texter, t.ex. `/mnt/project-files/<klubb>/banguide-*/H<NN>-1.jpg` och `pro-rad.md`.
- Lantmäteriet i `data/<klubb>/` (`python -m golfholes hamta klubbar/<klubb>`): `orto/*.tif` (4 band, behövs av
  `utkast`), `hojd/*.tif`, `utsnitt/orto.jpg + .jgw`. Laserdata Skog i `data/<klubb>/laser/*.copc.laz`.
- Startpunkt för tee 56 (eller klubbens mellantee) per hål, om en översikt finns.

## Steg för ett hål (NN = två siffror)

1. **Läs hålet.** Par, alla tees med längd (klubb.yaml), klubbens hålkarta `H<NN>-1.jpg`, pro-rådet. Notera
   spelriktning, dogleg, vatten, bunkrar och var tees ligger på kartan. Klubbens kompasspilar går inte att
   lita på: riktningen avgörs av ortofotot, längden och grannhålen.
2. **Hitta hålet på ortofotot.** Gör utsnitt med rutnät:
   `python verktyg/rutnat.py data/<klubb>/utsnitt/orto.jpg E N --radie 250 --steg 25 --ut <scratch>/hNN.jpg --punkt E,N,T56`
   Titta på bilden. Hitta alla teeplatser (små klippta rektanglar, ofta i rad), greenen (rund, jämnt ljusgrön,
   ofta med bunkrar) och fairway. Zooma (`--radie 80 --steg 10`) för att läsa koordinater på 1–2 m när.
   Jämför form och hinder med klubbens karta: hålet måste se ut som kartan.
3. **Kontrollera längden innan du skriver något.** Avstånd längs spelvägen från varje tee till greenens mitt
   ska vara scorekortets längd ±3 %. Stämmer det inte: fel tee, fel green eller fel hål. Hål 11 på Glasriket
   lades först åt fel håll – kontrollera mot grannhålen.
4. **Skriv fröfilen** `klubbar/<klubb>/utkast/hal-NN.yaml` i samma format som `klubbar/glasriket/utkast/hal-09.yaml`:
   kommentar om källor och osäkerheter, `tees` (namn som i scorekortet, `point`, `length_m`), `green`
   (mitten), `fairway` (2–4 punkter mitt i fairway), `centerline` (tee bakerst → brytpunkter → green; `auto`
   bara om hålet är rakt), `orto`, `laser`, `hojd`. En tee som inte syns på fotot placeras på spelvägen på
   scorekortets avstånd och markeras `# beräknad, syns inte på fotot`. Par 3 har ingen fairway-punkt om det
   inte finns en fairway.
5. **Kör utkastet:** `python -m golfholes utkast klubbar/<klubb>/utkast/hal-NN.yaml` → `klubbar/<klubb>/hal-NN.yaml`
   + kontrollbild under `data/<klubb>/utkast/`. Titta på kontrollbilden: green, fairway, bunkrar och vatten
   ska ligga på de riktiga ytorna. Falska bunkrar/vatten (grus vid tee, vägskuggor, tak) tas bort ur hålfilen.
   Saknas en green i skugga: lägg till `green_polygon` i fröfilen och kör om.
6. **Rapport:** `python -m golfholes rapport klubbar/<klubb>/hal-NN.yaml`. Alla tees "ok" (±3 %). Annars
   tillbaka till steg 2–4.
7. **AI-underlag:** `python -m golfholes aiunderlag klubbar/<klubb>/hal-NN.yaml` → underlag (9:16, 4K) under
   `klubbar/<klubb>/typbilder/ai-underlag/hal-NN-underlag.jpg`. Titta på det: inga suddiga fläckar i fairway
   (AI:n gör bunkrar av dem).
8. **Publicera underlaget** så OpenArt kan läsa det: `git add` bara underlaget, commit, `git pull --rebase`,
   `git push` (försök igen vid krock). URL = `https://raw.githubusercontent.com/niksengolfprojekt/golfholes/<commit-SHA>/klubbar/<klubb>/typbilder/ai-underlag/hal-NN-underlag.jpg`
   (SHA, aldrig grennamn – grenen cachas). Kontrollera med `curl -sI` att den svarar 200.
9. **Måla:** OpenArt `openart_generate_image`, model `nano-banana-2-1`, mode `image2image`, params
   `{imageCount: 2, aspectRatio: "9:16", resolution: "4K", autoEnhancePrompt: false,
   visualReferences: [{type: "image", id: "halNN", url: <URL>, label: "hole NN"}], prompt: <STANDARDPROMPT>}`.
   Bara underlaget som referens – aldrig ett annat hål som stilbild (då ritar AI:n om hålet). Kostar 160 krediter.
   Vänta med `openart_creation_get` (följ `pollAfterSeconds`). Ladda ner båda bilderna med curl.
10. **Lägg på formen:** `python -m golfholes aibild klubbar/<klubb>/hal-NN.yaml a.png b.png`. Koden väljer bästa
    formpoäng. Krav: **≥ 0,7**. Titta på kontrollbilden med hålfilens konturer: inga nya bunkrar, dammar,
    gångvägar eller flyttad green. Under 0,7 eller påhittat: måla en gång till (max 2 försök totalt), annars
    rapportera hålet som stoppat.
11. **Hålkort:** skriv `klubbar/<klubb>/halkort/hal-NN.yaml` i samma format som `klubbar/glasriket/halkort/hal-09.yaml`
    (tees som i scorekortet, rubrik ≤ fältgränsen, beskrivning ur hålfilen, pro-rådet nästan ordagrant,
    strategi Säkert/Chansa). Inga avståndslinjer, alla tees markerade. Kör
    `python -m golfholes halkort klubbar/<klubb>/halkort/hal-NN.yaml --layout 1` och titta på resultatet.
12. **Commit** hålfil, fröfil, hålkortsfil, målad hålbild (`halbilder/hal-NN-malad.webp`). Rådata (`data/`)
    checkas aldrig in. Kopiera hålkortets PNG och kontrollbilden till `/mnt/project-files/<klubb>/halkort-v3/`.

## Rapport per hål (till den som granskar)
Hålnummer, längd per tee mot scorekort (%), formpoäng, vilka tees som är beräknade, vad som avviker från
klubbens karta, filvägar, krediter använda, status: klart / klart med frågor / stoppat.

## STANDARDPROMPT (samma för alla hål)
Edit this image. This is a light retouching job on a real aerial photograph, not a redraw. Keep the image at
exactly the same framing, scale and position: every pixel of every edge must stay where it is. Only improve the
surfaces: make the grass a fresh, even late-summer green with subtle mowing stripes on the fairway and a smooth
putting green, give any water a clean deep blue with soft reflections, make the tree crowns crisp and natural
with gentle shadows (keep the golden autumn birches golden), clean up the sand in the bunkers and the gravel
paths. Remove the hazy yellow cast so colours are clear and sunny. Do not straighten, smooth, enlarge or reshape
any fairway, green, bunker, shoreline, path or tree group. Do not add or remove anything. No text, no flags, no
markers. Keep the cream background and its soft edge exactly as they are.
