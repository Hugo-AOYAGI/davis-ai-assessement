import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from agent.contracts.inputs.corpus import Corpus, Document, DocumentKind, Page
from agent.contracts.study import VerifiedStudy
from agent.tools.study.checks import corpus_facts
from agent.tools.study.messages import Verification
from evals.harness.items import Item, Status, load_items
from evals.harness.matching.grounding import CitationMatcher

FIXTURES = Path(__file__).parent / "fixtures"
ITEMS = FIXTURES / "items"
RASTER = "plu_reglement_graphique"


@pytest.fixture(scope="session")
def study() -> VerifiedStudy:
    return VerifiedStudy.model_validate_json(
        (FIXTURES / "verified_study.json").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="session")
def study_json(study) -> dict[str, Any]:
    return study.model_dump(mode="json")


@pytest.fixture
def variant(study_json) -> Callable[[Callable[[dict[str, Any]], None]], VerifiedStudy]:
    def build(mutate: Callable[[dict[str, Any]], None]) -> VerifiedStudy:
        data = json.loads(json.dumps(study_json))
        mutate(data)
        return VerifiedStudy.model_validate(data)

    return build


@pytest.fixture(scope="session")
def corpus() -> Corpus:
    raw = json.loads((FIXTURES / "pages.json").read_text(encoding="utf-8"))
    pages = [
        Page(doc=key.split("/")[0], number=int(key.split("/")[1]), text=text)
        for key, text in raw.items()
    ]
    kinds = {
        "plu_reglement": DocumentKind.REGULATORY_TEXT,
        "oap": DocumentKind.OAP,
        RASTER: DocumentKind.ZONING_MAP,
    }
    return Corpus(
        id="test",
        documents=tuple(
            Document(id=doc, kind=kind, title=doc, path=Path(f"{doc}.pdf"), page_count=465)
            for doc, kind in kinds.items()
        ),
        pages=(*pages, Page(doc=RASTER, number=1, text="")),
        sections=(),
    )


@pytest.fixture(scope="session")
def make_matcher(corpus) -> Callable[[int], CitationMatcher]:
    facts = corpus_facts(corpus)

    def build(neighbour_pages: int = 0) -> CitationMatcher:
        return CitationMatcher(facts, Verification(0.9, neighbour_pages, 160), check_raster=False)

    return build


@pytest.fixture(scope="session")
def matcher(make_matcher):
    return make_matcher(0)


@pytest.fixture(scope="session")
def items() -> dict[str, Item]:
    return {item.id: item for item in load_items(ITEMS, statuses=tuple(Status))}
