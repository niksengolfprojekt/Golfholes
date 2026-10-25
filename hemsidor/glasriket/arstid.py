"""Hålbilden i fyra årstider – samma målning, bara färgerna byts.

Formen rörs aldrig: varje pixel behåller sin plats och sin ljushet (penseldrag, klippränder,
skuggor), bara kulören byts efter vad pixeln är (gräs, träd, lövträd, sand). Spelinformationen
(röda och gula prickar, flaggan) skyddas och lämnas orörd.

    python hemsidor/glasriket/arstid.py in.webp utmapp/     # skriver in-var.webp, in-sommar.webp …
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ARSTIDER = ("var", "sommar", "host", "vinter")


def _hsv(a: np.ndarray):
    mx, mn = a.max(-1), a.min(-1)
    d = mx - mn + 1e-9
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    return h, (mx - mn) / (mx + 1e-9), mx


def _brus(storlek: tuple[int, int], skala: int, fro: int) -> np.ndarray:
    """Mjukt fläckmönster 0–1 (klungor av lövträd), samma för en given bild varje gång."""
    w, h = storlek
    rng = np.random.default_rng(fro)
    liten = Image.fromarray((rng.random((max(2, h // skala), max(2, w // skala))) * 255).astype(np.uint8))
    stor = liten.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(skala / 3))
    n = np.asarray(stor).astype(float) / 255
    return (n - n.min()) / (n.max() - n.min() + 1e-9)


def _box(x: np.ndarray, r: int) -> np.ndarray:
    """Medelvärde i en ruta (2r+1)², räknat med summerad tabell (exakt, inga avrundningar)."""
    p = np.pad(x.astype(float), r + 1, mode="edge")
    c = p.cumsum(0).cumsum(1)
    k = 2 * r + 1
    s = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return s[: x.shape[0], : x.shape[1]] / (k * k)


def _lokal_spridning(lum: np.ndarray, r: int = 4) -> np.ndarray:
    m = _box(lum, r)
    return np.sqrt(np.clip(_box(lum * lum, r) - m * m, 0, None))


def _tathet(mask: np.ndarray, r: int) -> np.ndarray:
    """Andel av pixlarna inom r px som ingår i masken."""
    return _box(mask, r)


def _mjuk(mask: np.ndarray, r: float = 3) -> np.ndarray:
    im = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im).astype(float)[..., None] / 255


def _ton(lum: np.ndarray, farg, ref: float) -> np.ndarray:
    """Färgen `farg` med pixelns egen ljushet (penseldragen syns kvar)."""
    return np.clip(np.asarray(farg, float)[None, None, :] * (lum / ref)[..., None] ** 0.85, 0, 1)


def arstidsbild(im: Image.Image, arstid: str) -> Image.Image:
    rgba = np.asarray(im.convert("RGBA")).astype(float)
    a = rgba[..., :3] / 255
    alfa = rgba[..., 3:]
    h, s, v = _hsv(a)
    lum = a @ np.array([0.299, 0.587, 0.114])
    spridning = _lokal_spridning(lum)

    # Spelinformation: kraftiga, platta färgfläckar (prickar, flagga) – lämnas orörda
    rod = (s > 0.55) & ((h < 15) | (h > 340)) & (v > 0.45)
    gul = (s > 0.7) & (h > 38) & (h < 58) & (v > 0.75) & (spridning < 0.04)
    bla = (s > 0.35) & (h > 190) & (h < 250) & (v > 0.25)
    # Bara små, ensamma fläckar räknas som spelinformation – inte lövträdens stora gula klungor
    r = max(8, round(min(im.size) / 52))  # prickens radie är ungefär 1/52 av bildens bredd
    farg = (rod | gul | bla) & (_lokal_spridning(lum, 2) < 0.015)   # prickarna är helt jämnt färgade
    kompakt = (_tathet(farg, r) > 0.25) & (_tathet(farg, 3 * r) < 0.15)
    # prickarna själva plus deras ljusa/mörka kant – inte gräset runt omkring
    nara = _tathet(kompakt, r + 6) > 0
    skydd = nara & ((rod | gul | bla) | (s < 0.25))

    gras = (h > 55) & (h < 115) & (s > 0.18) & (lum > 0.28) & ~skydd
    lov = (h > 12) & (h < 60) & (s > 0.28) & (lum > 0.1) & ~skydd & ~gras
    trad = (lum <= 0.28) & ~skydd & ~lov
    sand = (s < 0.2) & (lum > 0.7) & ~skydd
    if arstid == "sommar":
        # lövträdens höstfärger blir sommargröna, ljusheten behålls
        ut = a * (1 - _mjuk(lov)) + _ton(lum, (0.27, 0.43, 0.2), 0.6) * _mjuk(lov)
    elif arstid == "var":
        frisk = a * 0.4 + _ton(lum, (0.5, 0.66, 0.26), 0.5) * 0.6
        ut = np.where(gras[..., None], frisk, a)
        # lövträden ljust nyutslagna
        ut = ut * (1 - _mjuk(lov)) + _ton(lum, (0.47, 0.62, 0.27), 0.6) * _mjuk(lov)
    elif arstid == "host":
        mattat = a * 0.6 + _ton(lum, (0.55, 0.56, 0.3), 0.5) * 0.4
        ut = np.where(gras[..., None], mattat, a)
        # ungefär hälften av de mörka träden (lövträden) får rost och guld, i mjuka klungor
        klunga = np.clip((_brus(im.size, 40, 3) - 0.4) / 0.2, 0, 1)[..., None]
        vikt = klunga * _mjuk(trad & (lum > 0.05), 1.5) * 0.72
        val = _brus(im.size, 18, 11)[..., None]
        farg = _ton(lum, (0.75, 0.5, 0.14), 0.2) * val + _ton(lum, (0.62, 0.26, 0.1), 0.2) * (1 - val)
        ut = ut * (1 - vikt) + farg * vikt
        ut = ut * (1 - _mjuk(lov)) + np.clip(a * np.array([1.06, 0.86, 0.75]), 0, 1) * _mjuk(lov)
    elif arstid == "vinter":
        sno = np.array([0.93, 0.95, 0.97])
        # gräs, green och bunkrar under snö; klippränderna syns som svag skugga
        rel = (lum - 0.5) * 0.45
        snoyta = np.clip(sno[None, None, :] + rel[..., None] * np.array([1, 1, 0.9]), 0, 1)
        tackt = _mjuk(gras | sand, 1.2)
        ut = a * (1 - tackt) + snoyta * tackt
        # barrträd kalla och mörkt blågröna, med ett lätt lager snö
        kall = np.clip(np.stack([lum * 0.7 + 0.13, lum * 0.8 + 0.17, lum * 0.85 + 0.2], -1), 0, 1)
        snotacke = np.clip(_brus(im.size, 5, 5) * 1.6 - 0.6, 0, 1)[..., None] * np.clip(lum / 0.25, 0, 1)[..., None]
        traden = kall * (1 - snotacke * 0.4) + sno * snotacke * 0.4
        m = _mjuk(trad, 1.0)
        ut = ut * (1 - m) + traden * m
        # kala lövträd: grått och brunt
        kalt = np.stack([lum * 0.6 + 0.3, lum * 0.55 + 0.29, lum * 0.5 + 0.29], -1)
        ut = ut * (1 - _mjuk(lov)) + kalt * _mjuk(lov)
    else:
        raise ValueError(f"okänd årstid: {arstid}")
    ut = np.where(skydd[..., None], a, ut)
    rgba_ut = np.concatenate([np.clip(ut, 0, 1) * 255, alfa], -1).astype(np.uint8)
    return Image.fromarray(rgba_ut, "RGBA")


if __name__ == "__main__":
    kalla, mapp = Path(sys.argv[1]), Path(sys.argv[2])
    mapp.mkdir(parents=True, exist_ok=True)
    bild = Image.open(kalla)
    for a in ARSTIDER:
        arstidsbild(bild, a).save(mapp / f"{kalla.stem}-{a}.webp", quality=86)
