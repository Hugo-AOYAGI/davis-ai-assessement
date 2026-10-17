from pathlib import Path

import pytest

from agent.adapters.corpus.index import CorpusIndex, load_index
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
    assert index.page("plu_reglement_graphique", 1).image == Path(
        "images/plu_reglement_graphique/p0001.jpg"
    )
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


def test_zone_lookup_is_case_insensitive(index):
    assert index.zone("umg").id == UMG


def test_zone_ambiguous_lists_sectors(index):
    with pytest.raises(LookupError, match=r"several sectors.*Vallée, Chevry.*sector"):
        index.zone("UA")


def test_zone_sector_disambiguates(index):
    assert index.zone("UA", sector="vallee").id == "plu_reglement/titre-ii/vallee/ua"
    assert index.zone("ua", sector="CHEVRY").id == "plu_reglement/titre-ii/chevry/ua"


def test_zone_wrong_sector(index):
    with pytest.raises(LookupError, match=r"not in sector 'Moulon'.*Vallée, Chevry"):
        index.zone("UA", sector="Moulon")


def test_zone_unknown_lists_zones(index):
    with pytest.raises(LookupError, match="Known zones: UA, UMG"):
        index.zone("UX")


def test_article_lookup(index):
    assert index.article("UMG", "10").id == f"{UMG}/10"
    assert index.article("umg", 12).id == f"{UMG}/12"
    assert index.article("UA", "2", sector="Chevry").id == "plu_reglement/titre-ii/chevry/ua/2"
    assert index.article("UA", "1", sector="Vallée").id == "plu_reglement/titre-ii/vallee/ua/1"


def test_article_ambiguous_zone(index):
    with pytest.raises(LookupError, match="pass one as `sector`"):
        index.article("UA", "1")


def test_article_not_found_lists_available(index):
    with pytest.raises(LookupError, match=r"zone UMG \(Moulon\)\. Available articles: 1, 10, 12"):
        index.article("UMG", "15")


def test_definition_ordering(index):
    assert ids(index.definition("accès")) == [
        "plu_reglement/titre-iii/lexique/acces",
        "plu_reglement/titre-iii/lexique/acces-privatif",
        "plu_reglement/titre-iii/lexique/voie-d-acces",
    ]


def test_definition_folding_and_partial_matches(index):
    lexique = "plu_reglement/titre-iii/lexique"
    assert ids(index.definition("HAUTEUR")) == [f"{lexique}/hauteur-de-construction-art-10"]
    assert ids(index.definition("Acces :")) == ids(index.definition("accès"))
    assert ids(index.definition("faitage ou faite")) == [f"{lexique}/faitage-ou-faite"]
    assert ids(index.definition("le faîtage ou faîte d'un toit")) == [f"{lexique}/faitage-ou-faite"]
    assert index.definition("piscine") == []
    assert index.definition("  ") == []


def test_definition_without_lexicon(corpus):
    assert CorpusIndex(corpus).definition("accès") == []


def test_unknown_lexicon_section(corpus):
    with pytest.raises(ValueError, match="plu_reglement/lexique"):
        CorpusIndex(corpus, lexicon=("plu_reglement/lexique",))


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
    lexicon = ("plu_reglement/titre-iii/lexique",)

    first = load_index(tmp_path, lexicon, ("de",))

    assert load_index(tmp_path, lexicon, ("de",)) is first
    assert load_index(tmp_path, lexicon, ()) is not first
    assert first.zone("UMG").id == UMG
