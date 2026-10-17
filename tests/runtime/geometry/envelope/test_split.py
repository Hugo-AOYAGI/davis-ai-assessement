import pytest
import shapely
from shapely import affinity

from agent.contracts.geometry import Boundary, BoundaryKind
from agent.runtime.geometry.envelope.split import (
    layout_heights,
    part_gaps,
    part_shares,
    split_footprint,
)

GROUND = shapely.box(4, 5, 36, 26)
ROAD = (Boundary(kind=BoundaryKind.ROAD, start=(0, 0), end=(40, 0)),)
WEST_ROAD = (Boundary(kind=BoundaryKind.ROAD, start=(0, 30), end=(0, 0)),)


def split(cut="along_long_axis", shares=(0.5, 0.5), gaps=(10,), road=ROAD, ground=GROUND):
    return split_footprint(ground, road, cut=cut, shares=shares, gaps=gaps, tolerance_m=0.01)


def test_along_long_axis_starts_from_the_road():
    first, second = split().parts
    assert first.area == pytest.approx(176, abs=0.5)
    assert second.area == pytest.approx(176, abs=0.5)
    assert first.bounds[1] == pytest.approx(5)
    assert second.bounds[3] == pytest.approx(26)
    assert second.bounds[1] - first.bounds[3] == pytest.approx(10, abs=0.02)


def test_across_long_axis_cuts_perpendicular_to_it():
    first, second = split(cut="across_long_axis", road=WEST_ROAD).parts
    assert first.bounds[0] == pytest.approx(4)
    assert first.bounds[2] < second.bounds[0]
    assert first.bounds[1::2] == pytest.approx((5, 26))


def test_shares_apply_to_the_usable_area():
    first, second = split(shares=(0.25, 0.75), gaps=(6,)).parts
    usable = 32 * (21 - 6)
    assert first.area == pytest.approx(0.25 * usable, abs=0.5)
    assert second.area == pytest.approx(0.75 * usable, abs=0.5)


def test_three_parts():
    parts = split(shares=(0.5, 0.25, 0.25), gaps=(3, 3)).parts
    usable = 32 * (21 - 6)
    assert [part.area for part in parts] == pytest.approx(
        [0.5 * usable, 0.25 * usable, 0.25 * usable], abs=0.5
    )


def test_gap_wider_than_the_footprint_leaves_no_part():
    result = split(gaps=(25,))
    assert result.parts == ()
    assert result.extent_m == pytest.approx(21)


def test_one_part_is_the_whole_footprint():
    assert split(shares=(1.0,), gaps=()).parts == (GROUND,)


def test_heights_default_to_the_maximums(make_rules, make_layout):
    rules = make_rules(heights=(("A", 20), ("B", 15)))
    assert layout_heights(rules, make_layout(order=("B", "A"))) == (15, 20)
    assert layout_heights(rules, make_layout(heights_m=(12, 9))) == (12, 9)


def test_shares_split_the_rest_equally(make_layout):
    assert part_shares(make_layout(order=("A",))) == ((1.0,), [])
    assert part_shares(make_layout(first_share=0.6)) == ((0.6, pytest.approx(0.4)), [])
    shares, notes = part_shares(make_layout(first_share=0.5, order=("A", "B", "C")))
    assert shares == (0.5, 0.25, 0.25)
    assert notes


def test_gaps_follow_facing_windows(make_rules, make_layout, distance):
    rules = make_rules(spacing_with=10, spacing_without=6)
    assert part_gaps(rules, make_layout(), (20, 20)) == ((10,), [])
    assert part_gaps(rules, make_layout(facing_windows=False), (20, 20)) == ((6,), [])


def test_missing_spacing_falls_back(make_rules, make_layout):
    gaps, notes = part_gaps(make_rules(spacing_with=None), make_layout(), (20, 20))
    assert gaps == (6,)
    assert "other one applies" in notes[0]
    gaps, notes = part_gaps(
        make_rules(spacing_with=None, spacing_without=None), make_layout(), (20, 20)
    )
    assert gaps == (0,)
    assert "No spacing rule" in notes[0]


def test_height_ratio_spacing_uses_the_taller_neighbour(make_rules, make_layout, distance):
    rules = make_rules(spacing_with=None).model_copy(
        update={"spacing_with_windows": distance(6, 0.5)}
    )
    gaps, notes = part_gaps(rules, make_layout(), (20, 15))
    assert gaps == (10,)
    assert "taller" in notes[0]


def test_rotated_footprint_is_cut_on_its_own_axes():
    ground = affinity.rotate(GROUND, 30, origin=(0, 0))
    start, end = affinity.rotate(shapely.LineString([(0, 0), (40, 0)]), 30, origin=(0, 0)).coords
    road = (Boundary(kind=BoundaryKind.ROAD, start=start, end=end),)
    first, second = split(road=road, ground=ground).parts
    assert first.area == pytest.approx(176, abs=0.5)
    assert second.area == pytest.approx(176, abs=0.5)
    assert first.distance(second) == pytest.approx(10, abs=0.02)
    assert first.distance(shapely.LineString((start, end))) < second.distance(
        shapely.LineString((start, end))
    )


def test_non_convex_footprint_keeps_the_shares():
    ground = shapely.Polygon([(0, 0), (40, 0), (40, 10), (10, 10), (10, 30), (0, 30)])
    road = (Boundary(kind=BoundaryKind.ROAD, start=(0, 0), end=(40, 0)),)
    parts = split(cut="across_long_axis", road=road, ground=ground, gaps=(4,)).parts
    assert parts[0].distance(parts[1]) == pytest.approx(4, abs=0.02)
    assert parts[0].area == pytest.approx(parts[1].area, abs=1)
