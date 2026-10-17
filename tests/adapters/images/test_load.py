import pytest

from agent.adapters.images.load import page_count, page_image

GREEN = (0, 255, 0)
SCAN_SIZE = (1200, 600)
WHITE = (255, 255, 255)

DPI = 144


def load(pdf, page, coverage=0.8):
    return page_image(pdf, page, render_dpi=DPI, scan_min_coverage=coverage)


def test_page_count(pdf):
    assert page_count(pdf) == 3


def test_scan_page_yields_native_image(pdf, quadrants):
    image = load(pdf, 1)
    assert (image.width, image.height, image.n, image.alpha) == (*SCAN_SIZE, 3, 0)
    assert image.samples == quadrants(*SCAN_SIZE).samples


def test_vector_page_is_rendered_at_dpi(pdf):
    image = load(pdf, 2)
    assert (image.width, image.height, image.n, image.alpha) == (400, 200, 3, 0)
    assert image.pixel(50, 100) == GREEN
    assert image.pixel(390, 190) == WHITE


def test_small_image_does_not_make_a_scan(pdf):
    image = load(pdf, 3)
    assert (image.width, image.height) == (400, 200)


def test_coverage_threshold_decides(pdf):
    image = load(pdf, 3, coverage=0.01)
    assert (image.width, image.height) == (80, 40)


def test_page_out_of_range(pdf):
    with pytest.raises(ValueError, match="page 4 requested"):
        load(pdf, 4)
