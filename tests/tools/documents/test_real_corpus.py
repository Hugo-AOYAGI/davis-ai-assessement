"""Document tools on the real ingested corpus; skipped until the ingest entrypoint has run."""

import pytest
from hydra.utils import instantiate
from omegaconf import OmegaConf

from agent.adapters.corpus.store import CORPUS_FILE
from agent.agents.config import load_config
from agent.agents.subagents import build_tools

CFG = load_config(["subagents=[doc_analyst]", "retrieval=full_sections"])
SOURCE = instantiate(CFG.retrieval.corpus, _convert_="all")
UMG = "plu_reglement/titre-ii/moulon/umg"
SITE_VIEW = {  # stand-in for the surveyor package's site_view tool node
    "_target_": "agent.tools.submit.factory.submit_tool",
    "name": "site_view",
    "artifact": "unused",
    "contract": {"_target_": "hydra.utils.get_class", "path": "agent.contracts.evidence.Citation"},
}

pytestmark = pytest.mark.skipif(
    not (SOURCE.directory / CORPUS_FILE).is_file(),
    reason="corpus not ingested (uv run python -m agent.entrypoints.ingest)",
)


@pytest.fixture(scope="module")
def tools():
    OmegaConf.update(CFG, "geo.site_view", SITE_VIEW, force_add=True)
    built = build_tools(CFG.subagents.doc_analyst.tools)
    return {tool.name: tool for tool in built}


def test_documents_with_their_legal_force(tools):
    text = tools["list_documents"].invoke({})
    assert "- plu_reglement | regulatory_text |" in text
    assert "| 465 pages | legal force: conformity" in text
    assert "legal force: conformity | image only" in text
    assert "| 36 pages | legal force: compatibility" in text


def test_umg_article_10_is_on_page_326(tools):
    text = tools["read_section"].invoke({"section_id": f"{UMG}/10"})
    assert "--- plu_reglement p.326 ---" in text
    assert "20 mètres" in text


def test_umg_article_12_starts_on_page_327(tools):
    text = tools["read_section"].invoke({"section_id": f"{UMG}/12"})
    assert text.split("\n")[1] == "--- plu_reglement p.327 ---"
    assert "--- plu_reglement p.328 ---\nEn outre, une aire de livraison" in text


def test_whole_umg_chapter_fits_one_reply(tools):
    text = tools["read_section"].invoke({"section_id": UMG})
    assert "[truncated" not in text
    assert "--- plu_reglement p.332 ---" in text
