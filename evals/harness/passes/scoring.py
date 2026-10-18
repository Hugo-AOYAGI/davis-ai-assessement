"""Score a run against its item, retaining diagnostics separately from pass criteria."""

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import JsonValue

from agent.contracts.base import Contract
from agent.contracts.inputs.corpus import Section
from agent.contracts.study import VerifiedStudy
from evals.harness.items import Fact, Item, KeyFact, Level
from evals.harness.judge import Judge
from evals.harness.matching.grounding import CitationMatcher
from evals.harness.refusals import refusal_checks
from evals.harness.report.stats import Ratio
from evals.harness.runs.record import RunRecord
from evals.harness.scorers.citations import CitationScore, score_citations
from evals.harness.scorers.envelope import EnvelopeScore, expected_figures, score_envelope
from evals.harness.scorers.facts import FactScore, item_passes, score_facts
from evals.harness.scorers.notes import NO_OUTPUT, NotesScore, score_notes
from evals.harness.scorers.trajectory import TrajectoryScore, score_trajectory


@dataclass(frozen=True)
class EnvelopeSettings:
    """``eval.tolerances``: how the envelope is recomputed and compared."""

    tolerance: float
    quad_segs: int
    min_area_m2: float
    level_step_m: float
    cut_tolerance_m: float


@dataclass(frozen=True)
class Scoring:
    """What scoring needs besides the item and the record."""

    matcher: CitationMatcher
    judge: Judge
    sections: tuple[Section, ...]
    """Corpus sections, mapping ``read_section`` calls to pages."""
    mode: str
    """``retrieval.mode`` of the runs."""
    envelope: EnvelopeSettings


class RunInfo(Contract):
    """What the run itself reports, kept next to the scores."""

    cost_usd: float | None = None
    wall_time_s: float | None = None
    rejections: int = 0
    error: str | None = None
    has_output: bool = False


class ItemMetrics(Contract):
    """The headline numbers of one item, as shown per item in Phoenix."""

    item_id: str
    item_pass: bool
    grounded_accuracy: float | None
    answer_accuracy: float | None
    citation_validity: float | None
    must_flag_rate: float | None
    must_not_hits: int
    anti_patterns: int
    cost_usd: float | None


class ItemResult(Contract):
    """Every score of one item."""

    item_id: str
    level: Level
    passed: bool
    run: RunInfo
    facts: tuple[FactScore, ...]
    """Key facts, then statements (doc items)."""
    citations: CitationScore | None = None
    envelope: EnvelopeScore | None = None
    trajectory: TrajectoryScore | None = None
    notes: NotesScore | None = None

    def grounded(self) -> Ratio:
        """Grounded-correct facts out of facts."""
        return Ratio(hits=sum(f.grounded for f in self.facts), total=len(self.facts))

    def answered(self) -> Ratio:
        """Answer-correct facts out of facts."""
        return Ratio(hits=sum(f.correct for f in self.facts), total=len(self.facts))

    def failing_critical(self) -> tuple[FactScore, ...]:
        """Critical facts that are not grounded-correct."""
        return tuple(f for f in self.facts if f.critical and not f.grounded)

    def metrics(self) -> ItemMetrics:
        """Headline numbers of the item."""
        notes = self.notes
        flags = notes_flags(notes)
        return ItemMetrics(
            item_id=self.item_id,
            item_pass=self.passed,
            grounded_accuracy=_share(self.grounded()),
            answer_accuracy=_share(self.answered()),
            citation_validity=self.citations.share_valid if self.citations else None,
            must_flag_rate=_share(flags),
            must_not_hits=sum(must_not_hits(notes)),
            anti_patterns=len(anti_pattern_hits(notes)),
            cost_usd=self.run.cost_usd,
        )


def notes_flags(notes: NotesScore | None) -> Ratio:
    """``must_flag`` points raised out of those expected."""
    if notes is None:
        return Ratio(hits=0, total=0)
    return Ratio(hits=sum(j.hit for j in notes.must_flag), total=len(notes.must_flag))


