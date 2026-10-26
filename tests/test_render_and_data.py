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


def test_four_drawing_engines_render_from_same_data():
    from golfholes.render.styles import STYLE_NAMES, render_green, render_hole

    hole = Hole.from_yaml(EXAMPLE)
    for st in STYLE_NAMES:
        svg = render_hole(hole, st)
        assert svg.startswith("<svg") and svg.endswith("</svg>")
        assert render_green(hole, st).startswith("<svg")


def test_club_picks_one_of_six_styles_by_name():
    from golfholes.stilar import MENY, STILAR, las_stil

    assert [s.namn for s in MENY] == ["Akvarell", "Sommarakvarell", "Gravyr", "Mjuk 3D", "Arkitektskiss",
                                      "Papperssnitt"]
    assert las_stil("Mjuk 3D").nyckel == "mjuk-3d" and las_stil("gravyr").namn == "Gravyr"
    assert las_stil("PAPPERSSNITT").nyckel == "papperssnitt" and las_stil(None).nyckel == "foto"
    for s in STILAR.values():
        assert s.provbild.exists(), s.prov
        assert "every pixel of every edge must stay where it is" in s.prompt
        assert "Do not add or remove anything" in s.prompt
    assert len({s.prompt for s in MENY}) == 6
    for bad in (0, 5, "guld", "Blå gravyr"):
        try:
            las_stil(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} borde ge fel")


def test_old_style_numbers_still_read_with_warning():
    import contextlib
    import io

    from golfholes.stilar import las_stil

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        assert las_stil(3).nyckel == "gravyr" and las_stil("2").nyckel == "akvarell"
        assert las_stil("Nordisk").nyckel == "mjuk-3d" and las_stil(1).nyckel == "foto"
    assert err.getvalue().count("VARNING") == 4


def test_stilprov_shows_all_six_same_size(tmp_path):
    from PIL import Image

    from golfholes.stilar import stilprov

    files = stilprov(tmp_path, hojd_px=200)
    assert len([k for k in files if k not in ("alla", "promptar")]) == 6
    assert Image.open(files["alla"]).height == 200 + 70 + 80
    md = files["promptar"].read_text(encoding="utf-8")
    assert md.count("## ") == 6 and "Arkitektskiss" in md


def test_painted_image_path_per_style(tmp_path):
    from golfholes.stilar import las_stil, malad_bild

    assert malad_bild(tmp_path, 3, las_stil("foto")).name == "hal-03-malad.webp"
    assert malad_bild(tmp_path, 3, las_stil("Mjuk 3D")).name == "hal-03-malad-mjuk-3d.webp"


def test_scope_ids_keeps_svgs_apart():
    from golfholes.render.styles import scope_ids

    out = scope_ids('<filter id="wc"/><path filter="url(#wc)"/>', "h")
    assert 'id="h-wc"' in out and "url(#h-wc)" in out


def test_texture_styles_keep_exact_geometry():
    """Texturbilden ska ha vatten exakt där hålfilen säger – och ingen annanstans i närheten."""
    import numpy as np

    from golfholes.render import texture as T

    hole = Hole.from_yaml(EXAMPLE)
    c = T.Canvas(hole, 300)
    water = T._layers(c)["vatten"]
    img = np.asarray(T.render_nordisk(hole, 300), np.float32)
    blue = (img[..., 2] - img[..., 0]) > 25
    inside = blue[water > 0.95].mean()
    assert inside > 0.9
