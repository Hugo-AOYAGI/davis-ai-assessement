from typing import cast, override

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from agent.agents.subagents import build_subagent


@pytest.fixture(autouse=True)
def dummy_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")


def test_subagent_builds_offline(map_cfg):
    graph = build_subagent(map_cfg, "zoning_map_reader")
    assert "artifacts" in graph.channels
    tools = cast(ToolNode, graph.nodes["tools"].bound).tools_by_name
    assert set(tools) == {"view_map", "view_legend", "submit_map_findings"}


class ScriptedModel(GenericFakeChatModel):
    @override
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


def test_view_map_through_graph(map_cfg, site_data, monkeypatch):
    replies = iter(
        [
            AIMessage(content="", tool_calls=[{"name": "view_map", "args": {}, "id": "v1"}]),
            AIMessage("done"),
        ]
    )
    model = ScriptedModel(messages=replies)
    monkeypatch.setattr("agent.agents.subagents.build_model", lambda models, node: model)
    graph = build_subagent(map_cfg, "zoning_map_reader")
    state = graph.invoke(
        {"messages": [HumanMessage("read the plan")], "artifacts": {"site": site_data}}
    )
    (reply,) = [m for m in state["messages"] if isinstance(m, ToolMessage)]
    assert [block["type"] for block in reply.content] == ["text", "image"]
