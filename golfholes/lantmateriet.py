"""Läser Lantmäteriets GeoTIFF (ortofoto och markhöjdmodell) och gör utsnitt.

Byggt på Pillow i stället för GDAL/rasterio, så att det fungerar både i molnet
och på Macen utan krånglig installation. Klarar GeoTIFF i SWEREF 99 TM med
standardtaggarna ModelPixelScale (33550) och ModelTiepoint (33922).

Typiskt flöde:
    python -m golfholes utsnitt klubbar/glasriket data/glasriket/orto/*.tif
    → data/glasriket/utsnitt/orto.jpg + orto.jgw  (öppnas i ritverktyget)
"""
from __future__ import annotations

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
        with Image.open(r.path) as im:
            im = im.convert("RGB")
            # del av rutan som ligger i bbox, i rutans pixlar
            ce0, cn0 = max(e_min, r.bounds[0]), min(n_max, r.bounds[3])
            ce1, cn1 = min(e_max, r.bounds[2]), max(n_min, r.bounds[1])
            x0, y0 = r.to_pixel(ce0, cn0)
            x1, y1 = r.to_pixel(ce1, cn1)
            part = im.crop((round(x0), round(y0), round(x1), round(y1)))
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
