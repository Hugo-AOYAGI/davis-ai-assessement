import math

import pytest

from agent.contracts.evidence import Citation, Limit, SourceKind
from agent.contracts.geometry import Boundary, BoundaryKind, EnvelopeParameters, Polygon
from agent.runtime.geometry.envelope import compute_envelope

ROAD, SIDE, REAR = BoundaryKind.ROAD, BoundaryKind.SIDE, BoundaryKind.REAR
RECTANGLE = ((0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0), (0.0, 0.0))
L_SHAPE = (
    (0.0, 0.0),
    (30.0, 0.0),
    (30.0, 10.0),
    (10.0, 10.0),
    (10.0, 30.0),
    (0.0, 30.0),
    (0.0, 0.0),
)
DUMBBELL = (
    (0.0, 0.0),
    (20.0, 0.0),
    (20.0, 8.0),
    (30.0, 8.0),
    (30.0, 4.0),
    (42.0, 4.0),
    (42.0, 16.0),
    (30.0, 16.0),
    (30.0, 12.0),
    (20.0, 12.0),
    (20.0, 20.0),
    (0.0, 20.0),
    (0.0, 0.0),
)
CITATION = Citation(doc="plu", page=327, quote="5 mètres", source_kind=SourceKind.REGULATORY)
QUAD_SEGS = 8
MIN_AREA = 1.0


def limit(value):
    return Limit(value=value, rule="see article", citations=() if value is None else (CITATION,))


DEFAULTS = {"road": 5, "side": 3, "rear": 4, "height": None, "ratio": None, "green": None}


def parameters(**overrides):
    values = {**DEFAULTS, **overrides}
    return EnvelopeParameters(
        setback_road_m=limit(values["road"]),
        setback_side_m=limit(values["side"]),
        setback_rear_m=limit(values["rear"]),
        max_height_m=limit(values["height"]),
        max_storeys=limit(None),
        max_footprint_ratio=limit(values["ratio"]),
        min_green_ratio=limit(values["green"]),
    )


def site(exterior, kinds, holes=()):
    polygon = Polygon(crs="EPSG:2154", exterior=exterior, holes=holes)
    boundaries = tuple(
        Boundary(kind=kind, start=start, end=end)
        for kind, start, end in zip(kinds, exterior[:-1], exterior[1:], strict=True)
    )
    return polygon, boundaries


def rectangle(holes=()):
    return site(RECTANGLE, (ROAD, SIDE, REAR, SIDE), holes)


def envelope(target, params):
    polygon, boundaries = target
    return compute_envelope(polygon, boundaries, params, quad_segs=QUAD_SEGS, min_area_m2=MIN_AREA)


def test_rectangle_setbacks_give_inner_rectangle():
    result = envelope(rectangle(), parameters(road=5, side=3, rear=4, height=10, green=0.1))
    assert result.site_area_m2 == pytest.approx(1200)
    assert result.footprint_area_m2 == pytest.approx(34 * 21)
    assert result.max_footprint_area_m2 == pytest.approx(34 * 21)
    footprint = result.footprint
    assert footprint is not None
    assert footprint.crs == "EPSG:2154"
    assert footprint.exterior[0] == footprint.exterior[-1]
    xs = [x for x, _ in footprint.exterior]
    ys = [y for _, y in footprint.exterior]
    assert (min(xs), max(xs), min(ys), max(ys)) == pytest.approx((3, 37, 5, 26))
    assert result.assumptions == ("No footprint ratio set: footprint not capped by a ratio.",)


def test_l_shape_rounds_reflex_corner():
    target = site(L_SHAPE, (SIDE,) * 6)
    result = envelope(target, parameters(side=2, height=10, ratio=1, green=0))
    mitred = 26 * 6 + 6 * 20
    quarter_disc = QUAD_SEGS * 0.5 * 2**2 * math.sin(math.pi / (2 * QUAD_SEGS))
    assert result.site_area_m2 == pytest.approx(500)
    assert result.footprint_area_m2 == pytest.approx(mitred + 2 * 2 - quarter_disc)
    assert result.assumptions == ()