def must_not_hits(notes: NotesScore | None) -> tuple[bool, ...]:
    """One flag per ``must_not`` claim, true when the output makes it."""
    return notes.must_not_hits if notes else ()


def anti_pattern_hits(notes: NotesScore | None) -> tuple[str, ...]:
    """Names of the anti-patterns found in the output."""
    return tuple(str(j.question) for j in notes.anti_patterns if j.hit) if notes else ()


def score_record(item: Item, record: RunRecord, scoring: Scoring) -> ItemResult:
    """Score one run of an item with every scorer that applies to its level.

    A run without output fails every fact, raises no point and makes no claim; citations,
    envelope and trajectory are then not scored.

    Args:
        item: The item.
        record: Its run.
        scoring: Matcher, judge, corpus sections and tolerances.

    Returns:
        The item's scores and pass.
    """
    output = record.output
    run = RunInfo(
        cost_usd=record.cost.cost_usd,
        wall_time_s=record.wall_time_s,
        rejections=len(record.rejections),
        error=record.error,
        has_output=output is not None,
    )
    notes = score_notes(item, output, scoring.judge, matcher=scoring.matcher)
    if item.expected_refusal is not None:
        checks = refusal_checks(
            item.expected_refusal,
            record.messages,
            has_output=output is not None,
            error=record.error,
        )
        passed = all(checks.values())
        fact = FactScore(
            key_or_statement="expected_refusal",
            correct=passed,
            grounded=passed,
            critical=True,
            cited=None,
            detail=str(checks),
        )
        return ItemResult(
            item_id=item.id,
            level=item.level,
            passed=passed,
            run=run,
            facts=(fact,),
            notes=notes,
            trajectory=score_trajectory(
                record.messages, (), sections=scoring.sections, mode=scoring.mode, cost=record.cost
            ),
        )
    if output is None:
        facts = (*_unanswered(item.facts), *notes.statements)
        return ItemResult(
            item_id=item.id, level=item.level, passed=False, run=run, facts=facts, notes=notes
        )
    facts = (*score_facts(item.facts, output, scoring.matcher), *notes.statements)
    return ItemResult(
        item_id=item.id,
        level=item.level,
        passed=item_passes(facts, notes.must_not_hits),
        run=run,
        facts=facts,
        citations=score_citations(output, scoring.matcher, facts),
        envelope=_envelope(item, output, scoring.envelope),
        trajectory=score_trajectory(
            record.messages,
            item.facts,
            sections=scoring.sections,
            mode=scoring.mode,
            cost=record.cost,
        ),
        notes=notes,
    )


def _envelope(
    item: Item, output: dict[str, JsonValue], settings: EnvelopeSettings
) -> EnvelopeScore | None:
    """Score the envelope of an end-to-end study; ``None`` for the other levels."""
    if item.level is not Level.E2E:
        return None
    return score_envelope(
        VerifiedStudy.model_validate(output),
        expected_figures(item.facts),
        tolerance=settings.tolerance,
        quad_segs=settings.quad_segs,
        min_area_m2=settings.min_area_m2,
        level_step_m=settings.level_step_m,
        cut_tolerance_m=settings.cut_tolerance_m,
    )


def _unanswered(facts: Sequence[Fact]) -> tuple[FactScore, ...]:
    """Score every key fact as wrong, for a run that produced no output."""
    return tuple(
        FactScore(
            key_or_statement=fact.key,
            correct=False,
            grounded=False,
            critical=fact.critical,
            cited=False if fact.evidence else None,
            detail=NO_OUTPUT,
        )
        for fact in facts
        if isinstance(fact, KeyFact)
    )


def _share(ratio: Ratio) -> float | None:
    """``hits / total``; ``None`` when there is nothing to count."""
    return ratio.hits / ratio.total if ratio.total else None
