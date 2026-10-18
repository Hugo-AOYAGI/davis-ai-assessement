import json
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.messages.ai import UsageMetadata
from langchain_core.outputs import ChatGeneration, LLMResult
from langchain_core.runnables import RunnableLambda

from agent.agents.config import load_config
from evals.harness import tasks
from evals.harness.items import Item
from evals.harness.tasks import RunRecord, run_item

SITE = {"address": "4 rue Joliot Curie", "area_m2": 5952.0}


def item(level, payload, item_id="x01"):
    return Item.model_validate(
        {
            "id": item_id,
            "level": level,
            "tests": "t",
            "status": "verified",
            "built_by": "test",
            "input": payload,
        }
    )


SURVEYOR = item("surveyor", {"address": "4 rue Joliot Curie", "program": "housing"}, "s01")
DOC = item(
    "doc",
    {
        "label": "rules",
        "aim": "heights",
        "topics": ["height"],
        "context": {"zone": "UGa", "program": "housing"},
    },
    "d01",
)
E2E = item("e2e", {"address": "4 rue Joliot Curie", "program": "RSE", "facts": ["2 buildings"]})


def call(name, call_id):
    return {"name": name, "args": {}, "id": call_id, "type": "tool_call"}


def priced_call(handler, model="claude-haiku-5-5"):
    usage = UsageMetadata(input_tokens=1_000_000, output_tokens=0, total_tokens=1_000_000)
    message = AIMessage("ok", usage_metadata=usage, response_metadata={"model_name": model})
    handler.on_llm_end(LLMResult(generations=[[ChatGeneration(message=message)]]), run_id=uuid4())


class FakeGraph:
    def __init__(self, state=None, error=None):
        self.state = state
        self.error = error
        self.payloads = []

    def invoke(self, payload, config):
        self.payloads.append((payload, config))
        for handler in config["callbacks"]:
            priced_call(handler)
        if self.error is not None:
            raise self.error
        return self.state


@pytest.fixture
def cfg():
    return load_config(["+eval=harness"])


def install(monkeypatch, graph):
    built = []

    def build(cfg, name):
        built.append(name)
        return graph

    monkeypatch.setattr(tasks, "build_subagent", build)
    return built


def test_component_run_records_artifact_messages_rejections_and_cost(cfg, monkeypatch):
    messages = [
        HumanMessage("task"),
        AIMessage("", tool_calls=[call("submit_parcel", "a")]),
        ToolMessage("parcel_ids: required", tool_call_id="a", status="error"),
        AIMessage("", tool_calls=[call("revise_parcel", "b")]),
        ToolMessage("still wrong", tool_call_id="b", status="error"),
        AIMessage("", tool_calls=[call("revise_parcel", "c")]),
        ToolMessage("site accepted.", tool_call_id="c"),
        AIMessage("Done."),
    ]
    graph = FakeGraph({"messages": messages, "artifacts": {"site": SITE, "other": {}}})
    built = install(monkeypatch, graph)
    record = run_item(cfg, SURVEYOR)
    assert built == ["surveyor"]
    ((payload, config),) = graph.payloads
    text = payload["messages"][0].content
    assert "Address: 4 rue Joliot Curie" in text
    assert "Program: housing" in text
    assert config["recursion_limit"] == cfg.eval.eval_tasks.recursion_limit
    assert record.output == SITE
    assert record.error is None
    assert record.level == "surveyor"
    assert record.subagent_runs == ()
    assert len(record.messages) == len(messages)
    assert record.rejections == (
        "submit_parcel: parcel_ids: required",
        "revise_parcel: still wrong",
    )
    assert record.cost.cost_usd == pytest.approx(cfg.models.pricing["claude-haiku-5-5"].input)
    assert record.cost.wall_time_s == record.wall_time_s
    again = RunRecord.model_validate_json(record.model_dump_json())
    assert again == record
    assert isinstance(again.messages[2], ToolMessage)
    assert again.messages[2].status == "error"


def test_doc_run_reads_the_labelled_artifact(cfg, monkeypatch):
    notes = {"label": "rules", "notes": []}
    install(monkeypatch, FakeGraph({"messages": [], "artifacts": {"notes.rules": notes}}))
    record = run_item(cfg, DOC)
    assert record.output == notes


