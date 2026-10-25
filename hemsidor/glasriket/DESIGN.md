# Glasrikets GK – designfil

**Idé:** En skogsjuvel du flyger in i. Startsidan bärs av signaturhålet 14: besökaren flyger genom skogsgatan
mot green medan avståndet till flaggan räknas ner, och går sedan banan i förväg på en karta som byter årstid.

Registrerad i `hemsidor/designregister.yaml` (riktning `signaturhalet`, toppbild `flygfilm-med-avstand`).

## Typsnitt (klubbens profil "Glas och skog")
- Rubriker och siffror: Spectral 400/500. Brödtext och knappar: Hanken Grotesk 400–600.
- Fem storlekar på startsidan: display `clamp(46px, 8vw, 112px)` (avståndet upp till 168 px), rubrik
  `clamp(34px, 4.6vw, 60px)`, ingress 21 px, brödtext 17 px, liten 13 px. Inget under 13 px.
- Inga små versaler med spärrning ovanför rubriker. Rubriker balanseras (`text-wrap: balance`).

## Färger
| Roll | Färg |
|---|---|
| Sidans botten | dimma `#EEF3EC` |
| Kartans botten (samma som banöversiktens papper) | `#FBF2ED` |
| Text, mörka ytor | natt `#10202E`, djup `#1D4756` |
| Glas (detaljer, avståndets enhet) | is `#9CC9C3` |
| Knapp och vald hålsiffra | glöd `#D9A441` |

## Startsidan, avsnitt för avsnitt
1. **Scenen:** flygfilmen över hål 14 (3,6–19,4 s ur v3, 720p, ljudlös loop) med avståndet till flaggan
   som följer filmen, räknat ur kamerabanan längs hålets mittlinje. Rubrik, en mening och en knapp.
   Pausknapp. Stillbild i stället för film vid reducerad rörelse eller sparat dataläge.
2. **Kartan:** banöversikten i vår, sommar, höst och vinter. Siffrorna tänds en efter en (hål 1–18) när
   kartan syns. Tryck på ett hål: hålkortet, par, längd och rubrik visas bredvid; andra trycket går till hålet.
3. **Naturen:** bilden går ut i kanten, kort text om Fylleryd.
4. **Vägar in:** greenfee, medlemskap, hålsponsor – ytor utan ramar.
5. **Hitta hit** med öppettider.

## Rörelse
Bara transform och opacitet. Rubriken stiger in vid laddning, delarna glider in när de syns, årstiderna
tonas över varandra (0,7 s). Allt stängs av med `prefers-reduced-motion`.

## Bilder
Bara riktiga hål och riktiga vyer. Filmen och kartan bygger på Lantmäteriets data; ytan är målad, formen
aldrig ändrad. Inga personer. Lantmäteriet-raden och "Vissa bilder är visualiseringar" står i sidfoten.

## Kontroll
Mätt kontroll 2026-10-25 (1440/768/390 px): 0 fel i båda granskningsverktygen. Varning kvar: fler än
fem textstorlekar räknat över hela sidan, eftersom sidhuvud, sidfot och öppettider delas med övriga sidor.
