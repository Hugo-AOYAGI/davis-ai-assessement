import json
from pathlib import Path

import pytest

from agent.contracts.inputs.corpus import Corpus, Document, DocumentKind, Page
from agent.runtime.citations.match import index_pages

FIXTURE = Path(__file__).parent / "fixtures" / "plu_reglement_pages.json"


@pytest.fixture(scope="session")
def corpus() -> Corpus:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return Corpus(
        id="test",
        documents=(
            Document(
                id="plu_reglement",
                kind=DocumentKind.REGULATORY_TEXT,
                title="PLU - Règlement",
                path=Path("ressources/plu_reglement_91272_20210706.pdf"),
                page_count=465,
            ),
        ),
        pages=tuple(
            Page(doc="plu_reglement", number=int(number), text=text) for number, text in raw.items()
        ),
        sections=(),
    )


@pytest.fixture(scope="session")
def pages(corpus: Corpus) -> dict[tuple[str, int], str]:
    return index_pages(corpus)
