from typing import cast, override

import httpx
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from agent.agents.config import load_config
from agent.agents.subagents import build_subagent
from agent.contracts.envelope import EnvelopeStudy
from agent.tools.submit.artifacts import read_artifact

TOOLS = ["read_artifact", "preview_envelope", "submit_envelope"]


class ScriptedModel(GenericFakeChatModel):
    @override
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


def call(name, args, call_id):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


@pytest.fixture
def cfg(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")
    cfg = load_config()
    cfg.geo.http.cache_dir.relative = str(tmp_path)
    return cfg


@pytest.fixture
def offline(monkeypatch, transport):
    client = httpx.Client

    def replaying(**kwargs):
        return client(**{**kwargs, "transport": transport})

    monkeypatch.setattr(httpx, "Client", replaying)


def script(monkeypatch, replies):
    model = ScriptedModel(messages=iter(replies))
    monkeypatch.setattr("agent.agents.subagents.build_model", lambda models, node, ledger: model)


def test_architect_builds_offline_with_its_tools(cfg, monkeypatch):
    script(monkeypatch, [])
    graph = build_subagent(cfg, "architect")
    tools = cast("ToolNode", graph.nodes["tools"].bound).tools_by_name
    assert list(tools) == TOOLS
    assert "`envelope`" in cfg.subagents.architect.description
    assert cfg.models.nodes[cfg.subagents.architect.model].model == "claude-haiku-5-5"


def test_scripted_run_previews_then_stores_the_envelope(
    cfg, monkeypatch, offline, site, draft_args
):
    script(
        monkeypatch,
        [
            call("read_artifact", {"name": "site"}, "r1"),
            call("preview_envelope", draft_args, "p1"),
            call("submit_envelope", draft_args, "s1"),
            AIMessage("done"),
        ],
    )
    graph = build_subagent(cfg, "architect")
    state = graph.invoke(
        {
            "messages": [HumanMessage("place RSE and RJA")],
            "artifacts": {"site": site.model_dump(mode="json")},
        }
    )
    envelope = read_artifact(state["artifacts"], "envelope", EnvelopeStudy)
    assert envelope is not None
    assert [massing.building for massing in envelope.proposal.buildings] == ["RSE", "RJA"]
    replies = {m.tool_call_id: m for m in state["messages"] if isinstance(m, ToolMessage)}
    preview = replies["p1"].content
    assert isinstance(preview, list)
    assert [block["type"] for block in preview if isinstance(block, dict)] == [
        "text",
        "text",
        "image",
    ]
    assert str(replies["s1"].content).startswith("envelope accepted.")
