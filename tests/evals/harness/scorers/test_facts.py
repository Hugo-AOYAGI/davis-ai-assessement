import pytest

from agent.contracts.evidence import Citation, SourceKind
from agent.contracts.findings.notes import Note
from evals.harness.items import Evidence, KeyFact, StatementFact
from evals.harness.matching.values import normalise, same
from evals.harness.scorers.facts import (
    FactScore,
    item_passes,
    score_fact,
    score_facts,
    score_statement,
)

ACROTERE = f"10 mètres à l{chr(0x2019)}acrotère"
HEIGHT_EVIDENCE = [{"doc": "plu_reglement", "page": 326, "quote": "20 mètres"}]


def fact(**fields) -> KeyFact:
    return KeyFact.model_validate(fields)


def height_fact(**fields) -> KeyFact:
    return fact(
        key='envelope.rules.buildings[building~"Sociale"].max_height_m',
        expect=20,
        evidence=HEIGHT_EVIDENCE,
        **fields,
    )


def set_height(value=None, quote=None, page=None):
    def mutate(data):
        limit = data["envelope"]["rules"]["buildings"][0]["max_height_m"]
        if value is not None:
            limit["value"] = value
        for citation in limit["citations"]:
            citation["quote"] = quote or citation["quote"]
            citation["page"] = page or citation["page"]

    return mutate


def test_e01_facts_on_the_real_study_are_grounded(items, study, matcher):
    facts = [
        f for f in items["e01_reference"].facts if f.key != "envelope.proposal.total_volume_m3"
    ]
    scores = score_facts(facts, study, matcher)
    assert all(score.correct and score.grounded for score in scores), scores
    assert [s.cited for s in scores] == [None, None, None, True, True, None, None]
    assert item_passes(scores, [False, False])


def test_wrong_value_is_neither_correct_nor_grounded(variant, matcher):
    score = score_fact(height_fact(), variant(set_height(value=18)), matcher)
    assert (score.correct, score.grounded, score.cited) == (False, False, True)
    assert "expected [20]" in score.detail


def test_fabricated_quote_is_correct_but_not_grounded(variant, matcher):
    output = variant(set_height(quote="La hauteur maximale est fixée à 20 mètres au faîtage."))
    score = score_fact(height_fact(), output, matcher)
    assert (score.correct, score.grounded, score.cited) == (True, False, False)


def test_right_value_cited_on_a_page_that_is_not_evidence(study, matcher, make_matcher):
    elsewhere = [{"doc": "plu_reglement", "page": 327}]
    off_page = fact(
        key='envelope.rules.buildings[building~"Sociale"].max_height_m',
        expect=20,
        evidence=elsewhere,
    )
    assert not score_fact(off_page, study, matcher).grounded
    assert score_fact(off_page, study, make_matcher(1)).grounded


def test_quote_cited_on_the_wrong_page_is_invalid(variant, matcher):
    score = score_fact(height_fact(), variant(set_height(page=325)), matcher)
    assert (score.correct, score.grounded) == (True, False)


def test_fact_without_evidence_is_grounded_when_correct(study, matcher):
    score = score_fact(fact(key="study.regime.zone", expect="umg "), study, matcher)
    assert (score.correct, score.grounded, score.cited) == (True, True, None)


def test_null_means_not_regulated(study, matcher):
    assert score_fact(
        fact(key="envelope.rules.max_footprint_ratio", expect=None), study, matcher
    ).correct
    assert not score_fact(
        fact(key="envelope.rules.min_green_ratio", expect=None), study, matcher
    ).correct


def test_percent_strings_and_tolerance(study, matcher):
    assert score_fact(
        fact(key="envelope.rules.min_green_ratio", expect="20 %"), study, matcher
    ).correct
    area = fact(key="site.area_m2", expect=6000, tolerance=0.01)
    assert score_fact(area, study, matcher).correct
    assert not score_fact(fact(key="site.area_m2", expect=6000), study, matcher).correct


