import pytest

from agent.adapters.images.render import RULER_BAND_PX, crop_png, render_view
from agent.runtime.images.boxes import PixelBox
from agent.runtime.images.rulers import Ruler

BLUE = (0, 0, 255)
RED = (255, 0, 0)
WHITE = (255, 255, 255)

BAND = RULER_BAND_PX


@pytest.fixture
def raster(quadrants):
    return quadrants(200, 100)


def test_crop_png_keeps_native_pixels(raster, decode):
    box = PixelBox(x0=90, y0=40, x1=110, y1=60)
    image = decode(crop_png(raster, box, (20, 20)))
    assert (image.width, image.height) == (20, 20)
    assert image.pixel(5, 5) == RED
    assert image.pixel(15, 15) == BLUE


def test_crop_png_downscales(raster, decode):
    image = decode(crop_png(raster, PixelBox(x0=0, y0=0, x1=200, y1=100), (50, 25)))
    assert (image.width, image.height) == (50, 25)
    assert image.pixel(5, 5) == RED


def test_view_size_and_content(raster, decode):
    box = PixelBox(x0=0, y0=0, x1=100, y1=50)
    rulers = (Ruler(start=0, scale=4, length=400), Ruler(start=0, scale=4, length=200))
    image = decode(render_view(raster, box, rulers, step_px=100))
    assert (image.width, image.height) == (BAND + 400, BAND + 200)
    assert image.pixel(BAND + 200, BAND + 100) == RED
    assert image.pixel(BAND + 399, BAND + 199) == RED


def test_view_draws_rulers_in_bands(raster, decode):
    rulers = (Ruler(start=0, scale=1, length=200), Ruler(start=0, scale=1, length=100))
    image = decode(render_view(raster, PixelBox(x0=0, y0=0, x1=200, y1=100), rulers, step_px=50))
    assert image.pixel(1, 1) == WHITE
    top_band = {image.pixel(x, y) for x in range(BAND, BAND + 200) for y in range(BAND)}
    assert any(sum(pixel) < 200 for pixel in top_band)


def test_box_outside_raster(raster):
    rulers = (Ruler(start=0, scale=1, length=100), Ruler(start=0, scale=1, length=50))
    with pytest.raises(ValueError, match="exceeds"):
        render_view(raster, PixelBox(x0=150, y0=0, x1=250, y1=50), rulers, step_px=100)
