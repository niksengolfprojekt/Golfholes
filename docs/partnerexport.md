# Partnerexport – hålsponsorer till digitala partnerkanaler

Digitala partnerkanaler (t.ex. appar där golfaren ser hålet) får klubbens hålsponsorer som
en fil per hål. Partnern ritar hålen själv – exporten innehåller **inga hålbilder och ingen
geometri**, bara vem som sponsrar vilket hål och hur loggan ska visas.

## Kör

```
python -m golfholes partnerexport klubbar/<klubb>
```

Resultat i `output/<klubb>/partner/`:

```
hal-01.json … hal-18.json        en fil per hål
loggor/hal-03-emtec.svg          loggan i en färg (vektor)
loggor/hal-03-emtec.png          loggan i en färg på ljus platta, 1200 × 600 px
<klubb>-partnerexport.zip        allt ovan i en fil att skicka
```

Kommandot skriver "OBS: …" för allt som saknas (logga, webbadress, avtalsperiod, par, banans
namn). Skicka inte exporten förrän alla OBS är åtgärdade.

## Underlag i klubb.yaml

```yaml
club: Glasrikets Golfklubb
bana: <banans namn>
holes:
  - {hole: 3, par: 4}
sponsors:
  3:
    name: Emtec elinstallationer
    url: emtec.se                  # sponsorns webbplats
    logo: loggor/emtec.svg         # helst SVG; PNG går men ger en varning
    naming_rights: true            # false = inget "[Företag]-hålet"
    giltig_fran: 2027-04-01        # avtalsperiodens början
    giltig_till: 2027-10-31        # och slut
```

## Format, version 1.0

```json
{
  "format": "tacada-halsponsor/1.0",
  "exporterad": "2026-10-23",
  "klubb": "Ekbacka Golfklubb",
  "bana": "Ekbackabanan",
  "hal": 14,
  "par": 4,
  "sponsor": {
    "namn": "Nordvik",
    "halnamn": "Nordvik-hålet",
    "logga_svg": "loggor/hal-14-nordvik.svg",
    "logga_png": "loggor/hal-14-nordvik.png",
    "lank": "https://nordvik.se/?utm_source=partnerapp&utm_medium=halsponsor&utm_campaign=testklubb-hal-14",
    "giltig_fran": "2027-04-01",
    "giltig_till": "2027-10-31"
  }
}
```

(Exemplet är den påhittade testklubben i `tests/fixtures/testklubb/`. Filer från en testklubb
har dessutom `"testdata": true`.)

| Fält | Typ | Betydelse |
| --- | --- | --- |
| `format` | text | Formatets namn och version. Ändras bara om fälten ändras. |
| `exporterad` | datum (ÅÅÅÅ-MM-DD) | När filen gjordes. |
| `klubb` | text | Klubbens namn. |
| `bana` | text eller null | Banans namn (klubbar med flera banor). |
| `hal` | heltal | Hålnummer 1–18. |
| `par` | heltal eller null | Hålets par. |
| `sponsor` | objekt eller null | null = hålet har ingen sponsor just nu. |
| `sponsor.namn` | text | Företagets namn som det ska skrivas. |
| `sponsor.halnamn` | text eller null | Hålets namn, alltid "[Företag]-hålet". null om sponsorn inte har namnrätt. |
| `sponsor.logga_svg` | sökväg eller null | Loggan som vektor, i **en färg** (#1d2a22). Sökvägen är relativ till zip-filen. |
| `sponsor.logga_png` | sökväg eller null | Samma logga i en färg, centrerad på en ljus platta (#f6f4ee), 1200 × 600 px. |
| `sponsor.lank` | URL eller null | Sponsorns webbplats med utm-parametrar: `utm_source=partnerapp`, `utm_medium=halsponsor`, `utm_campaign=<klubb>-hal-NN`. Sponsorns egna parametrar behålls. |
| `sponsor.giltig_fran` / `giltig_till` | datum eller null | Visa loggan bara mellan dessa datum (båda inräknade). |

## Regler för partnern

- Loggan visas alltid i en färg på ljus platta – samma utseende för alla sponsorer.
- Visa bara sponsorn inom `giltig_fran`–`giltig_till`.
- Länken används oförändrad, så att sponsorn ser trafiken i sin egen statistik.
- Partnern skickar varje månad visningar och klick per hål som CSV:
  `klubb,bana,hal,manad,visningar,klick` (se `docs/statistik.md`).
