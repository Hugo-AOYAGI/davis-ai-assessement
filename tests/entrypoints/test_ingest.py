import sys
from pathlib import Path

import pytest

from agent.agents.config import PROJECT_ROOT
from agent.entrypoints import ingest as entrypoint
from agent.ingest.pipeline import CorpusSettings


def test_main_runs_the_pipeline_with_overrides(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")
    monkeypatch.setattr(sys, "argv", ["ingest", "corpus.dir=data/elsewhere", "subagents=[]"])
    calls: list[tuple[CorpusSettings, Path, object]] = []
    monkeypatch.setattr(
        entrypoint,
        "ingest_corpus",
        lambda settings, root, classify: calls.append((settings, root, classify)),
    )

    entrypoint.main()

    ((settings, root, classify),) = calls
    assert settings.dir == "data/elsewhere"
    assert root == PROJECT_ROOT
    assert callable(classify)
