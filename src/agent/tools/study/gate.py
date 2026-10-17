"""The ``submit_study`` gate: the orchestrator's final submission, checked and completed.

WP6 declares it in the orchestrator's ``tools`` list (``conf/agent/``)::

    - _target_: agent.tools.study.gate.submit_study_tool
      corpus: {_target_: <corpus loader>, _partial_: true, ...}
      artifact: study
      site_artifact: site
      policy: ${policies.citations.policy}
      min_score: ${policies.citations.min_score}
      neighbour_pages: ${policies.citations.neighbour_pages}
      max_quote_chars: ${policies.citations.max_quote_chars}
      quad_segs: ${policies.envelope.quad_segs}
      min_area_m2: ${policies.envelope.min_area_m2}

``corpus`` is a provider (``_partial_: true``): it is called on the first submission only.
"""

from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from functools import cache
from typing import NamedTuple

from langchain_core.tools import BaseTool

from agent.contracts.evidence import Citation, CitationCheck, SourceKind
from agent.contracts.findings.site import SiteContext
from agent.contracts.inputs.corpus import Corpus
from agent.contracts.study import Study, VerifiedStudy
from agent.observability.logs import get_logger
from agent.runtime.citations.collect import collect_citations
from agent.runtime.citations.match import PageIndex, check_citation, index_pages
from agent.runtime.geometry.envelope import compute_envelope
from agent.tools.study.messages import Verification, describe_mislabelled, describe_unverified
from agent.tools.submit.artifacts import ArtifactData, read_artifact
from agent.tools.submit.factory import SubmissionRejected, submit_tool

logger = get_logger(__name__)

type _CitedAt = dict[Citation, tuple[str, ...]]
"""Each distinct citation of a study, with every field path it appears at, in first-seen order."""


class CitationPolicy(StrEnum):
    """What ``submit_study`` does with a regulatory citation whose quote is not on its page."""

    REJECT = "reject"
    """Refuse the study and send one error per unverified citation back to the model."""
    FLAG = "flag"
    """Accept the study, keep the failed checks with ``verified=False`` and log a warning."""


class _CorpusIndex(NamedTuple):
    """Normalised page text and document ids of the corpus, built once per corpus."""

    pages: PageIndex
    documents: tuple[str, ...]


class _Check(NamedTuple):
    """A citation's check, with every study field path the citation appears at."""

    paths: tuple[str, ...]
    result: CitationCheck


def submit_study_tool(  # noqa: PLR0913
    *,
    corpus: Callable[[], Corpus],
    artifact: str,
    site_artifact: str,
    policy: str,
    min_score: float,
    neighbour_pages: int,
    max_quote_chars: int,
    quad_segs: int,
    min_area_m2: float,
) -> BaseTool:
    """Build the ``submit_<artifact>`` tool that turns a ``Study`` into a ``VerifiedStudy``.

    On each submission, the gate reads the ``SiteContext`` delivered by ``site_locator``,
    computes the envelope from the site and the study's envelope parameters, and checks every
    distinct regulatory citation of the study against the corpus. Under the ``reject`` policy an
    unverified citation refuses the study with one actionable error per citation; under ``flag``
    the study is accepted and the failed checks are kept and logged. A corpus document cited as
    a geometric source is a labelling error and refuses the study under either policy; the
    other geometric citations (cadastre, geocoder) are not checked.

    Args:
        corpus: Provider of the corpus, called on the first submission; its page index is cached.
        artifact: Artifact key the verified study is stored under (``study``).
        site_artifact: Artifact key holding the ``SiteContext`` (``site``).
        policy: ``reject`` or ``flag``, see ``CitationPolicy``.
        min_score: Similarity in [0, 1] from which a quote counts as found on its page.
        neighbour_pages: How many pages around the cited one are also searched.
        max_quote_chars: Quotes longer than this are truncated in error messages.
        quad_segs: Segments per quarter circle in the round setback buffers.
        min_area_m2: Footprint parts smaller than this are discarded as slivers.

    Returns:
        The submit tool, whose argument schema is ``Study``.

    Raises:
        ValueError: If ``policy`` is not a ``CitationPolicy`` value.
    """
    citation_policy = _parse_policy(policy)
    verification = Verification(min_score, neighbour_pages, max_quote_chars)

    @cache
    def corpus_index() -> _CorpusIndex:
        """Load the corpus and index its pages, once."""
        loaded = corpus()
        return _CorpusIndex(index_pages(loaded), tuple(doc.id for doc in loaded.documents))

    def finalize(study: Study, artifacts: Mapping[str, ArtifactData]) -> VerifiedStudy:
        """Complete the study with the site, its envelope and its citation checks."""
        site = _read_site(artifacts, site_artifact)
        envelope = compute_envelope(
            site, study.envelope, quad_segs=quad_segs, min_area_m2=min_area_m2
        )
        index = corpus_index()
        cited = _cited_at(study)
        checks = _check_regulatory(cited, index.pages, verification)
        mislabelled = _mislabelled(cited, index.documents)
        unverified = [
            describe_unverified(check.paths, check.result, index.documents, verification)
            for check in checks
            if not check.result.verified
        ]
        _apply_policy(citation_policy, mislabelled, unverified)
        return VerifiedStudy(
            study=study,
            site=site,
            envelope=envelope,
            citation_checks=tuple(check.result for check in checks),
        )

    return submit_tool(artifact, Study, finalize=finalize)


