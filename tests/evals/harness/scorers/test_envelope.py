from evals.harness.items import KeyFact
from evals.harness.scorers.envelope import Diagnosis, expected_figures, score_envelope


def score(output, expected):
    return score_envelope(
        output,
        expected,
        tolerance=1e-6,
        quad_segs=8,
        min_area_m2=1.0,
        level_step_m=1,
        cut_tolerance_m=0.01,
    )


def volume(expect, tolerance=0.02) -> KeyFact:
    return KeyFact(key="envelope.proposal.total_volume_m3", expect=expect, tolerance=tolerance)


def test_recomputed_envelope_matches_the_reported_one(study):
    result = score(study, [])
    assert all(check.ok for check in result.against_recomputed)
    assert result.recomputed.proposal.total_volume_m3 == study.envelope.proposal.total_volume_m3
    assert result.diagnosis is Diagnosis.UNCHECKED


def test_expected_volume_within_tolerance_is_correct(study):
    result = score(study, [volume(85000)])
    assert result.diagnosis is Diagnosis.CORRECT
    assert result.against_expected[0].expected == 85000


def test_consistent_envelope_from_wrong_parameters_is_a_wrong_rule(variant):
    taller = variant(
        lambda d: d["envelope"]["rules"]["buildings"][0]["max_height_m"].update(value=25)
    )

    result = score(taller, [volume(85000)])
    assert result.diagnosis is Diagnosis.WRONG_CALCULATION
    consistent = taller.model_copy(update={"envelope": result.recomputed})
    result = score(consistent, [volume(85000)])
    assert result.diagnosis is Diagnosis.WRONG_RULE
    assert [c.figure for c in result.against_expected if not c.ok] == ["proposal.total_volume_m3"]


def test_figures_inconsistent_with_parameters_are_a_wrong_calculation(variant):
    inflated = variant(lambda d: d["envelope"]["proposal"].update(total_volume_m3=90000.0))
    result = score(inflated, [volume(90000)])
    assert result.diagnosis is Diagnosis.WRONG_CALCULATION
    assert [c.figure for c in result.against_recomputed if not c.ok] == ["proposal.total_volume_m3"]


def test_expected_figures_selects_envelope_expectations(items):
    facts = [
        volume(1),
        KeyFact(key="envelope.proposal.total_volume_m3", at_least=1),
        KeyFact(key='envelope.rules.buildings[building~"Sociale"].max_height_m', expect=20),
        KeyFact(key="envelope.footprint", expect=None),
        *items["e01_reference"].facts,
    ]
    assert [f.key for f in expected_figures(facts)] == ["envelope.proposal.total_volume_m3"] * 2
