"""Citation checks shared by ``submit_study`` and the sub-agents' submit tools."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import NamedTuple

from agent.contracts.base import Contract
from agent.contracts.evidence import Citation, CitationCheck, SourceKind
from agent.contracts.inputs.corpus import Corpus
from agent.observability.logs import get_logger
from agent.runtime.citations.collect import collect_citations
from agent.runtime.citations.match import (
    PageIndex,
    check_citation,
    index_pages,
    raster_documents,
    unverifiable,
)
from agent.tools.study.messages import Verification, describe_mislabelled, describe_unverified
from agent.tools.submit.factory import SubmissionRejected

logger = get_logger(__name__)


class CitationPolicy(StrEnum):
    """What a submit tool does with a regulatory citation whose quote is not on its page."""

    REJECT = "reject"
    """Refuse the submission and send one error per unverified citation back to the model."""
    FLAG = "flag"
    """Accept the submission, keep the failed checks with ``verified=False`` and log a warning."""


class CorpusFacts(NamedTuple):
    """What citation checks need from the corpus, built once per corpus."""

    pages: PageIndex
    """Normalised page text, as built by ``index_pages``."""
    documents: tuple[str, ...]
    """Ids of the corpus documents."""
    raster: frozenset[str]
    """Ids of the documents without a text layer."""


@dataclass(frozen=True)
class CitationRules:
    """How citations are checked and what a failure does."""

    policy: CitationPolicy
    verification: Verification
    check_raster: bool
    """Whether citations of raster documents are text-checked (and then fail) or only recorded."""


class _Check(NamedTuple):
    """A citation's check, with every field path the citation appears at."""

    paths: tuple[str, ...]
    result: CitationCheck


def parse_policy(policy: str) -> CitationPolicy:
    """Convert a configured policy, failing at build time on an unknown value.

    Args:
        policy: ``reject`` or ``flag``.

    Returns:
        The policy.

    Raises:
        ValueError: If ``policy`` is not a ``CitationPolicy`` value.
    """
    try:
        return CitationPolicy(policy)
    except ValueError as error:
        expected = ", ".join(member.value for member in CitationPolicy)
        msg = f"unknown citation policy {policy!r}; expected one of: {expected}"
        raise ValueError(msg) from error


def corpus_facts(corpus: Corpus) -> CorpusFacts:
    """Index a corpus for citation checks.

    Args:
        corpus: The ingested corpus.

    Returns:
        Its normalised pages, document ids and raster document ids.
    """
    return CorpusFacts(
        index_pages(corpus),
        tuple(document.id for document in corpus.documents),
        raster_documents(corpus),
    )


def check_submission(
    name: str, submission: Contract, corpus: CorpusFacts, rules: CitationRules
) -> tuple[CitationCheck, ...]:
    """Check every distinct regulatory citation of a submission and apply the policy.

    Each distinct regulatory citation is checked once against the page it cites; a citation of a
    raster document is only recorded as not text-verifiable unless ``rules.check_raster``. A
    corpus document cited as geometric is refused under every policy, an unverified citation
    under ``reject`` only; a rejection reports both kinds, so the model fixes everything at once.
    Other geometric citations (cadastre, geocoder) are not checked.

    Args:
        name: Name of the submission in log lines, e.g. ``Study``.
        submission: The submitted contract.
        corpus: The corpus facts, from ``corpus_facts``.
        rules: Policy, match settings and raster handling.

    Returns:
        One check per distinct regulatory citation, in first-seen order.

    Raises:
        SubmissionRejected: With one error per citation the policy does not tolerate.
    """
    cited = _cited_at(submission)
    checks = [
        _Check(
            paths,
            check_regulatory(citation, corpus, rules.verification, check_raster=rules.check_raster),
        )
        for citation, paths in cited.items()
        if citation.source_kind is SourceKind.REGULATORY
    ]
    unverified = [
        describe_unverified(check.paths, check.result, corpus.documents, rules.verification)
        for check in checks
        if check.result.text_verifiable and not check.result.verified
    ]
    mislabelled = [
        describe_mislabelled(paths, citation.doc)
        for citation, paths in cited.items()
        if citation.source_kind is SourceKind.GEOMETRIC and citation.doc in corpus.documents
    ]
    results = tuple(check.result for check in checks)
    _log_counts(name, results)
    _apply_policy(name, rules.policy, mislabelled, unverified)
    return results


def _cited_at(submission: Contract) -> dict[Citation, tuple[str, ...]]:
    """Group the submission's citations, keeping every field path each one appears at."""
    found: dict[Citation, list[str]] = {}
    for path, citation in collect_citations(submission):
        found.setdefault(citation, []).append(path)
    return {citation: tuple(paths) for citation, paths in found.items()}


def check_regulatory(
    citation: Citation, corpus: CorpusFacts, verification: Verification, *, check_raster: bool
) -> CitationCheck:
    """Check one regulatory citation, or record it unchecked when it cites a raster document.

    Args:
        citation: A regulatory citation.
        corpus: The corpus facts, from ``corpus_facts``.
        verification: Match settings.
        check_raster: Whether a citation of a raster document is text-checked anyway.

    Returns:
        The check; not text-verifiable for a raster document unless ``check_raster``.
    """
    if citation.doc in corpus.raster and not check_raster:
        return unverifiable(citation)
    return check_citation(
        citation,
        corpus.pages,
        min_score=verification.min_score,
        neighbour_pages=verification.neighbour_pages,
    )


def _log_counts(name: str, checks: Sequence[CitationCheck]) -> None:
    """Log how many text-verifiable citations were verified, and how many were not checkable."""
    checkable = [check for check in checks if check.text_verifiable]
    verified = sum(check.verified for check in checkable)
    raster = len(checks) - len(checkable)
    suffix = f", {raster} not text-verifiable (raster)" if raster else ""
    logger.info("%s: %d/%d citations verified%s", name, verified, len(checkable), suffix)


def _apply_policy(
    name: str, policy: CitationPolicy, mislabelled: Sequence[str], unverified: Sequence[str]
) -> None:
    """Reject on errors the policy does not tolerate, reporting all of them, or log the rest."""
    if mislabelled or (unverified and policy is CitationPolicy.REJECT):
        raise SubmissionRejected([*mislabelled, *unverified])
    if unverified:
        logger.warning(
            "%s accepted with %d unverified citation(s) under the flag policy:\n%s",
            name,
            len(unverified),
            "\n".join(unverified),
        )
