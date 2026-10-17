import pytest
from pydantic import ValidationError

from agent.runtime.georef.crop import PixelBox, crop_box, output_size

SIZE = (1000, 800)


def test_box_from_config_list():
    box = PixelBox.model_validate([10, 20, 110, 70])
    assert (box.width, box.height, box.as_list()) == (100, 50, [10, 20, 110, 70])


@pytest.mark.parametrize("values", [[10, 20, 10, 70], [10, 20, 110, 20], [1, 2, 3]])
def test_box_rejects_empty_or_malformed(values):
    with pytest.raises(ValidationError):
        PixelBox.model_validate(values)


def test_crop_is_square_and_centred():
    assert crop_box((500.0, 400.0), 10, 0.5, SIZE) == PixelBox(x0=480, y0=380, x1=520, y1=420)


def test_crop_clamped_at_edges():
    assert crop_box((5.0, 790.0), 10, 0.5, SIZE) == PixelBox(x0=0, y0=770, x1=25, y1=800)


def test_crop_outside_raster():
    assert crop_box((-100.0, 400.0), 10, 0.5, SIZE) is None
    assert crop_box((500.0, 900.0), 10, 0.5, SIZE) is None


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
