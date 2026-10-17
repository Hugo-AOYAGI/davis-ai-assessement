import logging

import pytest

from agent.contracts.evidence import Citation, Rule, SourceKind
from agent.contracts.findings.oap import OAPFindings
from agent.tools.regulation.citations import citation_finalizer
from agent.tools.submit.factory import SubmissionRejected

HEIGHT = "la hauteur maximale des constructions est fixée à"
PARKING = "1 place par tranche de 150 m² pour les résidences étudiantes."


def cite(page, quote, doc="plu_reglement", kind=SourceKind.REGULATORY):
    return Citation(doc=doc, page=page, quote=quote, source_kind=kind)


def findings(*citations, prescriptions=()):
    return OAPFindings(
        applicable=True,
        name="Joliot Curie",
        prescriptions=prescriptions,
        rationale="The site is in the perimeter.",
        citations=citations,
    )


def finalizer(source, policy="reject", check_raster=False):
    return citation_finalizer(
        corpus=source,
        policy=policy,
        min_score=0.9,
        neighbour_pages=1,
        max_quote_chars=80,
        check_raster=check_raster,
    )


def test_verified_quotes_are_accepted_unchanged(source, caplog):
    submission = findings(cite(3, HEIGHT), cite(4, PARKING))
    with caplog.at_level(logging.INFO, logger="agent"):
        assert finalizer(source)(submission, {}) is submission
    assert "OAPFindings: 2/2 citations verified" in caplog.text


def test_wrong_quote_is_rejected_with_its_paths(source):
    wrong = cite(3, "la hauteur maximale est libre dans toute la zone")
    rule = Rule(topic="height", text="Height is free.", citations=(wrong,))
    with pytest.raises(SubmissionRejected) as rejected:
        finalizer(source)(findings(wrong, prescriptions=(rule,)), {})
    (error,) = rejected.value.errors
    assert error.startswith("prescriptions.0.citations.0, citations.0 (plu_reglement p.3)")
    assert "quote not found verbatim" in error


def test_quote_beyond_the_neighbour_pages_is_rejected(source):
    with pytest.raises(SubmissionRejected) as rejected:
        finalizer(source)(findings(cite(1, PARKING), cite(5, "La hauteur est mesurée")), {})
    (error,) = rejected.value.errors
    assert error.startswith("citations.0 (plu_reglement p.1): quote not found verbatim")


def test_number_mismatch_is_rejected(source):
    with pytest.raises(SubmissionRejected, match="numbers differ"):
        finalizer(source)(findings(cite(4, PARKING.replace("150", "180"))), {})


def test_flag_policy_accepts_and_logs(source, caplog):
    submission = findings(cite(3, HEIGHT), cite(3, "une phrase qui n'existe nulle part ici"))
    with caplog.at_level(logging.INFO, logger="agent"):
        assert finalizer(source, policy="flag")(submission, {}) is submission
    assert "OAPFindings: 1/2 citations verified" in caplog.text
    assert "accepted with 1 unverified citation(s)" in caplog.text


def test_corpus_document_cited_as_geometric_is_always_rejected(source):
    mislabelled = cite(None, "Joliot Curie", kind=SourceKind.GEOMETRIC, doc="oap")
    with pytest.raises(SubmissionRejected, match="cites corpus document 'oap' as geometric"):
        finalizer(source, policy="flag")(findings(mislabelled), {})


def test_other_geometric_sources_are_not_checked(source):
    cadastre = cite(None, "91272000AB0123", kind=SourceKind.GEOMETRIC, doc="cadastre")
    submission = findings(cadastre)
    assert finalizer(source)(submission, {}) is submission


def test_unknown_policy_fails_at_build(source):
    with pytest.raises(ValueError, match="unknown citation policy 'ignore'"):
        finalizer(source, policy="ignore")


def test_raster_plan_citation_is_accepted_without_text_check(source, caplog):
    plan = cite(1, "UMG", doc="plu_reglement_graphique")
    submission = findings(cite(3, HEIGHT), plan)
    with caplog.at_level(logging.INFO, logger="agent"):
        assert finalizer(source)(submission, {}) is submission
    assert "OAPFindings: 1/1 citations verified, 1 not text-verifiable (raster)" in caplog.text


def test_raster_plan_citation_is_rejected_when_text_checked(source):
    plan = cite(1, "UMG", doc="plu_reglement_graphique")
    with pytest.raises(SubmissionRejected) as rejected:
        finalizer(source, check_raster=True)(findings(plan), {})
    (error,) = rejected.value.errors
    assert error.startswith("citations.0 (plu_reglement_graphique p.1): quote not found verbatim")
