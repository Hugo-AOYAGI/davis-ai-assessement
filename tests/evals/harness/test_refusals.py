import pytest
from langchain_core.messages import AIMessage, ToolMessage
from pydantic import ValidationError

from evals.harness.items import Item
from evals.harness.passes.scoring import EnvelopeSettings, Scoring, score_record
from evals.harness.refusals import ExpectedRefusal, refusal_checks
from evals.harness.runs.record import RunRecord
from evals.harness.scorers.trajectory import RunCost
from tests.evals.test_run import fake_judge


@pytest.fixture
def expected():
    return ExpectedRefusal(reason_pattern=r"(?i)cannot identify.*address")


@pytest.fixture
def messages():
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "geocode",
                    "id": "lookup",
                    "args": {"query": "fictional address"},
                }
            ],
        ),
        ToolMessage(
            content="No address matches 'fictional address'. Check the spelling.",
            tool_call_id="lookup",
        ),
        AIMessage(content="I cannot identify this address; please check the street name."),
    ]


def test_clean_explained_refusal_passes(expected, messages):
    assert all(refusal_checks(expected, messages, has_output=False, error=None).values())


@pytest.mark.parametrize(
    "failure",
    ["crash", "artifact", "silence", "no_lookup", "lookup_error", "submission", "wrong_reason"],
)
def test_other_failure_modes_are_not_clean_refusals(expected, messages, failure):
    if failure == "silence":
        messages.pop()
    elif failure == "no_lookup":
        messages = messages[-1:]
    elif failure == "lookup_error":
        messages[1] = ToolMessage(content="HTTP failure", tool_call_id="lookup", status="error")
    elif failure == "submission":
        messages.insert(
            2,
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_parcel",
                        "id": "submit",
                        "args": {},
                    }
                ],
            ),
        )
    elif failure == "wrong_reason":
        messages[-1] = AIMessage(content="The service is unavailable; try again later.")
    checks = refusal_checks(
        expected,
        messages,
        has_output=failure == "artifact",
        error="TimeoutError" if failure == "crash" else None,
    )
    assert not all(checks.values())


def test_refusal_pattern_must_compile():
    with pytest.raises(ValidationError):
        ExpectedRefusal(reason_pattern="[")


def test_refusal_items_reject_artifact_facts_and_other_levels():
    data = {
        "id": "negative",
        "level": "surveyor",
        "tests": "unknown address",
        "status": "verified",
        "built_by": "test",
        "input": {"address": "fictional"},
        "expected_refusal": {"reason_pattern": "cannot identify"},
    }
    assert Item.model_validate(data).expected_refusal is not None
    with pytest.raises(ValidationError, match="without facts"):
        Item.model_validate(data | {"facts": [{"key": "area_m2", "expect": 10}]})
    with pytest.raises(ValidationError, match="surveyor item"):
        Item.model_validate(
            data | {"level": "e2e", "input": {"address": "x", "program": "housing"}}
        )


@pytest.fixture
def refusal_item(expected):
    return Item.model_validate(
        {
            "id": "negative",
            "level": "surveyor",
            "tests": "unknown address",
            "status": "verified",
            "built_by": "test",
            "input": {"address": "fictional address"},
            "expected_refusal": expected,
        }
    )


@pytest.fixture
def scoring(matcher):
    return Scoring(
        matcher=matcher,
        judge=fake_judge(),
        sections=(),
        mode="full_sections",
        envelope=EnvelopeSettings(
            tolerance=0.02, quad_segs=8, min_area_m2=1, level_step_m=1, cut_tolerance_m=0.01
        ),
    )


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "silence",
        "crash",
        "accepted_site",
        "tool_status_error",
        "infrastructure_error_text",
        "empty_tool_result",
        "latest_lookup_failed",
        "latest_lookup_recovered",
    ],
)
def test_score_record_expected_refusal_end_to_end(
    refusal_item, messages, scoring, study_json, failure
):
    passed = failure in {None, "latest_lookup_recovered"}
    if failure == "silence":
        messages = messages[:-1]
    elif failure == "tool_status_error":
        messages[1] = ToolMessage(content="HTTP timeout", tool_call_id="lookup", status="error")
    elif failure == "infrastructure_error_text":
        messages[1] = ToolMessage(content="geocode failed: HTTP timeout", tool_call_id="lookup")
    elif failure == "empty_tool_result":
        messages[1] = ToolMessage(content="", tool_call_id="lookup")
    elif failure in {"latest_lookup_failed", "latest_lookup_recovered"}:
        messages[2:2] = [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "geocode", "id": "retry", "args": {"query": "fictional address"}}
                ],
            ),
            ToolMessage(content="geocode failed: HTTP timeout", tool_call_id="retry"),
        ]
        if failure == "latest_lookup_recovered":
            messages[4:4] = [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "geocode",
                            "id": "recovery",
                            "args": {"query": "fictional address"},
                        }
                    ],
                ),
                ToolMessage(
                    content="No address matches 'fictional address'.", tool_call_id="recovery"
                ),
            ]
    record = RunRecord(
        item_id=refusal_item.id,
        level=refusal_item.level,
        output=study_json["site"] if failure == "accepted_site" else None,
        messages=tuple(messages),
        cost=RunCost(cost_usd=0.0029, wall_time_s=1),
        error="TimeoutError: interrupted" if failure == "crash" else None,
    )
    result = score_record(refusal_item, record, scoring)
    assert result.passed is passed
    assert result.metrics().item_pass is passed
    assert result.metrics().grounded_accuracy == float(passed)
    assert len(result.facts) == 1 and result.facts[0].critical
    assert result.run.has_output is (failure == "accepted_site")
    assert result.trajectory is not None
    assert result.trajectory.tool_calls["geocode"] == (
        3 if failure == "latest_lookup_recovered" else 2 if failure == "latest_lookup_failed" else 1
    )


def test_normal_missing_artifact_is_still_a_failure(items, scoring):
    item = items["s01_joliot_curie"]
    assert item.expected_refusal is None
    record = RunRecord(
        item_id=item.id,
        level=item.level,
        output=None,
        cost=RunCost(),
    )
    result = score_record(item, record, scoring)
    assert not result.passed
    assert len(result.facts) == len(item.facts)
    assert all(not fact.correct for fact in result.facts)
