"""The ``submit_study`` gate: the orchestrator's final submission, checked and completed.

It comes with ``revise_study``, which fixes a rejected study by edits instead of resubmitting it.

Declared in the orchestrator's ``tools`` list (``conf/agent/default.yaml``). ``corpus`` is a
provider (``_partial_: true``) called on the first submission only.
"""

from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path
from typing import Protocol

from langchain_core.tools import BaseTool

from agent.adapters.images.pages import RegionError
from agent.contracts.evidence import Citation, CitationCheck, ImageRegion, StoredCrop
from agent.contracts.inputs.corpus import Corpus
from agent.contracts.study import Study, VerifiedStudy
from agent.runtime.geometry.envelope.study import EnvelopeSettings
from agent.tools.envelope.compute import GeometrySettings, site_envelope
from agent.tools.study.checks import CitationRules, CorpusFacts, check_submission, corpus_facts
from agent.tools.study.envelope import EnvelopeCitations, envelope_errors
from agent.tools.study.inputs import (
    Delivery,
    Findings,
    StudyInputs,
    evidence_regions,
    open_points,
    read_findings,
    unmatched_open_points,
)
from agent.tools.study.messages import describe_accepted, describe_open_point, describe_unsaved_crop
from agent.tools.submit.artifacts import ArtifactData
from agent.tools.submit.factory import SubmissionRejected, submit_tools


class CropStore(Protocol):
    """Saves page image regions as evidence (``PageImages``)."""

    def save_crop(self, region: ImageRegion, directory: Path) -> StoredCrop:
        """Save a region at full resolution and describe the stored file.

        Raises:
            RegionError: If the document, page or region does not exist.
        """
        ...


def submit_study_tools(  # noqa: PLR0913 - one argument per configured bundle
    *,
    name: str,
    artifact: str,
    corpus: Callable[[], Corpus],
    citations: CitationRules,
    inputs: StudyInputs,
    geometry: GeometrySettings,
    envelope: EnvelopeSettings,
    images: CropStore,
    crops_dir: Path,
) -> list[BaseTool]:
    """Build the tool that turns a ``Study`` into a ``VerifiedStudy``, and its revise tool.

    On each submission the gate reads the site, the zone, the required document notes and the
    architect's envelope delivered by the sub-agents (a missing one refuses the study, naming the
    sub-agent to delegate to); checks that every open point of every notes artifact and of the
    envelope has an ambiguity with the same question (case and whitespace aside); checks the
    envelope against the notes and the study (``envelope_errors``); checks every distinct
    regulatory citation of the study and the envelope against the corpus, as
    ``check_submission`` describes; labels the site edges road / side / rear; recomputes the
    envelope's bounds and proposal from its rules and layout; and saves the zoning plan region
    and every note view as evidence crops. All open point, envelope and citation errors are
    reported together. On acceptance the reply gives the envelope figures for the
    orchestrator's answer.
    ``revise_study`` applies edits to the last rejected study and runs the same checks.

    Args:
        name: Tool name (``submit_study``).
        artifact: Artifact key the verified study is stored under (``study``).
        corpus: Provider of the corpus, called on the first submission; its index is cached.
        citations: Citation policy and match settings.
        inputs: Where the site, the zone and the notes are read, and who delivers them.
        geometry: Edge labelling knobs.
        envelope: Envelope computation knobs.
        images: Saves the evidence crops.
        crops_dir: Directory the crops are written to.

    Returns:
        ``[submit_study, revise_study]``; the submit tool's argument schema is ``Study``.
    """

    @cache
    def corpus_index() -> CorpusFacts:
        """Load the corpus and index it, once."""
        return corpus_facts(corpus())

    def finalize(study: Study, artifacts: Mapping[str, ArtifactData]) -> VerifiedStudy:
        """Check the study against the findings and complete it with what code computes."""
        findings = read_findings(artifacts, inputs)
        checks = _check(study, findings, inputs, corpus_index(), citations)
        delivered = findings.envelope
        computed = site_envelope(
            findings.site,
            delivered.rules,
            delivered.layout,
            geometry=geometry,
            settings=envelope,
            open_points=delivered.open_points,
        )
        return VerifiedStudy(
            study=study,
            site=findings.site,
            boundaries=computed.boundaries,
            zone=findings.zone,
            envelope=computed.study,
            citation_checks=checks,
            evidence=_save_crops(evidence_regions(findings, inputs), images, crops_dir),
        )

    return submit_tools(
        name=name,
        artifact=artifact,
        contract=Study,
        finalize=finalize,
        summarize=describe_accepted,
    )


def _check(
    study: Study,
    findings: Findings,
    inputs: StudyInputs,
    corpus: CorpusFacts,
    rules: CitationRules,
) -> tuple[CitationCheck, ...]:
    """Check the open points, the envelope and the citations, rejecting with every error."""
    errors = [
        describe_open_point(key, point.question)
        for key, point in unmatched_open_points(study, open_points(findings, inputs))
    ]
    errors += envelope_errors(study, findings, inputs)
    checks: dict[Citation, CitationCheck] = {}
    submissions = (study, EnvelopeCitations(envelope=findings.envelope))
    for submission in submissions:
        try:
            found = check_submission(type(submission).__name__, submission, corpus, rules)
        except SubmissionRejected as rejection:
            errors += rejection.errors
            continue
        for check in found:
            checks.setdefault(check.citation, check)
    if errors:
        raise SubmissionRejected(errors)
    return tuple(checks.values())


def _save_crops(
    regions: Mapping[ImageRegion, Delivery], images: CropStore, directory: Path
) -> tuple[StoredCrop, ...]:
    """Save every evidence region, rejecting the study with one error per region that fails."""
    crops: list[StoredCrop] = []
    errors: list[str] = []
    for region, delivery in regions.items():
        try:
            crops.append(images.save_crop(region, directory))
        except RegionError as error:
            errors.append(
                describe_unsaved_crop(region, delivery.artifact, delivery.producer, str(error))
            )
    if errors:
        raise SubmissionRejected(errors)
    return tuple(crops)
