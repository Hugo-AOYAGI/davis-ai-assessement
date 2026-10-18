"""Aggregate item results per level (``evals/README.md``§6): rates with their intervals."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from statistics import mean

from agent.contracts.base import Contract
from evals.harness.items import Level
from evals.harness.passes.scoring import (
    ItemResult,
    anti_pattern_hits,
    must_not_hits,
    notes_flags,
)
from evals.harness.report.stats import Interval, Ratio, bootstrap, pooled, wilson
from evals.harness.scorers.citations import CitationScore


@dataclass(frozen=True)
class Statistics:
    """``eval.confidence`` and ``eval.bootstrap``."""

    confidence: float
    resamples: int
    seed: int


class Spending(Contract):
    """What a pass cost."""

    runs_usd: float
    """Agent runs; for a re-scoring pass, what the re-scored runs cost when they ran."""
    judging_usd: float


class Failure(Contract):
    """An item that did not pass, and why."""

    item_id: str
    critical_facts: tuple[str, ...]
    """Critical facts that are not grounded-correct, with the scorer's detail."""
    must_not: int
    """``must_not`` claims the output makes."""
    error: str | None


class LevelReport(Contract):
    """The figures of one level."""

    level: Level
    items: int
    passed: int
    pass_rate: Interval | None
    grounded_accuracy: Interval | None
    answer_accuracy: Interval | None
    luck_rate: float | None
    """Answer minus grounded accuracy: right answers not justified from the right source."""
    citation_validity: float | None
    facts_cited: float | None
    must_flag_coverage: float | None
    must_not_hits: int
    anti_pattern_hits: int
    read_share: float | None
    rejections: int
    tool_calls: float | None
    """Mean tool calls per item."""
    cost_usd: float
    wall_time_s: float | None
    """Mean wall time per item."""
    errors: int
    failures: tuple[Failure, ...]


def report_levels(results: Sequence[ItemResult], stats: Statistics) -> tuple[LevelReport, ...]:
    """Aggregate results per level, in level order.

    Args:
        results: Item results of a pass, any levels.
        stats: Interval settings.

    Returns:
        One report per level present in the results.
    """
    return tuple(
        report_level(level, selected, stats)
        for level in Level
        if (selected := [result for result in results if result.level is level])
    )


def report_level(level: Level, results: Sequence[ItemResult], stats: Statistics) -> LevelReport:
    """Aggregate the results of one level.

    Args:
        level: The level.
        results: Its item results.
        stats: Interval settings.

    Returns:
        The level's figures.
    """
    passed = sum(result.passed for result in results)
    grounded = _interval([r.grounded() for r in results], stats)
    answered = _interval([r.answered() for r in results], stats)
    trajectories = [r.trajectory for r in results if r.trajectory is not None]
    return LevelReport(
        level=level,
        items=len(results),
        passed=passed,
        pass_rate=wilson(passed, len(results), confidence=stats.confidence),
        grounded_accuracy=grounded,
        answer_accuracy=answered,
        luck_rate=(
            answered.estimate - grounded.estimate
            if answered is not None and grounded is not None
            else None
        ),
        citation_validity=pooled(
            [Ratio(hits=c.verified, total=c.text_verifiable) for c in _citations(results)]
        ),
        facts_cited=pooled(
            [Ratio(hits=c.facts_cited, total=c.facts_with_evidence) for c in _citations(results)]
        ),
        must_flag_coverage=pooled([notes_flags(r.notes) for r in results]),
        must_not_hits=sum(sum(must_not_hits(r.notes)) for r in results),
        anti_pattern_hits=sum(len(anti_pattern_hits(r.notes)) for r in results),
        read_share=_mean(t.read_share for t in trajectories),
        rejections=sum(sum(t.rejections.values()) for t in trajectories),
        tool_calls=_mean(float(sum(t.tool_calls.values())) for t in trajectories),
        cost_usd=sum(r.run.cost_usd or 0.0 for r in results),
        wall_time_s=_mean(r.run.wall_time_s for r in results),
        errors=sum(r.run.error is not None for r in results),
        failures=tuple(_failure(r) for r in results if not r.passed),
    )


def _interval(ratios: Sequence[Ratio], stats: Statistics) -> Interval | None:
    """Bootstrap interval over items of a pooled fact share."""
    return bootstrap(
        ratios, resamples=stats.resamples, seed=stats.seed, confidence=stats.confidence
    )


def _citations(results: Iterable[ItemResult]) -> list[CitationScore]:
    """The citation scores of the results that have one."""
    return [result.citations for result in results if result.citations is not None]


def _failure(result: ItemResult) -> Failure:
    """Why an item failed."""
    return Failure(
        item_id=result.item_id,
        critical_facts=tuple(
            f"{fact.key_or_statement}: {fact.detail}" for fact in result.failing_critical()
        ),
        must_not=sum(must_not_hits(result.notes)),
        error=result.run.error,
    )


def _mean(values: Iterable[float | None]) -> float | None:
    """Mean of the known values; ``None`` when none is known."""
    known = [value for value in values if value is not None]
    return mean(known) if known else None
