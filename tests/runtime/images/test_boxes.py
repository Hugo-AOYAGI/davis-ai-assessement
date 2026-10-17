import pytest
from pydantic import ValidationError

from agent.runtime.images.boxes import OverviewScale, PixelBox, fit_size, output_size


def test_box_from_list():
    box = PixelBox.model_validate([10, 20, 110, 70])
    assert (box.width, box.height, box.as_list()) == (100, 50, [10, 20, 110, 70])


@pytest.mark.parametrize(
    "values", [[10, 20, 10, 70], [10, 20, 110, 20], [1, 2, 3], [-1, 0, 5, 5], [0, -2, 5, 5]]
)
def test_box_rejects_empty_negative_or_malformed(values):
    with pytest.raises(ValidationError):
        PixelBox.model_validate(values)


@pytest.mark.parametrize(
    ("box", "expected"),
    [
        ([0, 0, 100, 50], (300, 150)),
        ([0, 0, 2000, 1000], (1200, 600)),
        ([0, 0, 500, 500], (1200, 1200)),
    ],
)
def test_output_size(box, expected):
    assert output_size(PixelBox.model_validate(box), 1200, 3.0) == expected


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        ((7021, 4966), (1960, 1386)),
        ((4966, 7021), (1386, 1960)),
        ((800, 600), (800, 600)),
        ((1960, 10), (1960, 10)),
        ((100000, 10), (1960, 1)),
    ],
)
def test_fit_size(size, expected):
    assert fit_size(size, 1960) == expected


SCALE = OverviewScale(full=(1000, 700), overview=(300, 210))


def test_to_full_floors_starts_and_ceils_ends():
    box = SCALE.to_full(PixelBox(x0=10, y0=10, x1=21, y1=31))
    assert box == PixelBox(x0=33, y0=33, x1=70, y1=104)


def test_to_full_whole_overview_is_whole_image():
    assert SCALE.to_full(PixelBox(x0=0, y0=0, x1=300, y1=210)).as_list() == [0, 0, 1000, 700]


def test_to_full_clamps_to_image():
    assert SCALE.to_full(PixelBox(x0=299, y0=0, x1=400, y1=500)).as_list() == [996, 0, 1000, 700]
    assert SCALE.to_full(PixelBox(x0=500, y0=0, x1=600, y1=1)).as_list() == [999, 0, 1000, 4]


def test_contains():
    assert SCALE.contains(PixelBox(x0=0, y0=0, x1=300, y1=210))
    assert not SCALE.contains(PixelBox(x0=0, y0=0, x1=301, y1=210))
    assert not SCALE.contains(PixelBox(x0=0, y0=200, x1=10, y1=211))


def test_scale_rejects_empty_sizes():
    with pytest.raises(ValidationError):
        OverviewScale(full=(0, 10), overview=(1, 1))


@pytest.mark.parametrize("value", [30, 42.5, 59])
def test_rulers_map_overview_coordinates_to_output_pixels(value):
    box = SCALE.to_full(PixelBox(x0=30, y0=30, x1=60, y1=60))
    horizontal, vertical = SCALE.rulers(box, (600, 600))
    assert (horizontal.length, vertical.length) == (600, 600)
    x = (value * 1000 / 300 - box.x0) * 600 / box.width
    y = (value * 700 / 210 - box.y0) * 600 / box.height
    assert (value - horizontal.start) * horizontal.scale == pytest.approx(x)
    assert (value - vertical.start) * vertical.scale == pytest.approx(y)


def test_overview_rulers_have_unit_scale():
    whole = PixelBox(x0=0, y0=0, x1=1000, y1=700)
    horizontal, vertical = SCALE.rulers(whole, SCALE.overview)
    assert horizontal.start == vertical.start == 0
    assert horizontal.scale == pytest.approx(1)
    assert vertical.scale == pytest.approx(1)