def test_any_of_rejects_hedging_between_elements(variant, study, matcher):
    open_verdict = fact(key="study.admissibility.verdict", any_of=["permitted", "conditional"])
    assert score_fact(open_verdict, study, matcher).correct
    hedged = variant(lambda d: d["study"]["admissibility"][1].update(verdict="conditional"))
    assert not score_fact(open_verdict, hedged, matcher).correct
    assert not score_fact(
        fact(key="study.admissibility[verdict=prohibited].verdict", expect="prohibited"),
        study,
        matcher,
    ).correct


def test_expect_none_of_and_lists_as_sets(variant, study, matcher):
    not_strip = fact(key="site.choice.parcel_ids", expect_none_of=["91272000CR0249"])
    assert score_fact(not_strip, study, matcher).correct
    both = variant(
        lambda d: d["site"]["choice"].update(parcel_ids=["91272000CR0249", "91272000CR0247"])
    )
    assert not score_fact(not_strip, both, matcher).correct
    as_set = fact(key="site.choice.parcel_ids", expect=["91272000CR0247", "91272000CR0249"])
    assert score_fact(as_set, both, matcher).correct
    assert not score_fact(as_set, study, matcher).correct


def test_at_least_counts_elements_and_list_items(study, matcher):
    assert score_fact(
        fact(key='site.edges[neighbours~"CR0249"]', at_least=10), study, matcher
    ).correct
    assert not score_fact(
        fact(key="site.edges[other_side=public_land]", at_least=1), study, matcher
    ).correct
    assert score_fact(fact(key="site.choice.parcel_ids", at_least=1), study, matcher).correct


def test_present_and_absent_legend_items(study, matcher):
    oap = "secteur a orientation d'amenagement et de programmation"
    ok = fact(key="zone.overlays", present=[oap], absent=["Espaces Boisés Classés"])
    assert score_fact(ok, study, matcher).correct
    wrong = score_fact(
        fact(key="zone.overlays", present=["Espaces Boisés Classés"]), study, matcher
    )
    assert not wrong.correct
    assert "missing" in wrong.detail
    assert not score_fact(
        fact(key="study.regime.overlays", absent=["Limites de zones"]), study, matcher
    ).correct


@pytest.mark.parametrize(
    ("actual", "expected", "tolerance", "result"),
    [
        ("20 %", 0.2, None, True),
        ("1,5 m", 1.5, None, True),
        (" UMG ", "umg", None, True),
        (True, 1, None, False),
        (102, 100, 0.02, True),
        (103, 100, 0.02, False),
        (None, 0, None, False),
        (["a", "b"], ("B", "A"), None, True),
    ],
)
def test_normalisation(actual, expected, tolerance, result):
    assert same(normalise(actual), normalise(expected), tolerance) is result


def note(citation: Citation) -> Note:
    return Note(topic="height", text="10 m", citations=(citation,))


def test_statement_coverage_and_grounding(matcher):
    statement = StatementFact(
        statement="Maximum height in UGa is 10 m",
        critical=True,
        evidence=(
            Evidence(
                doc="plu_reglement",
                page=91,
                quote=ACROTERE,
            ),
        ),
    )
    real = Citation(
        doc="plu_reglement",
        page=91,
        quote=ACROTERE,
        source_kind=SourceKind.REGULATORY,
    )
    fabricated = real.model_copy(update={"quote": f"7 {ACROTERE.removeprefix('10 ')} maximum"})
    grounded = score_statement(statement, [note(real)], matcher)
    assert (grounded.correct, grounded.grounded, grounded.cited) == (True, True, True)
    lucky = score_statement(statement, [note(fabricated)], matcher)
    assert (lucky.correct, lucky.grounded, lucky.cited) == (True, False, False)
    missed = score_statement(statement, [], matcher)
    assert (missed.correct, missed.grounded, missed.cited) == (False, False, False)
    assert missed.key_or_statement == statement.statement


def score(critical: bool, grounded: bool) -> FactScore:
    return FactScore(
        key_or_statement="k",
        correct=grounded,
        grounded=grounded,
        critical=critical,
        cited=None,
        detail="",
    )


def test_item_passes():
    assert item_passes([score(True, True), score(False, False)], [False])
    assert not item_passes([score(True, False)], [])
    assert not item_passes([score(True, True)], [False, True])
