import pytest
from langchain_anthropic import ChatAnthropic
from omegaconf import OmegaConf

from agent.agents.config import load_config
from agent.llm.costs import CostLogger
from agent.llm.factory import build_model, load_pricing


@pytest.fixture(autouse=True)
def dummy_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")


def test_builds_configured_model_with_cost_logger():
    models = load_config().models
    model = build_model(models, "orchestrator")
    assert isinstance(model, ChatAnthropic)
    assert model.model == models.nodes.orchestrator.model
    assert model.max_tokens == models.nodes.orchestrator.max_tokens
    assert isinstance(model.callbacks, list)
    [cost_logger] = model.callbacks
    assert isinstance(cost_logger, CostLogger)
    assert cost_logger.node == "orchestrator"


def test_unknown_node_raises():
    with pytest.raises(KeyError, match="unknown model node 'nope'"):
        build_model(load_config().models, "nope")


def test_non_chat_target_raises():
    models = OmegaConf.create(
        {"pricing": {}, "nodes": {"bad": {"_target_": "builtins.dict", "a": 1}}}
    )
    with pytest.raises(TypeError, match="expected a BaseChatModel"):
        build_model(models, "bad")


def test_pricing_covers_every_configured_model():
    models = load_config().models
    pricing = load_pricing(models)
    assert {node.model for node in models.nodes.values()} <= set(pricing)
