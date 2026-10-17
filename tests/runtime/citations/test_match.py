from pathlib import Path

import pytest

from agent.contracts.evidence import Citation, SourceKind
from agent.contracts.inputs.corpus import Corpus, Document, DocumentKind, Page
from agent.runtime.citations.match import check_citation, raster_documents, unverifiable

MIN_SCORE = 0.9
NEIGHBOURS = 1
APOSTROPHE = "\N{RIGHT SINGLE QUOTATION MARK}"
NBSP = "\N{NO-BREAK SPACE}"

HEIGHT_RULE = (
    "la hauteur maximale des constructions est limitée à 20 mètres, "
    "avec un nombre de niveaux limité à R+5"
)


def check(pages, quote, page, doc="plu_reglement"):
    citation = Citation(doc=doc, page=page, quote=quote, source_kind=SourceKind.REGULATORY)
    return check_citation(citation, pages, min_score=MIN_SCORE, neighbour_pages=NEIGHBOURS)


def test_exact_quote_is_verified_on_the_cited_page(pages):
    result = check(pages, HEIGHT_RULE, 326)
    assert result.verified
    assert result.score == 1.0
    assert result.matched_page is None


def test_quote_over_a_line_end_hyphenation_is_verified(pages):
    result = check(pages, "l'impact des ondes électromagnétiques sur la santé humaine", 403)
    assert result.verified
    assert result.score == 1.0


def test_compound_word_broken_at_a_line_end_is_verified(pages):
    quote = "par une légende EBC (comme indiqué ci-après) sont des espaces boisés classés"
    assert check(pages, quote, 373).score == 1.0


@pytest.mark.parametrize(
    "quote",
    [
        "Pour les constructions à destination principale d'habitation : la hauteur maximale des "
        f"constructions est limitée à 20{NBSP}mètres",
        f"Pour les constructions à destination principale d{APOSTROPHE}habitation: la hauteur "
        "maximale des   constructions\nest limitée à 20 mètres",
        "POUR LES CONSTRUCTIONS À DESTINATION PRINCIPALE D'HABITATION : LA HAUTEUR MAXIMALE",
        "intitulé « Champs électromagnétiques et santé publique, stations de base et "
        "technologies sans fil »",
    ],
)
def test_typographic_variants_are_verified(pages, quote):
    page = 403 if "Champs" in quote else 326
    result = check(pages, quote, page)
    assert result.verified
    assert result.score == 1.0


def test_quote_on_the_next_page_is_verified_with_the_matched_page(pages):
    quote = (
        "L'emploi à nu de matériaux, destinés à être recouverts (briques creuses, parpaing, "
        "etc.), est interdit."
    )
    result = check(pages, quote, 326)
    assert result.verified
    assert result.matched_page == 327


def test_quote_cited_far_from_its_page_is_not_verified(pages):
    result = check(pages, HEIGHT_RULE, 320)
    assert not result.verified
    assert result.score < 0.6


@pytest.mark.parametrize(
    ("quote", "page"),
    [
        (
            "La hauteur maximale des constructions est limitée à 25 mètres pour les "
            "constructions à destination d'habitation.",
            326,
        ),
        (
            "Les constructions doivent être implantées à une distance au moins égale à 6 mètres "
            "de l'alignement des voies.",
            326,
        ),
        (
            "L'emprise au sol des constructions ne peut excéder 60 % de la superficie du terrain.",
            326,
        ),
        ("Les toitures terrasses végétalisées sont obligatoires pour toute construction.", 327),
    ],
)
def test_fabricated_quote_is_not_verified(pages, quote, page):
    result = check(pages, quote, page)
    assert not result.verified
    assert result.score < 0.8


def test_unknown_document_scores_zero(pages):
    result = check(pages, HEIGHT_RULE, 326, doc="unknown")
    assert result.score == 0
    assert not result.verified
    assert result.matched_page is None


