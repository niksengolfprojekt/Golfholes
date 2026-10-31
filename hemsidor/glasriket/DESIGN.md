# Glasrikets GK – designfil

**Idé:** Glaskulan öppnas. Sidan börjar med banan i ett glasklot mot nattblått, samma klot som i klubbens sigill
"Småland", och klotet vidgas till hela skärmen: glaset i Glasriket och skogen i Fylleryd i en och samma rörelse. Sedan hela banan ovanifrån i dagens årstid,
där varje hål går att zooma in på (Eric 2026-10-30: toppen ska andas kvalitet, Småland och skogsbana, stolthet för
medlemmar och lust för gäster; banöversikten i avsnitt 2).

Registrerad i `hemsidor/designregister.yaml` (riktning `arstiderna`, toppbild `glaskula`).

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
1. **Entrén (helskärm, Eric 2026-10-31):** glaskulan med guldring öppnas till helbild (1,9 s, startar först när
   bilden är laddad), ett ljusskimmer drar genom glaset, bilden andas ut och glider långsammare än sidan vid skroll.
   Sedan vita sigillet, rubriken "Nära Växjö. Djupt i skogen.",
   en mening plus "Välkommen hem. Eller välkommen hit." (medlem och gäst), "Boka starttid" och "Se banan".
   Ingen versalrad, inga textskuggor, ingen sifferrad. Sidhuvudet är genomskinligt över entrén och sigillet i
   huvudet syns först när man skrollat förbi. Bilden byts mot klubbens eget foto i `forbered.py` (STAMNINGSBILD).
2. **Banan:** rubrik, en mening som byts efter årstid och "Se alla 18 hål" bredvid kartan. Siffrorna tänds en
   efter en (hål 1–18) direkt, så att man förstår att de går att trycka på. Tryck på ett hål: hålbilden (samma årstid),
   par, längd och rubrik visas under knapparna; andra trycket går till hålet. Under hålet en ruta för hålsponsorns logga.
   Tryck zoomar kartan in på hålet ("Visa hela banan" eller Esc zoomar ut). På mobil: rubrik, karta, sedan hålet.
3. **Alla arton hål:** en rad hålkort att svepa i sidled. Ett avsnitt med hål i ögonhöjd väntar tills alla
   18 hål har en sådan vy (Eric 2026-10-27); CSS-klasserna `signatur`/`sig-*` finns kvar för det.
4. **Naturen:** bilden går ut i kanten, kort text om Fylleryd.
5. **Vägar in:** greenfee, medlemskap, hålsponsor – ytor utan ramar.
6. **Hitta hit** med öppettider.

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
- Förslag 2 (2026-10-27): banan som toppbild, svepbar rad med alla hål, nya säljtexter. Stämningsfotot finns kvar i forbered.py men används inte på startsidan.
- 2026-10-29: inzoomning på hålet och hålen i raden som växer fram ett i taget.
- 2026-10-30 (Eric): ny entré överst. Första försöket (helbild, versalrad, två knappar) fälldes i smakgranskningen som
  standardmall; ersatt av glaskulan. Banöversikten flyttad till avsnitt 2.
- 2026-10-31 (Eric: hero som täcker hela skärmen, med effekt): glaskulan öppnas till helbild i stället för att stå kvar.
