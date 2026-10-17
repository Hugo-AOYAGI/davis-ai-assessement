from collections.abc import Iterator
from typing import cast, override

import httpx
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from omegaconf import DictConfig
from pydantic import JsonValue

from agent.agents.config import load_config
from agent.agents.subagents import build_subagent
from agent.contracts.findings.site import SiteContext
from agent.contracts.geometry import BoundaryKind
from agent.tools.submit.artifacts import read_artifact

TOOLS = ["geocode_address", "find_parcels", "preview_site", "submit_site"]
LABEL = "4 Rue Joliot-curie 91190 Gif-sur-Yvette"
SITE_ARGS: dict[str, JsonValue] = {
    "address": LABEL,
    "parcel_ids": ["91272000CR0247"],
    "public_parcel_ids": ["91272000CR0249"],
    "method": "Geocoded the address and retained the plot nearest to the point.",
    "assumptions": ["CR0249 is a strip along the street, declared public space."],
}


class ScriptedModel(GenericFakeChatModel):
    """Fake chat model replaying scripted messages, accepting any tool binding."""

    @override
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


def call(name: str, args: dict[str, JsonValue], call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


@pytest.fixture
def cfg(monkeypatch, tmp_path) -> DictConfig:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")
    cfg = load_config(["subagents=[site_locator]"])
    cfg.subagents.site_locator.geo.http.cache_dir.relative = str(tmp_path)
    return cfg


@pytest.fixture
def offline(monkeypatch, transport):
    client = httpx.Client

    def replaying(**kwargs) -> httpx.Client:
        return client(**{**kwargs, "transport": transport})

    monkeypatch.setattr(httpx, "Client", replaying)


def test_subagent_builds_with_its_tools(cfg):
    graph = build_subagent(cfg, "site_locator")
    tools = cast("ToolNode", graph.nodes["tools"].bound).tools_by_name
    assert list(tools) == TOOLS
    assert "site" in cfg.subagents.site_locator.description


def test_scripted_run_stores_site(cfg, monkeypatch, offline, tmp_path):
    replies: Iterator[AIMessage] = iter(
        [
            call("geocode_address", {"query": "4 rue Joliot Curie, 91190 Gif-sur-Yvette"}, "g1"),
            call("submit_site", SITE_ARGS, "s1"),
            AIMessage("done"),
        ]
    )
    model = ScriptedModel(messages=replies)
    monkeypatch.setattr("agent.agents.subagents.build_model", lambda models, node: model)

    state = build_subagent(cfg, "site_locator").invoke({"messages": [HumanMessage("locate")]})

    site = read_artifact(state["artifacts"], "site", SiteContext)
    assert site is not None
    assert site.address == LABEL
    assert {b.kind for b in site.boundaries} == set(BoundaryKind)
    replies_by_id = {m.tool_call_id: m for m in state["messages"] if isinstance(m, ToolMessage)}
    assert LABEL in str(replies_by_id["g1"].content)
    assert replies_by_id["s1"].content == "site accepted."
    assert state["messages"][-1].content == "done"
    assert any(tmp_path.glob("*.json"))
