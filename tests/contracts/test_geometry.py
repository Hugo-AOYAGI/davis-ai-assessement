import pytest
from pydantic import ValidationError

from agent.contracts.geometry import Level, Polygon


def test_open_ring_rejected():
    with pytest.raises(ValidationError, match="closed"):
        Polygon(crs="EPSG:2154", exterior=((0, 0), (1, 0), (1, 1), (0, 1)))


@pytest.mark.parametrize("ring", [(), ((0, 0),), ((0, 0), (1, 1), (0, 0))])
def test_short_hole_ring_rejected(polygon: Polygon, ring):
    with pytest.raises(ValidationError, match="at least 4"):
        Polygon.model_validate({**polygon.model_dump(), "holes": (ring,)})


def test_open_hole_ring_rejected(polygon: Polygon):
    with pytest.raises(ValidationError, match="closed"):
        Polygon.model_validate(
            {**polygon.model_dump(), "holes": (((1, 1), (2, 1), (2, 2), (1, 2)),)}
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_polygon_coordinate_rejected(polygon: Polygon, value):
    with pytest.raises(ValidationError, match="finite"):
        Polygon.model_validate(
            {**polygon.model_dump(), "exterior": ((value, 0), (1, 0), (1, 1), (value, 0))}
        )


def test_level_must_rise():
    with pytest.raises(ValidationError, match="above its from_m"):
        Level(from_m=5, to_m=5, area_m2=10)
