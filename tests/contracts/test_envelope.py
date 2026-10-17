import pytest
from pydantic import ValidationError

from agent.contracts.envelope import (
    BuildingLimits,
    Distance,
    EnvelopeRules,
    EnvelopeStudy,
    EnvelopeSubmission,
    Layout,
    SetbackRule,
    layout_errors,
)
from agent.contracts.evidence import Citation, Limit
from agent.contracts.geometry import BoundaryKind


def test_distance_needs_a_term(citation: Citation):
    with pytest.raises(ValidationError, match="min_m, height_ratio or both"):
        Distance(rule="H/2", citations=(citation,))
    assert Distance(height_ratio=0.5, rule="H/2", citations=(citation,)).min_m is None


def test_distance_needs_a_citation():
    with pytest.raises(ValidationError, match="at least 1 item"):
        Distance(min_m=4, rule="4 m", citations=())


def test_setback_off_the_limit_needs_a_distance():
    with pytest.raises(ValidationError, match="may not be built on"):
        SetbackRule(kind=BoundaryKind.SIDE, on_limit_allowed=False)
    assert SetbackRule(kind=BoundaryKind.SIDE, on_limit_allowed=True).with_windows is None


def test_building_needs_a_height():
    with pytest.raises(ValidationError, match="positive value"):
        BuildingLimits(
            building="A",
            max_height_m=Limit(value=None, rule="none"),
            max_storeys=Limit(value=None, rule="none"),
        )


def test_rules_need_one_setback_per_kind(rules: EnvelopeRules):
    data = rules.model_dump()
    data["setbacks"] = [data["setbacks"][0], data["setbacks"][1], data["setbacks"][1]]
    with pytest.raises(ValidationError) as error:
        EnvelopeRules.model_validate(data)
    assert "2 rules for kind side" in str(error.value)
    assert "0 rules for kind rear" in str(error.value)


def test_rules_reject_repeated_buildings_and_bad_ratios(rules: EnvelopeRules, citation: Citation):
    data = rules.model_dump()
    data["buildings"] = [data["buildings"][0], data["buildings"][0]]
    data["min_green_ratio"] = Limit(value=20, rule="20 %", citations=(citation,)).model_dump()
    with pytest.raises(ValidationError) as error:
        EnvelopeRules.model_validate(data)
    assert "label 'A' repeated" in str(error.value)
    assert "between 0 and 1" in str(error.value)


@pytest.mark.parametrize("share", [0, 1, 1.5])
def test_first_share_is_strictly_between_0_and_1(layout: Layout, share):
    with pytest.raises(ValidationError, match="first_share"):
        Layout.model_validate({**layout.model_dump(), "first_share": share})


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"order": ("A", "A")}, "each building appears once"),
        ({"heights_m": (15,)}, "one height per building"),
        ({"heights_m": (15, 0)}, "must be positive"),
    ],
)
def test_layout_validation(layout: Layout, changes, message):
    with pytest.raises(ValidationError, match=message):
        Layout.model_validate({**layout.model_dump(), **changes})


def test_layout_errors(rules: EnvelopeRules, layout: Layout):
    assert layout_errors(rules, layout) == ()
    taller = layout.model_copy(update={"heights_m": (21, 18)})
    assert layout_errors(rules, taller) == (
        "layout.heights_m.0: 21 m is above the maximum height of 'A' (20 m)",
    )
    renamed = layout.model_copy(update={"order": ("A", "C")})
    errors = layout_errors(rules, renamed)
    assert "layout.order: 'C' is not a building of rules.buildings (A, B)" in errors
    assert "layout.order: building 'B' of rules.buildings is missing" in errors


def test_submission_rejects_inconsistent_layout(rules: EnvelopeRules, layout: Layout):
    assert EnvelopeSubmission(rules=rules, layout=layout).open_points == ()
    with pytest.raises(ValidationError, match="above the maximum height"):
        EnvelopeSubmission(rules=rules, layout=layout.model_copy(update={"heights_m": (25, 18)}))


def test_envelope_study_round_trip(envelope: EnvelopeStudy):
    assert EnvelopeStudy.model_validate_json(envelope.model_dump_json()) == envelope
