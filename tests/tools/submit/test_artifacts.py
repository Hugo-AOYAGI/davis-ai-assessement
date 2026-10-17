from agent.contracts.evidence import Ambiguity, Resolution
from agent.tools.submit.artifacts import Artifacts, merge_artifacts, read_artifact

AMBIGUITY = Ambiguity(
    question="Which height applies?",
    chosen="20 m",
    rationale="Zone rule prevails.",
    resolved_by=Resolution.AGENT,
)


def test_merge_right_wins_per_key():
    left: Artifacts = {"site": {"a": 1}, "map": {"b": 2}}
    right: Artifacts = {"site": {"a": 3}}
    assert merge_artifacts(left, right) == {"site": {"a": 3}, "map": {"b": 2}}


def test_merge_is_none_safe_and_idempotent():
    data: Artifacts = {"site": {"a": 1}}
    assert merge_artifacts(None, None) == {}
    assert merge_artifacts(None, data) == data
    assert merge_artifacts(data, None) == data
    assert merge_artifacts(data, data) == data


def test_read_artifact_revalidates_dumped_contract():
    artifacts: Artifacts = {"ambiguity": AMBIGUITY.model_dump(mode="json")}
    assert read_artifact(artifacts, "ambiguity", Ambiguity) == AMBIGUITY


def test_read_artifact_missing():
    assert read_artifact(None, "ambiguity", Ambiguity) is None
    assert read_artifact({}, "ambiguity", Ambiguity) is None
