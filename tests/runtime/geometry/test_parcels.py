from itertools import pairwise

import pytest
import shapely

from agent.contracts.geometry import Polygon
from agent.runtime.geometry.parcels import (
    DisjointParcelsError,
    mean_width,
    polygon_from_rings,
    shared_length,
    to_contract,
    to_shape,
    touching,
    union_parcels,
)

GRID = 0.05
SLIVER = 1.0


def test_polygon_from_rings_single_and_multi():
    square = [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)]]
    other = [[(5.0, 0.0), (6.0, 0.0), (6.0, 1.0), (5.0, 0.0)]]
    assert isinstance(polygon_from_rings([square]), shapely.Polygon)
    multi = polygon_from_rings([square, other])
    assert isinstance(multi, shapely.MultiPolygon)
    assert len(multi.geoms) == 2


def test_polygon_from_rings_with_hole():
    rings = [
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)],
        [(4.0, 4.0), (6.0, 4.0), (6.0, 6.0), (4.0, 6.0), (4.0, 4.0)],
    ]
    assert polygon_from_rings([rings]).area == pytest.approx(96.0)


def test_polygon_from_rings_empty_rejected():
    with pytest.raises(ValueError, match="no polygon"):
        polygon_from_rings([])


@pytest.mark.parametrize("gap_start", [20.0, 20.02])
def test_adjacent_parcels_with_digitising_gap_merge(gap_start: float):
    left = shapely.box(0, 0, gap_start, 30)
    right = shapely.box(gap_start + 0.01, 0, 40, 30)
    site = union_parcels([left, right], GRID, SLIVER)
    assert len(site.interiors) == 0
    assert site.area == pytest.approx(left.area + right.area, rel=1e-3)


def test_disjoint_parcels_rejected():
    with pytest.raises(DisjointParcelsError, match="2 separate parts") as caught:
        union_parcels([shapely.box(0, 0, 10, 10), shapely.box(20, 0, 30, 10)], GRID, SLIVER)
    assert caught.value.part_areas_m2 == pytest.approx((100.0, 100.0))


def test_l_shape_union():
    site = union_parcels([shapely.box(0, 0, 20, 10), shapely.box(0, 10, 10, 20)], GRID, SLIVER)
    assert site.area == pytest.approx(300.0)
    assert len(site.exterior.coords) == 7


def test_sliver_hole_removed():
    hole = shapely.box(10, 10, 10.5, 10.5).exterior
    site = union_parcels(
        [shapely.Polygon(shapely.box(0, 0, 30, 30).exterior, [hole])], GRID, SLIVER
    )
    assert len(site.interiors) == 0
    assert site.area == pytest.approx(900.0)


def test_large_hole_kept():
    hole = shapely.box(10, 10, 20, 20).exterior
    site = union_parcels(
        [shapely.Polygon(shapely.box(0, 0, 30, 30).exterior, [hole])], GRID, SLIVER
    )
    assert len(site.interiors) == 1


def test_sliver_part_dropped():
    site = union_parcels([shapely.box(0, 0, 10, 10), shapely.box(20, 0, 20.5, 0.5)], GRID, SLIVER)
    assert site.area == pytest.approx(100.0)


def test_empty_union_rejected():
    with pytest.raises(ValueError, match="no area"):
        union_parcels([shapely.box(0, 0, 0.1, 0.1)], GRID, SLIVER)


def test_union_is_counter_clockwise_without_repeated_points():
    clockwise = shapely.Polygon([(0, 0), (0, 10), (0, 10), (10, 10), (10, 0)])
    site = union_parcels([clockwise], GRID, SLIVER)
    assert site.exterior.is_ccw
    coords = list(site.exterior.coords)
    assert all(a != b for a, b in pairwise(coords))


def test_to_contract_rounds_closes_and_orients():
    clockwise = shapely.Polygon([(0, 0), (0, 10.004), (10.0012, 10.0), (10.0, 0.001)])
    contract = to_contract(clockwise, "EPSG:2154", 2)
    assert contract.crs == "EPSG:2154"
    assert contract.exterior[0] == contract.exterior[-1]
    assert set(contract.exterior) == {(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)}
    assert to_shape(contract).exterior.is_ccw


def test_to_contract_drops_duplicates_created_by_rounding():
    shape = shapely.Polygon([(0, 0), (10, 0), (10.001, 0.001), (10, 10), (0, 10)])
    assert len(to_contract(shape, "EPSG:2154", 2).exterior) == 5


def test_round_trip_contract_shape():
    contract = Polygon(
        crs="EPSG:2154",
        exterior=((0.0, 0.0), (20.0, 0.0), (20.0, 40.0), (0.0, 40.0), (0.0, 0.0)),
        holes=(((5.0, 5.0), (5.0, 10.0), (10.0, 10.0), (10.0, 5.0), (5.0, 5.0)),),
    )
    assert to_contract(to_shape(contract), "EPSG:2154", 2) == contract


def test_mean_width_of_a_strip_and_a_square():
    assert mean_width(shapely.box(0, 0, 100, 1)) == pytest.approx(0.99, abs=0.01)
    assert mean_width(shapely.box(0, 0, 40, 40)) == pytest.approx(20)
    assert mean_width(shapely.Point(0, 0)) == 0


def test_touching_within_tolerance():
    shapes = {
        "a": shapely.box(0, 0, 10, 10),
        "b": shapely.box(10.3, 0, 20, 10),
        "c": shapely.box(30, 0, 40, 10),
    }
    assert touching(shapes, 0.5) == {"a": ("b",), "b": ("a",), "c": ()}
    assert touching(shapes, 0.1) == {"a": (), "b": (), "c": ()}


def test_shared_length_along_a_neighbour():
    site = shapely.box(0, 0, 20, 40)
    assert shared_length(site, shapely.box(20, 10, 30, 30), 0.5) == pytest.approx(20, abs=1.1)
    assert shared_length(site, shapely.box(50, 0, 60, 40), 0.5) == 0
