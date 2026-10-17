from concurrent.futures import ThreadPoolExecutor

import pymupdf
import pytest
from pydantic import ValidationError

from agent.adapters.images.pages import PageImages, RegionError
from agent.adapters.images.render import RULER_BAND_PX
from agent.contracts.evidence import ImageRegion

BLUE = (0, 0, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
WHITE = (255, 255, 255)

BAND = RULER_BAND_PX
MAX_PX = 440


def make(
    root,
    documents=({"id": "plan", "path": "plan.pdf", "kind": "map", "title": "Plan"},),
    max_image_px=MAX_PX,
    cache_size=2,
    scan_min_coverage=0.8,
):
    return PageImages(
        documents=documents,
        root=root,
        render_dpi=144,
        max_image_px=max_image_px,
        max_upscale=4.0,
        ruler_step_px=100,
        crop_max_px=500,
        cache_size=cache_size,
        scan_min_coverage=scan_min_coverage,
    )


@pytest.fixture
def images(tmp_path, pdf):
    return make(tmp_path)


def region(page, box):
    return ImageRegion(doc="plan", page=page, region=box)


def test_scan_overview(images, decode):
    view = images.overview("plan", 1)
    assert view.full_size == (1200, 600)
    assert view.overview_size == (400, 200)
    assert view.image_size == (440, 240)
    image = decode(view.png)
    assert (image.width, image.height) == view.image_size
    assert max(view.image_size) <= MAX_PX
    assert image.pixel(BAND + 10, BAND + 10) == RED
    assert image.pixel(BAND + 390, BAND + 190) == BLUE
    assert image.pixel(2, 2) == WHITE


def test_vector_page_follows_render_dpi(images, decode):
    view = images.overview("plan", 2)
    assert view.full_size == (400, 200)
    assert view.overview_size == (400, 200)
    assert decode(view.png).pixel(BAND + 50, BAND + 100) == GREEN


def test_zoom_on_red_quadrant(images, decode):
    view = images.zoom(region(1, (0, 0, 100, 50)))
    assert view.image_size == (440, 240)
    image = decode(view.png)
    assert (image.width, image.height) == view.image_size
    assert image.pixel(BAND + 200, BAND + 100) == RED
    assert (
        decode(images.zoom(region(1, (300, 150, 400, 200))).png).pixel(BAND + 9, BAND + 9) == BLUE
    )


def test_zoom_upscale_is_capped(images):
    view = images.zoom(region(1, (0, 0, 10, 5)))
    assert view.image_size == (BAND + 120, BAND + 60)
    assert max(view.image_size) <= MAX_PX


def test_check_unknown_doc(images):
    with pytest.raises(RegionError, match="known documents: plan"):
        images.check(ImageRegion(doc="nope", page=1, region=(0, 0, 10, 10)))


def test_check_bad_page(images):
    with pytest.raises(RegionError, match="plan has 3 pages"):
        images.check(region(4, (0, 0, 10, 10)))
    with pytest.raises(RegionError, match="page 0"):
        images.overview("plan", 0)


def test_check_region_outside_overview(images):
    with pytest.raises(RegionError, match=r"plan p\.1 is 400x200 px; region \[0, 0, 401, 10\]"):
        images.check(region(1, (0, 0, 401, 10)))
    images.check(region(1, (0, 0, 400, 200)))


def test_save_crop(images, tmp_path):
    stored = images.save_crop(region(1, (0, 0, 200, 100)), tmp_path / "outputs" / "crops")
    assert stored.path == "outputs/crops/plan_p1_0-0-200-100.png"
    assert stored.pixels == (0, 0, 600, 300)
    image = pymupdf.Pixmap(str(tmp_path / stored.path))
    assert (image.width, image.height) == (500, 250)
    assert image.pixel(250, 125) == RED
    again = images.save_crop(region(1, (0, 0, 200, 100)), tmp_path / "outputs" / "crops")
    assert again == stored


def test_save_crop_keeps_full_resolution(images, tmp_path):
    stored = images.save_crop(region(1, (10, 10, 20, 20)), tmp_path / "crops")
    assert stored.pixels == (30, 30, 60, 60)
    image = pymupdf.Pixmap(str(tmp_path / stored.path))
    assert (image.width, image.height) == (30, 30)


def test_save_crop_outside_root(tmp_path, pdf):
    images = make(tmp_path / "project", documents=[{"id": "plan", "path": "../plan.pdf"}])
    stored = images.save_crop(region(1, (0, 0, 10, 10)), tmp_path / "crops")
    assert stored.path == "../crops/plan_p1_0-0-10-10.png"


def test_cache_evicts(tmp_path, pdf):
    images = make(tmp_path, cache_size=1)
    first = images.overview("plan", 1)
    assert images.overview("plan", 2).full_size == (400, 200)
    assert images.overview("plan", 1) == first


def test_concurrent_calls(images):
    with ThreadPoolExecutor(max_workers=4) as pool:
        views = list(pool.map(lambda page: images.overview("plan", page), [1, 2, 3, 1, 2, 3]))
    assert views[0] == views[3]


@pytest.mark.parametrize(
    "override", [{"max_image_px": BAND}, {"cache_size": 0}, {"scan_min_coverage": 1.5}]
)
def test_rejects_bad_settings(tmp_path, override):
    with pytest.raises(ValidationError):
        make(tmp_path, **override)
