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
