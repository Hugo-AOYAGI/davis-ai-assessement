import numpy as np
import pymupdf
import pytest

from agent.adapters.raster.load import load_raster


def gradient(width: int, height: int) -> pymupdf.Pixmap:
    columns = np.arange(width, dtype=np.uint8)[None, :].repeat(height, axis=0)
    rows = np.arange(height, dtype=np.uint8)[:, None].repeat(width, axis=1)
    array = np.stack([columns, rows, np.full_like(columns, 128)], axis=-1)
    return pymupdf.Pixmap(pymupdf.csRGB, width, height, array.tobytes(), 0)


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "plan.pdf"
    with pymupdf.open() as document:
        page = document.new_page(width=100, height=50)
        page.insert_image(pymupdf.Rect(0, 0, 10, 5), pixmap=gradient(20, 10))
        page.insert_image(pymupdf.Rect(0, 0, 100, 50), pixmap=gradient(240, 120))
        document.new_page(width=100, height=50)
        document.save(path)
    return path


def test_pdf_page_yields_largest_image_at_native_size(pdf):
    image = load_raster(pdf, 1)
    assert (image.width, image.height, image.n, image.alpha) == (240, 120, 3, 0)
    assert image.samples == gradient(240, 120).samples


def test_pdf_page_out_of_range(pdf):
    with pytest.raises(ValueError, match="page 3 requested"):
        load_raster(pdf, 3)


def test_pdf_page_without_image(pdf):
    with pytest.raises(ValueError, match="no embedded image"):
        load_raster(pdf, 2)


def test_image_file(tmp_path):
    path = tmp_path / "plan.png"
    gradient(64, 32).save(path)
    image = load_raster(path, 1)
    assert (image.width, image.height) == (64, 32)
    assert image.samples == gradient(64, 32).samples
