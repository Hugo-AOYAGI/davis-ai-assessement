import pytest
import shapely

from agent.runtime.geometry.projection import fit_half_width, square_around, to_crs, to_pixels


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


def test_square_around():
    assert square_around((100.0, 200.0), 50) == (50.0, 150.0, 150.0, 250.0)


@pytest.mark.parametrize(
    ("bounds", "expected"),
    [((0.0, 0.0, 100.0, 40.0), 80.0), ((0.0, 0.0, 10.0, 10.0), 40.0)],
    ids=["margin", "minimum"],
)
def test_fit_half_width(bounds, expected):
    assert fit_half_width(bounds, margin_ratio=0.3, min_half_width_m=40) == expected


def test_to_pixels_is_north_up():
    bounds = (1000.0, 2000.0, 1100.0, 2100.0)
    corners = [(1000.0, 2100.0), (1100.0, 2000.0), (1050.0, 2050.0)]
    assert to_pixels(corners, bounds, (200, 100)) == [(0.0, 0.0), (200.0, 100.0), (100.0, 50.0)]
