import pytest
import shapely

from agent.runtime.geometry.projection import to_crs


def test_known_point_in_lambert93():
    projected = to_crs(shapely.Point(2.165254, 48.709836), "EPSG:4326", "EPSG:2154")
    assert projected.x == pytest.approx(638580.2, abs=0.5)
    assert projected.y == pytest.approx(6845846.57, abs=0.5)


def test_round_trip_keeps_coordinates_and_type():
    polygon = shapely.Polygon([(2.165, 48.709), (2.166, 48.709), (2.166, 48.710)])
    back = to_crs(to_crs(polygon, "EPSG:4326", "EPSG:2154"), "EPSG:2154", "EPSG:4326")
    assert isinstance(back, shapely.Polygon)
    for (x0, y0), (x1, y1) in zip(polygon.exterior.coords, back.exterior.coords, strict=True):
        assert x1 == pytest.approx(x0, abs=1e-7)
        assert y1 == pytest.approx(y0, abs=1e-7)
