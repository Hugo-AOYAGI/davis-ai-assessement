import numpy as np
import pymupdf
import pytest

from agent.adapters.images.render import (
    RULER_BAND_PX,
    LineStyle,
    Overlay,
    crop_png,
    render_view,
    render_within,
)
from agent.runtime.images.boxes import OverviewScale, PixelBox
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


def test_view_overlay_is_drawn_and_kept_off_the_rulers(raster, decode):
    box = PixelBox(x0=100, y0=50, x1=200, y1=100)
    rulers = (Ruler(start=0, scale=4, length=400), Ruler(start=0, scale=4, length=200))
    ring = ((90.0, 75.0), (150.0, 75.0), (150.0, 90.0), (90.0, 90.0), (90.0, 75.0))
    overlay = Overlay(rings=(ring,), style=LineStyle(rgb=RED, width_px=3))
    image = decode(render_view(raster, box, rulers, step_px=100, overlay=overlay))
    assert image.pixel(BAND + 200, BAND + 100) == RED
    assert image.pixel(BAND + 100, BAND + 150) == BLUE
    assert image.pixel(BAND // 2, BAND + 100) != RED


def test_render_within_shrinks_an_oversized_view_until_it_fits(decode):
    noise = np.random.default_rng(0).integers(0, 256, (300, 600, 3), dtype=np.uint8)
    raster = pymupdf.Pixmap(pymupdf.csRGB, 600, 300, noise.tobytes(), 0)
    box = PixelBox(x0=0, y0=0, x1=600, y1=300)
    scale = OverviewScale(full=(600, 300), overview=(300, 150))
    big, size = render_within(raster, box, scale, (900, 450), step_px=100, max_bytes=10**8)
    assert size == (900, 450)
    budget = len(big) // 3
    png, small = render_within(raster, box, scale, (900, 450), step_px=100, max_bytes=budget)
    assert len(png) <= budget
    assert small[0] < 900
    assert small[0] / small[1] == pytest.approx(2, abs=0.02)
    image = decode(png)
    assert (image.width, image.height) == (BAND + small[0], BAND + small[1])
    horizontal, vertical = scale.rulers(box, small)
    assert horizontal.start == 0
    assert horizontal.length / horizontal.scale == pytest.approx(300)
    assert vertical.length / vertical.scale == pytest.approx(150)


def test_render_within_rejects_an_impossible_byte_budget(raster):
    box = PixelBox(x0=0, y0=0, x1=200, y1=100)
    scale = OverviewScale(full=(200, 100), overview=(200, 100))
    with pytest.raises(ValueError, match="exceeding 1 bytes"):
        render_within(raster, box, scale, (200, 100), step_px=100, max_bytes=1)
