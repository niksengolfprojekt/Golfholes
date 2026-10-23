# Sponsorstatistik – så kommer siffrorna in

Varje hålsponsor får efter säsongen en sida med hålbilden, sitt namn och hur många
gånger hålet och loggan har visats, kanal för kanal. Den här sidan beskriver exakt vad
klubben och vi (TACADA) måste göra för att siffrorna ska finnas när säsongen är slut.

**Viktigt om orden:** siffrorna heter alltid **visningar** – antal gånger något har visats.
Vi skriver aldrig "personer", "besökare" eller "unika". En person kan se hålet många gånger.

## Varifrån siffrorna kommer

| Kanal på sponsorns sida | Var siffran kommer ifrån | Vem gör vad |
| --- | --- | --- |
| **Tee-skylten** (märkt *uppskattning*) | Klubbens antal ronder under året × andelen ronder som spelar hålet. På en 18-hålsbana spelar alla ronder alla hål, så siffran blir = ronderna. | Klubben lämnar antalet ronder efter säsongen. |
| **Hålsidan på webben** | Sidvisningar av hålets sida (t.ex. `/banan/hal-03/`) från mätverktyget Plausible. Klick på sponsorns länk räknas också. | Vi sätter upp mätningen, klubben/vi exporterar varje månad. |
| **varav via QR-koden på skylten** | De sidvisningar som kom via QR-koden på tee-skylten. QR-koden pekar på `…/banan/hal-03/?q=h03`. | Sker automatiskt när QR-koden och mätningen är på plats. |
| **Digital partnerkanal** | Visningar och klick per hål och månad från de digitala partnerkanaler där sponsorns logga syns. | Partnern skickar en fil varje månad (se nedan). |

## Steg för steg

### En gång, innan säsongen (vi gör)

1. **Skaffa ett Plausible-konto** (plausible.io, betaltjänst per månad – kolla aktuellt pris,
   eller klubbens eget konto om de redan har ett). Lägg till klubbens webbplats, t.ex. `glasriketsgk.se`.
2. **Slå på egna egenskaper i Plausible:** Site settings → *Custom properties* → lägg till
   egenskaperna `q` och `hal`. Lägg till målet (Goal) *Sponsorklick* av typen *Custom event*.
3. **Skriv in domänen i klubbens `klubb.yaml`:**
   ```yaml
   statistik:
     plausible_doman: glasriketsgk.se
   ```
   Då lägger `python -m golfholes webb klubbar/<klubb>` in mätkoden på alla hålsidor
   automatiskt. Byggs hemsidan på annat sätt måste samma mätkod läggas in där – den
   finns i funktionen `matkod()` i `golfholes/statistik.py`. Glasrikets hemsida
   (`hemsidor/glasriket/`) har egen kod i `tillgangar/js/site.js` med samma namn: händelsen
   *QR-besök* med `q` = hNN och *Sponsorklick* med `hal` = hNN. Lägg där också till målet
   *QR-besök* (Custom event) och sätt `PLAUSIBLE_DOMAN` i `bygg.py`.
4. **Hålsidorna ska ligga på adresser som slutar på `/hal-01/`, `/hal-02/` … `/hal-18/`**,
   på klubbhemsidorna under `/banan/` (Glasriket: `https://www.glasriketsgk.se/banan/hal-03/`).
   Det är så koden känner igen vilket hål en sidvisning hör till.
5. **QR-koden på varje tee-skylt** ska peka på `https://<klubbens-domän>/banan/hal-NN/?q=hNN`
   (hål 3: `/banan/hal-03/?q=h03`). Adressen bestäms på ett enda ställe, `qr_lank()` i
   `golfholes/statistik.py`, som skylten (`skylt`), prospektet (`prospekt`) och hemsidans
   `qr-lankar.csv` använder. Ordningen: `sponsring.halsida` i `klubb.yaml` (mall med `{hal:02d}`)
   om den finns, annars `web_base` + `/hal-NN/` (sidorna som `webb` bygger), annars
   `web` + `/banan/hal-NN/`. Det som krävs är att `web` i `klubb.yaml` är klubbens riktiga
   webbadress, och att `segno` är installerat så att QR-koden är äkta (annars blir den en
   platshållare som aldrig får tryckas).
