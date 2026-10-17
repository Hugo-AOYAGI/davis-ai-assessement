import pymupdf
import pytest

from agent.adapters.raster.render import Outline, render_crop
from agent.runtime.georef.crop import PixelBox

RED = (255, 0, 0)
BOX = PixelBox(x0=50, y0=20, x1=150, y1=80)
RING = ((70.0, 30.0), (130.0, 30.0), (130.0, 70.0), (70.0, 70.0), (70.0, 30.0))


@pytest.fixture
def white() -> pymupdf.Pixmap:
    image = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 100), 0)
    image.clear_with(255)
    return image


def decode(png: bytes) -> pymupdf.Pixmap:
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    return pymupdf.Pixmap(png)


def test_output_size_follows_limits(white):
    image = decode(render_crop(white, BOX, max_output_px=300, max_upscale=2.0))
    assert (image.width, image.height) == (200, 120)
    image = decode(render_crop(white, BOX, max_output_px=50, max_upscale=2.0))
    assert (image.width, image.height) == (50, 30)


def test_without_outline_crop_is_unchanged(white):
    image = decode(render_crop(white, BOX, max_output_px=300, max_upscale=2.0))
    assert set(image.samples) == {255}


def test_outline_is_drawn_in_output_coordinates(white):
    outline = Outline(rings=(RING,), rgb=RED, width_px=3)
    image = decode(render_crop(white, BOX, max_output_px=300, max_upscale=2.0, outline=outline))
    for x, y in [(100, 20), (40, 60), (160, 60), (100, 100)]:
        assert image.pixel(x, y) == RED
    assert image.pixel(100, 60) == (255, 255, 255)
    assert image.pixel(10, 10) == (255, 255, 255)


def test_box_outside_raster(white):
    with pytest.raises(ValueError, match="exceeds"):
        render_crop(white, PixelBox(x0=150, y0=0, x1=250, y1=50), max_output_px=100, max_upscale=1)
