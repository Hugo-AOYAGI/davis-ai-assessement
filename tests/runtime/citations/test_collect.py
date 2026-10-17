from pydantic import BaseModel

from agent.contracts.evidence import Citation, Limit, SourceKind
from agent.runtime.citations.collect import collect_citations


def cite(quote):
    return Citation(doc="plu_reglement", page=326, quote=quote, source_kind=SourceKind.REGULATORY)


class Inner(BaseModel):
    height: Limit
    notes: dict[str, tuple[Citation, ...]]


class Outer(BaseModel):
    title: str
    citations: tuple[Citation, ...]
    inner: Inner
    items: list[Inner]
    single: Citation | None = None


def test_collects_every_citation_with_its_path_in_field_order():
    a, b, c, d, e, f = (cite(q) for q in "abcdef")
    model = Outer(
        title="t",
        citations=(a, b),
        inner=Inner(height=Limit(value=20, rule="r", citations=(c,)), notes={"x": (d,)}),
        items=[Inner(height=Limit(value=None, rule="r"), notes={"y": (e,)})],
        single=f,
    )
    assert collect_citations(model) == (
        ("citations.0", a),
        ("citations.1", b),
        ("inner.height.citations.0", c),
        ("inner.notes.x.0", d),
        ("items.0.notes.y.0", e),
        ("single", f),
    )


def test_model_without_citations_yields_nothing():
    assert collect_citations(Limit(value=None, rule="r")) == ()
