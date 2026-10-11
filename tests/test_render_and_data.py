from pathlib import Path

from PIL import Image, TiffImagePlugin

from golfholes import Hole
from golfholes.lantmateriet import mosaic_crop, open_geotiff
from golfholes.render import render_flat
from golfholes.render.web import hole_page

ROOT = Path(__file__).parent.parent
EXAMPLE = ROOT / "klubbar" / "exempel-ekbacka" / "hal-07.yaml"


def test_flat_render_has_all_parts():
    svg = render_flat(Hole.from_yaml(EXAMPLE))
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    for colour in ("#bfe0a0", "#efe5cc", "#93b6c6"):  # green, bunker, vatten
        assert colour in svg
    assert ">100<" in svg and ">150<" in svg and ">200<" in svg


def test_hole_page_contains_sponsor_and_tees():
    import yaml

    club = yaml.safe_load((EXAMPLE.parent / "klubb.yaml").read_text(encoding="utf-8"))
    page = hole_page(Hole.from_yaml(EXAMPLE), club)
    assert "Nordvik-hålet" in page and "sponsras av" in page
    assert 'data-t="58"' in page and 'data-t="48"' in page


def _tile(path, img, e0, n0, res):
    ifd = TiffImagePlugin.ImageFileDirectory_v2()
    ifd[33550] = (res, res, 0.0)
    ifd.tagtype[33550] = 12
    ifd[33922] = (0.0, 0.0, 0.0, e0, n0, 0.0)
    ifd.tagtype[33922] = 12
    img.save(path, tiffinfo=ifd)


def test_mosaic_crop_places_tiles_correctly(tmp_path):
    # Två rutor 100×100 px à 1 m: vänster röd, höger blå
    _tile(tmp_path / "a.tif", Image.new("RGB", (100, 100), (255, 0, 0)), 500000, 6300100, 1.0)
    _tile(tmp_path / "b.tif", Image.new("RGB", (100, 100), (0, 0, 255)), 500100, 6300100, 1.0)
    assert open_geotiff(tmp_path / "b.tif").bounds == (500100, 6300000, 500200, 6300100)
    out = mosaic_crop([tmp_path / "a.tif", tmp_path / "b.tif"], (500050, 6300020, 500150, 6300080), tmp_path / "u.jpg")
    im = Image.open(out).convert("RGB")
    assert im.size == (100, 60)
    assert im.getpixel((10, 30))[0] > 200 and im.getpixel((90, 30))[2] > 200
    jgw = out.with_suffix(".jgw").read_text().split()
    assert float(jgw[4]) == 500050.5 and float(jgw[5]) == 6300079.5
