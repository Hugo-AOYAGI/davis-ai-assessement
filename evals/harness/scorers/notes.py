"""Judge-scored checks (``evals/README.md``§4): must_flag, must_not, coverage, anti-patterns.

Coverage takes one call per expected statement, not one per (statement, note) pair: the judge
reads the numbered notes and answers with the numbers of those stating the fact. A doc item has
a handful of statements and a dozen or more notes, so this keeps the calls at the number of
statements, and the judge sees every candidate note side by side (a vaguer note does not count
just because it is asked about alone).
"""

from collections.abc import Callable, Mapping, Sequence

from pydantic import BaseModel

from agent.contracts.base import Contract
from agent.contracts.findings.notes import DocNotes, Note
from agent.contracts.findings.zone import ZoneFindings
from agent.contracts.study import VerifiedStudy
from evals.harness.extract import Output
from evals.harness.items import Item, Level, StatementFact
from evals.harness.judge import ANTI_PATTERNS, Judge, Question
from evals.harness.judging.views import (
    ViewSettings,
    notes_view,
    numbered_notes,
    study_view,
    zone_view,
)
from evals.harness.matching.grounding import CitationMatcher
from evals.harness.scorers.facts import FactScore, score_statement

NO_OUTPUT = "no output"
"""Reason recorded when the run delivered nothing to judge."""


class Judgement(Contract):
    """One question asked about an output, and the judge's answer."""

    question: Question
    subject: str
    """The expected point or forbidden claim; empty for an anti-pattern."""
    hit: bool
    """``must_flag``: the point is raised; ``must_not``: the claim is made; anti-pattern: the
    study shows it."""
    reason: str


class Coverage(Contract):
    """The notes the judge found stating one expected statement."""

    statement: str
    notes: tuple[int, ...]
    """1-based numbers of the covering notes, in ``DocNotes.notes`` order."""
    reason: str


class NotesScore(Contract):
    """Everything the judge decided about one output."""

    must_flag: tuple[Judgement, ...] = ()
    must_not: tuple[Judgement, ...] = ()
    coverage: tuple[Coverage, ...] = ()
    """doc items: one entry per statement fact."""
    statements: tuple[FactScore, ...] = ()
    """doc items: the statement facts scored from their covering notes."""
    anti_patterns: tuple[Judgement, ...] = ()
    """e2e items: one entry per anti-pattern."""

    @property
    def must_not_hits(self) -> tuple[bool, ...]:
        """One flag per ``must_not`` claim, true when made: what ``item_passes`` takes."""
        return tuple(judgement.hit for judgement in self.must_not)


_CONTRACTS: Mapping[Level, type[ZoneFindings | DocNotes | VerifiedStudy]] = {
    Level.ZONING: ZoneFindings,
    Level.DOC: DocNotes,
    Level.E2E: VerifiedStudy,
}


def score_notes(
    item: Item,
    output: Output | None,
    judge: Judge,
    *,
    matcher: CitationMatcher | None = None,
) -> NotesScore:
    """Ask the judge every question an item calls for.

    The surveyor level has none. A missing output raises nothing and costs no call: points
    count as not raised, claims as not made, statements as not covered.

    Args:
        item: The item.
        output: Its run's artifact (contract or JSON), ``None`` when nothing was delivered.
        judge: The judge.
        matcher: Citation checks, needed to score the statements of doc items.

    Returns:
        The judgements.

    Raises:
        ValueError: For a doc item with statements and no ``matcher``.
    """
    statements = [fact for fact in item.facts if isinstance(fact, StatementFact)]
    if statements and matcher is None:
        msg = f"item {item.id}: scoring statements needs a citation matcher"
        raise ValueError(msg)
    contract = _CONTRACTS.get(item.level)
    if contract is None:
        return NotesScore()
    if output is None:
        return _without_output(item, statements, matcher)
    parsed = _parse(contract, output)
    view = _view(parsed, judge.views)
    ask = _asker(judge, view)
    score = NotesScore(
        must_flag=tuple(ask(Question.MUST_FLAG, point) for point in item.must_flag),
        must_not=tuple(ask(Question.MUST_NOT, claim) for claim in item.must_not),
        anti_patterns=tuple(ask(q, "") for q in ANTI_PATTERNS) if item.level is Level.E2E else (),
    )
    if isinstance(parsed, DocNotes) and matcher is not None:
        coverage = tuple(_cover(judge, parsed, fact) for fact in statements)
        scores = tuple(
            score_statement(fact, _notes(parsed, entry), matcher)
            for fact, entry in zip(statements, coverage, strict=True)
        )
        return score.model_copy(update={"coverage": coverage, "statements": scores})
    return score


def _parse(
    contract: type[ZoneFindings | DocNotes | VerifiedStudy], output: Output
) -> ZoneFindings | DocNotes | VerifiedStudy:
    """Read an output as its level's contract."""
    if isinstance(output, contract):
        return output
    data = output.model_dump(mode="json") if isinstance(output, BaseModel) else dict(output)
    return contract.model_validate(data)


def _view(output: ZoneFindings | DocNotes | VerifiedStudy, settings: ViewSettings) -> str:
    """Render an output as the judge reads it."""
    if isinstance(output, ZoneFindings):
        return zone_view(output)
    if isinstance(output, DocNotes):
        return notes_view(output)
    return study_view(output, settings)


def _asker(judge: Judge, view: str) -> Callable[[Question, str], Judgement]:
    """Bind the judge to one rendered output."""

    def ask(question: Question, subject: str) -> Judgement:
        """Ask one question about the bound output and keep the judge's explanation."""
        answer = judge.ask(question, view, subject)
        return Judgement(question=question, subject=subject, hit=answer.yes, reason=answer.reason)

    return ask


def _cover(judge: Judge, notes: DocNotes, fact: StatementFact) -> Coverage:
    """Ask which notes state a statement; numbers outside the notes are dropped."""
    answer = judge.ask(Question.COVERS, numbered_notes(notes), fact.statement)
    count = len(notes.notes)
    numbers = tuple(dict.fromkeys(n for n in answer.notes if 1 <= n <= count)) if answer.yes else ()
    return Coverage(statement=fact.statement, notes=numbers, reason=answer.reason)


def _notes(notes: DocNotes, coverage: Coverage) -> list[Note]:
    """The covering notes of a coverage entry."""
    return [notes.notes[number - 1] for number in coverage.notes]


def _without_output(
    item: Item, statements: Sequence[StatementFact], matcher: CitationMatcher | None
) -> NotesScore:
    """The score of a run that delivered nothing."""

    def missed(question: Question, subject: str) -> Judgement:
        """Record an unmet check without calling the judge."""
        return Judgement(question=question, subject=subject, hit=False, reason=NO_OUTPUT)

    return NotesScore(
        must_flag=tuple(missed(Question.MUST_FLAG, point) for point in item.must_flag),
        must_not=tuple(missed(Question.MUST_NOT, claim) for claim in item.must_not),
        coverage=tuple(
            Coverage(statement=f.statement, notes=(), reason=NO_OUTPUT) for f in statements
        ),
        statements=tuple(
            score_statement(f, (), matcher) for f in statements if matcher is not None
        ),
    )
