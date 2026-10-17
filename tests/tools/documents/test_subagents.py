from typing import cast, override

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from omegaconf import OmegaConf

from agent.agents.config import load_config
from agent.agents.subagents import build_subagent
from agent.tools.submit.factory import DONE

ZONING_TOOLS = {"list_documents", "site_view", "view_image", "zoom", "submit_zone"}
DOC_TOOLS = {
    "list_documents",
    "list_sections",
    "read_section",
    "search",
    "read_pages",
    "view_image",
    "zoom",
    "site_view",
    "submit_notes",
}
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
    cfg = load_config([f"retrieval={retrieval}"])
    assert tool_names(build_subagent(cfg, "zoning_analyst")) == ZONING_TOOLS
    assert tool_names(build_subagent(cfg, "doc_analyst")) == DOC_TOOLS


def test_site_view_comes_from_the_geo_group():
    cfg = load_config()
    for name in ("zoning_analyst", "doc_analyst"):
        nodes = OmegaConf.to_container(cfg.subagents[name].tools, resolve=False)
        assert "${geo.site_view}" in cast(list[object], nodes)


class ScriptedModel(GenericFakeChatModel):
    @override
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


def call(name, args, call_id):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def notes(quote):
    note = {"topic": "height", "text": "20 m.", "citations": [{**HEIGHT, "quote": quote}]}
    return {"label": "rules", "topics": ["height"], "notes": [note]}


def run(cfg, name, replies, monkeypatch):
    model = ScriptedModel(messages=iter([*replies, AIMessage("done")]))
    monkeypatch.setattr("agent.agents.subagents.build_model", lambda models, node, ledger: model)
    state = build_subagent(cfg, name).invoke({"messages": [HumanMessage("task")]})
    return state, [m for m in state["messages"] if isinstance(m, ToolMessage)]


def test_doc_analyst_reads_and_submits_through_graph(corpus_dir, monkeypatch):
    cfg = load_config([f"retrieval.corpus.directory.relative='{corpus_dir.as_posix()}'"])
    replies = [
        call("read_section", {"section_id": "plu_reglement/titre-ii/moulon/umg/10"}, "r1"),
        call("submit_notes", notes("une citation inventée de toutes pièces"), "s1"),
        call("submit_notes", notes(HEIGHT["quote"]), "s2"),
    ]
    state, (read, rejected, accepted) = run(cfg, "doc_analyst", replies, monkeypatch)
    assert "--- plu_reglement p.3 ---" in read.content
    assert "notes.0.citations.0 (plu_reglement p.3, UMG 10)" in rejected.content
    assert accepted.content == f"notes.rules accepted.\n\n{DONE}"
    assert state["artifacts"]["notes.rules"]["notes"][0]["topic"] == "height"


def test_zoning_analyst_submits_a_region_on_the_plan(monkeypatch):
    zone = {
        "zone": "UMG",
        "overlays": [{"item": "Périmètre d'OAP", "applies": True, "note": "Hatched."}],
        "rationale": "Matched the road layout.",
        "region": {"doc": "plu_reglement_graphique", "page": 1, "region": [100, 100, 9000, 200]},
    }
    inside = {**zone, "region": {**zone["region"], "region": [100, 100, 300, 200]}}
    replies = [call("submit_zone", zone, "s1"), call("submit_zone", inside, "s2")]
    state, (rejected, accepted) = run(load_config(), "zoning_analyst", replies, monkeypatch)
    assert "region: the overview of plu_reglement_graphique p.1 is" in rejected.content
    assert accepted.content == f"zone accepted.\n\n{DONE}"
    assert state["artifacts"]["zone"]["region"]["region"] == [100, 100, 300, 200]
