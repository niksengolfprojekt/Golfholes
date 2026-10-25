# Banrundan (startsideprov 2026-10-25)

Hela banan ovanifrån (Erics banbild "A-gyllene"), ett och ett halvt varv runt banan när man scrollar, ner på tee 56 på hål 14 och sedan tar vybilden från tee över.

Datafiler läggs bredvid index.html (checkas inte in, de visar en riktig klubbs bana):
- `karta.webp`: banbilden utan nummerbrickor och källrad (borttagna med inpaint), 2048×3072.
  Georeferens: 0,372 m/px, övre vänstra hörn E 491404,48 N 6306830,72 (SWEREF 99 TM), hittad med korrelation mot ortofotot. Hål 14:s bricka hamnar 1,5 m från tee 56.
- `terrang.json`: Markhöjdmodellen samplad var 3:e meter över samma yta (uint16 cm över `bas`, base64).
- `tee14.webp`: godkänd ögonhöjdsvy v2, hål 14 tee.
- `fonts/`: Marcellus och Inter.
