import asyncio

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from agent.entrypoints.graph import graph, run_overrides


@pytest.fixture(autouse=True)
def dummy_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")


def test_factory_builds_offline():
    built = asyncio.run(graph({"configurable": {}}))
    assert isinstance(built, CompiledStateGraph)
    assert "artifacts" in built.channels


def test_factory_without_configurable():
    assert asyncio.run(graph({})) is asyncio.run(graph({"configurable": {}}))


def test_overrides_select_cached_graph():
    low: RunnableConfig = {
        "configurable": {"overrides": ["models.nodes.orchestrator.max_tokens=8000"]}
    }
    high: RunnableConfig = {
        "configurable": {"overrides": ["models.nodes.orchestrator.max_tokens=12000"]}
    }
    first = asyncio.run(graph(low))
    assert asyncio.run(graph(low)) is first
    assert asyncio.run(graph(high)) is not first


def test_bad_overrides_rejected():
    with pytest.raises(TypeError, match="list of Hydra override strings"):
        run_overrides({"configurable": {"overrides": "agent.model=x"}})
