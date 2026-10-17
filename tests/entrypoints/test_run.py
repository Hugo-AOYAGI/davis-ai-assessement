import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.messages.ai import UsageMetadata
from langchain_core.outputs import ChatGeneration, LLMResult

from agent.agents.config import load_config
from agent.contracts.inputs.case import Case
from agent.contracts.study import Verdict
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
    usage_by_node={},
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


def llm_result(model, input_tokens, output_tokens):
    message = AIMessage(
        "ok",
        usage_metadata=UsageMetadata(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
        response_metadata={"model_name": model},
    )
    return LLMResult(generations=[[ChatGeneration(message=message)]])


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
    assert summary.study.parcel_ids == ("91272000AB0123",)
    assert summary.study.overlays == ("Périmètre d'OAP",)
    assert summary.study.oap_applicable
    assert summary.study.evidence_crops == 1
    assert [(entry.building, entry.verdict) for entry in summary.study.admissibility] == [
        ("RSE", Verdict.PERMITTED),
        ("RJA", Verdict.CONDITIONAL),
    ]
    envelope = summary.study.envelope
    assert envelope.site_area_m2 == pytest.approx(1200)
    assert envelope.max_footprint_ratio is None
    assert envelope.min_green_ratio == 0.2
    assert envelope.min_green_area_m2 == pytest.approx(240)
    assert [bound.name for bound in envelope.bounds] == ["largest", "windows"]
    assert envelope.bounds[1].footprint_area_m2 == pytest.approx(32 * 22)
    assert envelope.bounds[1].total_volume_m3 == pytest.approx(32 * 22 * 20)
    proposal = envelope.proposal
    assert proposal.fits
    assert [m.building for m in proposal.buildings] == ["RSE", "RJA"]
    assert [m.max_height_m for m in proposal.buildings] == [20, 20]
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

    def fake_build(_cfg, ledger):
        ledger.logger("orchestrator").on_llm_end(llm_result("claude-sonnet-5-5", 1_000, 100))
        ledger.logger("surveyor")
        return fake

    monkeypatch.setattr(run, "build", fake_build)
    case = Case(address="1 rue X", program="Two buildings", corpus_id="c@1", facts=("120 rooms",))
    result, messages, study = run.run_study(cfg, case, ["case=reference"])
    assert study == verified
    assert messages == MESSAGES
    assert result.rejected_submissions == 1
    assert result.overrides == ("case=reference",)
    assert result.cost_usd == 0.0
    assert result.usage_by_node.keys() == {"orchestrator", "surveyor"}
    orchestrator = result.usage_by_node["orchestrator"]
    assert (orchestrator.calls, orchestrator.input, orchestrator.output) == (1, 1_000, 100)
    assert orchestrator.cost_usd == pytest.approx(0.003)
    assert result.usage_by_node["surveyor"].calls == 0
    [(payload, config)] = fake.calls
    [request] = payload["messages"]
    assert "1 rue X" in request.text
    assert "- 120 rooms" in request.text
    assert config["recursion_limit"] == cfg.agent.recursion_limit


def test_write_outputs(tmp_path, verified):
    root = tmp_path / "root"
    crop = root / verified.evidence[0].path
    crop.parent.mkdir(parents=True)
    crop.write_bytes(b"png")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    summary = run_summary(METRICS, verified)
    run.write_outputs(run_dir, summary, verified, max_quote_chars=50, root=root)
    assert json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))["accepted"]
    assert (run_dir / "verified_study.json").exists()
    report = (run_dir / "report.md").read_text(encoding="utf-8")
    assert report.startswith("# Buildability study")
    assert "(evidence/plu_graphique_p1.png)" in report
    assert (run_dir / "evidence" / "plu_graphique_p1.png").read_bytes() == b"png"


def test_missing_crop_is_skipped(tmp_path, verified, caplog):
    run.write_outputs(
        tmp_path, run_summary(METRICS, verified), verified, max_quote_chars=50, root=tmp_path
    )
    assert not (tmp_path / "evidence").exists()
    assert "plu_graphique_p1.png is missing, not copied" in caplog.text


def test_write_outputs_without_study(tmp_path):
    run.write_outputs(tmp_path, run_summary(METRICS, None), None, max_quote_chars=50, root=tmp_path)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["run_summary.json"]
