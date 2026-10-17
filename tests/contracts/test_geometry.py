import pytest
from pydantic import ValidationError

from agent.contracts.evidence import Citation, Limit
from agent.contracts.geometry import EnvelopeParameters, Polygon


def test_open_ring_rejected():
    with pytest.raises(ValidationError, match="closed"):
        Polygon(crs="EPSG:2154", exterior=((0, 0), (1, 0), (1, 1), (0, 1)))


def test_ratio_out_of_range_rejected(parameters: EnvelopeParameters, citation: Citation):
    data = parameters.model_dump()
    data["min_green_ratio"] = Limit(value=20, rule="20 %", citations=(citation,)).model_dump()
    with pytest.raises(ValidationError, match="between 0 and 1"):
        EnvelopeParameters.model_validate(data)


@pytest.mark.parametrize("ring", [(), ((0, 0),), ((0, 0), (1, 1), (0, 0))])
def test_short_hole_ring_rejected(polygon: Polygon, ring):
    with pytest.raises(ValidationError, match="at least 4"):
        Polygon.model_validate({**polygon.model_dump(), "holes": (ring,)})


def test_open_hole_ring_rejected(polygon: Polygon):
    with pytest.raises(ValidationError, match="closed"):
        Polygon.model_validate(
            {**polygon.model_dump(), "holes": (((1, 1), (2, 1), (2, 2), (1, 2)),)}
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_polygon_coordinate_rejected(polygon: Polygon, value):
    with pytest.raises(ValidationError, match="finite"):
        Polygon.model_validate(
            {**polygon.model_dump(), "exterior": ((value, 0), (1, 0), (1, 1), (value, 0))}
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("setback_road_m", -1, "nonnegative"),
        ("setback_side_m", -1, "nonnegative"),
        ("setback_rear_m", -1, "nonnegative"),
        ("max_height_m", 0, "positive"),
        ("max_height_m", -1, "positive"),
        ("max_storeys", 0, "positive"),
        ("max_storeys", -1, "positive"),
        ("max_storeys", 2.5, "whole numbers"),
    ],
)
def test_invalid_envelope_limit_rejected(parameters, citation, field, value, message):
    data = parameters.model_dump()
    data[field] = Limit(value=value, rule="see article", citations=(citation,)).model_dump()
    with pytest.raises(ValidationError, match=message):
        EnvelopeParameters.model_validate(data)


@pytest.mark.parametrize("field", EnvelopeParameters.model_fields)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_envelope_limit_rejected(parameters, citation, field, value):
    data = parameters.model_dump()
    data[field] = Limit(value=value, rule="see article", citations=(citation,)).model_dump()
    with pytest.raises(ValidationError, match="finite"):
        EnvelopeParameters.model_validate(data)


def test_zero_setbacks_are_valid(parameters):
    data = parameters.model_dump()
    for field in ("setback_road_m", "setback_side_m", "setback_rear_m"):
        data[field]["value"] = 0
    validated = EnvelopeParameters.model_validate(data)
    assert validated.setback_road_m.value == 0


def test_absent_limits_are_valid(parameters):
    data = parameters.model_dump()
    for limit in data.values():
        limit["value"] = None
    validated = EnvelopeParameters.model_validate(data)
    assert all(getattr(validated, field).value is None for field in EnvelopeParameters.model_fields)
