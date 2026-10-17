import pytest
from pydantic import ValidationError

from agent.contracts.evidence import Citation, Limit, SourceKind
from agent.contracts.inputs.clarification import Question, QuestionKind


def test_regulatory_citation_requires_page():
    with pytest.raises(ValidationError, match="needs a page"):
        Citation(doc="plu_reglement", quote="x", source_kind=SourceKind.REGULATORY)


def test_geometric_citation_without_page():
    citation = Citation(doc="cadastre", quote="x", source_kind=SourceKind.GEOMETRIC)
    assert citation.page is None


def test_limit_with_value_requires_citation():
    with pytest.raises(ValidationError, match="at least one citation"):
        Limit(value=20, rule="20 m")


def test_limit_without_value_may_be_uncited():
    assert Limit(value=None, rule="not regulated").citations == ()


def test_contracts_are_frozen(citation: Citation):
    with pytest.raises(ValidationError):
        citation.page = 1  # ty: ignore[invalid-assignment]


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        Citation.model_validate(
            {"doc": "d", "page": 1, "quote": "q", "source_kind": "regulatory", "extra": 1}
        )


def test_recommended_must_be_an_option():
    with pytest.raises(ValidationError, match="one of options"):
        Question(
            id="q1",
            text="Is an RJA a résidence sociale?",
            kind=QuestionKind.INTERPRETATION,
            why="selects the destination",
            options=("yes", "no"),
            recommended="maybe",
        )
