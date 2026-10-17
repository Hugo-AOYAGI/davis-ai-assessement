import pytest
from pydantic import ValidationError

from agent.contracts.geometry import Level, Polygon


def test_open_ring_rejected():
    with pytest.raises(ValidationError, match="closed"):
        Polygon(crs="EPSG:2154", exterior=((0, 0), (1, 0), (1, 1), (0, 1)))


def test_level_must_rise():
    with pytest.raises(ValidationError, match="above its from_m"):
        Level(from_m=5, to_m=5, area_m2=10)
