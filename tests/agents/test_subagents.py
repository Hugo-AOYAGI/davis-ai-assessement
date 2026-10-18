import pytest

from agent.agents import subagents
from agent.agents.config import load_config
from agent.tools.images.inline import InlineImagesMiddleware
from agent.tools.images.prune import PruneImagesMiddleware


def built_middleware(monkeypatch, name, overrides=()):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")
    captured = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return kwargs

    monkeypatch.setattr(subagents, "create_agent", fake_create_agent)
    subagents.build_subagent(load_config(list(overrides)), name)
    return captured["middleware"], captured["model"]


def test_zoning_analyst_prunes_images_before_inlining(monkeypatch: pytest.MonkeyPatch):
    middleware, model = built_middleware(monkeypatch, "zoning_analyst")
    assert isinstance(middleware[0], PruneImagesMiddleware)
    assert middleware[0]._keep == 4
    assert isinstance(middleware[1], InlineImagesMiddleware)
    assert model.model == "claude-sonnet-5-5"


@pytest.mark.parametrize("name", ["surveyor", "doc_analyst", "architect"])
def test_other_subagents_keep_every_image(monkeypatch: pytest.MonkeyPatch, name):
    middleware, _ = built_middleware(monkeypatch, name)
    assert not any(isinstance(item, PruneImagesMiddleware) for item in middleware)


def test_max_images_null_disables_pruning(monkeypatch: pytest.MonkeyPatch):
    middleware, _ = built_middleware(
        monkeypatch, "zoning_analyst", ["subagents.zoning_analyst.max_images=null"]
    )
    assert not any(isinstance(item, PruneImagesMiddleware) for item in middleware)
