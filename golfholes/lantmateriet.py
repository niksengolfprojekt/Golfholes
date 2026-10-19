"""Läser Lantmäteriets GeoTIFF (ortofoto och markhöjdmodell) och gör utsnitt.

Byggt på Pillow i stället för GDAL/rasterio, så att det fungerar både i molnet
och på Macen utan krånglig installation. Klarar GeoTIFF i SWEREF 99 TM med
standardtaggarna ModelPixelScale (33550) och ModelTiepoint (33922).

Typiskt flöde:
    python -m golfholes utsnitt klubbar/glasriket data/glasriket/orto/*.tif
    → data/glasriket/utsnitt/orto.jpg + orto.jgw  (öppnas i ritverktyget)
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # ortofoton är stora

TAG_SCALE = 33550
TAG_TIEPOINT = 33922


@dataclass
class GeoRaster:
    path: Path
    width: int
    height: int
    e0: float  # E för bildens övre vänstra hörn (pixelkant)
    n0: float  # N för bildens övre vänstra hörn
    sx: float  # meter per pixel i E
    sy: float  # meter per pixel i N (positivt tal)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (self.e0, self.n0 - self.height * self.sy, self.e0 + self.width * self.sx, self.n0)

    def to_pixel(self, e: float, n: float) -> tuple[float, float]:
        return ((e - self.e0) / self.sx, (self.n0 - n) / self.sy)


def open_geotiff(path: str | Path) -> GeoRaster:
    path = Path(path)
    with Image.open(path) as im:
        tags = im.tag_v2
        if TAG_SCALE not in tags or TAG_TIEPOINT not in tags:
            raise ValueError(f"{path.name} saknar georeferens (inte en GeoTIFF?)")
        sx, sy = float(tags[TAG_SCALE][0]), float(tags[TAG_SCALE][1])
        i, j, _k, x, y, _z = (float(v) for v in tags[TAG_TIEPOINT][:6])
        return GeoRaster(path, im.width, im.height, e0=x - i * sx, n0=y + j * sy, sx=sx, sy=sy)


def _intersects(a, b) -> bool:
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def mosaic_crop(tiffs: list[str | Path], bbox: tuple[float, float, float, float],
                out_jpg: str | Path, resolution: float | None = None, quality: int = 90) -> Path:
    """Sätter ihop de rutor som täcker bbox (e_min, n_min, e_max, n_max) och sparar JPG + world-fil.

    resolution: meter per pixel i utsnittet (None = samma som källan).
    """
    rasters = [open_geotiff(t) for t in tiffs]
    hits = [r for r in rasters if _intersects(r.bounds, bbox)]
    if not hits:
        raise ValueError("Ingen av filerna täcker området – kontrollera att rätt rutor laddats ner.")
    src_res = hits[0].sx
    res = resolution or src_res
    e_min, n_min, e_max, n_max = bbox
    W, H = round((e_max - e_min) / res), round((n_max - n_min) / res)
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    for r in hits:
        # del av rutan som ligger i bbox, i rutans pixlar
        ce0, cn0 = max(e_min, r.bounds[0]), min(n_max, r.bounds[3])
        ce1, cn1 = min(e_max, r.bounds[2]), max(n_min, r.bounds[1])
        x0, y0 = r.to_pixel(ce0, cn0)
        x1, y1 = r.to_pixel(ce1, cn1)
        try:  # snabbt: läs bara de rutor som behövs (Lantmäteriets COG)
            a, we0, wn0, _ = read_window(r.path, (ce0, cn1, ce1, cn0))
            part = Image.fromarray(a[:, :, :3] if a.shape[2] >= 3 else a[:, :, 0])
            ox, oy = round((ce0 - we0) / r.sx), round((wn0 - cn0) / r.sy)
            part = part.convert("RGB").crop((ox, oy, ox + round(x1 - x0), oy + round(y1 - y0)))
        except (ValueError, ImportError):
            with Image.open(r.path) as im:
                part = im.convert("RGB").crop((round(x0), round(y0), round(x1), round(y1)))
        size = (round((ce1 - ce0) / res), round((cn0 - cn1) / res))
        if part.size != size:
            part = part.resize(size, Image.LANCZOS)
        canvas.paste(part, (round((ce0 - e_min) / res), round((n_max - cn0) / res)))
    out_jpg = Path(out_jpg)
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_jpg, quality=quality)
    # World-fil: koordinat för mitten av övre vänstra pixeln
    out_jpg.with_suffix(".jgw").write_text(f"{res}\n0\n0\n{-res}\n{e_min + res / 2}\n{n_max - res / 2}\n")
    return out_jpg


def read_window(path: str | Path, bbox: tuple[float, float, float, float]):
    """Läser bara de rutor (tiles) i en GeoTIFF som täcker bbox, utan att avkoda hela filen.

    Klarar Lantmäteriets COG: okomprimerad eller deflate, prediktor 1/2/3 (3 = flyttal,
    som markhöjdmodellen använder och Pillow inte kan läsa). Returnerar (array, e0, n0, res)
    där e0/n0 är övre vänstra pixelkanten. Kastar ValueError för andra format.
    """
    import numpy as np

    g = open_geotiff(path)
    with Image.open(path) as im:
        t = im.tag_v2
        comp, pred = int(t.get(259, 1)), int(t.get(317, 1))
        if comp not in (1, 8) or 322 not in t or int(t.get(284, 1)) != 1:
            raise ValueError(f"{Path(path).name}: format som read_window inte klarar")
        tw, th = int(t[322]), int(t[323])
        spp, bits = int(t.get(277, 1)), int(t[258][0])
        fmt = int(t.get(339, (1,))[0])
        offs, cnts = list(t[324]), list(t[325])
        order = t._endian  # "<" eller ">" enligt filhuvudet
    kind = {1: "u", 2: "i", 3: "f"}[fmt]
    dt = np.dtype(f"{order}{kind}{bits // 8}")
    e_min, n_min, e_max, n_max = bbox
    x0, y0 = (max(0, int(v)) for v in g.to_pixel(e_min, n_max))
    x1, y1 = g.to_pixel(e_max, n_min)
    x1, y1 = min(g.width, int(np.ceil(x1))), min(g.height, int(np.ceil(y1)))
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"{Path(path).name} täcker inte området")
    across = -(-g.width // tw)
    out = np.zeros((y1 - y0, x1 - x0, spp), dtype=dt.newbyteorder("="))
    with open(path, "rb") as f:
        for ty in range(y0 // th, (y1 - 1) // th + 1):
            for tx in range(x0 // tw, (x1 - 1) // tw + 1):
                i = ty * across + tx
                f.seek(offs[i])
                raw = f.read(cnts[i])
                if comp == 8:
                    raw = zlib.decompress(raw)
                b = np.frombuffer(raw, dtype=np.uint8)
                if pred == 3:  # flyttal: bytes differens-kodade per rad och sorterade MSB först
                    nb = dt.itemsize
                    b = b.reshape(th, tw * spp * nb).cumsum(axis=1, dtype=np.uint8)
                    b = b.reshape(th, nb, tw * spp).transpose(0, 2, 1)
                    tile = np.ascontiguousarray(b).view(np.dtype(f">{kind}{nb}")).reshape(th, tw, spp)
                else:
                    tile = b.view(dt).reshape(th, tw, spp)
                    if pred == 2:  # horisontell differens per kanal
                        tile = tile.cumsum(axis=1, dtype=tile.dtype)
                tile = tile.astype(out.dtype)
                ax0, ay0 = tx * tw, ty * th
                sx0, sy0 = max(x0, ax0), max(y0, ay0)
                sx1, sy1 = min(x1, ax0 + tw), min(y1, ay0 + th)
                out[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = tile[sy0 - ay0:sy1 - ay0, sx0 - ax0:sx1 - ax0]
    return out, g.e0 + x0 * g.sx, g.n0 - y0 * g.sy, g.sx


def hojd_utsnitt(tiffs: list[str | Path], bbox: tuple[float, float, float, float], out_dir: str | Path) -> dict:
    """Klipper ut markhöjdmodellen för bbox: hojd.tif (meter, 32-bit) + hojd_skuggning.png (relief),
    båda med world-fil. Returnerar lägsta/högsta höjd."""
    import numpy as np

    hits = [t for t in tiffs if _intersects(open_geotiff(t).bounds, bbox)]
    if not hits:
        raise ValueError("Ingen höjdfil täcker området.")
    if len(hits) > 1:
        raise ValueError("Banan ligger över flera höjdrutor – sammanfogning är inte byggd än.")
    z, e0, n0, res = read_window(hits[0], bbox)
    z = z[:, :, 0].astype(np.float32)
    giltig = z > -9000  # -9999 = saknas
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    world = f"{res}\n0\n0\n{-res}\n{e0 + res / 2}\n{n0 - res / 2}\n"
    Image.fromarray(z, mode="F").save(out_dir / "hojd.tif")
    (out_dir / "hojd.tfw").write_text(world)
    # Relief: belysning från nordväst, 45°, lätt överdriven så att svackor och kullar syns
    zf = np.where(giltig, z, np.nanmean(z[giltig]))
    gy, gx = np.gradient(zf * 2.0, res)
    lutning = np.arctan(np.hypot(gx, gy))
    riktning = np.arctan2(-gx, gy)
    sol_az, sol_h = np.radians(315), np.radians(45)
    ljus = np.sin(sol_h) * np.cos(lutning) + np.cos(sol_h) * np.sin(lutning) * np.cos(sol_az - riktning)
    Image.fromarray((np.clip(ljus, 0, 1) * 255).astype(np.uint8)).save(out_dir / "hojd_skuggning.png")
    (out_dir / "hojd_skuggning.pgw").write_text(world)
    return {"lagst": round(float(z[giltig].min()), 1), "hogst": round(float(z[giltig].max()), 1),
            "upplosning_m": res, "fil": str(out_dir / "hojd.tif")}


class Elevation:
    """Markhöjd (meter över havet) från markhöjdmodellen, för uppför/nedför-info."""

    def __init__(self, tiffs: list[str | Path]):
        self.rasters = [open_geotiff(t) for t in tiffs]
        self._cache: dict[Path, Image.Image] = {}

    def at(self, e: float, n: float) -> float | None:
        for r in self.rasters:
            b = r.bounds
            if b[0] <= e < b[2] and b[1] < n <= b[3]:
                if r.path not in self._cache:
                    self._cache[r.path] = Image.open(r.path).convert("F")
                x, y = r.to_pixel(e, n)
                return float(self._cache[r.path].getpixel((int(x), int(y))))
        return None