def _parse_policy(policy: str) -> CitationPolicy:
    """Convert the configured policy, failing at build time on an unknown value."""
    try:
        return CitationPolicy(policy)
    except ValueError as error:
        expected = ", ".join(member.value for member in CitationPolicy)
        msg = f"unknown citation policy {policy!r}; expected one of: {expected}"
        raise ValueError(msg) from error


def _read_site(artifacts: Mapping[str, ArtifactData], key: str) -> SiteContext:
    """Read the site delivered by ``site_locator``, or reject the study if there is none."""
    site = read_artifact(artifacts, key, SiteContext)
    if site is None:
        raise SubmissionRejected(
            [
                "(whole study): no site in state, so the envelope cannot be computed. Delegate "
                f"to site_locator so that it delivers the site with submit_{key}, then submit "
                "the study again."
            ]
        )
    return site


def _cited_at(study: Study) -> _CitedAt:
    """Group the study's citations, keeping every field path each one appears at."""
    found: dict[Citation, list[str]] = {}
    for path, citation in collect_citations(study):
        found.setdefault(citation, []).append(path)
    return {citation: tuple(paths) for citation, paths in found.items()}


def _check_regulatory(
    cited: _CitedAt, pages: PageIndex, verification: Verification
) -> list[_Check]:
    """Check each distinct regulatory citation once against the corpus."""
    return [
        _Check(
            paths,
            check_citation(
                citation,
                pages,
                min_score=verification.min_score,
                neighbour_pages=verification.neighbour_pages,
            ),
        )
        for citation, paths in cited.items()
        if citation.source_kind is SourceKind.REGULATORY
    ]


def _mislabelled(cited: _CitedAt, documents: Sequence[str]) -> list[str]:
    """Report every corpus document cited as a geometric source, which skips verification."""
    return [
        describe_mislabelled(paths, citation.doc)
        for citation, paths in cited.items()
        if citation.source_kind is SourceKind.GEOMETRIC and citation.doc in documents
    ]


def _apply_policy(
    policy: CitationPolicy, mislabelled: Sequence[str], unverified: Sequence[str]
) -> None:
    """Reject the study on errors the policy does not tolerate, or log the tolerated ones.

    Mislabelled citations are rejected under every policy; unverified ones only under
    ``reject``. A rejection reports both kinds, so the model fixes everything in one round.
    """
    if mislabelled or (unverified and policy is CitationPolicy.REJECT):
        raise SubmissionRejected([*mislabelled, *unverified])
    if unverified:
        logger.warning(
            "submit_study accepted %d unverified citation(s) under the flag policy:\n%s",
            len(unverified),
            "\n".join(unverified),
        )
