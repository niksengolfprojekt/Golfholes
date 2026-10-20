"""Lantmäteriets Laserdata Skog (punktmoln, COPC/LAZ) → trädhöjd per ruta.

Markhöjdmodellen saknar träd. Laserpunkterna har dem: varje träds topp, form och
glipor finns med, så 3D-vyn kan visa de riktiga träden i stället för en gissad skog.
Kräver laspy + lazrs (läses bara här, resten av koden klarar sig utan).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

STAC = "https://api.lantmateriet.se/stac-hojd/v1/collections/dsm-skoglig-copc/items"
BRUS = {7, 18}  # LAS-klass för brus (låg/hög) – skippas


def ytor(laz: str | Path, bbox: tuple[float, float, float, float], res: float = 0.5):
    """Högsta punkten per ruta (ytmodell) inom bbox. Returnerar (yta, e0, n0, res);
    rutor utan punkter blir NaN."""
    import laspy

    e_min, n_min, e_max, n_max = bbox
    w, h = int(np.ceil((e_max - e_min) / res)), int(np.ceil((n_max - n_min) / res))
    yta = np.full(h * w, -np.inf, np.float32)
    with laspy.open(laz) as f:
        for bit in f.chunk_iterator(2_000_000):
            x, y, z = np.asarray(bit.x), np.asarray(bit.y), np.asarray(bit.z, np.float32)
            k = (x >= e_min) & (x < e_max) & (y > n_min) & (y <= n_max)
            k &= ~np.isin(np.asarray(bit.classification), list(BRUS))
            if not k.any():
                continue
            cx = ((x[k] - e_min) / res).astype(int)
            cy = ((n_max - y[k]) / res).astype(int)
            np.maximum.at(yta, np.clip(cy, 0, h - 1) * w + np.clip(cx, 0, w - 1), z[k])
    yta = yta.reshape(h, w)
    yta[np.isinf(yta)] = np.nan
    return yta, e_min, n_max, res


def tradhojd(laz: str | Path, mark: np.ndarray, bbox, res: float = 0.5, min_m: float = 2.0) -> np.ndarray:
    """Trädhöjd över mark (m) på samma rutnät som `mark`. Under min_m räknas som mark
    (gräs, buskar, flaggstänger)."""
    yta = ytor(laz, bbox, res)[0]
    yta = np.pad(yta, ((0, max(0, mark.shape[0] - yta.shape[0])), (0, max(0, mark.shape[1] - yta.shape[1]))),
                 constant_values=np.nan)[: mark.shape[0], : mark.shape[1]]
    # tomma rutor (glest moln) fylls med grannens värde så kronorna blir hela
    for _ in range(2):
        tom = np.isnan(yta)
        if not tom.any():
            break
        p = np.pad(yta, 1, constant_values=np.nan)
        gr = np.nanmax(np.stack([p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]]), axis=0)
        yta[tom] = gr[tom]
    h = np.nan_to_num(yta - mark, nan=0.0)
    return np.where(h >= min_m, h, 0.0).astype(np.float32)


def vatten_och_trad(laz: str | Path, dem: str | Path, bbox, res: float = 1.0, min_m: float = 2.0):
    """Vatten och träd ur laserpunkterna, på ett rutnät med `res` m (övre vänstra hörn
    = bbox[0], bbox[3]). Vatten = rutor där laserpulsen inte kom tillbaka (vatten
    reflekterar inte) eller punkter klassade som vatten (LAS 9). Mörka skuggor, tak och
    asfalt som färgen tar för vatten har vanliga markpunkter och faller bort.
    Returnerar (vatten, tradhojd_m)."""
    import laspy
    from .lantmateriet import read_window

    e_min, n_min, e_max, n_max = bbox
    w, h = int(np.ceil((e_max - e_min) / res)), int(np.ceil((n_max - n_min) / res))
    antal = np.zeros(h * w, np.int32)
    vatten = np.zeros(h * w, np.int32)
    with laspy.open(laz) as f:
        for bit in f.chunk_iterator(2_000_000):
            x, y = np.asarray(bit.x), np.asarray(bit.y)
            k = (x >= e_min) & (x < e_max) & (y > n_min) & (y <= n_max)
            if not k.any():
                continue
            c = np.asarray(bit.classification)[k]
            i = np.clip(((n_max - y[k]) / res).astype(int), 0, h - 1) * w + \
                np.clip(((x[k] - e_min) / res).astype(int), 0, w - 1)
            np.add.at(antal, i[~np.isin(c, list(BRUS))], 1)
            np.add.at(vatten, i[c == 9], 1)
    antal, vatten = antal.reshape(h, w), vatten.reshape(h, w)
    vm = (antal == 0) | (vatten * 2 >= np.maximum(antal, 1))

    d, de0, dn0, dr = read_window(dem, bbox)
    d = d.astype(np.float32).reshape(d.shape[0], d.shape[1])
    yy, xx = np.mgrid[:h, :w]
    ix = np.clip(((e_min + (xx + 0.5) * res - de0) / dr).astype(int), 0, d.shape[1] - 1)
    iy = np.clip(((dn0 - (n_max - (yy + 0.5) * res)) / dr).astype(int), 0, d.shape[0] - 1)
    th = tradhojd(laz, d[iy, ix], bbox, res=res, min_m=min_m)
    return vm, th


def till_fonster(m: np.ndarray, bbox, res: float, f) -> np.ndarray:
    """Lägger ett laserrutnät (övre vänstra hörn bbox[0], bbox[3]) på fönstrets pixlar."""
    h, w = f.rgbn.shape[:2]
    yy, xx = np.mgrid[:h, :w]
    ix = np.clip(((f.e0 + (xx + 0.5) * f.res - bbox[0]) / res).astype(int), 0, m.shape[1] - 1)
    iy = np.clip(((bbox[3] - (f.n0 - (yy + 0.5) * f.res)) / res).astype(int), 0, m.shape[0] - 1)
    return m[iy, ix]
