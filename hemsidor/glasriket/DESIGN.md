# Glasrikets GK – designfil

**Idé:** En skogsjuvel som följer säsongen. Överst en stämningsbild från banan där avståndet till flaggan på
hål 14 räknas ner när man scrollar. Sedan hela banan ovanifrån som den ser ut just nu – vår, sommar, höst
eller vinter efter datum – med alla 18 hål klickbara.

Registrerad i `hemsidor/designregister.yaml` (riktning `arstiderna`, toppbild `stamningsfoto-med-avstand`).

## Typsnitt (klubbens profil "Glas och skog")
- Rubriker och siffror: Spectral 400/500. Brödtext och knappar: Hanken Grotesk 400–600.
- Fem storlekar på startsidan: display `clamp(46px, 8vw, 112px)` (avståndet upp till 168 px), rubrik
  `clamp(34px, 4.6vw, 60px)`, ingress 21 px, brödtext 17 px, liten 13–15 px. Inget under 13 px.
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
1. **Scenen:** stämningsbild över hela skärmen (andas in långsamt vid laddning). Rubrik, en mening, en knapp.
   Avståndet "335 m från tee 56 till flaggan" på hål 14 räknas ner till 0 medan man scrollar förbi bilden.
   **Platshållare:** ögonhöjdsvyn av hål 14 från tee. Byt till klubbens eget foto genom att ändra
   `STAMNINGSBILD` i `forbered.py` och köra `python forbered.py stamning`. Fotot: sol, öppen bana, inga personer,
   liggande, minst 2400 px brett.
2. **Kartan:** banöversikten i dagens årstid (ingen väljare). Siffrorna tänds en efter en (hål 1–18) första
   gången kartan syns, så att man förstår att de går att trycka på. Tryck på ett hål: hålbilden (samma årstid),
   par, längd och rubrik visas bredvid; andra trycket går till hålet. Under hålet en ruta för hålsponsorns logga
   (namnet om loggan saknas, "Ge ert företag hål N" om hålet är ledigt).
3. **Naturen:** bilden går ut i kanten, kort text om Fylleryd.
4. **Vägar in:** greenfee, medlemskap, hålsponsor – ytor utan ramar.
5. **Hitta hit** med öppettider.

## Årstider
- Vår april–maj, sommar juni–augusti, höst september–oktober, vinter november–mars (i `site.js`).
- Byts av skriptet: kartan, hålbilderna på alla sidor och kartans ingress. Utan skript syns sommaren.
- Granskning: lägg till `?arstid=var|sommar|host|vinter` i adressen; valet gäller resten av besöket.
- Hålbilderna färgas om i koden (`arstid.py`): varje pixel behåller plats och ljushet, bara kulören byts efter
  vad den är (gräs, barrträd, lövträd, sand). Tees, prickar och flagga lämnas orörda. Formen ändras aldrig.

## Rörelse
Bara transform och opacitet. Rubriken stiger in vid laddning, toppbilden zoomar sakta ut, delarna glider in när
de syns. Allt stängs av med `prefers-reduced-motion` (då står avståndet still på 335 m).

## Bilder
Bara riktiga hål och riktiga vyer. Kartan och hålbilderna bygger på Lantmäteriets data; ytan är målad, formen
aldrig ändrad. Inga personer. Lantmäteriet-raden och "Vissa bilder är visualiseringar" står i sidfoten.

## Historik
- v1 standardmall – fälld i mätt kontroll.
- v2 flygfilm över hål 14 med nedräkning – filmen fälld av Eric (för låg kvalitet), nedräkningen behölls.
- v3 (2026-10-25) stämningsbild, årstid efter datum, sponsorruta.
