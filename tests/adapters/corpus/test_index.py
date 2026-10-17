import pytest

from agent.adapters.corpus.index import load_index
from agent.adapters.corpus.store import save_corpus

UMG = "plu_reglement/titre-ii/moulon/umg"


def ids(sections):
    return [section.id for section in sections]


def test_documents(index):
    assert [document.id for document in index.documents()] == [
        "plu_reglement",
        "plu_reglement_graphique",
        "oap",
    ]
    assert index.document("oap").page_count == 4
    with pytest.raises(
        LookupError, match="Known documents: plu_reglement, plu_reglement_graphique"
    ):
        index.document("plu")


def test_page_and_pages(index):
    assert index.page("plu_reglement", 3).text == "règlement page 3"
    assert index.page("plu_reglement_graphique", 1).text == ""
    assert [page.number for page in index.pages("oap", 2, 4)] == [2, 3, 4]


@pytest.mark.parametrize(("start", "end"), [(0, 1), (4, 5), (3, 2)])
def test_pages_out_of_range(index, start, end):
    with pytest.raises(LookupError, match="valid pages are 1-4"):
        index.pages("oap", start, end)


def test_page_unknown_document(index):
    with pytest.raises(LookupError, match="Unknown document"):
        index.page("nope", 1)


def test_sections_in_document_order(index, corpus):
    assert index.sections() == list(corpus.sections)
    assert ids(index.sections("oap")) == ["oap/chapitre-8"]
    assert index.corpus is corpus


def test_section_lookup_and_suggestions(index):
    assert index.section(f"{UMG}/10").article == "10"
    with pytest.raises(LookupError, match=f"Did you mean: {UMG}/10"):
        index.section(f"{UMG}/100")


def test_parent_children_subtree(index):
    assert index.parent(f"{UMG}/10").id == UMG
    assert index.parent("plu_reglement/titre-ii") is None
    assert ids(index.children("plu_reglement/titre-ii")) == [
        "plu_reglement/titre-ii/vallee",
        "plu_reglement/titre-ii/chevry",
        "plu_reglement/titre-ii/moulon",
    ]
    assert index.children(f"{UMG}/10") == []
    assert ids(index.subtree(UMG)) == [UMG, f"{UMG}/1", f"{UMG}/10", f"{UMG}/12"]
    assert ids(index.subtree("plu_reglement/titre-i")) == [
        "plu_reglement/titre-i",
        "plu_reglement/titre-i/5",
        "plu_reglement/titre-i/5-2",
    ]


def test_search_ranks_height_article_first(index):
    hits = index.search("hauteur maximale", k=3)

    assert hits[0].section.id == f"{UMG}/10"
    assert all(hit.score > 0 for hit in hits)
    assert [hit.score for hit in hits] == sorted((hit.score for hit in hits), reverse=True)


def test_search_doc_filter_applies_before_k(index):
    hits = index.search("hauteur", k=1, doc="oap")

    assert ids(hit.section for hit in hits) == ["oap/chapitre-8"]


def test_search_empty_query_and_unknown_doc(index):
    assert index.search("", k=5) == []
    assert index.search("les de", k=5) == []
    with pytest.raises(LookupError, match="Unknown document"):
        index.search("hauteur", k=5, doc="nope")


def test_load_index_is_cached(tmp_path, corpus):
    save_corpus(corpus, tmp_path)

    first = load_index(tmp_path, ("de",))

    assert load_index(tmp_path, ("de",)) is first
    assert load_index(tmp_path, ()) is not first
    assert first.section(UMG).zone == "UMG"
