"""Per-fact scores (``docs/EVALS.md`` §4): answer-correct and grounded-correct."""

from collections.abc import Iterable, Sequence

from agent.contracts.base import Contract
from agent.contracts.evidence import Citation
from agent.contracts.findings.notes import Note
from evals.harness.extract import Output, resolve
from evals.harness.items import Fact, KeyFact, StatementFact
from evals.harness.matching.expectations import evaluate
from evals.harness.matching.grounding import CitationMatcher


class FactScore(Contract):
    """The score of one expected fact."""

    key_or_statement: str
    correct: bool
    """Answer-correct: the value matches (for a statement, a note states it)."""
    grounded: bool
    """Grounded-correct: correct, and backed by a valid citation on an evidence page (just
    correct when the fact has no evidence)."""
    critical: bool
    cited: bool | None
    """Whether a valid citation sits on an evidence page, right answer or not; ``None`` when
    the fact has no evidence."""
    detail: str


def score_fact(fact: KeyFact, output: Output, matcher: CitationMatcher) -> FactScore:
    """Score one key fact against an output.

    Args:
        fact: The expected answer.
        output: The output contract of the item's level, or its JSON form.
        matcher: Citation checks against the corpus.

    Returns:
        The score.

    Raises:
        KeyPathError: When the fact's key does not fit the output's contract.
    """
    elements = resolve(output, fact.key)
    outcome = evaluate(fact, elements)
    cited = matcher.cited(_distinct(c for e in elements for c in e.citations), fact.evidence)
    return FactScore(
        key_or_statement=fact.key,
        correct=outcome.correct,
        grounded=outcome.correct and cited is not False,
        critical=fact.critical,
        cited=cited,
        detail=outcome.detail,
    )


def score_facts(
    facts: Sequence[Fact], output: Output, matcher: CitationMatcher
) -> tuple[FactScore, ...]:
    """Score the key facts of an item; statements are scored with ``score_statement``.

    Args:
        facts: The item's facts.
        output: The output contract of the item's level, or its JSON form.
        matcher: Citation checks against the corpus.

    Returns:
        One score per key fact, in item order.
    """
    return tuple(score_fact(fact, output, matcher) for fact in facts if isinstance(fact, KeyFact))


def score_statement(
    fact: StatementFact, covering_notes: Sequence[Note], matcher: CitationMatcher
) -> FactScore:
    """Score an expected statement from the notes the judge found stating it.

    Args:
        fact: The expected statement.
        covering_notes: The notes that state it, as decided by the judge; empty when none does.
        matcher: Citation checks against the corpus.

    Returns:
        The score: covered when a note states it, grounded when one of those notes also has a
        valid citation on an evidence page.
    """
    cited = matcher.cited(_distinct(c for n in covering_notes for c in n.citations), fact.evidence)
    covered = bool(covering_notes)
    return FactScore(
        key_or_statement=fact.statement,
        correct=covered,
        grounded=covered and cited is not False,
        critical=fact.critical,
        cited=cited,
        detail=f"stated by {len(covering_notes)} note(s)",
    )


def item_passes(fact_scores: Sequence[FactScore], must_not_hits: Sequence[bool]) -> bool:
    """Tell whether an item passes: every critical fact grounded-correct, no ``must_not`` made.

    Args:
        fact_scores: Scores of all the item's facts, key facts and statements.
        must_not_hits: One flag per ``must_not`` claim, true when the output makes it.

    Returns:
        Whether the item passes.
    """
    critical_ok = all(score.grounded for score in fact_scores if score.critical)
    return critical_ok and not any(must_not_hits)


def _distinct(citations: Iterable[Citation]) -> tuple[Citation, ...]:
    """Drop repeated citations, keeping first-seen order."""
    return tuple(dict.fromkeys(citations))