def test_setbacks_consuming_site_leave_no_footprint():
    result = envelope(rectangle(), parameters(road=16, side=21, rear=16, height=10))
    assert result.footprint is None
    assert result.footprint_area_m2 == 0
    assert result.max_footprint_area_m2 == 0
    assert result.max_volume_m3 == 0
    assert "Setbacks consume the whole site: no buildable footprint remains." in (
        result.assumptions
    )


@pytest.mark.parametrize(("ratio", "expected"), [(0.4, 480), (0.7, 714)])
def test_footprint_ratio_caps_footprint(ratio, expected):
    result = envelope(rectangle(), parameters(ratio=ratio))
    assert result.footprint_area_m2 == pytest.approx(714)
    assert result.max_footprint_area_m2 == pytest.approx(expected)


def test_missing_limits_are_assumed_absent():
    result = envelope(rectangle(), parameters(road=None, side=None, rear=None))
    assert result.footprint_area_m2 == pytest.approx(1200)
    assert result.min_green_area_m2 is None
    assert result.max_height_m is None
    assert result.max_volume_m3 is None
    assert result.assumptions == (
        "No road setback set: road limits not set back.",
        "No side setback set: side limits not set back.",
        "No rear setback set: rear limits not set back.",
        "No footprint ratio set: footprint not capped by a ratio.",
        "No green ratio set: no minimum green area.",
        "No height limit set: height and volume left open.",
    )


def test_volume_is_capped_footprint_times_height():
    result = envelope(rectangle(), parameters(height=12, ratio=0.4))
    assert result.max_height_m == 12
    assert result.max_volume_m3 == pytest.approx(480 * 12)


def test_green_requirement_caps_footprint():
    result = envelope(rectangle(), parameters(green=0.5, height=10))
    assert result.footprint_area_m2 == pytest.approx(714)
    assert result.min_green_area_m2 == pytest.approx(600)
    assert result.max_footprint_area_m2 == pytest.approx(600)
    assert result.max_volume_m3 == pytest.approx(6000)
    assert not any("green" in note for note in result.assumptions)


def test_smallest_cap_binds():
    result = envelope(rectangle(), parameters(ratio=0.4, green=0.5, height=10))
    assert result.max_footprint_area_m2 == pytest.approx(480)
    assert result.assumptions == ()


def test_green_requirement_left_unbinding_when_room_left():
    result = envelope(rectangle(), parameters(green=0.2))
    assert result.min_green_area_m2 == pytest.approx(240)
    assert result.max_footprint_area_m2 == pytest.approx(714)
    assert not any("green" in note for note in result.assumptions)


def test_split_footprint_keeps_largest_part():
    target = site(DUMBBELL, (SIDE,) * 12)
    result = envelope(target, parameters(side=3, height=10, ratio=1, green=0))
    footprint = result.footprint
    assert footprint is not None
    assert max(x for x, _ in footprint.exterior) < 20
    assert result.footprint_area_m2 > 14 * 14
    (note,) = result.assumptions
    assert note.startswith("Setbacks split the footprint into 2 parts: kept the largest")
    assert note.endswith("m² in 1 smaller part(s).")


def test_hole_is_kept_in_footprint():
    hole = ((10.0, 10.0), (20.0, 10.0), (20.0, 20.0), (10.0, 20.0), (10.0, 10.0))
    result = envelope(rectangle(holes=(hole,)), parameters(road=2, side=2, rear=2))
    assert result.site_area_m2 == pytest.approx(1100)
    assert result.footprint_area_m2 == pytest.approx(36 * 26 - 100)
    footprint = result.footprint
    assert footprint is not None
    (kept,) = footprint.holes
    assert kept[0] == kept[-1]
    assert sorted(set(kept)) == sorted(set(hole))