6. **Testa:** skanna QR-koden med mobilen, öppna Plausible och se att besöket syns under
   *Custom properties → q → h03* inom någon minut.
7. **Skriv in sponsorerna i `klubb.yaml`** (namn, webbadress, logga, avtalsperiod):
   ```yaml
   sponsors:
     3:
       name: Nordvik            # påhittat exempel
       url: nordvik.se
       logo: loggor/nordvik.svg
       naming_rights: true
       giltig_fran: 2027-04-01
       giltig_till: 2027-10-31
   ```
8. **Avtala med varje digital partnerkanal** att de skickar en månadsfil i formatet nedan.

### Varje månad under säsongen (ca 10 minuter)

1. **Exportera från Plausible:** öppna klubbens sida i Plausible, välj *Month* för förra
   månaden, klicka på exportknappen (pil nedåt). Du får en zip-fil.
2. **Döp om zip-filen** så att månaden står i namnet: `plausible-2027-05.zip`.
3. **Lägg filen i projektmappen** `glasriket/statistik/2027/plausible/` (byt klubb och år).
4. **Partnerkanalens fil** läggs i `glasriket/statistik/2027/partner/`. Format, en rad per hål och månad:
   ```
   klubb,bana,hal,manad,visningar,klick
   Glasrikets Golfklubb,,3,2027-05,2310,41
   ```
   Kolumnen `bana` får vara tom. Flera partners = flera filer.
5. Glöm inte en månad – Plausible kan exportera i efterhand, men det är lätt att tappa bort.

### Efter säsongen

1. **Be klubben om antalet ronder** för året och skriv in det i `klubb.yaml`:
   ```yaml
   ronder_per_ar:
     2027: 21500
   ```
   Spelar inte alla ronder hålet (t.ex. många 9-hålsronder) sätts andelen:
   `statistik: {andel_spelar_halet: 0.8}`.
2. **Be Claude köra rapporten:**
   ```
   python -m golfholes sponsorrapport klubbar/glasriket --sasong 2027 --kalla /mnt/project-files/glasriket/statistik/2027
   ```
   Det ger en sida per sponsor som PNG och PDF, plus `sammanstallning-2027.csv` med alla siffror,
   i `output/glasriket/sponsorrapport/2027/`.
3. **Läs igenom varningarna** ("OBS: …") som kommandot skriver ut – de säger vilka siffror som saknas.
   Saknas en kanal står det på sponsorns sida att det inte finns någon siffra för den kanalen.
4. **Skicka sidan till sponsorn** tillsammans med förnyelseerbjudandet. Rapporten är ett
   underlag för sponsorn, inte ett löfte om nästa år.

## Bra att veta

- **TESTDATA:** ligger det en fil `TESTDATA.txt` i statistikmappen, eller står `testdata: true`
  i `klubb.yaml`, får rapporten ett rött band "TESTDATA". En sådan sida får aldrig gå till en sponsor.
  Testsiffrorna ligger i `tests/fixtures/testklubb/` (påhittade klubben och sponsorn Nordvik).
- **QR-besöken räknas inte två gånger.** De ingår i hålsidans siffra och visas som "varav".
- **Tee-skylten räknas inte in i "Digitala visningar"**, eftersom den är en uppskattning.
- **Plausible-exporten:** koden läser `pages.csv` (sidvisningar) och tabellen med egna egenskaper
  (`q` och `hal`). Kontrollera första riktiga exporten (maj 2027) mot rapporten, så att
  kolumnnamnen stämmer med Plausibles aktuella format.
- **Integritet:** Plausible använder inga kakor och sparar inga personuppgifter, så klubben
  behöver ingen kakbanner för mätningen. Nämn mätningen i klubbens integritetspolicy.
