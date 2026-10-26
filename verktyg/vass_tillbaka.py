"""Lägger tillbaka riktig vegetation i vatten (vass, näckrosor) som AI:n tagit bort,
från en tidigare inpassad bild där den finns kvar. Bara inom en ruta (andelar av bilden).

    python verktyg/vass_tillbaka.py <med-vass.webp> <utan-vass.webp> <ut.webp> x0,x1,y0,y1
"""
import sys

import numpy as np
from PIL import Image, ImageFilter

kalla, mal, ut, ruta = sys.argv[1:5]
x0f, x1f, y0f, y1f = (float(v) for v in ruta.split(","))
A = np.asarray(Image.open(kalla).convert("RGBA")).astype(np.float32)
B = np.asarray(Image.open(mal).convert("RGBA")).astype(np.float32)
h, w = A.shape[:2]
x0, x1, y0, y1 = int(x0f * w), int(x1f * w), int(y0f * h), int(y1f * h)
veg = (A[..., 1] > A[..., 2] + 25) & (A[..., 0] > A[..., 2])   # gulgrön vegetation i källan
vatten = B[..., 2] > B[..., 0] + 15                              # vatten i målet
m = np.zeros((h, w), bool)
m[y0:y1, x0:x1] = (veg & vatten)[y0:y1, x0:x1]
mi = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(6))
M = (np.asarray(mi, np.float32) / 255)[..., None]
Image.fromarray((B * (1 - M) + A * M).clip(0, 255).astype(np.uint8), "RGBA").save(ut, quality=92)
print(ut, int(m.sum()), "px")
