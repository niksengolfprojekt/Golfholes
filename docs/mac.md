# Installera på Mac Pro (en gång, ca 20 minuter)

Claude kan göra detta åt dig via länken till Claude-appen. Om du gör det själv:

1. **Öppna Terminal** (Program → Verktygsprogram → Terminal).
2. **Installera Homebrew** (pakethanterare) – klistra in raden från [brew.sh](https://brew.sh) och följ instruktionerna.
3. **Installera Python och git:**
   ```bash
   brew install python git
   ```
4. **Hämta projektet:**
   ```bash
   cd ~/Documents
   git clone https://github.com/niksengolfprojekt/Golfholes.git
   cd Golfholes
   ```
5. **Installera det som behövs:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install pyyaml pillow segno playwright pytest
   playwright install chromium
   ```
6. **Testa:**
   ```bash
   python -m pytest
   python -m golfholes skylt klubbar/exempel-ekbacka/hal-07.yaml
   open output/exempel-ekbacka/skylt/skylt-hal-07.png
   ```

Varje gång du öppnar en ny Terminal: `cd ~/Documents/Golfholes && source .venv/bin/activate`.

## Senare (flygfilmer)
Blender installeras från [blender.org](https://www.blender.org) när vi bygger 3D-steget.
