# tacada.se

TACADA:s egen hemsida. Statiska sidor utan databas eller kakor, i grafiska profilen v1.2.

## Så är det ordnat
- `sidor/` – innehållet på varje sida. Huvudet överst säger titel, beskrivning och adress.
- `mallar/ordmarke.svg` – ordmärket från profilens filpaket (färgen följer texten).
- `bygg.py` – lägger på sidhuvud, meny och sidfot och skriver färdiga sidor till `public/`.
- `public/` – det som publiceras: sidorna, `css/`, `js/`, `img/`, `fonts/` (Marcellus och Inter, egna kopior så att inga anrop går till Google).

## Kör
```
python hemsida/bygg.py                  # bygger och letar trasiga länkar och bilder utan alt-text
python hemsida/bygg.py --lansering      # stoppar om luckor ([FYLL I]) eller noindex finns kvar
python hemsida/bygg.py --forhandsvisning <mapp>   # kopia med relativa länkar, för förhandsvisning
```

## Inställningar överst i `bygg.py`
- `LANSERAD` – False ger noindex på alla sidor och stänger ute sökmotorer i `robots.txt`.
- `REFERENS_GLASRIKET` – False tills Glasrikets styrelse har sagt ja (möte 2026-12-08) och klubben godkänt texten skriftligt. Kontrollen stoppar om Glasriket nämns innan dess.
- `BOLAG` – bolagsnamn, org.nr, ort, e-post och telefon.

## Regler för innehållet
- Inga TACADA-priser på sajten (Eric 2026-10-22). Kalkylatorn visar bara klubbens egna sponsorintäkter, märkt "inte ett löfte".
- Inga personer på bilder. Bilder märks aldrig med AI-stämpel (Erics beslut 2026-10-23); Eric 2026-10-27: Om oss har en enda rad om att vi tar hjälp av AI för visualiseringar och bilder (testet tillåter just den raden, bara där), aldrig vid bilder eller på startsidan. Lantmäteriets källtext (CC BY 4.0) står alltid i sidfoten och vid hålbilden, den är ett licenskrav.
- Lova aldrig fler medlemmar, rundor eller högre sponsorpriser.
- Riktiga sponsorer och klubbar nämns bara med tillstånd. Exempelföretaget är Nordvik (påhittat).

## Publicering
Kontaktformuläret är förberett för Netlify Forms. Med en annan värd byts formulärets mottagare.

## Startsidans bana är påhittad (Eric 2026-11-05)
Banrundan, hålrullen, "Slag för slag" och skylten visar en påhittad bana, inte Glasriket eller någon annan riktig klubb. Banbilden och tee-utsikten är målade av AI, och terrängen räknas fram ur bilden:
- `python hemsida/verktyg/fiktiv_bana.py <banbild.png>` skriver `img/banrunda/karta.webp`, `karta-reserv.webp` och `terrang.json`.
- `python hemsida/verktyg/fiktiva_hal.py <banbild.png>` klipper ut hål 4, 7, 10 och 12 till `img/hal/`.
Källbilden ligger i projektfilerna under `tacada/hemsida/fiktiv-bana/` (checkas inte in). Regeln om verklig geometri gäller riktiga klubbars hålfiler, inte den här demobanan.
Exempelsponsorn är "Nordvik" (påhittad).
