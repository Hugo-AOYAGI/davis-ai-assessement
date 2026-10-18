import pytest
from shapely import Polygon

from agent.runtime.geometry.envelope.shapes import trim_area


@pytest.mark.parametrize(
    "polygon",
    [
        Polygon([(0, 0), (8, 0), (8, 2), (2, 2), (2, 8), (0, 8)]),
        Polygon([(0, 0), (8, 0), (8, 8), (0, 8)], [[(2, 2), (6, 2), (6, 6), (2, 6)]]),
    ],
)
def test_area_trim_preserves_concavity_and_holes(polygon):
    target = polygon.area * 0.7
    trimmed = trim_area(polygon, target, tolerance_m=0.001)
    assert polygon.covers(trimmed)
    assert trimmed.is_valid
    assert trimmed.area <= target
    assert trimmed.area == pytest.approx(target, abs=0.01)
