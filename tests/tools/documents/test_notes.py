import logging

import pymupdf
import pytest

from agent.adapters.images.pages import PageImages
from agent.contracts.evidence import Citation, ImageRegion, SourceKind
from agent.contracts.findings.notes import DocNotes, Note, OpenPoint
from agent.tools.documents.notes import notes_finalizer
from agent.tools.submit.factory import SubmissionRejected

HEIGHT = "la hauteur maximale des constructions est fixée à"
PARKING = "1 place par tranche de 150 m² pour les résidences étudiantes."


def cite(page, quote, doc="plu_reglement", kind=SourceKind.REGULATORY):
    return Citation(doc=doc, page=page, quote=quote, source_kind=kind)


def view(box, page=1):
    return ImageRegion(doc="oap", page=page, region=box)


def notes(*citations, views=(), open_points=()):
    return DocNotes(
        label="rules",
        notes=(Note(topic="height", text="Height is capped.", citations=citations, views=views),),
        open_points=open_points,
    )


@pytest.fixture(scope="module")
def images(tmp_path_factory):
    root = tmp_path_factory.mktemp("pdfs")
    with pymupdf.open() as document:
        for _ in range(2):
            document.new_page(width=200, height=100).insert_text((20, 50), "Schéma")
        document.save(root / "oap.pdf")
    return PageImages(
        documents=[{"id": "oap", "path": "oap.pdf"}],
        root=root,
        render_dpi=72,
        max_image_px=440,
        max_upscale=4.0,
        ruler_step_px=100,
        crop_max_px=500,
        cache_size=2,
        scan_min_coverage=0.8,
    )


def finalizer(source, images, policy="reject", check_raster=False):
    return notes_finalizer(
        corpus=source,
        images=images,
        policy=policy,
        min_score=0.9,
        neighbour_pages=1,
        max_quote_chars=80,
        check_raster=check_raster,
    )


def test_verified_quotes_and_valid_views_are_accepted_unchanged(source, images, caplog):
    submission = notes(cite(3, HEIGHT), cite(4, PARKING), views=(view((0, 0, 100, 50)),))
    with caplog.at_level(logging.INFO, logger="agent"):
        assert finalizer(source, images)(submission, {}) is submission
    assert "DocNotes: 2/2 citations verified" in caplog.text


def test_wrong_quote_is_rejected_with_its_paths(source, images):
    wrong = cite(3, "la hauteur maximale est libre dans toute la zone")
    point = OpenPoint(question="Is height free?", why="Unclear.", citations=(wrong,))
    with pytest.raises(SubmissionRejected) as rejected:
        finalizer(source, images)(notes(wrong, open_points=(point,)), {})
    (error,) = rejected.value.errors
    assert error.startswith("notes.0.citations.0, open_points.0.citations.0 (plu_reglement p.3)")
    assert "quote not found verbatim" in error


def test_every_error_comes_back_at_once(source, images):
    submission = notes(
        cite(1, PARKING),
        views=(view((0, 0, 100, 50)), view((0, 0, 5000, 50)), view((0, 0, 9, 9), 3)),
    )
    with pytest.raises(SubmissionRejected) as rejected:
        finalizer(source, images)(submission, {})
    quote, wide, page = rejected.value.errors
    assert quote.startswith("notes.0.citations.0 (plu_reglement p.1): quote not found verbatim")
    assert wide.startswith("notes.0.views.1: the overview of oap p.1 is")
    assert "exceeds it" in wide
    assert page == "notes.0.views.2: oap has 2 pages (1 to 2); page 3 does not exist"


def test_bad_view_alone_is_rejected_even_under_flag(source, images):
    with pytest.raises(SubmissionRejected, match="unknown document 'plan'"):
        bad = ImageRegion(doc="plan", page=1, region=(0, 0, 10, 10))
        finalizer(source, images, policy="flag")(notes(cite(3, HEIGHT), views=(bad,)), {})


def test_number_mismatch_is_rejected(source, images):
    with pytest.raises(SubmissionRejected, match="numbers differ"):
        finalizer(source, images)(notes(cite(4, PARKING.replace("150", "180"))), {})


def test_flag_policy_accepts_and_logs(source, images, caplog):
    submission = notes(cite(3, HEIGHT), cite(3, "une phrase qui n'existe nulle part ici"))
    with caplog.at_level(logging.INFO, logger="agent"):
        assert finalizer(source, images, policy="flag")(submission, {}) is submission
    assert "DocNotes: 1/2 citations verified" in caplog.text
    assert "accepted with 1 unverified citation(s)" in caplog.text


def test_corpus_document_cited_as_geometric_is_always_rejected(source, images):
    mislabelled = cite(None, "Joliot Curie", kind=SourceKind.GEOMETRIC, doc="oap")
    with pytest.raises(SubmissionRejected, match="cites corpus document 'oap' as geometric"):
        finalizer(source, images, policy="flag")(notes(mislabelled), {})


def test_unknown_policy_fails_at_build(source, images):
    with pytest.raises(ValueError, match="unknown citation policy 'ignore'"):
        finalizer(source, images, policy="ignore")


def test_raster_plan_citation_is_accepted_without_text_check(source, images, caplog):
    plan = cite(1, "UMG", doc="plu_reglement_graphique")
    submission = notes(cite(3, HEIGHT), plan)
    with caplog.at_level(logging.INFO, logger="agent"):
        assert finalizer(source, images)(submission, {}) is submission
    assert "DocNotes: 1/1 citations verified, 1 not text-verifiable (raster)" in caplog.text


def test_raster_plan_citation_is_rejected_when_text_checked(source, images):
    plan = cite(1, "UMG", doc="plu_reglement_graphique")
    with pytest.raises(SubmissionRejected) as rejected:
        finalizer(source, images, check_raster=True)(notes(plan), {})
    (error,) = rejected.value.errors
    assert error.startswith(
        "notes.0.citations.0 (plu_reglement_graphique p.1): quote not found verbatim"
    )
