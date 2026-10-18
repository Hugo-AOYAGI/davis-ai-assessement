"""Citation validity of an output (``evals/README.md``§4), deterministic only."""

from collections.abc import Sequence

from pydantic import BaseModel, JsonValue

from agent.contracts.base import Contract
from agent.contracts.evidence import Citation, CitationCheck, SourceKind
from agent.runtime.citations.collect import collect_citations, collect_json_citations
from evals.harness.extract import Output
from evals.harness.matching.grounding import CitationMatcher
from evals.harness.scorers.facts import FactScore


class LocatedCheck(Contract):
    """The check of one distinct regulatory citation, with every path it appears at."""

    paths: tuple[str, ...]
    check: CitationCheck


class CitationScore(Contract):
    """Validity of an output's regulatory citations."""

    checks: tuple[LocatedCheck, ...]
    text_verifiable: int
    """Distinct regulatory citations whose quote can be checked against a text layer."""
    verified: int
    """Text-verifiable citations whose quote is found on the cited page."""
    raster: int
    """Distinct citations of documents without a text layer, not text-checked."""
    share_valid: float | None
    """``verified / text_verifiable``; ``None`` without a text-verifiable citation."""
    facts_with_evidence: int
    facts_cited: int
    """Facts with a valid citation on one of their evidence pages, right answer or not."""
    share_facts_cited: float | None
    """``facts_cited / facts_with_evidence``; ``None`` when no fact has evidence."""


def located_citations(output: Output) -> tuple[tuple[str, Citation], ...]:
    """List every citation of an output with its dotted path.

    Args:
        output: An output contract, or its JSON form.

    Returns:
        ``(path, citation)`` pairs, in field order.
    """
    if isinstance(output, BaseModel):
        return collect_citations(output)
    data: JsonValue = dict(output)
    return tuple((path.removeprefix("."), c) for path, c in collect_json_citations(data, ""))


def score_citations(
    output: Output, matcher: CitationMatcher, fact_scores: Sequence[FactScore]
) -> CitationScore:
    """Check every distinct regulatory citation of an output and count the cited facts.

    Args:
        output: An output contract, or its JSON form.
        matcher: Citation checks against the corpus.
        fact_scores: The item's fact scores, for the share of facts cited on an evidence page.

    Returns:
        The citation score.
    """
    paths: dict[Citation, list[str]] = {}
    for path, citation in located_citations(output):
        if citation.source_kind is SourceKind.REGULATORY:
            paths.setdefault(citation, []).append(path)
    checks = tuple(
        LocatedCheck(paths=tuple(found), check=matcher.check(citation))
        for citation, found in paths.items()
    )
    checkable = [located.check for located in checks if located.check.text_verifiable]
    verified = sum(check.verified for check in checkable)
    with_evidence = [score for score in fact_scores if score.cited is not None]
    cited = sum(bool(score.cited) for score in with_evidence)
    return CitationScore(
        checks=checks,
        text_verifiable=len(checkable),
        verified=verified,
        raster=len(checks) - len(checkable),
        share_valid=verified / len(checkable) if checkable else None,
        facts_with_evidence=len(with_evidence),
        facts_cited=cited,
        share_facts_cited=cited / len(with_evidence) if with_evidence else None,
    )
