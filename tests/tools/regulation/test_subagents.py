from typing import cast, override

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from agent.agents.config import load_config
from agent.agents.subagents import build_subagent

SUBAGENTS = "subagents=[regulation_researcher,oap_analyst]"
RESEARCHER_TOOLS = {
    "read_zone",
    "read_article",
    "read_section",
    "list_sections",
    "read_pages",
    "get_definition",
    "search",
    "submit_regulation_findings",
}
OAP_TOOLS = {"list_sections", "read_section", "read_pages", "search", "submit_oap_findings"}
HEIGHT = {
    "doc": "plu_reglement",
    "page": 3,
    "article": "UMG 10",
    "quote": "la hauteur maximale des constructions est fixée à",
    "source_kind": "regulatory",
}


@pytest.fixture(autouse=True)
def dummy_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")


def tool_names(graph):
    return set(cast(ToolNode, graph.nodes["tools"].bound).tools_by_name)


@pytest.mark.parametrize("retrieval", ["navigation", "full_sections"])
def test_subagents_build_offline(retrieval):
    cfg = load_config([SUBAGENTS, f"retrieval={retrieval}"])
    assert tool_names(build_subagent(cfg, "regulation_researcher")) == RESEARCHER_TOOLS
    assert tool_names(build_subagent(cfg, "oap_analyst")) == OAP_TOOLS


class ScriptedModel(GenericFakeChatModel):
    @override
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


def limit(value=None, citations=()):
    return {"value": value, "rule": "not regulated", "citations": list(citations)}


def findings(quote):
    return {
        "zone": "UMG",
        "admissibility": [
            {
                "building": "A",
                "stated_use": "Résidence étudiante",
                "destination": "Habitation",
                "verdict": "permitted",
                "citations": [{**HEIGHT, "quote": quote}],
            }
        ],
        "envelope": {
            "setback_road_m": limit(),
            "setback_side_m": limit(),
            "setback_rear_m": limit(),
            "max_height_m": limit(20, [HEIGHT]),
            "max_storeys": limit(),
            "max_footprint_ratio": limit(),
            "min_green_ratio": limit(),
        },
        "parking": [],
        "rules": [],
    }


def call(name, args, call_id):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def test_researcher_reads_and_submits_through_graph(corpus_dir, monkeypatch):
    cfg = load_config([SUBAGENTS, f"retrieval.corpus.directory='{corpus_dir.as_posix()}'"])
    replies = iter(
        [
            call("read_article", {"zone": "UMG", "article": "10"}, "r1"),
            call(
                "submit_regulation_findings",
                findings("une citation inventée de toutes pièces"),
                "s1",
            ),
            call("submit_regulation_findings", findings(HEIGHT["quote"]), "s2"),
            AIMessage("done"),
        ]
    )
    model = ScriptedModel(messages=replies)
    monkeypatch.setattr("agent.agents.subagents.build_model", lambda models, node: model)
    graph = build_subagent(cfg, "regulation_researcher")
    state = graph.invoke({"messages": [HumanMessage("read zone UMG")]})
    read, rejected, accepted = [m for m in state["messages"] if isinstance(m, ToolMessage)]
    assert "--- plu_reglement p.3 ---" in read.content
    assert "admissibility.0.citations.0 (plu_reglement p.3, UMG 10)" in rejected.content
    assert accepted.content == "regulation_findings accepted."
    assert state["artifacts"]["regulation_findings"]["zone"] == "UMG"
