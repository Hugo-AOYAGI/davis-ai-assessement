import json
from typing import cast, override

import httpx
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from omegaconf import DictConfig
from pydantic import JsonValue

from agent.agents.config import load_config
from agent.agents.subagents import build_subagent, build_tools
from agent.contracts.findings.site import Site
from agent.tools.submit.artifacts import read_artifact
from agent.tools.submit.factory import DONE

TOOLS = ["geocode", "find_parcels", "describe_parcels", "site_view", "submit_parcel"]
LON, LAT = 2.165254, 48.709836
LABEL = "4 Rue Joliot-curie 91190 Gif-sur-Yvette"
PLOT, STRIP = "91272000CR0247", "91272000CR0249"
CHOICE: dict[str, JsonValue] = {
    "address": LABEL,
    "parcel_ids": [PLOT],
    "rationale": "Point 2.5 m from CR0247; CR0249 (1.8 m) is a 116 m2 strip, set aside.",
    "assumptions": ["Cadastre is current."],
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
    cfg = load_config()
    cfg.geo.http.cache_dir.relative = str(tmp_path)
    return cfg


@pytest.fixture
def offline(monkeypatch, transport):
    client = httpx.Client

    def replaying(**kwargs) -> httpx.Client:
        return client(**{**kwargs, "transport": transport})

    monkeypatch.setattr(httpx, "Client", replaying)


def script(monkeypatch, replies: list[AIMessage]) -> None:
    model = ScriptedModel(messages=iter(replies))
    monkeypatch.setattr("agent.agents.subagents.build_model", lambda models, node, ledger: model)


def test_subagent_builds_with_its_tools(cfg, monkeypatch):
    script(monkeypatch, [])
    graph = build_subagent(cfg, "surveyor")
    tools = cast("ToolNode", graph.nodes["tools"].bound).tools_by_name
    assert list(tools) == TOOLS
    assert "`site` artifact" in cfg.subagents.surveyor.description


def test_site_view_node_is_shared_by_interpolation(cfg):
    (tool,) = build_tools([cfg.geo.site_view])
    assert tool.name == "site_view"
    assert cfg.geo.site_view.image_px <= 2000
    assert set(cfg.geo.imagery.layers) == {"map", "aerial"}


def test_scripted_run_stores_site(cfg, monkeypatch, offline, tmp_path):
    point: dict[str, JsonValue] = {"longitude": LON, "latitude": LAT}
    script(
        monkeypatch,
        [
            call("geocode", {"query": "4 rue Joliot Curie, 91190 Gif-sur-Yvette"}, "g1"),
            call("find_parcels", point, "f1"),
            call("describe_parcels", {"ids": [STRIP, PLOT], **point}, "d1"),
            call("site_view", {"ids": [STRIP, PLOT], "kind": "aerial"}, "v1"),
            call("submit_parcel", CHOICE, "s1"),
            AIMessage("done"),
        ],
    )
    state = build_subagent(cfg, "surveyor").invoke({"messages": [HumanMessage("locate")]})

    site = read_artifact(state["artifacts"], "site", Site)
    assert site is not None
    assert site.address == LABEL
    assert [parcel.id for parcel in site.parcels] == [PLOT]
    replies = {m.tool_call_id: m for m in state["messages"] if isinstance(m, ToolMessage)}
    assert LABEL in str(replies["g1"].content)
    assert json.loads(str(replies["d1"].content))["one_piece"] is True
    view = replies["v1"].content
    assert isinstance(view, list)
    assert [block["type"] for block in view if isinstance(block, dict)] == ["text", "image"]
    accepted, summary, done = str(replies["s1"].content).split("\n\n")
    assert accepted == "site accepted."
    assert done == DONE
    assert json.loads(summary)["parcels"] == [{"id": PLOT, "contenance_m2": 5960}]
    assert state["messages"][-1].content == "done"
    assert any(tmp_path.glob("*.png"))
