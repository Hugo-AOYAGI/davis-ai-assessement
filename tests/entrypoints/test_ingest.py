import sys
from pathlib import Path

import pytest

from agent.adapters.georef.boundary import CommuneBoundaryClient
from agent.agents.config import PROJECT_ROOT
from agent.entrypoints import ingest as entrypoint
from agent.ingest.georef.plan import GeorefSettings
from agent.ingest.pipeline import CorpusSettings


def _record_georef(monkeypatch: pytest.MonkeyPatch) -> list[tuple[GeorefSettings, Path]]:
    calls: list[tuple[GeorefSettings, Path]] = []

    def georeference(settings, root, plan, boundary, today):
        assert isinstance(boundary, CommuneBoundaryClient)
        calls.append((settings, plan))

    monkeypatch.setattr(entrypoint, "georeference_plan", georeference)
    return calls


def test_main_runs_the_pipeline_with_overrides(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")
    monkeypatch.setattr(sys, "argv", ["ingest", "corpus.dir=data/elsewhere"])
    calls: list[tuple[CorpusSettings, Path, object]] = []
    monkeypatch.setattr(
        entrypoint,
        "ingest_corpus",
        lambda settings, root, classify: calls.append((settings, root, classify)),
    )
    georef_calls = _record_georef(monkeypatch)

    entrypoint.main()

    ((settings, root, classify),) = calls
    assert settings.dir == "data/elsewhere"
    assert root == PROJECT_ROOT
    assert callable(classify)
    ((georef, _),) = georef_calls
    assert georef.output.startswith("data/elsewhere/")


def test_georef_step_alone_skips_the_corpus(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "argv", ["ingest", "georef", "corpus.georef.page=1"])
    monkeypatch.setattr(entrypoint, "ingest_corpus", lambda *args: pytest.fail("corpus ran"))
    calls = _record_georef(monkeypatch)

    entrypoint.main()

    ((settings, plan),) = calls
    assert settings.document == "plu_reglement_graphique"
    assert plan == PROJECT_ROOT / "ressources/plu_reglement_graphique_91272_20210706.pdf"


def test_unknown_step_is_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "argv", ["ingest", "georeference"])

    with pytest.raises(ValueError, match="unknown ingest step"):
        entrypoint.main()
