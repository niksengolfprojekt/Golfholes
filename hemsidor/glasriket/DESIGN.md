# Glasrikets GK – designfil

**Idé:** Banan först. Det första besökaren ser är hela banan ovanifrån i dagens årstid (vår, sommar, höst eller vinter
efter datum), med alla 18 hål klickbara. Förslag 2 (2026-10-27, Eric: banan i fokus och mycket bättre säljande texter).

Registrerad i `hemsidor/designregister.yaml` (riktning `arstiderna`, toppbild `stamningsfoto`).

## Typsnitt (klubbens profil "Glas och skog")
- Rubriker och siffror: Spectral 400/500. Brödtext och knappar: Hanken Grotesk 400–600.
- Fem storlekar på startsidan: display `clamp(46px, 8vw, 112px)`, rubrik
  `clamp(34px, 4.6vw, 60px)`, ingress 21 px, brödtext 17 px, liten 13–15 px. Inget under 13 px.
- Inga små versaler med spärrning ovanför rubriker. Rubriker balanseras (`text-wrap: balance`).

## Färger
| Roll | Färg |
|---|---|
| Sidans botten | dimma `#EEF3EC` |
| Kartans botten (samma som banöversiktens papper) | `#FBF2ED` |
| Text, mörka ytor | natt `#10202E`, djup `#1D4756` |
| Glas (detaljer) | is `#9CC9C3` |
| Knapp och vald hålsiffra | glöd `#D9A441` |

## Startsidan, avsnitt för avsnitt
1. **Banan (toppen):** rubrik, en mening som byts efter årstid och "Boka starttid" bredvid kartan. Siffrorna tänds en
   efter en (hål 1–18) direkt, så att man förstår att de går att trycka på. Tryck på ett hål: hålbilden (samma årstid),
   par, längd och rubrik visas under knapparna; andra trycket går till hålet. Under hålet en ruta för hålsponsorns logga.
   På mobil: rubrik, karta, sedan hålet.
2. **Tre hål avgör din runda:** hål 14, 3 och 5 i ögonhöjd (godkända vyer v2) med kort säljtext ur pro:ns råd.
   **Alla arton hål:** en rad hålkort att svepa i sidled.
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
de syns. Allt stängs av med `prefers-reduced-motion`.

## Bilder
Bara riktiga hål och riktiga vyer. Kartan och hålbilderna bygger på Lantmäteriets data; ytan är målad, formen
aldrig ändrad. Inga personer. Lantmäteriet-raden och "Vissa bilder är visualiseringar" står i sidfoten.

## Historik
- v1 standardmall – fälld i mätt kontroll.
- v2 flygfilm över hål 14 med nedräkning – filmen fälld av Eric (för låg kvalitet), nedräkningen behölls.
- v3 (2026-10-25) stämningsbild, årstid efter datum, sponsorruta. Nedräkningen borttagen samma kväll.
- Förslag 2 (2026-10-27): banan som toppbild, tre signaturhål, svepbar rad med alla hål, nya säljtexter. Stämningsfotot finns kvar i forbered.py men används inte på startsidan.
