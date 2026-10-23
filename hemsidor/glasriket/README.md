# Glasrikets GK – ny hemsida

Statisk sajt i profilen "Glas och skog" (Spectral + Hanken Grotesk, sigillet "Småland").
Inga kakor, ingen databas. Bygget skriver allt till `public/`, som publiceras som den är.

## Så är det ordnat
- `sidor/` – innehållet på de fasta sidorna (start, banan, greenfee, bli medlem, hålsponsorer, kontakt,
  integritet, tack, 404). Huvudet överst säger titel, beskrivning och adress. `{{namn}}` fylls i av bygget.
- Hålsidorna 1–18 skapas av bygget ur `klubbar/glasriket/klubb.yaml` (par, index, tees, längder),
  hålkorten i `klubbar/glasriket/halkort/` och texterna i `data/hal.yaml`.
- `data/klubbfakta.yaml` – priser, öppettider, adress och kontakt (från glasriketsgk.se 2026-10-23).
- `tillgangar/` – css, js, typsnitt (woff2), sigill och foton i webbstorlek. Görs om med `forbered.py`.
- `cache/` – hålbilderna med inritade tees, så att bygget fungerar utan Lantmäteriets data.
- `public/` – det som publiceras. `qr-lankar.csv` – adresserna till QR-koderna på teeskyltarna.

## Kör
```
python hemsidor/glasriket/bygg.py                        # bygger och kontrollerar länkar, bilder, alt-text
python hemsidor/glasriket/bygg.py --lansering-kontroll   # stoppar om något saknas inför lansering
python hemsidor/glasriket/bygg.py --forhandsvisning <mapp>   # kopia med relativa länkar
```

## Hålbilder kommer till automatiskt
När en färdig hålbild läggs i `klubbar/glasriket/halbilder/hal-NN-malad.webp` och bygget körs, får
hålet sin bild på hålsidan och på banöversikten. Tees ritas in ur hålfilen (`hal-NN.yaml`) och
Lantmäteriets ortofoto (`data/glasriket/`). Saknas bilden byggs sidan utan bild och bygget
skriver en VARNING – sidan visar aldrig en trasig bild. Saknas Lantmäteriets data visas bilden
utan inritade tees (varning).

## Flaggor överst i `bygg.py`
- `LANSERAD` – False ger noindex och stänger ute sökmotorer.
- `DOMAN` – sajtens adress (kanoniska länkar, sitemap, QR-länkar).
- `BOKNING_URL` – "Boka starttid" (i dag Min Golf).
- `PLAUSIBLE_DOMAN` – cookiefri besöksräknare. None = avstängd.
- `VARD`, `ORGNR` – står i integritetspolicyn.

## Hålsponsorer
Sponsor läggs in per hål i `data/hal.yaml` (eller hålkortet):
`sponsor: {name: "Företag AB", url: "https://…", logo: "sponsorer/foretag.svg"}` (loggan relativt
`klubbar/glasriket/`, i en färg). Då visas "Företag AB-hålet" överst på hålsidan. Utan sponsor: inget fält.

## Sponsorstatistik
QR-koden på skylten pekar på `…/banan/hal-NN/?q=hNN` (adressen bestäms på ett ställe:
`golfholes/statistik.py`, `qr_lank`, som skylten, prospektet och `qr-lankar.csv` använder).
Med Plausible påslaget registreras ett "QR-besök" med egenskapen `q` = hNN och klick på
sponsorns länk som "Sponsorklick" med `hal` = hNN – samma namn som sponsorrapporten läser. `statistik.py` hämtar sidvisningar och QR-besök per hål för en
period till en CSV (se instruktionerna överst i filen).

## Regler för innehållet
- Riktiga uppgifter från klubben, aldrig platshållare. Saknas något: fråga klubben.
- Inga personer på bilder. Inga märkningar på eller vid bilder; sidfoten säger bara "Vissa bilder är visualiseringar."
  Lantmäteriets källtext i sidfoten och vid varje hålbild.
- Klubbens texter i klubbens röst. Inga löften om fler rundor eller medlemmar.

## Publicering
`netlify.toml` publicerar `public/` utan byggsteg. Formulären är förberedda för Netlify Forms
(aviseringar till info@glasriketsgk.se ställs in hos Netlify). Domänen pekas om när klubben bestämt.
