"""Acceptance checks on the real ingested corpus; skipped until the ingest entrypoint has run."""

import re
from collections import defaultdict

import pymupdf
import pytest

from agent.adapters.corpus.store import CORPUS_FILE, load_corpus
from agent.agents.config import load_config, project_path
from agent.contracts.inputs.corpus import Corpus, DocumentKind

CORPUS_DIR = project_path(str(load_config().corpus.dir))
UMG = "plu_reglement/titre-ii/moulon/umg"
UMG_PAGES = {
    1: 320, 2: 321, 3: 321, 4: 322, 5: 324, 6: 324, 7: 325, 8: 325,
    9: 326, 10: 326, 11: 326, 12: 327, 13: 330, 14: 331, 15: 331, 16: 332,
}  # fmt: skip
ZONE_ARTICLE = re.compile(r"^plu_reglement/titre-ii/[^/]+/[^/]+/\d+$")

pytestmark = pytest.mark.skipif(
    not (CORPUS_DIR / CORPUS_FILE).is_file(),
    reason="corpus not ingested (uv run python -m agent.entrypoints.ingest)",
)


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return load_corpus(CORPUS_DIR)


def test_every_zone_has_articles_1_to_16(corpus):
    articles = [s for s in corpus.sections if ZONE_ARTICLE.match(s.id)]
    assert len(articles) == 448
    by_zone: defaultdict[str, list[str]] = defaultdict(list)
    for section in articles:
        by_zone[section.id.rsplit("/", 1)[0]].append(section.article or "")
    assert len(by_zone) == 28
    assert all(numbers == [str(n) for n in range(1, 17)] for numbers in by_zone.values())


def test_umg_articles_on_their_pages(corpus):
    pages = {
        int(s.article or 0): s.page_start
        for s in corpus.sections
        if s.id.startswith(f"{UMG}/") and s.id.count("/") == UMG.count("/") + 1
    }
    assert pages == UMG_PAGES


def test_titre_i_and_lexique_present(corpus):
    ids = {s.id for s in corpus.sections}
    assert {"plu_reglement/titre-i", "plu_reglement/titre-i/5-2"} <= ids
    assert "plu_reglement/titre-iii/lexique" in ids
    terms = [s for s in corpus.sections if s.id.startswith("plu_reglement/titre-iii/lexique/")]
    assert len(terms) == 42
    assert all(374 <= s.page_start <= 379 for s in terms)


def test_oap_chapter_8(corpus):
    chapter = next(s for s in corpus.sections if s.id == "oap/chapitre-8")
    assert (chapter.page_start, chapter.page_end) == (33, 36)


def test_zoning_map_image(corpus):
    kinds = {d.id: d.kind for d in corpus.documents}
    assert kinds == {
        "plu_reglement": DocumentKind.REGULATORY_TEXT,
        "plu_reglement_graphique": DocumentKind.ZONING_MAP,
        "oap": DocumentKind.OAP,
    }
    (page,) = [p for p in corpus.pages if p.doc == "plu_reglement_graphique"]
    assert page.image is not None
    assert page.image.suffix in {".jpeg", ".jpg"}
    pixmap = pymupdf.Pixmap(str(page.image))
    assert (pixmap.width, pixmap.height) == (7021, 4966)
