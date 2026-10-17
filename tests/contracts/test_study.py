import pytest
from pydantic import BaseModel

from agent.contracts.findings.map import MapFindings
from agent.contracts.findings.oap import OAPFindings
from agent.contracts.findings.regulation import RegulationFindings
from agent.contracts.findings.site import SiteContext
from agent.contracts.inputs.clarification import ClarificationRequest
from agent.contracts.study import Study

SUBMITTED = (SiteContext, MapFindings, RegulationFindings, OAPFindings, Study, ClarificationRequest)


def test_study_json_round_trip(study: Study):
    assert Study.model_validate_json(study.model_dump_json()) == study


@pytest.mark.parametrize("model", SUBMITTED)
def test_tool_schemas_carry_field_descriptions(model: type[BaseModel]):
    schema = model.model_json_schema()
    described = [
        field
        for definition in (schema, *schema.get("$defs", {}).values())
        for field in definition.get("properties", {}).values()
        if "description" in field
    ]
    assert described
