import pytest
from langgraph.types import Command

from agent.contracts.envelope import EnvelopeStudy, EnvelopeSubmission
from agent.runtime.geometry.envelope.summary import describe_envelope
from agent.tools.envelope.compute import site_envelope
from agent.tools.envelope.submit import envelope_finalizer
from agent.tools.submit.factory import SubmissionRejected, submit_tool

QUESTION = "Does UMG 8 apply to two buildings joined by a podium?"


@pytest.fixture
def submit(geometry, settings):
    return submit_tool(
        name="submit_envelope",
        artifact="envelope",
        contract=EnvelopeSubmission,
        finalize=envelope_finalizer(site="site", geometry=geometry, settings=settings),
        summarize=describe_envelope,
    )


@pytest.fixture
def artifacts(site):
    return {"site": site.model_dump(mode="json")}


@pytest.fixture
def submitted(submit, invoke):
    def run(args, artifacts):
        return invoke(submit, args, artifacts)

    return run


@pytest.fixture
def submission_args(draft_args):
    point = {"question": QUESTION, "options": ["yes", "no"], "why": "UMG 8 is silent."}
    return {**draft_args, "open_points": [point]}


@pytest.fixture
def expected(site, rules, layout, geometry, settings):
    return site_envelope(site, rules, layout, geometry=geometry, settings=settings).study


def test_submission_stores_the_computed_envelope(
    submitted, reply, submission_args, artifacts, expected
):
    command = submitted(submission_args, artifacts)
    assert isinstance(command, Command)
    stored = EnvelopeStudy.model_validate(command.update["artifacts"]["envelope"])
    assert stored.proposal == expected.proposal
    assert stored.bounds == expected.bounds
    assert [point.question for point in stored.open_points] == [QUESTION]
    content = reply(command).content
    assert content.startswith("envelope accepted.\n\nSite area: 1800 m²")
    assert f"Open points:\n- {QUESTION}" in content


def test_bad_layout_is_rejected(submitted, reply, submission_args, artifacts):
    submission_args["layout"] = {**submission_args["layout"], "heights_m": [30, 15]}
    command = submitted(submission_args, artifacts)
    assert "artifacts" not in command.update
    message = reply(command)
    assert message.status == "error"
    assert "layout.heights_m.0: 30 m is above the maximum height of 'RSE' (25 m)" in message.content


def test_missing_site_is_rejected(submitted, reply, submission_args):
    command = submitted(submission_args, {})
    assert "artifacts" not in command.update
    assert "no `site` artifact in state" in reply(command).content


def test_compute_error_is_a_rejection(geometry, settings, site, rules, layout):
    finalize = envelope_finalizer(site="site", geometry=geometry, settings=settings)
    shorter = rules.model_copy(update={"buildings": rules.buildings[:1]})
    submission = EnvelopeSubmission.model_construct(rules=shorter, layout=layout, open_points=())
    with pytest.raises(SubmissionRejected, match="'RJA' has no maximum height"):
        finalize(submission, {"site": site.model_dump(mode="json")})
