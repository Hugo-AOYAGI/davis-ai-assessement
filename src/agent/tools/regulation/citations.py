from collections.abc import Mapping
from functools import cache

from agent.contracts.base import Contract
from agent.tools.regulation.source import CorpusSource
from agent.tools.study.checks import (
    CitationRules,
    CorpusFacts,
    check_submission,
    corpus_facts,
    parse_policy,
)
from agent.tools.study.messages import Verification
from agent.tools.submit.artifacts import ArtifactData
from agent.tools.submit.factory import Finalizer


def citation_finalizer(  # noqa: PLR0913
    *,
    corpus: CorpusSource,
    policy: str,
    min_score: float,
    neighbour_pages: int,
    max_quote_chars: int,
    check_raster: bool,
) -> Finalizer[Contract]:
    """Build a submit-tool finalizer checking a submission's citations, as ``submit_study`` does.

    Each distinct regulatory citation is checked once against the corpus page it cites. Under
    the ``reject`` policy an unverified citation refuses the submission with one error per
    citation, naming every field path it appears at; under ``flag`` the submission is accepted
    and the failures are logged. A citation of a raster document (no text layer) is not checked
    and never refuses the submission, unless ``check_raster``. A corpus document cited as
    geometric is refused under either policy. The submission itself is stored unchanged.

    Args:
        corpus: The corpus the quotes are checked against; its pages are indexed on first use.
        policy: ``reject`` or ``flag``, see ``CitationPolicy``.
        min_score: Similarity in [0, 1] from which a quote counts as found on its page.
        neighbour_pages: How many pages around the cited one are also searched.
        max_quote_chars: Quotes longer than this are truncated in error messages.
        check_raster: Whether citations of raster documents are text-checked, and then fail.

    Returns:
        The finalizer, for ``submit_tool(..., finalize=...)``.

    Raises:
        ValueError: If ``policy`` is not a ``CitationPolicy`` value.
    """
    rules = CitationRules(
        parse_policy(policy),
        Verification(min_score, neighbour_pages, max_quote_chars),
        check_raster,
    )

    @cache
    def facts() -> CorpusFacts:
        """Index the corpus, once."""
        return corpus_facts(corpus.index().corpus)

    def finalize(submission: Contract, _artifacts: Mapping[str, ArtifactData]) -> Contract:
        """Check the submission's citations and apply the policy."""
        check_submission(type(submission).__name__, submission, facts(), rules)
        return submission

    return finalize
