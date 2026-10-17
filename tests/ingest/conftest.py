import json
from pathlib import Path

import pytest
from omegaconf import OmegaConf

from agent.agents.config import load_config
from agent.contracts.inputs.corpus import Section
from agent.ingest.rules import Line, SplitterConfig
from agent.ingest.split import split_document

FIXTURES = Path(__file__).parent / "fixtures"


def load_lines(name: str) -> list[Line]:
    rows = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return [Line.model_validate(row) for row in rows]


def splitter_config(kind: str) -> SplitterConfig:
    raw = OmegaConf.to_container(load_config(["subagents=[]"]).corpus.splitter[kind], resolve=True)
    return SplitterConfig.model_validate(raw)


def split_fixture(doc: str, name: str, kind: str) -> dict[str, Section]:
    sections = split_document(doc, load_lines(name), splitter_config(kind))
    return {section.id: section for section in sections}


@pytest.fixture(scope="session")
def umg() -> dict[str, Section]:
    return split_fixture("plu_reglement", "reglement_umg.json", "regulatory_text")


@pytest.fixture(scope="session")
def titre_i() -> dict[str, Section]:
    return split_fixture("plu_reglement", "reglement_titre_i.json", "regulatory_text")


@pytest.fixture(scope="session")
def titre_iii() -> dict[str, Section]:
    return split_fixture("plu_reglement", "reglement_titre_iii.json", "regulatory_text")


@pytest.fixture(scope="session")
def oap() -> dict[str, Section]:
    return split_fixture("oap", "oap.json", "oap")
