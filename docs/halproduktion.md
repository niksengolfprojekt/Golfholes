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

## STIL A (kvällsljus)
Realistisk målning i kvällsljus, vald av Eric 2026-10-25 (Glasriket hål 14 och 17 som prov). Mörk duk, aldrig krämvit.

1. Underlag (0 krediter): `python verktyg/underlag_lyft.py klubbar/<klubb>/hal-NN.yaml` →
   `typbilder/ai-underlag/hal-NN-underlag-lyft-mork.jpg`. Indata är `halbilder/hal-NN-malad-utan-flagga.webp`;
   finns den inte (ny klubb) lyfts ortofotot direkt. Lyftet lägger laserträdens skuggor (sol 235°, 30°),
   relief ur höjdmodellen och mörkblå kant (`verktyg/lyft.py`).
2. Pusha underlaget och ge det som enda referens via raw.githubusercontent-URL på en commit-SHA.
3. OpenArt `nano-banana-2-1`, image2image, 4K, 9:16, 3 varianter (240 krediter per hål).
   Aldrig ett annat hål som referens.
4. Passa in: `python verktyg/ai_tillbaka_test.py klubbar/<klubb>/hal-NN.yaml a <png...>` (formpoäng ≥ 0,7,
   titta på kontrollbilden efter påhittade tees, klippta ytor eller borttagen vass/vegetation).

Prompt, hål utan vatten (ordagrant, gav Glasriket hål 14 = 0,87):

Edit this image. It is an exact map: keep every shape, outline and position pixel-for-pixel as it is (fairway
edges, green, bunker, tee boxes, tree lines, every tree crown, every shadow, the red and yellow dots). Do not add,
remove, widen or move anything. Upgrade only the surface rendering into a photorealistic, premium golf course image
seen straight from above, like a high-end drone photograph at golden hour: warm low late-afternoon sun from the
upper right, crisp long cool-blue shadows exactly where the existing shadows are, fresh vivid green fairway with
lime-yellow sunlit highlights and sharp alternating light and dark mowing stripes, a brighter finely mown green with
a crisp darker collar ring, slightly darker textured rough, bright white sand with a crisp lip shadow. Trees are
Swedish Norway spruce and Scots pine seen from directly above: dense dark-green conical crowns with soft round tops
and layered needle texture, NEVER star-shaped, NEVER palm-like, plus a few birches with small rounded warm golden
crowns. High contrast, sharp micro-detail, rich natural colour, not washed out. The surroundings fall off into the
dark navy background exactly as now. No text, no people, no flags, no paths, no buildings.

Prompt, hål med vatten (ordagrant, gav Glasriket hål 17 = 0,78; första meningarna beskriver hålets egna former
och skrivs om per hål):

Edit this image. It is an exact map: keep every shape, outline and position pixel-for-pixel as it is. The two
ponds keep exactly their shorelines, the round tree island stays exactly where and as big as it is, the green stays
exactly round and in place, the fairway and both tee areas keep their exact outline, the path, the buildings and
the gravel yard stay. The narrow strip of land between the two ponds is unmown rough grass with a gravel path: no
stripes, no mown patch, no tee there. Do not add any tee box, mown area, path, jetty or anything that is not
already there; do not remove anything. Only change the surface into a photorealistic, premium golf course image
seen straight from above, like a high-end drone photograph at golden hour: warm low late-afternoon sun from the
upper right, crisp cool-blue shadows exactly where the existing shadows are, fresh green fairway grass with
lime-yellow sunlit highlights and soft mowing stripes only on the fairway, a bright finely mown green with a darker
collar ring, deep clear blue-green water with a soft warm golden sky reflection near the upper right and reed
edges, broadleaf crowns with real 3D volume, birches with small rounded warm golden crowns (not neon), roofs and
gravel in quiet muted grey. High contrast, sharp micro-detail, rich natural colour. The surroundings fall off into
the dark navy background exactly as now. No text, no people, no flags, no cars.

Under prov 2026-10-25 (Eric vill ha "mer renderat och krispigt"): ett andra AI-pass med den valda målningen som
referens ("premium high-end 3D render, ultra crisp…") och/eller en skärpning i kod (klarhet + mikrokontrast)
innan inpassningen. Det andra AI-passet tog bort vassen i dammen på hål 17, så kontrollera vegetation i vatten.
Uppdateras när Eric valt.

## Stil B · Tecknad bokstil (Eric 2026-10-30, gäller nu för Glasriket)

Alla 18 hål gjorda om i stil B. Samma kedja som stil A, men prompten byter ytan till en tecknad banguide
(nano-banana-2-1 image2image, 3 bilder per hål, 9:16, 4K, 240 krediter per hål). Ordagrant slut på prompten:

> Only turn this aerial image into a premium hand-finished golf course illustration seen straight from above, the quality of a luxury resort yardage book: fine ink linework with soft painted colour, late afternoon golden-hour sunlight from the upper right, long soft blue-green shadows exactly where the existing shadows are, fresh lush green fairway with soft alternating mowing stripes only on the fairway, a finely mown green with a darker collar ring, slightly darker textured rough, bright clean sand with a crisp lip[, clear deep blue-green water with gentle light reflections]. Trees are Swedish Norway spruce and Scots pine drawn with dense rounded dark-green crowns and real volume, NEVER star-shaped, NEVER palm-like, plus birches with small rounded warm muted-gold crowns (not neon). Roads and buildings in quiet muted grey. Rich, saturated but natural colour, good contrast, high micro-detail, sharp. The surroundings fall off into the dark navy background exactly as now. No text, no people, no flags, no cars. Do not add any path, tee, bunker or building that is not already there.

Början är densamma som för stil A (låst inramning + hålets egna former). Lärdomar:
- Stil B drar en tuschkant runt varje fairway. En smal fairwaybit som i underlaget ser ut som ruff blir
  då två skilda fairways (hål 1). Tona biten i underlaget först: `python verktyg/underlag_fairway_ton.py
  klubbar/glasriket/hal-01.yaml 2`, och säg i prompten att det är EN sammanhängande fairway.
- Formpoängen blir något lägre än i stil A eftersom kanterna ritas skarpare. Hål 17 nådde 0,68 på sex
  försök; vatten, ö och green låg exakt, bara fairwaykanten avvek, och bilden godkändes efter ögonkontroll.
- Hål 6: ta bort sandfrasen ur prompten (hålet har ingen bunker). Hål 7: "the area behind the green is grass".
- Kedja per hål: `ai_tillbaka_test <hålfil> b5 data/<klubb>/ai-b/hNN-?.png` → (fairway_ton) → `fairway_frisk
  --namn b5` → `prick_flytt --namn b5` → `halkort` (bild: ../halbilder/hal-NN-b5.webp).
