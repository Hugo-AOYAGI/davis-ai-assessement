from collections.abc import Iterator
from typing import cast, override

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from omegaconf import DictConfig, OmegaConf, open_dict
from pydantic import JsonValue

from agent.agents.config import load_config, read_prompt
from agent.agents.orchestrator import build, system_prompt
from agent.agents.subagents import build_subagent, build_tools, subagent_specs
from agent.contracts.findings.oap import OAPFindings


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


OAP_ARGS: dict[str, JsonValue] = {
    "applicable": True,
    "name": "Joliot Curie",
    "rationale": "The site lies inside the OAP perimeter.",
    "citations": [{"doc": "oap", "page": 33, "quote": "Joliot Curie", "source_kind": "regulatory"}],
}

SUBMIT_OAP: dict[str, JsonValue] = {
    "_target_": "agent.tools.submit.factory.submit_tool",
    "artifact": "oap_findings",
    "contract": {
        "_target_": "hydra.utils.get_class",
        "path": "agent.contracts.findings.oap.OAPFindings",
    },
}

DESCRIPTION = "Reads the OAP covering the site and reports its prescriptions."

TESTER: dict[str, JsonValue] = {
    "description": DESCRIPTION,
    "prompt": "prompts/orchestrator/system.md",
    "model": "oap_analyst",
    "tools": [SUBMIT_OAP],
}


@pytest.fixture(autouse=True)
def dummy_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")


@pytest.fixture
def cfg() -> DictConfig:
    cfg = load_config()
    with open_dict(cfg):
        cfg.subagents.tester = TESTER
    return cfg


def install_fakes(monkeypatch: pytest.MonkeyPatch, models: dict[str, ScriptedModel]) -> None:
    def fake_build_model(models_cfg: DictConfig, node: str) -> ScriptedModel:
        return models[node]

    monkeypatch.setattr("agent.agents.orchestrator.build_model", fake_build_model)
    monkeypatch.setattr("agent.agents.subagents.build_model", fake_build_model)


def graph_tools(graph) -> dict[str, BaseTool]:
    return cast(ToolNode, graph.nodes["tools"].bound).tools_by_name


def test_default_config_builds():
    graph = build(load_config())
    assert isinstance(graph, CompiledStateGraph)
    assert "artifacts" in graph.channels
    assert "task" in graph_tools(graph)


def test_subagent_appears_in_task_tool(cfg):
    graph = build(cfg)
    description = graph_tools(graph)["task"].description
    assert "tester" in description
    assert DESCRIPTION in description


def test_playbook_is_appended():
    agent_cfg = load_config(["agent.playbook=conf/config.yaml"]).agent
    prompt = system_prompt(agent_cfg)
    assert prompt.startswith(read_prompt(agent_cfg.prompt))
    assert prompt.endswith(read_prompt("conf/config.yaml"))


def test_build_tools_instantiates_submit_tool():
    tools = build_tools(OmegaConf.create([SUBMIT_OAP]))
    assert [tool.name for tool in tools] == ["submit_oap_findings"]


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
        {"oap_analyst": scripted(call("submit_oap_findings", OAP_ARGS, "s1"), AIMessage("done"))},
    )
    graph = build_subagent(cfg, "tester")
    assert "artifacts" in graph.channels
    state = graph.invoke({"messages": [HumanMessage("analyse the OAP")]})
    assert OAPFindings.model_validate(state["artifacts"]["oap_findings"]) == (
        OAPFindings.model_validate(OAP_ARGS)
    )
    assert state["messages"][-1].content == "done"


def test_end_to_end_delegation(cfg, monkeypatch):
    install_fakes(
        monkeypatch,
        {
            "orchestrator": scripted(
                call("task", {"description": "analyse the OAP", "subagent_type": "tester"}, "t1"),
                AIMessage("parent done"),
            ),
            "oap_analyst": scripted(
                call("submit_oap_findings", OAP_ARGS, "s1"), AIMessage("child done")
            ),
        },
    )
    state = build(cfg).invoke({"messages": [HumanMessage("go")]})

    assert OAPFindings.model_validate(state["artifacts"]["oap_findings"]) == (
        OAPFindings.model_validate(OAP_ARGS)
    )
    replies = {m.tool_call_id: m.content for m in state["messages"] if isinstance(m, ToolMessage)}
    assert replies == {"t1": "child done"}
    assert state["messages"][-1].content == "parent done"
