import shapely

from agent.contracts.geometry import BoundaryKind, Polygon
from agent.runtime.geometry.boundaries import classify_boundaries
from agent.runtime.geometry.parcels import to_shape

ROAD = BoundaryKind.ROAD
SIDE = BoundaryKind.SIDE
REAR = BoundaryKind.REAR

RECTANGLE = Polygon(
    crs="EPSG:2154",
    exterior=((0.0, 0.0), (20.0, 0.0), (20.0, 40.0), (0.0, 40.0), (0.0, 0.0)),
)
WEST = shapely.box(-15, -5, 0, 45)
EAST = shapely.box(20, -5, 35, 45)
NORTH = shapely.box(0, 40, 20, 60)
SOUTH = shapely.box(0, -20, 20, 0)


def classify(site, neighbours):
    return classify_boundaries(
        site, neighbours, snap_tolerance_m=0.5, min_shared_ratio=0.5, collinear_angle_deg=20
    )


def kinds(site, neighbours):
    return [boundary.kind for boundary in classify(site, neighbours)]


def test_mid_street_plot():
    assert kinds(RECTANGLE, [WEST, EAST, NORTH]) == [ROAD, SIDE, REAR, SIDE]


def test_split_side_limit_stays_side():
    east_limit = ((20.0, 0.0), (20.1, 13.0), (19.95, 27.0), (20.0, 40.0))
    site = Polygon(crs="EPSG:2154", exterior=((0.0, 0.0), *east_limit, (0.0, 40.0), (0.0, 0.0)))
    east = shapely.Polygon([*east_limit, (35.0, 40.0), (35.0, 0.0)])
    assert kinds(site, [WEST, east, NORTH]) == [ROAD, SIDE, SIDE, SIDE, REAR, SIDE]


def test_corner_plot_has_no_rear():
    assert kinds(RECTANGLE, [WEST, NORTH]) == [ROAD, ROAD, SIDE, SIDE]


def test_enclosed_plot_is_all_rear():
    assert kinds(RECTANGLE, [WEST, EAST, NORTH, SOUTH]) == [REAR] * 4


def test_no_neighbours_is_all_road():
    assert kinds(RECTANGLE, []) == [ROAD] * 4


def test_neighbour_that_is_the_site_is_ignored():
    site = to_shape(RECTANGLE)
    assert kinds(RECTANGLE, [site]) == [ROAD] * 4
    assert kinds(RECTANGLE, [site, WEST, EAST, NORTH]) == [ROAD, SIDE, REAR, SIDE]


def test_partial_contact_is_not_shared():
    assert kinds(RECTANGLE, [shapely.box(20, 0, 30, 5)]) == [ROAD] * 4


def test_short_jog_does_not_split_limit():
    east_limit = ((20.0, 0.0), (20.0, 20.0), (20.2, 20.0), (20.2, 40.0))
    site = Polygon(crs="EPSG:2154", exterior=((0.0, 0.0), *east_limit, (0.0, 40.0), (0.0, 0.0)))
    east = shapely.Polygon([*east_limit, (35.0, 40.0), (35.0, 0.0)])
    assert kinds(site, [WEST, east, NORTH]) == [ROAD, SIDE, SIDE, SIDE, REAR, SIDE]


def test_limit_run_wrapping_around_the_ring_start():
    assert kinds(RECTANGLE, [WEST, NORTH, SOUTH]) == [SIDE, ROAD, SIDE, REAR]


def test_boundaries_follow_the_ring():
    boundaries = classify(RECTANGLE, [WEST, EAST, NORTH])
    assert len(boundaries) == len(RECTANGLE.exterior) - 1
    ring = RECTANGLE.exterior
    for boundary, start, end in zip(boundaries, ring[:-1], ring[1:], strict=True):
        assert boundary.start == start
        assert boundary.end == end
