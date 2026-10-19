"""read_window mot små, egenbyggda GeoTIFF i samma format som Lantmäteriets COG."""
import struct
import zlib

import numpy as np

from golfholes.lantmateriet import hojd_utsnitt, read_window


def _tiff(path, a, pred, tile=4, e0=490000.0, n0=6310000.0, res=1.0):
    """Skriver en tiled, deflate-komprimerad GeoTIFF (little endian) med prediktor 2 eller 3."""
    h, w, spp = a.shape
    nb = a.dtype.itemsize
    tiles = []
    for ty in range(0, h, tile):
        for tx in range(0, w, tile):
            t = np.zeros((tile, tile, spp), a.dtype)
            blk = a[ty:ty + tile, tx:tx + tile]
            t[:blk.shape[0], :blk.shape[1]] = blk
            if pred == 3:  # MSB först per rad, sedan bytedifferens
                b = t.astype(">" + a.dtype.str[1:]).view(np.uint8).reshape(tile, tile * spp, nb)
                b = b.transpose(0, 2, 1).reshape(tile, -1)
                b = np.diff(b, axis=1, prepend=0).astype(np.uint8)
            else:
                b = np.diff(t, axis=1, prepend=0).astype(a.dtype).view(np.uint8)
            tiles.append(zlib.compress(b.tobytes()))
    fmt = 3 if a.dtype.kind == "f" else 1
    data_off = 8
    offs, pos = [], data_off
    for t in tiles:
        offs.append(pos)
        pos += len(t)
    extra = pos
    arrays = {324: ("L", offs), 325: ("L", [len(t) for t in tiles]), 258: ("H", [nb * 8] * spp),
              339: ("H", [fmt] * spp), 33550: ("d", [res, res, 0.0]),
              33922: ("d", [0.0, 0.0, 0.0, e0, n0, 0.0])}
    blobs, entries = b"", {}
    for tag, (c, vals) in arrays.items():
        raw = struct.pack("<" + c * len(vals), *vals)
        if len(raw) <= 4:
            entries[tag] = (c, len(vals), raw.ljust(4, b"\0"))
        else:
            entries[tag] = (c, len(vals), struct.pack("<I", extra + len(blobs)))
            blobs += raw
    for tag, v in {256: w, 257: h, 259: 8, 262: 2 if spp >= 3 else 1, 277: spp, 284: 1, 317: pred,
                   322: tile, 323: tile}.items():
        entries[tag] = ("H", 1, struct.pack("<H", v).ljust(4, b"\0"))
    typ = {"H": 3, "L": 4, "d": 12}
    ifd_off = extra + len(blobs)
    ifd = struct.pack("<H", len(entries))
    for tag in sorted(entries):
        c, n, v = entries[tag]
        ifd += struct.pack("<HHI", tag, typ[c], n) + v
    ifd += struct.pack("<I", 0)
    with open(path, "wb") as f:
        f.write(b"II*\0" + struct.pack("<I", ifd_off) + b"".join(tiles) + blobs + ifd)


def test_float_predictor_3(tmp_path):
    z = (180 + np.arange(10 * 9, dtype=np.float32).reshape(10, 9, 1) / 7).astype("<f4")
    p = tmp_path / "hojd.tif"
    _tiff(p, z, pred=3)
    a, e0, n0, res = read_window(p, (490002, 6309993, 490007, 6309998))
    assert (e0, n0, res) == (490002, 6309998, 1.0)
    assert np.array_equal(a, z[2:7, 2:7])
    h = hojd_utsnitt([p], (490000, 6309990, 490009, 6310000), tmp_path / "ut")
    assert h["lagst"] == round(float(z.min()), 1) and (tmp_path / "ut" / "hojd_skuggning.png").exists()


def test_rgb_predictor_2(tmp_path):
    rgb = np.random.default_rng(1).integers(0, 255, (9, 11, 4), dtype=np.uint8)
    p = tmp_path / "orto.tif"
    _tiff(p, rgb, pred=2, res=0.5)
    a, *_ = read_window(p, (490000, 6309995.5, 490005.5, 6310000))
    assert np.array_equal(a, rgb)
