import numpy as np
import pymupdf
import pytest

RED = (255, 0, 0)
BLUE = (0, 0, 255)


def make_quadrants(width: int, height: int) -> pymupdf.Pixmap:
    array = np.empty((height, width, 3), dtype=np.uint8)
    array[:] = BLUE
    array[: height // 2, : width // 2] = RED
    return pymupdf.Pixmap(pymupdf.csRGB, width, height, array.tobytes(), 0)


def decode_png(png: bytes) -> pymupdf.Pixmap:
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    return pymupdf.Pixmap(png)


@pytest.fixture
def quadrants():
    return make_quadrants


@pytest.fixture
def decode():
    return decode_png


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "plan.pdf"
    with pymupdf.open() as document:
        scan = document.new_page(width=300, height=150)
        scan.insert_image(scan.rect, pixmap=make_quadrants(1200, 600))
        vector = document.new_page(width=200, height=100)
        vector.draw_rect(pymupdf.Rect(0, 0, 100, 100), color=None, fill=(0, 1, 0))
        vector.insert_text((110, 50), "UMG", fontsize=20)
        small = document.new_page(width=200, height=100)
        small.insert_image(pymupdf.Rect(0, 0, 20, 10), pixmap=make_quadrants(80, 40))
        document.save(path)
    return path
