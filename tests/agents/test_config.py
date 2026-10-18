import pytest
from hydra.errors import MissingConfigException
from langchain_anthropic import ChatAnthropic
from omegaconf import OmegaConf

from agent.agents.config import PROJECT_ROOT, load_config, project_path, read_prompt
from agent.contracts.inputs.case import Case
from agent.llm.factory import build_model

SUBAGENTS = ["surveyor", "zoning_analyst", "doc_analyst", "architect"]
NODES = {"orchestrator", *SUBAGENTS, "ingest_classifier", "judge"}


def test_groups_compose():
    cfg = load_config()
    assert set(cfg) >= {"models", "agent", "case", "policies", "corpus", "retrieval", "subagents"}
    assert {"geo", "images"} <= set(cfg)
    assert "hydra" not in cfg
    assert set(cfg.models.nodes) == NODES
    assert cfg.agent.model in cfg.models.nodes
    assert cfg.policies.ask_user.mode == "interactive"
    assert cfg.retrieval.mode == "full_sections"
    assert list(cfg.policies.study.required_notes) == ["rules", "oap", "destinations"]
    assert cfg.policies.evidence.crops_dir == "data/crops"


def test_four_subagents_by_default():
    cfg = load_config()
    assert list(cfg.subagents) == SUBAGENTS
    assert {spec.model for spec in cfg.subagents.values()} <= set(cfg.models.nodes)


def test_case_validates_against_contract():
    cfg = load_config()
    case = Case.model_validate(OmegaConf.to_container(cfg.case, resolve=True))
    assert case.corpus_id == cfg.corpus.id
    assert "Résidence Jeunes Actifs" in case.program


def test_subagents_can_be_emptied():
    assert OmegaConf.to_container(load_config(["subagents=[]"]).subagents) == {}


def test_unknown_subagent_is_rejected():
    with pytest.raises(MissingConfigException, match="subagents/nope"):
        load_config(["subagents=[nope]"])


def test_overrides_apply():
    cfg = load_config(["policies.citations.policy=flag", "case.facts=[a,b]"])
    assert cfg.policies.citations.policy == "flag"
    assert list(cfg.case.facts) == ["a", "b"]


SONNET_NODES = {"zoning_analyst", "judge"}


def test_default_models():
    nodes = load_config().models.nodes
    for node in NODES - SONNET_NODES:
        assert nodes[node].model == "claude-haiku-5-5"
        assert "effort" not in nodes[node]
    assert nodes.judge.model == "claude-sonnet-5-5"


def test_zoning_analyst_runs_on_sonnet(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")
    models = load_config().models
    node = models.nodes.zoning_analyst
    assert node.model == "claude-sonnet-5-5"
    assert node.effort == "medium"
    assert node.max_tokens == models.nodes.surveyor.max_tokens
    assert list(node.tags) == ["nostream"]
    model = build_model(models, "zoning_analyst")
    assert isinstance(model, ChatAnthropic)
    assert model.reasoning_effort == "medium"


def test_only_zoning_analyst_prunes_images():
    subagents = load_config().subagents
    assert subagents.zoning_analyst.max_images == 4
    for name in set(SUBAGENTS) - {"zoning_analyst"}:
        assert subagents[name].get("max_images") is None


def test_zoning_analyst_has_plan_site():
    cfg = load_config()
    nodes = OmegaConf.to_container(cfg.subagents.zoning_analyst.tools, resolve=False)
    assert isinstance(nodes, list)
    assert "${geo.plan_site}" in nodes
    plan_site = cfg.geo.plan_site
    assert plan_site._target_ == "agent.tools.plan.site.plan_site_tool"
    assert plan_site.georeference.relative == cfg.corpus.georef.output
    assert plan_site.close_margin_m < plan_site.context_margin_m


def test_node_override_is_isolated():
    cfg = load_config(
        [
            "models.nodes.doc_analyst.model=claude-sonnet-5-5",
            "+models.nodes.doc_analyst.effort=medium",
        ]
    )
    nodes = cfg.models.nodes
    assert nodes.doc_analyst.model == "claude-sonnet-5-5"
    assert nodes.doc_analyst.effort == "medium"
    assert nodes.orchestrator.model == "claude-haiku-5-5"
    assert "effort" not in nodes.orchestrator


def test_every_node_instantiates_offline(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")
    models = load_config().models
    for node in models.nodes:
        model = build_model(models, node)
        assert isinstance(model, ChatAnthropic)
        assert model.model == models.nodes[node].model


def test_project_paths():
    assert (PROJECT_ROOT / "conf" / "config.yaml").is_file()
    assert project_path("conf/config.yaml") == PROJECT_ROOT / "conf" / "config.yaml"
    assert "defaults:" in read_prompt("conf/config.yaml")
