# Partnerprogrammet – klubbens eget sponsorerbjudande

Klubben säljer, klubben behåller hela intäkten. TACADA tar fram materialet och levererar plattor, inlägg,
hålsidor och årsrapporter. Ett kommando bygger allt för en klubb:

```
python -m golfholes partnerprogram klubbar/<klubb> [--ut mapp] [--bara deck,manual,...] [--logg fil.xlsx]
```

## Var sakerna står

| Fil | Vad |
| --- | --- |
| `golfholes/partnerprogram/standard.yaml` | Produktbiblioteket, samma för alla klubbar: varje produkt med namn, vem den passar, varför den köps, vad som ingår, ytor, leverans, TACADA:s material, pris, kostnad, tid, kombinationer och uppföljning. Villkor, partnerveckans ytor och administrationen. |
| `klubbar/<klubb>/partnerprogram.yaml` | Klubbens val: aktiva produkter, priser (prismodell), premiumhål med sin extra yta, ändrade namn och texter, partnerveckor, tävlingar, räknemall för företagsdagen, dagens läge, exempelföretaget och bilderna. |
| `klubbar/<klubb>/klubb.yaml` | Namn, färger, typsnitt, loggor, hål, kontakt, `sponsring.status` per hål. |
| `data/<klubb>/partnerprogram/partneroversikt-<säsong>.xlsx` | Klubbens levande lista (skapas första gången): partners och status, säljkontakter, leveranser, mätvärden, ronder. Checkas inte in. |

## Det som byggs (utmapp, standard `output/<klubb>/partnerprogram/`)

| Del | Fil |
| --- | --- |
| A Huvudpresentation, 16 sidor | `A-huvudpresentation-<Exempel>.pdf` (med påhittat exempelföretag) och `A-huvudpresentation.pdf` (neutral, "[Ert företag]") + `bilder/A-NN.png` |
| B Prospekt | `B-prospekt/hal-NN.pdf` och `hal-NN-<Exempel>.pdf` per hål, `B-prospekt/produkter/<produkt>.pdf` per verksamhetsprodukt |
| C Försäljningsmanual | `C-forsaljningsmanual.pdf`: vem man ringer, mötet, säg/säg aldrig, invändningar, dagens sponsorer, nej-stegen, förnyelse, sex mejlutkast |
| D Årsrapport | `D-arsrapport-mall.pdf` + `D-rapporter/<plats>-<företag>.pdf` för varje partner i översikten |
| E Årskalender | `E-arskalender.pdf` (A3): månad för månad, veckorutin, vem gör vad, partnerveckorna |
| F Prislista och översikt | `F-prislista.pdf`, `F-partneroversikt.pdf` (sålt, reserverat, ledigt) |
| Beslutsunderlag | `beslutsunderlag.pdf`: ekonomin, räkneexempel, prismodeller, produktekonomi, besluten klubben måste ta |
| Framtida kanal | `framtida-kanal.pdf` (neutral) och `INTERNT-framtida-kanal.pdf` (med partnerns namn, visas aldrig externt) |

## Reglerna som koden håller

- **En yta säljs en gång.** Partnerveckorna räcker eller så stoppar bygget. Huvudpartnern får golfveckan.
- **Premiumhål kräver en verklig extra yta** (`extra` i `premiumhal`), annars stopp.
- **Ingen skärm lovas** om `partnerveckor.skarm` är `false`.
- **Uppmätt, uppskattat och levererat hålls isär** i rapporten. Tom cell i översikten blir "fylls i".
  Ett mätvärde utan källa stoppas. Exponering = visningar, aldrig personer.
- **Inga löften** om fler kunder, medlemmar eller ronder. Intäkter är räkneexempel.
- **Flygfilmen** ingår först när den är färdig och godkänd, och säljs aldrig som levererad.
- **Den digitala partnerkanalen** nämns bara som "under utveckling" i externt material.
- **Exempelföretaget** är påhittat (Glasriket: Nordvik). Riktiga företag bara med deras tillstånd.

## Ny klubb

1. Kopiera `klubbar/glasriket/partnerprogram.yaml` till klubbens mapp.
2. Ändra aktiva produkter, priser, premiumhål (bara hål med en extra yta), partnerveckor, tävlingar,
   `idag` (sålda hål och pris i dag), kontakt och bilder (ögonhöjdsbilder som matchar banan, hålsidans skärmbild).
3. Kör kommandot och läs `beslutsunderlag.pdf`: klubben tar besluten där innan försäljningen börjar.
4. Smakgranska presentationen och prospekten innan något visas.
