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
from pydantic import Field, NonNegativeFloat, PositiveInt

from agent.adapters.images.pages import RegionError
from agent.contracts.base import Contract
from agent.contracts.evidence import CitationCheck, ImageRegion, StoredCrop
from agent.contracts.inputs.corpus import Corpus
from agent.contracts.study import Study, VerifiedStudy
from agent.runtime.geometry.edges import label_edges
from agent.runtime.geometry.envelope import compute_envelope
from agent.tools.study.checks import CitationRules, CorpusFacts, check_submission, corpus_facts
from agent.tools.study.inputs import (
    Delivery,
    Findings,
    StudyInputs,
    evidence_regions,
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


class GeometrySettings(Contract):
    """Knobs of the edge labelling and of the envelope computation."""

    snap_tolerance_m: NonNegativeFloat
    """Edges shorter than this never split a limit."""
    collinear_angle_deg: NonNegativeFloat
    """Largest direction change between parcel edges of one limit."""
    quad_segs: PositiveInt
    """Segments per quarter circle in the round setback buffers."""
    min_area_m2: float = Field(ge=0)
    """Footprint parts smaller than this are discarded as slivers."""


def submit_study_tools(  # noqa: PLR0913 - one argument per configured bundle
    *,
    name: str,
    artifact: str,
    corpus: Callable[[], Corpus],
    citations: CitationRules,
    inputs: StudyInputs,
    geometry: GeometrySettings,
    images: CropStore,
    crops_dir: Path,
) -> list[BaseTool]:
    """Build the tool that turns a ``Study`` into a ``VerifiedStudy``, and its revise tool.

    On each submission the gate reads the site, the zone and the required document notes
    delivered by the sub-agents (a missing one refuses the study, naming the sub-agent to
    delegate to); checks that every open point of the notes has an ambiguity with the same
    question (case and whitespace aside); checks every distinct regulatory citation of the study
    against the corpus, as ``check_submission`` describes; labels the site edges road / side /
    rear; computes the envelope; and saves the zoning plan region and every note view as
    evidence crops. All open point and citation errors are reported together. On acceptance the
    reply gives the envelope figures for the orchestrator's answer. ``revise_study`` applies
    edits to the last rejected study and runs the same checks.

    Args:
        name: Tool name (``submit_study``).
        artifact: Artifact key the verified study is stored under (``study``).
        corpus: Provider of the corpus, called on the first submission; its index is cached.
        citations: Citation policy and match settings.
        inputs: Where the site, the zone and the notes are read, and who delivers them.
        geometry: Edge labelling and envelope knobs.
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
        boundaries = label_edges(
            findings.site.edges,
            snap_tolerance_m=geometry.snap_tolerance_m,
            collinear_angle_deg=geometry.collinear_angle_deg,
        )
        envelope = compute_envelope(
            findings.site.polygon,
            boundaries,
            study.envelope,
            quad_segs=geometry.quad_segs,
            min_area_m2=geometry.min_area_m2,
        )
        return VerifiedStudy(
            study=study,
            site=findings.site,
            boundaries=boundaries,
            zone=findings.zone,
            envelope=envelope,
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
    """Check the open points and the citations, rejecting with every error of both."""
    errors = [
        describe_open_point(inputs.notes_key(label), point.question)
        for label, point in unmatched_open_points(study, findings.notes)
    ]
    try:
        checks = check_submission(type(study).__name__, study, corpus, rules)
    except SubmissionRejected as rejection:
        raise SubmissionRejected([*errors, *rejection.errors]) from rejection
    if errors:
        raise SubmissionRejected(errors)
    return checks


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
