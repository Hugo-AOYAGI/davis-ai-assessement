import pytest
from pydantic import BaseModel

from agent.contracts.envelope import EnvelopeStudy, EnvelopeSubmission
from agent.contracts.evidence import ImageRegion, StoredCrop
from agent.contracts.findings.notes import DocNotes
from agent.contracts.findings.site import ParcelChoice, Site
from agent.contracts.findings.zone import ZoneFindings
from agent.contracts.geometry import Boundary, BoundaryKind
from agent.contracts.inputs.clarification import ClarificationRequest
from agent.contracts.study import Study, Verdict, VerifiedStudy

SUBMITTED = (
    ParcelChoice,
    ZoneFindings,
    DocNotes,
    Study,
    ClarificationRequest,
    EnvelopeSubmission,
)


def test_study_json_round_trip(study: Study):
    assert Study.model_validate_json(study.model_dump_json()) == study


def test_verified_study_json_round_trip(
    study: Study, site: Site, zone: ZoneFindings, envelope: EnvelopeStudy
):
    crop = StoredCrop(
        region=zone.region,
        pixels=(35, 70, 386, 316),
        path="outputs/crops/plu_reglement_graphique_p1_10-20-110-90.png",
    )
    verified = VerifiedStudy(
        study=study,
        site=site,
        boundaries=(Boundary(kind=BoundaryKind.ROAD, start=(0, 0), end=(40, 0)),),
        zone=zone,
        envelope=envelope,
        citation_checks=(),
        evidence=(crop,),
    )
    assert VerifiedStudy.model_validate_json(verified.model_dump_json()) == verified


def test_stored_crop_rejects_empty_pixels(zone: ZoneFindings):
    with pytest.raises(ValueError, match="not a box"):
        StoredCrop(region=zone.region, pixels=(5, 5, 5, 9), path="x.png")


@pytest.mark.parametrize("prohibited", [False, True])
def test_envelope_presence_matches_program(study, site, zone, envelope, prohibited):
    if prohibited:
        study = study.model_copy(
            update={
                "admissibility": tuple(
                    entry.model_copy(update={"verdict": Verdict.PROHIBITED})
                    for entry in study.admissibility
                )
            }
        )
    fields = dict(study=study, site=site, zone=zone, boundaries=(), citation_checks=(), evidence=())
    assert study.requires_envelope is not prohibited
    accepted = VerifiedStudy.model_validate(
        {**fields, "envelope": None if prohibited else envelope}
    )
    assert VerifiedStudy.model_validate_json(accepted.model_dump_json()) == accepted
    with pytest.raises(ValueError, match="envelope must be absent exactly"):
        VerifiedStudy.model_validate({**fields, "envelope": envelope if prohibited else None})


def test_region_schema_is_described():
    schema = ImageRegion.model_json_schema()
    assert "view_image overview" in schema["properties"]["region"]["description"]


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
