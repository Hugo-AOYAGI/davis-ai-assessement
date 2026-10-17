from collections.abc import Iterator
from typing import cast, override

import pytest
from hydra.utils import instantiate
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from omegaconf import DictConfig, OmegaConf, open_dict
from pydantic import JsonValue

from agent.agents.config import load_config, project_path
from agent.agents.orchestrator import (
    AskUserMode,
    build,
    orchestrator_tools,
    parse_ask_user_mode,
)
from agent.agents.subagents import build_subagent, build_tools, subagent_specs
from agent.contracts.findings.notes import DocNotes
from agent.llm.costs import CostLedger
from agent.llm.factory import load_pricing


class ScriptedModel(GenericFakeChatModel):
    """Fake chat model replaying scripted messages, accepting any tool binding."""

    @override
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


def scripted(*messages: AIMessage) -> ScriptedModel:
    replies: Iterator[AIMessage] = iter(messages)
    return ScriptedModel(messages=replies)


def call(name: str, args: dict[str, JsonValue], call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


NOTES_ARGS: dict[str, JsonValue] = {
    "label": "oap",
    "notes": [
        {
            "topic": "perimeter",
            "text": "The site lies inside the OAP perimeter.",
            "citations": [
                {"doc": "oap", "page": 33, "quote": "Joliot Curie", "source_kind": "regulatory"}
            ],
        }
    ],
}

SUBMIT_NOTES: dict[str, JsonValue] = {
    "_target_": "agent.tools.submit.factory.submit_tool",
    "name": "submit_notes",
    "artifact": "notes.{label}",
    "contract": {
        "_target_": "hydra.utils.get_class",
        "path": "agent.contracts.findings.notes.DocNotes",
    },
}

DESCRIPTION = "Reads the documents for an aim and returns cited notes."

TESTER: dict[str, JsonValue] = {
    "description": DESCRIPTION,
    "prompt": "prompts/orchestrator/system.md",
    "model": "doc_analyst",
    "tools": [SUBMIT_NOTES],
}


@pytest.fixture(autouse=True)
def dummy_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")


def with_tester(*overrides: str) -> DictConfig:
    cfg = load_config(["subagents=[]", *overrides])
    with open_dict(cfg):
        cfg.subagents.tester = TESTER
    return cfg


@pytest.fixture
def cfg() -> DictConfig:
    return with_tester()


def install_fakes(monkeypatch: pytest.MonkeyPatch, models: dict[str, ScriptedModel]) -> None:
    def fake_build_model(models_cfg: DictConfig, node: str, ledger: CostLedger) -> ScriptedModel:
        return models[node]

    monkeypatch.setattr("agent.agents.orchestrator.build_model", fake_build_model)
    monkeypatch.setattr("agent.agents.subagents.build_model", fake_build_model)


def graph_tools(graph) -> dict[str, BaseTool]:
    return cast(ToolNode, graph.nodes["tools"].bound).tools_by_name


SUBAGENTS = ("surveyor", "zoning_analyst", "doc_analyst", "architect")
OWN_TOOLS = {"read_artifact", "submit_study", "revise_study", "load_playbook", "ask_user"}


def test_default_config_builds():
    graph = build(load_config())
    assert isinstance(graph, CompiledStateGraph)
    assert "artifacts" in graph.channels
    tools = graph_tools(graph)
    assert {"task", *OWN_TOOLS} <= tools.keys()
    description = tools["task"].description
    assert all(f"- {name}:" in description for name in SUBAGENTS)
    assert "- general-purpose:" not in description


def test_ledger_keeps_one_logger_per_model_node():
    cfg = load_config()
    ledger = CostLedger(load_pricing(cfg.models))
    build(cfg, ledger)
    usage = ledger.usage()
    assert usage.keys() == {"orchestrator", *SUBAGENTS}
    assert all(entry.calls == 0 and entry.cost_usd == 0.0 for entry in usage.values())


def test_orchestrator_tools(cfg):
    graph = build(cfg)
    assert "artifacts" in graph.channels
    tools = graph_tools(graph)
    assert {"task", *OWN_TOOLS} <= tools.keys()


def test_ask_user_disabled():
    tools = graph_tools(build(with_tester("policies.ask_user.mode=disabled")))
    assert "ask_user" not in tools
    assert {"task", *OWN_TOOLS - {"ask_user"}} <= tools.keys()


def test_general_purpose_follows_config_on_rebuild():
    enabled = build(with_tester("agent.general_purpose_subagent=true"))
    assert "- general-purpose:" in graph_tools(enabled)["task"].description
    disabled = build(with_tester())
    assert "- general-purpose:" not in graph_tools(disabled)["task"].description


def test_unknown_ask_user_mode():
    with pytest.raises(ValueError, match=r"unknown policies\.ask_user\.mode 'sometimes'"):
        build(with_tester("policies.ask_user.mode=sometimes"))
    assert parse_ask_user_mode("disabled") is AskUserMode.DISABLED


def test_playbook_tool_reads_configured_files():
    cfg = load_config(["agent.language=French"])
    tools = {tool.name: tool for tool in orchestrator_tools(cfg)}
    playbook = tools["load_playbook"]
    assert "- `study`: Full buildability study" in playbook.description
    text = playbook.invoke({"name": "study"})
    assert text.startswith("# Playbook: buildability study")
    assert "$language" not in text
    assert "French" in text


def test_playbook_has_a_task_per_required_notes_label():
    cfg = load_config()
    tools = {tool.name: tool for tool in orchestrator_tools(cfg)}
    text = tools["load_playbook"].invoke({"name": "study"})
    for label in cfg.policies.study.required_notes:
        assert f"**Task `{label}`**" in text
    assert "`uses`" not in text


def test_subagent_appears_in_task_tool(cfg):
    graph = build(cfg)
    description = graph_tools(graph)["task"].description
    assert "tester" in description
    assert DESCRIPTION in description


def test_gate_corpus_is_loaded_lazily(monkeypatch):
    calls = []

    def fake_load_corpus(directory):
        calls.append(directory)
        return "corpus"

    monkeypatch.setattr("agent.adapters.corpus.store.load_corpus", fake_load_corpus)
    cfg = with_tester()
    build(cfg)
    assert calls == []
    [gate] = [node for node in cfg.agent.tools if node._target_.endswith(".submit_study_tools")]
    provider = instantiate(gate.corpus)
    assert calls == []
    assert provider() == "corpus"
    assert calls == [project_path(cfg.corpus.dir)]


def test_build_tools_instantiates_submit_tool():
    tools = build_tools(OmegaConf.create([SUBMIT_NOTES]))
    assert [tool.name for tool in tools] == ["submit_notes"]


def test_build_tools_flattens_tool_lists():
    pair = {**SUBMIT_NOTES, "_target_": "agent.tools.submit.factory.submit_tools"}
    tools = build_tools(OmegaConf.create([pair, SUBMIT_NOTES]))
    assert [tool.name for tool in tools] == ["submit_notes", "revise_notes", "submit_notes"]


def test_build_tools_rejects_lists_of_non_tools():
    with pytest.raises(TypeError, match="built int, not a BaseTool"):
        build_tools(OmegaConf.create([{"_target_": "builtins.list", "_args_": [[1]]}]))


@pytest.mark.parametrize(
    ("name", "artifact"),
    [("surveyor", "parcel"), ("zoning_analyst", "zone"), ("doc_analyst", "notes")],
)
def test_default_subagents_have_revise_tools(name, artifact):
    tools = {tool.name for tool in build_tools(load_config().subagents[name].tools)}
    assert {f"submit_{artifact}", f"revise_{artifact}"} <= tools


def test_build_tools_rejects_non_tools():
    with pytest.raises(TypeError, match="not a BaseTool"):
        build_tools(OmegaConf.create([{"_target_": "builtins.dict"}]))


def test_unknown_subagent(cfg):
    with pytest.raises(KeyError, match=r"unknown sub-agent 'nope'.*tester"):
        build_subagent(cfg, "nope")


def test_specs_follow_config(cfg):
    specs = subagent_specs(cfg)
    assert [(spec["name"], spec["description"]) for spec in specs] == [("tester", DESCRIPTION)]


def test_subagent_standalone(cfg, monkeypatch):
    install_fakes(
        monkeypatch,
        {"doc_analyst": scripted(call("submit_notes", NOTES_ARGS, "s1"), AIMessage("done"))},
    )
    graph = build_subagent(cfg, "tester")
    assert "artifacts" in graph.channels
    state = graph.invoke({"messages": [HumanMessage("read the OAP")]})
    assert DocNotes.model_validate(state["artifacts"]["notes.oap"]) == (
        DocNotes.model_validate(NOTES_ARGS)
    )
    assert state["messages"][-1].content == "done"


def test_end_to_end_delegation(cfg, monkeypatch):
    install_fakes(
        monkeypatch,
        {
            "orchestrator": scripted(
                call("task", {"description": "read the OAP", "subagent_type": "tester"}, "t1"),
                AIMessage("parent done"),
            ),
            "doc_analyst": scripted(
                call("submit_notes", NOTES_ARGS, "s1"), AIMessage("child done")
            ),
        },
    )
    state = build(cfg).invoke({"messages": [HumanMessage("go")]})

    assert DocNotes.model_validate(state["artifacts"]["notes.oap"]) == (
        DocNotes.model_validate(NOTES_ARGS)
    )
    replies = {m.tool_call_id: m.content for m in state["messages"] if isinstance(m, ToolMessage)}
    assert replies == {"t1": "child done"}
    assert state["messages"][-1].content == "parent done"
