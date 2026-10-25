"""Skärpning för stil A (klarhet + mikrokontrast + skärpa) på en AI-målning före inpassningen.

    python verktyg/krisp.py in.png ut.png
"""
import sys
from PIL import Image, ImageFilter, ImageEnhance
src,dst=sys.argv[1:3]
im=Image.open(src).convert('RGBA'); a=im.getchannel('A'); rgb=im.convert('RGB')
rgb=rgb.filter(ImageFilter.UnsharpMask(radius=40,percent=30,threshold=0))   # klarhet
rgb=rgb.filter(ImageFilter.UnsharpMask(radius=6,percent=40,threshold=2))    # mikrokontrast
rgb=rgb.filter(ImageFilter.UnsharpMask(radius=1.4,percent=75,threshold=3))  # skärpa
rgb=ImageEnhance.Color(rgb).enhance(1.08); rgb=ImageEnhance.Contrast(rgb).enhance(1.05)
out=rgb.convert('RGBA'); out.putalpha(a); out.save(dst,quality=92)
