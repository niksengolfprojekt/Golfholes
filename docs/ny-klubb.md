# Ny klubb – hela paketet, samma steg varje gång

Ny klubb = ny mapp, samma kommandon. Byggt på det som fungerade för Glasriket (pilot, oktober 2026).
Skillen `ny-golfklubb` pekar hit. Detaljer per hål: [halproduktion.md](halproduktion.md). Flödet och status:
[flode.md](flode.md). Statistik: [statistik.md](statistik.md).

## 0. Start

- Utgå från `main`. Kontrollera att verktygen finns:
  `python -m golfholes --help` ska lista `hamta utkast aiunderlag aibild halkort prospekt inlagg flygfilm sponsorrapport designregister`.
  Saknas något ligger det på en ej sammanslagen gren – säg det till Eric i stället för att bygga om.
- Nätverket måste släppa igenom `api.lantmateriet.se` och `dl1.lantmateriet.se` (Geotorget-inloggningen är
  nätverkshemlighet). Nekas de: läs miljödokumentationen och be Eric öppna dem.
- Kolla OpenArt-saldot (`openart_account_get`) innan något planeras.
- **Omfattning** (fråga om det inte är sagt): *referensklubb* = 3 hål + kort presentation, bara när ett möte är
  bokat; *hela paketet* = allt nedan.

## 1. Underlag (0 krediter)

| Vad | Var |
| --- | --- |
| Scorekort: par, index, längd per tee (teenamn som klubben skriver dem) | `klubbar/<slug>/klubb.yaml` → `holes:` |
| Banans yta + 100 m marginal i SWEREF 99 TM | `klubb.yaml` → `bbox_sweref99tm` (OSM Nominatim för grov ruta) |
| Klubbens hålbilder `H<NN>-1.jpg`, översiktskarta, PRO-råd, scorekort.csv | `/mnt/project-files/<slug>/banguide-<år>/` (internt, publiceras aldrig) |
| Ortofoto, höjdmodell, utsnitt | `python -m golfholes sok\|hamta klubbar/<slug>` → `data/<slug>/` (checkas aldrig in) |
| Laserdata Skog (träd, vatten) | STAC `dsm-skoglig-copc` → `data/<slug>/laser/*.copc.laz` (kräver `laspy lazrs`) |
| Klubbens anläggning (range, korthålsbana, kiosk …), kontakt, org.nr | `klubb.yaml` → `web`, `contact`, `sponsring.tillval.finns` |

Mall för `klubb.yaml`: `klubbar/glasriket/klubb.yaml`. Skillen `golf-banunderlag` gör samma insamling.

## 2. Hålbilder och hålkort

Ett testhål först (gärna klubbens signaturhål), visa Eric, sedan resten parallellt (t.ex. 3 hålagenter med samma
styrning + en granskare). Varje hål följer [halproduktion.md](halproduktion.md) steg 1–12. Hårda krav:

- **Riktning:** avgörs av ortofotot, längden och grannhålen – klubbens kompasspilar ljuger. Glasriket hål 11 lades
  först baklänges.
- **Tees:** varje tee jämförs med klubbens hålbild `H<NN>-1.jpg`. Alla tees ritas. En tee som inte syns på fotot
  placeras på scorekortets avstånd och märks `# beräknad` och listas som fråga till klubben.
- **Längd:** varje tee inom ±3 % mot scorekortet (`rapport`).
- **Formpoäng ≥ 0,7** (`aibild`) och kontrollbilden visar inga nya bunkrar, dammar, gångar eller flyttad green.
  Max 2 målningsförsök, annars stoppas hålet.
- **Stil:** Glasriket har stil A, realistisk målning i kvällsljus (Eric 2026-10-25). Ny klubb får stil ur stilmenyn
  (`stil:` i `klubb.yaml`), A är standard tills klubben valt. Svensk gran, tall och björk – aldrig palmer eller
  stjärnkronor. Aldrig ett annat hål som stilreferens (då ritar AI:n om hålet). Underlaget via SHA-länk.
- **OB:** bara där klubbens gamla hålbilder visar out. Aldrig gissad.
- **Flagga:** klubbens logga på duk i klubbens färg (`flagga:` i `klubb.yaml`), mitt på greenen.
- **Hålkort:** inga avståndslinjer, alla tees markerade, layout ur `klubb.yaml` (`layout:`). Håltexter säljande och
  pedagogiska; PRO-rådet är klubbens, våra egna strategirader märks som utkast tills klubben godkänt.

## 3. Grafisk profil

1. Utgå från klubbens nuvarande logga – förnya den (Glasriket: pokalen i sigillet "Småland") hellre än att byta.
   Visa 3–4 vägar på en bild, Eric väljer. Loggan måste gå att brodera (enkla former, ≥ 4 cm).
2. Palett 5–7 färger (mörk bärfärg, ljus yta, accent) + två typsnitt (OFL, hämtas från
   `raw.githubusercontent.com/google/fonts`). Får inte likna TACADA (Marcellus, mörk topo) eller en tidigare klubb.
