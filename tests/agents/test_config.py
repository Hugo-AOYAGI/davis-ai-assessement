import pytest
from hydra.errors import MissingConfigException
from langchain_anthropic import ChatAnthropic
from omegaconf import OmegaConf

from agent.agents.config import PROJECT_ROOT, load_config, project_path, read_prompt
from agent.contracts.inputs.case import Case
from agent.llm.factory import build_model

NODES = {
    "orchestrator",
    "site_locator",
    "zoning_map_reader",
    "regulation_researcher",
    "oap_analyst",
    "ingest_classifier",
}


def test_defaults_compose():
    cfg = load_config()
    assert set(cfg) >= {"models", "agent", "case", "policies", "corpus", "retrieval", "subagents"}
    assert "hydra" not in cfg
    assert set(cfg.models.nodes) == NODES
    assert cfg.agent.model in cfg.models.nodes
    assert cfg.policies.ask_user.mode == "interactive"


def test_case_validates_against_contract():
    cfg = load_config()
    case = Case.model_validate(OmegaConf.to_container(cfg.case, resolve=True))
    assert case.corpus_id == cfg.corpus.id
    assert "Résidence Jeunes Actifs" in case.program


def test_subagents_empty_by_default():
    assert OmegaConf.to_container(load_config().subagents) == {}


def test_unknown_subagent_is_rejected():
    with pytest.raises(MissingConfigException, match="subagents/nope"):
        load_config(["subagents=[nope]"])


def test_overrides_apply():
    cfg = load_config(["policies.citations.policy=flag", "case.facts=[a,b]"])
    assert cfg.policies.citations.policy == "flag"
    assert list(cfg.case.facts) == ["a", "b"]


def test_node_override_is_isolated():
    cfg = load_config(["models.nodes.site_locator.model=claude-haiku-5-5"])
    nodes = cfg.models.nodes
    assert nodes.site_locator.model == "claude-haiku-5-5"
    assert nodes.orchestrator.model == "claude-sonnet-5-5"
    assert nodes.oap_analyst.model == "claude-sonnet-5-5"


def test_every_node_instantiates_offline(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")
    models = load_config().models
    for node in models.nodes:
        model = build_model(models, node)
        assert isinstance(model, ChatAnthropic)
        assert model.model == models.nodes[node].model


def test_project_paths(tmp_path):
    assert (PROJECT_ROOT / "conf" / "config.yaml").is_file()
    assert project_path("conf/config.yaml") == PROJECT_ROOT / "conf" / "config.yaml"
    assert "defaults:" in read_prompt("conf/config.yaml")
