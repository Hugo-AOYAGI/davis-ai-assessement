import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.agents.config import load_config
from agent.contracts.findings.regulation import Verdict
from agent.contracts.inputs.case import Case
from agent.entrypoints import run
from agent.entrypoints.summary import (
    RunMetrics,
    RunSummary,
    citation_stats,
    final_text,
    rejected_submissions,
    run_summary,
)

METRICS = RunMetrics(
    address="4 rue Joliot Curie",
    overrides=("case=reference",),
    wall_time_s=12.5,
    usage={},
    total_tokens=0,
    cost_usd=0.0,
    rejected_submissions=0,
)


def submit_call(call_id):
    return {"name": "submit_study", "args": {}, "id": call_id, "type": "tool_call"}


MESSAGES = [
    HumanMessage("go"),
    AIMessage("", tool_calls=[submit_call("a")]),
    ToolMessage("rejected", tool_call_id="a", status="error"),
    AIMessage(
        "",
        tool_calls=[{"name": "read_file", "args": {}, "id": "b", "type": "tool_call"}],
    ),
    ToolMessage("boom", tool_call_id="b", status="error"),
    AIMessage("", tool_calls=[submit_call("c")]),
    ToolMessage("study accepted.", tool_call_id="c"),
    AIMessage("Study done."),
]


class FakeGraph:
    def __init__(self, state):
        self.state = state
        self.calls = []

    def invoke(self, payload, config):
        self.calls.append((payload, config))
        return self.state


def test_summary_of_accepted_study(verified):
    summary = run_summary(METRICS, verified)
    assert summary.accepted
    assert summary.study is not None
    assert summary.study.zone == "UMG"
    assert [(entry.building, entry.verdict) for entry in summary.study.admissibility] == [
        ("RSE", Verdict.PERMITTED),
        ("RJA", Verdict.CONDITIONAL),
    ]
    envelope = summary.study.envelope
    assert (envelope.site_area_m2, envelope.max_height_m, envelope.max_storeys) == (1200, 20, 6)
    assert envelope.max_footprint_ratio is None
    assert envelope.min_green_ratio == 0.2
    assert envelope.max_volume_m3 == 13020
    assert summary.study.ambiguities == 1
    stats = summary.study.citations
    assert (stats.checks, stats.text_verifiable, stats.verified) == (3, 2, 1)
    assert stats.pass_rate == pytest.approx(0.5)
    assert RunSummary.model_validate_json(summary.model_dump_json()) == summary


def test_summary_without_study():
    summary = run_summary(METRICS, None)
    assert not summary.accepted
    assert summary.study is None


def test_pass_rate_none_without_checkable_citations():
    assert citation_stats(()).pass_rate is None


def test_rejected_submissions_counts_gate_errors_only():
    assert rejected_submissions(MESSAGES, "submit_study") == 1


def test_final_text():
    assert final_text(MESSAGES) == "Study done."
    assert final_text([HumanMessage("go")]) == ""


def test_make_unattended_disables_ask_user():
    cfg = load_config(["policies.ask_user.mode=interactive"])
    run.make_unattended(cfg)
    assert cfg.policies.ask_user.mode == "disabled"


def test_run_study_offline(monkeypatch, verified):
    cfg = load_config()
    state = {"messages": MESSAGES, "artifacts": {"study": verified.model_dump(mode="json")}}
    fake = FakeGraph(state)
    monkeypatch.setattr(run, "build", lambda _cfg: fake)
    case = Case(address="1 rue X", program="Two buildings", corpus_id="c@1", facts=("120 rooms",))
    result, messages, study = run.run_study(cfg, case, ["case=reference"])
    assert study == verified
    assert messages == MESSAGES
    assert result.rejected_submissions == 1
    assert result.overrides == ("case=reference",)
    assert result.cost_usd == 0.0
    [(payload, config)] = fake.calls
    [request] = payload["messages"]
    assert "1 rue X" in request.text
    assert "- 120 rooms" in request.text
    assert config["recursion_limit"] == cfg.agent.recursion_limit


def test_write_outputs(tmp_path, verified):
    summary = run_summary(METRICS, verified)
    run.write_outputs(tmp_path, summary, verified, max_quote_chars=50)
    assert json.loads((tmp_path / "run_summary.json").read_text(encoding="utf-8"))["accepted"]
    assert (tmp_path / "verified_study.json").exists()
    assert (tmp_path / "report.md").read_text(encoding="utf-8").startswith("# Buildability study")


def test_write_outputs_without_study(tmp_path):
    run.write_outputs(tmp_path, run_summary(METRICS, None), None, max_quote_chars=50)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["run_summary.json"]
