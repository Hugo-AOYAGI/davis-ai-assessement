"""Page markers on the real ingested corpus; skipped until the ingest entrypoint has run."""

import pytest
from hydra.utils import instantiate

from agent.adapters.corpus.store import CORPUS_FILE
from agent.agents.config import load_config
from agent.agents.subagents import build_tools

CFG = load_config(["subagents=[regulation_researcher]"])
SOURCE = instantiate(CFG.retrieval.corpus, _convert_="all")

pytestmark = pytest.mark.skipif(
    not (SOURCE.directory / CORPUS_FILE).is_file(),
    reason="corpus not ingested (uv run python -m agent.entrypoints.ingest)",
)


@pytest.fixture(scope="module")
def tools():
    return {tool.name: tool for tool in build_tools(CFG.subagents.regulation_researcher.tools)}


def test_umg_article_10_is_on_page_326(tools):
    text = tools["read_article"].invoke({"zone": "UMG", "article": "10"})
    assert text.count("--- plu_reglement p.") == 1
    assert "--- plu_reglement p.326 ---" in text
    assert "20 mètres" in text


def test_umg_article_12_starts_on_page_327(tools):
    text = tools["read_article"].invoke({"zone": "UMG", "article": "12", "sector": "Moulon"})
    assert text.split("\n")[1] == "--- plu_reglement p.327 ---"
    assert "--- plu_reglement p.328 ---\nEn outre, une aire de livraison" in text
