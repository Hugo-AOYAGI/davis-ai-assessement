import pytest

from evals.harness.report.stats import Ratio, bootstrap, pooled, wilson, z_score


def test_z_score_of_95_percent():
    assert z_score(0.95) == pytest.approx(1.959964, abs=1e-6)


@pytest.mark.parametrize(
    ("successes", "total", "low", "high"),
    [(7, 10, 0.3968, 0.8922), (0, 10, 0.0, 0.2775), (10, 10, 0.7225, 1.0), (1, 2, 0.0945, 0.9055)],
)
def test_wilson_known_values(successes, total, low, high):
    interval = wilson(successes, total, confidence=0.95)
    assert interval is not None
    assert interval.estimate == pytest.approx(successes / total)
    assert interval.low == pytest.approx(low, abs=1e-4)
    assert interval.high == pytest.approx(high, abs=1e-4)


def test_wilson_without_items():
    assert wilson(0, 0, confidence=0.95) is None


def test_wilson_narrows_with_lower_confidence():
    wide = wilson(7, 10, confidence=0.95)
    narrow = wilson(7, 10, confidence=0.8)
    assert wide is not None and narrow is not None
    assert wide.low < narrow.low < narrow.high < wide.high


def test_pooled_weighs_items_by_their_facts():
    assert pooled([Ratio(hits=1, total=1), Ratio(hits=0, total=3)]) == 0.25
    assert pooled([Ratio(hits=0, total=0)]) is None
    assert pooled([]) is None


RATIOS = [Ratio(hits=h, total=t) for h, t in [(4, 5), (2, 4), (3, 3), (0, 2), (5, 6), (1, 3)]]


def test_bootstrap_is_seeded():
    first = bootstrap(RATIOS, resamples=500, seed=7, confidence=0.95)
    again = bootstrap(RATIOS, resamples=500, seed=7, confidence=0.95)
    other = bootstrap(RATIOS, resamples=500, seed=8, confidence=0.95)
    assert first == again
    assert first != other


def test_bootstrap_brackets_the_pooled_share():
    interval = bootstrap(RATIOS, resamples=2000, seed=0, confidence=0.95)
    assert interval is not None
    assert interval.estimate == pytest.approx(15 / 23)
    assert 0.0 <= interval.low < interval.estimate < interval.high <= 1.0


def test_bootstrap_of_identical_items_has_no_width():
    interval = bootstrap([Ratio(hits=1, total=2)] * 5, resamples=100, seed=0, confidence=0.95)
    assert interval is not None
    assert interval.low == interval.estimate == interval.high == 0.5


def test_bootstrap_without_facts():
    assert bootstrap([Ratio(hits=0, total=0)], resamples=10, seed=0, confidence=0.95) is None
