"""Interval estimates for the eval report (``docs/EVALS.md`` §6): Wilson and bootstrap."""

import math
import random
from collections.abc import Sequence
from statistics import NormalDist

from agent.contracts.base import Contract


class Interval(Contract):
    """A point estimate with a two-sided confidence interval."""

    estimate: float
    low: float
    high: float


class Ratio(Contract):
    """One item's share: ``hits`` out of ``total``."""

    hits: int
    total: int


def z_score(confidence: float) -> float:
    """Return the two-sided normal quantile of a confidence level (1.96 for 0.95).

    Args:
        confidence: Level in ``(0, 1)``.

    Returns:
        The quantile.
    """
    return NormalDist().inv_cdf(1 - (1 - confidence) / 2)


def wilson(successes: int, total: int, *, confidence: float) -> Interval | None:
    """Wilson score interval of a pass rate.

    Args:
        successes: Items that passed.
        total: Items scored.
        confidence: Level of the interval, e.g. 0.95.

    Returns:
        The rate and its interval; ``None`` when nothing was scored.
    """
    if total == 0:
        return None
    z = z_score(confidence)
    rate = successes / total
    denominator = 1 + z * z / total
    centre = (rate + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return Interval(estimate=rate, low=max(0.0, centre - margin), high=min(1.0, centre + margin))


def pooled(ratios: Sequence[Ratio]) -> float | None:
    """Pool item ratios into one share: all hits over all totals.

    Args:
        ratios: One ratio per item.

    Returns:
        The pooled share; ``None`` when the totals sum to zero.
    """
    total = sum(ratio.total for ratio in ratios)
    return sum(ratio.hits for ratio in ratios) / total if total else None


def bootstrap(
    ratios: Sequence[Ratio], *, resamples: int, seed: int, confidence: float
) -> Interval | None:
    """Percentile bootstrap of a pooled share, resampling items rather than facts.

    Facts within an item are correlated, so the item is the unit that is resampled.

    Args:
        ratios: One ratio per item (e.g. grounded-correct facts out of facts).
        resamples: Bootstrap resamples.
        seed: Seed of the resampling, for a reproducible interval.
        confidence: Level of the interval.

    Returns:
        The pooled share and its interval; ``None`` without any fact.
    """
    estimate = pooled(ratios)
    if estimate is None:
        return None
    rng = random.Random(seed)  # noqa: S311 - statistics, not security
    shares = sorted(
        share
        for _ in range(resamples)
        if (share := pooled(rng.choices(ratios, k=len(ratios)))) is not None
    )
    if not shares:
        return Interval(estimate=estimate, low=estimate, high=estimate)
    tail = (1 - confidence) / 2
    return Interval(
        estimate=estimate,
        low=_quantile(shares, tail),
        high=_quantile(shares, 1 - tail),
    )


def _quantile(values: Sequence[float], q: float) -> float:
    """Nearest-rank quantile of sorted values."""
    index = min(len(values) - 1, max(0, math.ceil(q * len(values)) - 1))
    return values[index]