def test_missing_artifact_gives_no_output(cfg, monkeypatch):
    install(monkeypatch, FakeGraph({"messages": [AIMessage("I give up.")]}))
    record = run_item(cfg, SURVEYOR)
    assert record.output is None
    assert record.error is None


def test_exception_becomes_a_failed_record(cfg, monkeypatch):
    install(monkeypatch, FakeGraph(error=RuntimeError("API down")))
    record = run_item(cfg, SURVEYOR)
    assert record.error == "RuntimeError: API down"
    assert record.output is None
    assert record.messages == ()
    assert record.cost.cost_usd == pytest.approx(cfg.models.pricing["claude-haiku-5-5"].input)
    json.loads(record.model_dump_json())


def test_e2e_runs_the_study_unattended_and_captures_subagents(cfg, monkeypatch):
    seen = {}
    read = call("read_pages", "r")
    read["args"] = {"doc": "plu_reglement", "start": 326, "end": 326}
    sub_messages = [
        HumanMessage("rules task"),
        AIMessage("", tool_calls=[read]),
        ToolMessage("text", tool_call_id="r"),
        AIMessage("", tool_calls=[call("submit_notes", "n")]),
        ToolMessage("notes.rules accepted.", tool_call_id="n"),
    ]
    doc_analyst = RunnableLambda(lambda state: {"messages": sub_messages}).with_config(
        {"run_name": "doc_analyst"}
    )
    orchestrator_messages = [
        HumanMessage("study"),
        AIMessage("", tool_calls=[call("submit_study", "s")]),
        ToolMessage("study accepted.", tool_call_id="s"),
    ]

    def fake_run_study(study_cfg, case, overrides, callbacks):
        seen["mode"] = study_cfg.policies.ask_user.mode
        seen["case"] = case
        RunnableLambda(lambda _: doc_analyst.invoke({})).invoke(
            None, config={"callbacks": list(callbacks)}
        )
        return None, orchestrator_messages, None

    monkeypatch.setattr(tasks, "run_study", fake_run_study)
    record = run_item(cfg, E2E)
    assert seen["mode"] == "disabled"
    assert cfg.policies.ask_user.mode != "disabled"
    assert seen["case"].facts == ("2 buildings",)
    assert seen["case"].corpus_id == cfg.corpus.id
    assert record.subagent_runs == ("doc_analyst",)
    assert [m.content for m in record.messages[:1]] == ["rules task"]
    assert record.messages[-1].content == "study accepted."
    assert record.output is None


def test_e2e_output_is_the_verified_study(cfg, monkeypatch, study):
    monkeypatch.setattr(tasks, "run_study", lambda *args: (None, [], study))
    record = run_item(cfg, E2E)
    assert record.output == study.model_dump(mode="json")


def test_legacy_wall_time_is_loaded_but_not_duplicated(cfg, monkeypatch):
    install(monkeypatch, FakeGraph({"messages": []}))
    record = run_item(cfg, SURVEYOR)
    saved = record.model_dump(mode="json")
    saved["wall_time_s"] = 99.0
    restored = RunRecord.model_validate(saved)
    assert restored.wall_time_s == record.cost.wall_time_s
    assert "wall_time_s" not in restored.model_dump()
    assert "wall_time_s" in restored.model_dump()["cost"]


def test_failed_component_retains_submission_rejections(cfg, monkeypatch):
    rejected = [
        AIMessage("", tool_calls=[call("submit_parcel", "rejected")]),
        ToolMessage("parcel_ids: missing", tool_call_id="rejected", status="error"),
    ]

    def fail(_):
        raise RuntimeError("inference unavailable")

    graph = RunnableLambda(lambda _: {"messages": rejected}) | RunnableLambda(fail)
    install(monkeypatch, graph)
    record = run_item(cfg, SURVEYOR)
    assert record.error == "RuntimeError: inference unavailable"
    assert record.rejections == ("submit_parcel: parcel_ids: missing",)
    assert [type(message) for message in record.messages] == [HumanMessage, AIMessage, ToolMessage]
    assert record.subagent_runs == ()
