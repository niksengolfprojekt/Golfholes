# Banrundan (startsideprov 2026-10-25)

Hela banan ovanifrån (Erics banbild "A-gyllene"), ett och ett halvt varv runt banan när man scrollar, ner på tee 56 på hål 14 och sedan tar vybilden från tee över.

Datafiler läggs bredvid index.html (checkas inte in, de visar en riktig klubbs bana):
- `karta.webp`: banbilden utan nummerbrickor och källrad (borttagna med inpaint), 2048×3072.
  Georeferens: 0,372 m/px, övre vänstra hörn E 491404,48 N 6306830,72 (SWEREF 99 TM), hittad med korrelation mot ortofotot. Hål 14:s bricka hamnar 1,5 m från tee 56.
- `terrang.json`: Markhöjdmodellen samplad var 3:e meter över samma yta (uint16 cm över `bas`, base64).
- `tee14.webp`: godkänd ögonhöjdsvy v2, hål 14 tee.
- `fonts/`: Marcellus och Inter.

v2 (Eric 2026-10-25 22:50): halvt varv i stället för ett och ett halvt. Träden höjda: `terrang.json` är nu marken plus trädkronornas höjd ur Laserdata Skog (rutan y26a023-63050_4900_25, högsta punkt per 2 m minus markhöjden, under 2,5 m räknas som mark), tonad till noll i pappersranden. Vybilden tar över mellan 87 och 93 % av scrollen.
