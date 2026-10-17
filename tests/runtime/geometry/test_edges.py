import pytest
import shapely

from agent.contracts.findings.site import Edge, EdgeSide
from agent.contracts.geometry import BoundaryKind, Polygon
from agent.runtime.geometry.edges import label_edges, site_edges
from agent.runtime.geometry.parcels import to_shape

ROAD = BoundaryKind.ROAD
SIDE = BoundaryKind.SIDE
REAR = BoundaryKind.REAR
PARCEL = EdgeSide.PARCEL
PUBLIC = EdgeSide.PUBLIC_LAND

RECTANGLE = Polygon(
    crs="EPSG:2154",
    exterior=((0.0, 0.0), (20.0, 0.0), (20.0, 40.0), (0.0, 40.0), (0.0, 0.0)),
)
WEST = shapely.box(-15, -5, 0, 45)
EAST = shapely.box(20, -5, 35, 45)
NORTH = shapely.box(0, 40, 20, 60)
SOUTH = shapely.box(0, -20, 20, 0)
NAMED = {"west": WEST, "east": EAST, "north": NORTH, "south": SOUTH}


def neighbours(*names, **extra):
    return {**{name: NAMED[name] for name in names}, **extra}


def edges(site, around):
    return site_edges(site, around, snap_tolerance_m=0.5, min_shared_ratio=0.5)


def kinds(site, around):
    labelled = label_edges(edges(site, around), snap_tolerance_m=0.5, collinear_angle_deg=20)
    return [boundary.kind for boundary in labelled]


def east_split_site(east_limit):
    site = Polygon(crs="EPSG:2154", exterior=((0.0, 0.0), *east_limit, (0.0, 40.0), (0.0, 0.0)))
    east = shapely.Polygon([*east_limit, (35.0, 40.0), (35.0, 0.0)])
    return site, east


def test_edges_are_neutral_facts():
    result = edges(RECTANGLE, neighbours("west", "east", "north"))
    assert [edge.other_side for edge in result] == [PUBLIC, PARCEL, PARCEL, PARCEL]
    assert [edge.neighbours for edge in result] == [(), ("east",), ("north",), ("west",)]
    assert [edge.length_m for edge in result] == pytest.approx([20, 40, 20, 40])


def test_edges_follow_the_ring():
    result = edges(RECTANGLE, neighbours("west", "east", "north"))
    ring = RECTANGLE.exterior
    for edge, start, end in zip(result, ring[:-1], ring[1:], strict=True):
        assert (edge.start, edge.end) == (start, end)


def test_edge_shared_by_two_neighbours_lists_both():
    around = {"a": shapely.box(20, -5, 35, 20), "b": shapely.box(20, 20, 35, 45)}
    result = edges(RECTANGLE, around)
    assert result[1].neighbours == ("a", "b")
    assert result[0].neighbours == ()


def test_mid_street_plot():
    assert kinds(RECTANGLE, neighbours("west", "east", "north")) == [ROAD, SIDE, REAR, SIDE]


def test_split_side_limit_stays_side():
    site, east = east_split_site(((20.0, 0.0), (20.1, 13.0), (19.95, 27.0), (20.0, 40.0)))
    around = neighbours("west", "north", east=east)
    assert kinds(site, around) == [ROAD, SIDE, SIDE, SIDE, REAR, SIDE]


def test_corner_plot_has_no_rear():
    assert kinds(RECTANGLE, neighbours("west", "north")) == [ROAD, ROAD, SIDE, SIDE]


def test_enclosed_plot_is_all_rear():
    assert kinds(RECTANGLE, neighbours("west", "east", "north", "south")) == [REAR] * 4


def test_no_neighbours_is_all_road():
    assert kinds(RECTANGLE, {}) == [ROAD] * 4


def test_neighbour_that_is_the_site_is_ignored():
    site = to_shape(RECTANGLE)
    assert kinds(RECTANGLE, {"self": site}) == [ROAD] * 4
    around = neighbours("west", "east", "north", self=site)
    assert kinds(RECTANGLE, around) == [ROAD, SIDE, REAR, SIDE]


def test_partial_contact_is_not_shared():
    assert kinds(RECTANGLE, {"small": shapely.box(20, 0, 30, 5)}) == [ROAD] * 4


def test_short_jog_does_not_split_limit():
    site, east = east_split_site(((20.0, 0.0), (20.0, 20.0), (20.2, 20.0), (20.2, 40.0)))
    around = neighbours("west", "north", east=east)
    assert kinds(site, around) == [ROAD, SIDE, SIDE, SIDE, REAR, SIDE]


def test_limit_run_wrapping_around_the_ring_start():
    assert kinds(RECTANGLE, neighbours("west", "north", "south")) == [SIDE, ROAD, SIDE, REAR]


def test_labels_follow_the_edges():
    result = edges(RECTANGLE, neighbours("west", "east", "north"))
    labelled = label_edges(result, snap_tolerance_m=0.5, collinear_angle_deg=20)
    for boundary, edge in zip(labelled, result, strict=True):
        assert (boundary.start, boundary.end) == (edge.start, edge.end)


def test_labels_read_only_the_other_side():
    ring = RECTANGLE.exterior
    sides = (PUBLIC, PARCEL, PARCEL, PARCEL)
    given = [
        Edge(start=start, end=end, length_m=1, other_side=side)
        for start, end, side in zip(ring[:-1], ring[1:], sides, strict=True)
    ]
    labelled = label_edges(given, snap_tolerance_m=0.5, collinear_angle_deg=20)
    assert [boundary.kind for boundary in labelled] == [ROAD, SIDE, REAR, SIDE]