3. In i `klubb.yaml` → `profil`, `typsnitt`, `flagga`. Allt annat (hålkort, inlägg, prospekt, sajt) läser därifrån.
4. Manual: kopiera `verktyg/grafisk_manual/glasriket_manual.py` till `<slug>_manual.py`, byt innehåll – PDF i
   `/mnt/project-files/<slug>/grafisk-manual-v1/`.

## 4. Hemsida

Kör skillen `unik-klubbhemsida` först (inventering, riktning, `hemsidor/<slug>/DESIGN.md`), sedan bygg med
`hemsidor/glasriket/` som teknisk förebild – men aldrig samma utseende. `python -m golfholes designregister` måste
gå igenom (≥ 3 av 4 skiljer mot alla tidigare sajter, ingen standardmall). Texter: `saljande-texter`. Inga AI-ord:
`inga-ai-stamplar` (bygget stoppar på "AI", "GameBook", "Emtec"). Lantmäteriets källtext i sidfoten. Granska med
`smakgranskning`. Lansering kräver klubbens skriftliga OK, domän och integritetspolicy.

## 5. SoMe-kit

`klubbar/<slug>/some/inlagg.yaml` (mall: Glasriket) → `python -m golfholes inlagg klubbar/<slug>`.
3 fästa inlägg, hål för hål, "Vilket blir ert hål?", highlight-ikoner i klubbens färger. 4:5, hela hålet syns,
inga människor, soligt. Bildtexter i `texter.md`.

## 6. Hålsponsring

- `klubb.yaml` → `sponsring`: pris per hål (klubbens val; räkneexempel upp till 25 000 kr, aldrig ett löfte),
  `ronder_per_ar` (fjolårets siffra från klubben), `exempelhal`, `omslagshal`, `sponsorsida`, `tillval`
  (`finns` = klubbens anläggning i dag, `nytt` = förslag), `status` per hål.
- `python -m golfholes prospekt klubbar/<slug> --gemensam` (en säljpresentation: hålet först, allt som ingår,
  sedan tillvalen) och vid behov `--alla` (en PDF per hål).
- Statistik: `docs/statistik.md`, `sponsorrapport`. Exponering = visningar, inte personer. Lova aldrig fler
  ronder, medlemmar eller högre sponsorpriser.
- Partnerprogram (hela sponsorerbjudandet, inte bara hålen): kopiera `klubbar/glasriket/partnerprogram.yaml`,
  anpassa och kör `python -m golfholes partnerprogram klubbar/<slug>`. Se `docs/partnerprogram.md`.

## 7. Flygfilm (bara efter Erics OK och kredittak)

1. `python -m golfholes flygfilm klubbar/<slug>/hal-NN.yaml --forlopp oversikt` – rå film ur data: översikt →
   ner till mellanteen → hålet → upp igen, ≥ 20 s.
2. `python -m golfholes.render.flygfilm_kontroll animatic|omproj …` räknar ut AI-delarna.
3. AI-yta: Wan 3.0 video-till-video i OpenArt, **480p** (Eric ser ingen skillnad mot 720p). AI:n byter bara yta.
   Varje del kontrolleras med konturer (`flygfilm_kontroll konturer`); påhittat underkänns eller tvättas bort
   (`tvatt`, bara borttagning).
4. `python -m golfholes.render.flygfilm_jamna <klipp> <rutor> --ut …` på varje klipp (inga ryck, inget flimmer),
   sedan `flygfilm_kontroll hopklipp`.
5. `python -m golfholes.render.flygfilm_tracer <hålfil> --kam <bana.json> --film <film> --ut …` bränner in
   nedräkningen till flaggan och slagkurvorna ur `strategy: slag:` (PRO-rådet; klubben godkänner slagen).
6. Kreditlogg och `resultat.md` bredvid filmen.

## 8. Leverans och granskning

- `smakgranskning` på allt visuellt innan Eric ser det.
- Eric läser på mobilen: bilder på en Artifact-sida, inte filvägar. All klubbens material som egen sida i Claude
  Design-canvasen "Tacada" (en sida per klubb).
- Presentationer: PDF + Google Slides, aldrig PowerPoint. Ersatta filer i Drive får "ERSATT" i namnet.
- Varje hål godkänns av klubben skriftligt innan tryck. Tryckprov hos Ecosign innan skyltar beställs.
- Uppdatera `docs/flode.md` och en projektminnesfil per klubb.

## Krediter (OpenArt, oktober 2026)

| Del | Ungefär |
| --- | --- |
| Hålbild, 2 varianter 4K | 160 per försök, 250–375 per hål med omtag |
| 18 hålbilder | 4 000–6 000 |
| Ögonhöjdsvy 2K, 2 varianter | 84 |
| Flygfilm 480p per hål | ca 600–1 200 med omtag (720p: 1 900–2 300) |
| Referensklubb, 3 hål | ca 1 000 |

Ingen generering utan Erics OK på beloppet. Stanna vid taket och fråga.
