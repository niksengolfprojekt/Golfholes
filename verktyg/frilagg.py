"""Frilägger en hålbild på krämvit botten: gör bakgrunden genomskinlig så att hålkortsmallen
kan lägga hålet på valfri bakgrund (ljus, mörk, poster).

  python verktyg/frilagg.py in.png ut.png [mjukhet] [--textkolumn]

--textkolumn tar bort textkolumnen till höger i hålkortet för hål 14 (Glasrikets typbild).

Originalet är tonat mot krämvitt i kanten: original = v * hål + (1 - v) * kräm.
Vi uppskattar tonningen v som en mjuk mask kring hålet och räknar tillbaka hålets färg."""
import sys
import numpy as np
from PIL import Image, ImageFilter

args = [a for a in sys.argv[1:] if not a.startswith("--")]
src, dst = args[0], args[1]
sigma = float(args[2]) if len(args) > 2 else 30
textkolumn = "--textkolumn" in sys.argv
im = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
H, W, _ = im.shape
bg = np.median(np.concatenate([im[:60, :60].reshape(-1, 3), im[-60:, -60:].reshape(-1, 3)]), axis=0)

# Textkolumnen bort (siffran börjar x≈1195 ovanför y 490, PAR-raden x≈1100, brödtexten x≈1034)
ys = np.arange(H)[:, None].astype(np.float32)
cut = np.interp(ys, [0, 420, 620, H], [1185, 1185, 1030, 1020])
xs = np.arange(W)[None, :]
keep = np.clip((cut + 40 - xs) / 230.0, 0, 1) ** 1.3 if textkolumn else np.ones((H, W), np.float32)

# Grov innehållsmask: allt som skiljer sig tydligt från bakgrunden, hål igenfyllda.
# Bilden förlängs i kanterna först, så att ett hål som går ut i bildkanten inte tonas där.
P = 120
dist = np.pad(np.abs(im - bg).max(axis=2), P, mode="edge")
M = Image.fromarray(((dist > 40) * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(7))
M = M.filter(ImageFilter.MaxFilter(81)).filter(ImageFilter.MinFilter(81))
M = M.filter(ImageFilter.MinFilter(int(sigma) | 1))
v = np.asarray(M.filter(ImageFilter.GaussianBlur(sigma))).astype(np.float32)[P:-P, P:-P] / 255
v = v * keep
alpha = np.clip((v - 0.04) / 0.96, 0, 1)
vv = np.maximum(v, 0.2)[..., None]
rgb = (im - (1 - vv) * bg) / vv
out = np.dstack([np.clip(rgb, 0, 255), alpha * 255]).astype(np.uint8)
img = Image.fromarray(out, "RGBA")
img = img.crop(img.getbbox())
print("bakgrund", bg, "storlek", img.size)
img.save(dst)
