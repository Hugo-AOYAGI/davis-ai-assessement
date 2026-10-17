from itertools import pairwise

import pytest
import shapely

from agent.contracts.geometry import BoundaryKind, BuildingMassing, Level
from agent.runtime.geometry.envelope.levels import (
    Bound,
    Cap,
    SetBackSite,
    distance_at,
    ground_cap,
    rise,
    scale_together,
    setback_at,
    volume,
)
from agent.runtime.geometry.envelope.shapes import site_shape


def test_distance_takes_the_larger_term(distance):
    rule = distance(4, 0.5)
    assert distance_at(rule, 6) == 4
    assert distance_at(rule, 20) == 10
    assert distance_at(distance(None, 1), 12) == 12


def test_largest_uses_zero_on_the_limit_else_the_smallest(setback, distance):
    on_limit = setback(BoundaryKind.ROAD, without_windows=distance(1), on_limit=True)
    choice = setback(BoundaryKind.SIDE, distance(6), distance(3))
    assert setback_at(on_limit, Bound.LARGEST, 20) == 0
    assert setback_at(choice, Bound.LARGEST, 20) == 3


def test_windows_falls_back_to_without_then_zero(setback, distance):
    assert setback_at(setback(BoundaryKind.SIDE, distance(6), distance(3)), Bound.WINDOWS, 5) == 6
    blind = setback(BoundaryKind.ROAD, without_windows=distance(1), on_limit=True)
    assert setback_at(blind, Bound.WINDOWS, 5) == 1
    free = setback(BoundaryKind.REAR, on_limit=True)
    assert setback_at(free, Bound.WINDOWS, 5) == 0


def raised(polygon, boundaries, rules, height, step=1.0):
    site = site_shape(polygon)
    allowed = SetBackSite(site, boundaries, rules, Bound.WINDOWS, quad_segs=8)
    ground = allowed.at(0)
    return rise(ground, height, allowed.at, step_m=step, min_area_m2=1)


def test_fixed_setbacks_give_one_level(polygon, boundaries, make_rules):
    result = raised(polygon, boundaries, make_rules(), 20)
    (level,) = result.levels
    assert (level.from_m, level.to_m, level.area_m2) == (0, 20, pytest.approx(32 * 21))
    assert result.footprint is not None
    assert result.footprint.bounds == pytest.approx((4, 5, 36, 26))
    assert volume(result.levels) == pytest.approx(32 * 21 * 20)


def test_height_ratio_gives_shrinking_levels(polygon, boundaries, make_rules, setback, distance):
    rules = make_rules(side=setback(BoundaryKind.SIDE, distance(4, 0.5)))
    levels = raised(polygon, boundaries, rules, 20).levels
    assert (levels[0].from_m, levels[0].to_m, levels[0].area_m2) == (0, 8, pytest.approx(672))
    assert len(levels) == 13
    assert [level.area_m2 for level in levels[1:]] == pytest.approx(
        [(40 - top) * 21 for top in range(9, 21)]
    )
    assert all(a.area_m2 > b.area_m2 for a, b in pairwise(levels))
    assert volume(levels) == pytest.approx(8 * 672 + 21 * sum(40 - top for top in range(9, 21)))


def test_last_slice_may_be_thinner(polygon, boundaries, make_rules, setback, distance):
    rules = make_rules(side=setback(BoundaryKind.SIDE, distance(None, 1)))
    levels = raised(polygon, boundaries, rules, 2.5).levels
    assert [(level.from_m, level.to_m) for level in levels] == [(0, 1), (1, 2), (2, 2.5)]


def test_rise_stops_when_nothing_is_left(polygon, boundaries, make_rules, setback, distance):
    rules = make_rules(side=setback(BoundaryKind.SIDE, distance(None, 1)))
    levels = raised(polygon, boundaries, rules, 30).levels
    assert (levels[-1].to_m, levels[-1].area_m2) == (19, pytest.approx(2 * 21))


def test_rise_of_nothing_is_empty():
    result = rise(None, 10, lambda _: shapely.Polygon(), step_m=1, min_area_m2=1)
    assert (result.footprint, result.levels) == (None, ())


def test_ground_cap_takes_the_smaller(make_rules):
    assert ground_cap(make_rules(), 1000) is None
    ratio_cap = ground_cap(make_rules(ratio=0.4), 1000)
    assert ratio_cap is not None
    assert ratio_cap.area_m2 == pytest.approx(400)
    cap = ground_cap(make_rules(ratio=0.4, green=0.7), 1000)
    assert cap is not None
    assert cap.area_m2 == pytest.approx(300)
    assert "green" in cap.reason


def massing(name, area_m2):
    levels = (Level(from_m=0, to_m=10, area_m2=area_m2),)
    return BuildingMassing(
        building=name,
        footprint=None,
        footprint_area_m2=area_m2,
        max_height_m=10,
        levels=levels,
        volume_m3=area_m2 * 10,
    )


def test_caps_scale_every_building_by_one_factor():
    scaled, notes = scale_together([massing("A", 300), massing("B", 100)], Cap(200, "the cap"))
    assert [m.footprint_area_m2 for m in scaled] == pytest.approx([150, 50])
    assert [m.levels[0].area_m2 for m in scaled] == pytest.approx([150, 50])
    assert [m.volume_m3 for m in scaled] == pytest.approx([1500, 500])
    (note,) = notes
    assert "exceeds the cap" in note
    assert "0.500" in note


def test_caps_below_the_limit_change_nothing():
    massings = [massing("A", 100)]
    assert scale_together(massings, Cap(200, "the cap")) == (massings, [])
    assert scale_together(massings, None) == (massings, [])
