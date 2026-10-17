# Stilbild med originalets alfakanal: exakt samma siluett och uttoning som spikade hål 14-kortet.
import sys
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
orig = Image.open('/home/user/Golfholes/klubbar/glasriket/typbilder/hal-14.webp').convert('RGBA')
im = Image.open(src).convert('RGB').crop((100, 100, 1292, 2214))
im.putalpha(orig.split()[-1]); im.save(dst)
