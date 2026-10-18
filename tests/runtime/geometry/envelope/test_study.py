import pytest

from agent.contracts.findings.notes import OpenPoint
from agent.contracts.geometry import BoundaryKind
from agent.runtime.geometry.envelope.shapes import site_shape
from agent.runtime.geometry.envelope.study import compute_envelope_study
from agent.runtime.geometry.envelope.summary import describe_envelope


@pytest.fixture
def compute(polygon, boundaries, make_rules, make_layout, settings):
    def run(rules=None, layout=None, **kwargs):
        return compute_envelope_study(
            polygon,
            boundaries,
            rules or make_rules(),
            layout or make_layout(),
            settings=settings,
            **kwargs,
        )

    return run


def test_fixed_setbacks_give_a_prism_per_bound(compute):
    study = compute()
    assert [bound.name for bound in study.bounds] == ["largest", "windows"]
    windows = study.bounds[1]
    assert windows.footprint_area_m2 == pytest.approx(672)
    (massing,) = windows.buildings
    assert massing.building == "A, B"
    assert len(massing.levels) == 1
    assert massing.volume_m3 == pytest.approx(672 * 20)
    assert windows.total_volume_m3 == pytest.approx(672 * 20)
    assert windows.fits
    assert study.site_area_m2 == pytest.approx(1200)
    assert study.min_green_area_m2 is None


def test_largest_builds_on_the_limits_allowed(compute, make_rules, setback, distance):
    rules = make_rules(
        road=setback(BoundaryKind.ROAD, without_windows=distance(1), on_limit=True),
        side=setback(BoundaryKind.SIDE, distance(6), distance(3)),
    )
    largest, windows = compute(rules).bounds
    assert largest.footprint_area_m2 == pytest.approx((40 - 6) * (30 - 4))
    assert windows.footprint_area_m2 == pytest.approx((40 - 12) * (30 - 1 - 4))


def test_bound_has_one_massing_per_height(compute, make_rules):
    study = compute(make_rules(heights=(("A", 25), ("B", 18), ("C", 18))), None)
    windows = study.bounds[1]
    assert [m.building for m in windows.buildings] == ["A", "B, C"]
    assert windows.total_volume_m3 == pytest.approx(672 * 25)
    assert any("alternatives" in note for note in windows.assumptions)


def test_height_ratio_gives_several_levels(compute, make_rules, setback, distance):
    rules = make_rules(side=setback(BoundaryKind.SIDE, distance(4, 0.5)))
    (massing,) = compute(rules).bounds[1].buildings
    assert len(massing.levels) == 13
    assert massing.levels[-1].area_m2 < massing.levels[0].area_m2


def test_proposal_splits_with_the_spacing(compute):
    proposal = compute().proposal
    assert proposal.name == "proposal"
    assert proposal.fits
    assert [m.building for m in proposal.buildings] == ["A", "B"]
    assert [m.footprint_area_m2 for m in proposal.buildings] == pytest.approx([176, 176], abs=0.5)
    first, second = (m.footprint for m in proposal.buildings)
    assert max(y for _, y in first.exterior) < min(y for _, y in second.exterior)
    assert proposal.total_volume_m3 == pytest.approx(352 * 20, abs=10)


def test_proposal_uses_the_layout_heights(compute, make_layout):
    proposal = compute(layout=make_layout(heights_m=(12, 20))).proposal
    assert [m.max_height_m for m in proposal.buildings] == [12, 20]
    assert proposal.buildings[0].volume_m3 == pytest.approx(176 * 12, abs=10)


def test_gap_that_does_not_fit_fails(compute, make_rules):
    proposal = compute(make_rules(spacing_with=25)).proposal
    assert not proposal.fits
    assert "does not fit" in proposal.warnings[0]
    assert all(m.footprint is None and m.volume_m3 == 0 for m in proposal.buildings)
    assert "DO NOT FIT" in describe_envelope(compute(make_rules(spacing_with=25)))


def test_empty_part_fails(compute, make_layout):
    proposal = compute(layout=make_layout(first_share=0.001)).proposal
    assert not proposal.fits
    assert proposal.warnings == ("A: its part of the footprint is empty.",)


def test_caps_trim_physical_footprints(compute, make_rules):
    study = compute(make_rules(ratio=0.2))
    proposal = study.proposal
    assert sum(m.footprint_area_m2 for m in proposal.buildings) == pytest.approx(240, abs=0.5)
    assert [m.footprint_area_m2 for m in proposal.buildings] == pytest.approx([120, 120], abs=0.5)
    assert any("trimmed" in note for note in proposal.assumptions)
    assert study.bounds[1].buildings[0].footprint_area_m2 == pytest.approx(240, abs=0.5)


def test_green_cap_is_reported(compute, make_rules):
    study = compute(make_rules(green=0.5))
    assert study.min_green_area_m2 == pytest.approx(600, abs=0.5)
    assert study.bounds[1].buildings[0].footprint_area_m2 == pytest.approx(600, abs=0.5)


def test_one_building_takes_the_whole_footprint(compute, make_rules, make_layout):
    rules = make_rules(heights=(("A", 20),))
    proposal = compute(rules, make_layout(order=("A",))).proposal
    assert proposal.buildings[0].footprint_area_m2 == pytest.approx(672)


def test_open_points_are_kept(compute):
    point = OpenPoint(question="Is the spacing measured at the eaves?", why="Not defined.")
    study = compute(open_points=(point,))
    assert study.open_points == (point,)
    assert "Is the spacing measured at the eaves?" in describe_envelope(study)


def test_summary_gives_each_scenario(compute):
    text = describe_envelope(compute())
    assert text.startswith("Site area: 1200 m²; minimum green area: not set")
    assert "Bound largest" in text
    assert "Bound windows" in text
    assert "Proposal (cut along_long_axis, first share 0.5, order A then B" in text
    assert "- A, B: ground 672 m², height 20 m, volume 13440 m³" in text
    assert "the buildings fit" in text


def test_capped_areas_and_volumes_match_geometry(compute, make_rules, setback, distance):
    uncapped = compute(make_rules(side=setback(BoundaryKind.SIDE, distance(4, 0.5))))
    capped = compute(make_rules(side=setback(BoundaryKind.SIDE, distance(4, 0.5)), ratio=0.2))
    for original, scenario in zip(
        (*uncapped.bounds, uncapped.proposal), (*capped.bounds, capped.proposal), strict=True
    ):
        for before, after in zip(original.buildings, scenario.buildings, strict=True):
            assert after.footprint is not None
            shape = site_shape(after.footprint)
            assert site_shape(before.footprint).covers(shape)
            assert after.footprint_area_m2 == pytest.approx(shape.area)
            assert after.levels[0].area_m2 == pytest.approx(shape.area)
            assert all(level.area_m2 <= shape.area for level in after.levels)
            assert after.volume_m3 == pytest.approx(
                sum(level.area_m2 * (level.to_m - level.from_m) for level in after.levels)
            )
    first, second = (site_shape(massing.footprint) for massing in capped.proposal.buildings)
    assert first.distance(second) >= 10


def test_zero_cap_has_no_building_geometry(compute, make_rules):
    study = compute(make_rules(ratio=0))
    for scenario in (*study.bounds, study.proposal):
        assert not scenario.fits
        assert scenario.total_volume_m3 == 0
        assert all(
            building.footprint is None and not building.levels for building in scenario.buildings
        )
