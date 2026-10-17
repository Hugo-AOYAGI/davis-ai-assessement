from collections.abc import Mapping, Sequence
from functools import cache

from agent.contracts.base import Contract
from agent.contracts.evidence import Citation, CitationCheck, SourceKind
from agent.observability.logs import get_logger
from agent.runtime.citations.collect import collect_citations
from agent.runtime.citations.match import PageIndex, check_citation, index_pages
from agent.tools.regulation.source import CorpusSource
from agent.tools.study.gate import CitationPolicy
from agent.tools.study.messages import Verification, describe_mislabelled, describe_unverified
from agent.tools.submit.artifacts import ArtifactData
from agent.tools.submit.factory import Finalizer, SubmissionRejected

logger = get_logger(__name__)


def citation_finalizer(
    *,
    corpus: CorpusSource,
    policy: str,
    min_score: float,
    neighbour_pages: int,
    max_quote_chars: int,
) -> Finalizer[Contract]:
    """Build a submit-tool finalizer checking a submission's citations, as ``submit_study`` does.

    Each distinct regulatory citation is checked once against the corpus page it cites. Under
    the ``reject`` policy an unverified citation refuses the submission with one error per
    citation, naming every field path it appears at; under ``flag`` the submission is accepted
    and the failures are logged. A corpus document cited as geometric is refused under either
    policy. The submission itself is stored unchanged.

    Args:
        corpus: The corpus the quotes are checked against; its pages are indexed on first use.
        policy: ``reject`` or ``flag``, see ``CitationPolicy``.
        min_score: Similarity in [0, 1] from which a quote counts as found on its page.
        neighbour_pages: How many pages around the cited one are also searched.
        max_quote_chars: Quotes longer than this are truncated in error messages.

    Returns:
        The finalizer, for ``submit_tool(..., finalize=...)``.

    Raises:
        ValueError: If ``policy`` is not a ``CitationPolicy`` value.
    """
    citation_policy = CitationPolicy(policy)
    verification = Verification(min_score, neighbour_pages, max_quote_chars)

    @cache
    def pages() -> PageIndex:
        """Normalise the corpus pages, once."""
        return index_pages(corpus.index().corpus)

    def finalize(submission: Contract, _artifacts: Mapping[str, ArtifactData]) -> Contract:
        """Check the submission's citations and apply the policy."""
        documents = tuple(document.id for document in corpus.index().documents())
        cited = _cited_at(submission)
        checks = [
            (paths, _check(citation, pages(), verification))
            for citation, paths in cited.items()
            if citation.source_kind is SourceKind.REGULATORY
        ]
        unverified = [
            describe_unverified(paths, check, documents, verification)
            for paths, check in checks
            if not check.verified
        ]
        mislabelled = [
            describe_mislabelled(paths, citation.doc)
            for citation, paths in cited.items()
            if citation.source_kind is SourceKind.GEOMETRIC and citation.doc in documents
        ]
        name = type(submission).__name__
        verified = len(checks) - len(unverified)
        logger.info("%s: %d/%d citations verified", name, verified, len(checks))
        _apply_policy(name, citation_policy, mislabelled, unverified)
        return submission

    return finalize


def _cited_at(submission: Contract) -> dict[Citation, tuple[str, ...]]:
    """Group the submission's citations, keeping every field path each one appears at."""
    found: dict[Citation, list[str]] = {}
    for path, citation in collect_citations(submission):
        found.setdefault(citation, []).append(path)
    return {citation: tuple(paths) for citation, paths in found.items()}


def _check(citation: Citation, pages: PageIndex, verification: Verification) -> CitationCheck:
    """Check one regulatory citation with the configured tolerance."""
    return check_citation(
        citation,
        pages,
        min_score=verification.min_score,
        neighbour_pages=verification.neighbour_pages,
    )


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
