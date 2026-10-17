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
      check_raster: ${policies.citations.check_raster}
      quad_segs: ${policies.envelope.quad_segs}
      min_area_m2: ${policies.envelope.min_area_m2}

``corpus`` is a provider (``_partial_: true``): it is called on the first submission only.
"""

from collections.abc import Callable, Mapping
from functools import cache

from langchain_core.tools import BaseTool

from agent.contracts.findings.site import SiteContext
from agent.contracts.inputs.corpus import Corpus
from agent.contracts.study import Study, VerifiedStudy
from agent.runtime.geometry.envelope import compute_envelope
from agent.tools.study.checks import (
    CitationRules,
    CorpusFacts,
    check_submission,
    corpus_facts,
    parse_policy,
)
from agent.tools.study.messages import Verification
from agent.tools.submit.artifacts import ArtifactData, read_artifact
from agent.tools.submit.factory import SubmissionRejected, submit_tool


def submit_study_tool(  # noqa: PLR0913
    *,
    corpus: Callable[[], Corpus],
    artifact: str,
    site_artifact: str,
    policy: str,
    min_score: float,
    neighbour_pages: int,
    max_quote_chars: int,
    check_raster: bool,
    quad_segs: int,
    min_area_m2: float,
) -> BaseTool:
    """Build the ``submit_<artifact>`` tool that turns a ``Study`` into a ``VerifiedStudy``.

    On each submission, the gate reads the ``SiteContext`` delivered by ``site_locator``,
    computes the envelope from the site and the study's envelope parameters, and checks every
    distinct regulatory citation of the study against the corpus. Under the ``reject`` policy an
    unverified citation refuses the study with one actionable error per citation; under ``flag``
    the study is accepted and the failed checks are kept and logged. A citation of a raster
    document (no text layer, e.g. the zoning plan) is recorded as not text-verifiable and never
    refuses the study, unless ``check_raster``. A corpus document cited as a geometric source is
    a labelling error and refuses the study under either policy; the other geometric citations
    (cadastre, geocoder) are not checked.

    Args:
        corpus: Provider of the corpus, called on the first submission; its page index is cached.
        artifact: Artifact key the verified study is stored under (``study``).
        site_artifact: Artifact key holding the ``SiteContext`` (``site``).
        policy: ``reject`` or ``flag``, see ``CitationPolicy``.
        min_score: Similarity in [0, 1] from which a quote counts as found on its page.
        neighbour_pages: How many pages around the cited one are also searched.
        max_quote_chars: Quotes longer than this are truncated in error messages.
        check_raster: Whether citations of raster documents are text-checked, and then fail.
        quad_segs: Segments per quarter circle in the round setback buffers.
        min_area_m2: Footprint parts smaller than this are discarded as slivers.

    Returns:
        The submit tool, whose argument schema is ``Study``.

    Raises:
        ValueError: If ``policy`` is not a ``CitationPolicy`` value.
    """
    rules = CitationRules(
        parse_policy(policy),
        Verification(min_score, neighbour_pages, max_quote_chars),
        check_raster,
    )

    @cache
    def corpus_index() -> CorpusFacts:
        """Load the corpus and index it, once."""
        return corpus_facts(corpus())

    def finalize(study: Study, artifacts: Mapping[str, ArtifactData]) -> VerifiedStudy:
        """Complete the study with the site, its envelope and its citation checks."""
        site = _read_site(artifacts, site_artifact)
        envelope = compute_envelope(
            site, study.envelope, quad_segs=quad_segs, min_area_m2=min_area_m2
        )
        checks = check_submission(type(study).__name__, study, corpus_index(), rules)
        return VerifiedStudy(study=study, site=site, envelope=envelope, citation_checks=checks)

    return submit_tool(artifact, Study, finalize=finalize)


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