def test_missing_page_scores_zero(pages):
    assert check(pages, HEIGHT_RULE, 100).score == 0


def test_quote_empty_after_normalisation_scores_zero(pages):
    assert check(pages, " \n ", 326).score == 0


def test_quote_longer_than_the_page_is_compared_whole():
    pages = {("doc", 1): "20 mètres"}
    result = check(pages, f"{HEIGHT_RULE} et la hauteur est de 20 mètres", 1, doc="doc")
    assert not result.verified


def test_tie_prefers_the_cited_page():
    pages = {("doc", 1): "même texte", ("doc", 2): "même texte"}
    result = check(pages, "même texte", 2, doc="doc")
    assert result.matched_page is None


@pytest.mark.parametrize(
    "quote",
    [HEIGHT_RULE.replace("20 mètres", "25 mètres"), HEIGHT_RULE.replace("R+5", "R+6")],
)
def test_changed_number_is_not_verified_despite_a_high_score(pages, quote):
    result = check(pages, quote, 326)
    assert not result.verified
    assert result.score >= MIN_SCORE


@pytest.mark.parametrize(
    "quote",
    [
        "les arbres de haute tige sont des arbres dont le tronc mesure à la plantation au moins "
        "1,80 mètre de haut et 15/20 centimètres de circonférence à 1 mètre du sol",
        "ils pourront être plantés à au moins 0.50 mètres des limites de terrain",
    ],
)
def test_correct_numbers_are_verified(pages, quote):
    result = check(pages, quote, 375)
    assert result.verified
    assert result.score == 1.0


def test_truncated_number_is_not_verified():
    pages = {("doc", 1): "le plafond est fixé à 1250 m pour tous"}
    assert check(pages, "le plafond est fixé à 125", 1, doc="doc").score == 1.0
    assert not check(pages, "le plafond est fixé à 125", 1, doc="doc").verified
    assert check(pages, "le plafond est fixé à 1250", 1, doc="doc").verified


def test_number_matching_page_wins_over_a_higher_score_elsewhere():
    pages = {("doc", 1): "hauteur de 25 mètres", ("doc", 2): "hauteur de 20 mètres"}
    result = check(pages, "hauteur de 20 mètres", 1, doc="doc")
    assert result.verified
    assert result.matched_page == 2


def test_geometric_citation_is_rejected(pages):
    citation = Citation(doc="cadastre", quote="91272000AB0123", source_kind=SourceKind.GEOMETRIC)
    with pytest.raises(ValueError, match="regulatory"):
        check_citation(citation, pages, min_score=MIN_SCORE, neighbour_pages=NEIGHBOURS)


def raster_corpus(*pages):
    documents = tuple(
        Document(
            id=doc,
            kind=DocumentKind.ZONING_MAP,
            title=doc,
            path=Path(f"{doc}.pdf"),
            page_count=2,
        )
        for doc in ("plan", "text", "mixed", "empty")
    )
    return Corpus(id="test", documents=documents, pages=pages, sections=())


def test_raster_documents_are_those_without_any_text():
    corpus = raster_corpus(
        Page(doc="plan", number=1, text=""),
        Page(doc="plan", number=2, text="  \n\t"),
        Page(doc="text", number=1, text="Article 10"),
        Page(doc="mixed", number=1, text=""),
        Page(doc="mixed", number=2, text="Légende"),
    )
    assert raster_documents(corpus) == frozenset({"plan", "empty"})


def test_unverifiable_check_is_not_verified_and_scores_zero():
    citation = Citation(doc="plan", page=1, quote="UMG", source_kind=SourceKind.REGULATORY)
    result = unverifiable(citation)
    assert result.citation == citation
    assert not result.verified
    assert result.score == 0.0
    assert not result.text_verifiable
    assert result.matched_page is None


def test_checked_citations_are_text_verifiable(pages):
    assert check(pages, HEIGHT_RULE, 326).text_verifiable
