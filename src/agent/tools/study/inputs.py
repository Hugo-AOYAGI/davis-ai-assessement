"""What the ``submit_study`` gate reads from the artifacts delivered by the sub-agents."""

from collections.abc import Mapping, Sequence
from typing import NamedTuple, Self

from pydantic import Field, model_validator

from agent.contracts.base import Contract
from agent.contracts.evidence import ImageRegion
from agent.contracts.findings.notes import DocNotes, OpenPoint
from agent.contracts.findings.site import Site
from agent.contracts.findings.zone import ZoneFindings
from agent.contracts.study import Study
from agent.tools.study.messages import describe_missing_artifact, describe_missing_notes
from agent.tools.submit.artifacts import ArtifactData, read_artifact
from agent.tools.submit.factory import SubmissionRejected


class Delivery(Contract):
    """An artifact the gate reads, and the sub-agent that delivers it."""

    artifact: str = Field(min_length=1)
    """State key, e.g. ``site``; for notes, a template holding ``{label}``."""
    producer: str = Field(min_length=1)
    """Sub-agent to delegate to when the artifact is missing."""


class StudyInputs(Contract):
    """Where the gate finds the site, the zone and the document notes the study rests on."""

    site: Delivery
    zone: Delivery
    notes: Delivery
    labels: tuple[str, ...]
    """Labels of the notes every study needs, e.g. ``rules`` and ``oap``."""

    @model_validator(mode="after")
    def _notes_key_has_label(self) -> Self:
        """Reject a notes key template that cannot tell labels apart."""
        if "{label}" not in self.notes.artifact:
            msg = f"notes artifact {self.notes.artifact!r} must hold the {{label}} placeholder"
            raise ValueError(msg)
        return self

    def notes_key(self, label: str) -> str:
        """Artifact key of the notes with this label, e.g. ``notes.rules``.

        Args:
            label: A notes label.

        Returns:
            The key.
        """
        return self.notes.artifact.format(label=label)


class Findings(NamedTuple):
    """The delivered artifacts a study is checked and completed with."""

    site: Site
    zone: ZoneFindings
    notes: tuple[DocNotes, ...]
    """The required notes, in label order."""


def read_findings(artifacts: Mapping[str, ArtifactData], inputs: StudyInputs) -> Findings:
    """Read the site, the zone and the required notes from the artifacts.

    Args:
        artifacts: The ``artifacts`` value of the graph state.
        inputs: Where each artifact is stored and who delivers it.

    Returns:
        The findings.

    Raises:
        SubmissionRejected: With one error per missing artifact, naming the sub-agent to
            delegate to.
    """
    site = read_artifact(artifacts, inputs.site.artifact, Site)
    zone = read_artifact(artifacts, inputs.zone.artifact, ZoneFindings)
    keys = {label: inputs.notes_key(label) for label in inputs.labels}
    notes = {label: read_artifact(artifacts, key, DocNotes) for label, key in keys.items()}
    errors = [
        describe_missing_artifact(delivery.artifact, delivery.producer)
        for delivery, found in ((inputs.site, site), (inputs.zone, zone))
        if found is None
    ]
    errors += [
        describe_missing_notes(keys[label], label, inputs.notes.producer)
        for label, found in notes.items()
        if found is None
    ]
    if errors or site is None or zone is None:
        raise SubmissionRejected(errors)
    return Findings(site, zone, tuple(found for found in notes.values() if found is not None))


def fold(question: str) -> str:
    """Fold case and whitespace, so that a copied question matches its original.

    Args:
        question: A question as written.

    Returns:
        The question lower-cased, on one line, with single spaces.
    """
    return " ".join(question.split()).casefold()


def unmatched_open_points(study: Study, notes: Sequence[DocNotes]) -> list[tuple[str, OpenPoint]]:
    """List the open points of the notes that no ambiguity of the study answers.

    An open point is answered by an ambiguity whose question is the same text, case and
    whitespace aside.

    Args:
        study: The submitted study.
        notes: The required notes.

    Returns:
        ``(label, open point)`` pairs, in note and open point order.
    """
    answered = {fold(ambiguity.question) for ambiguity in study.ambiguities}
    return [
        (note.label, point)
        for note in notes
        for point in note.open_points
        if fold(point.question) not in answered
    ]


def evidence_regions(findings: Findings, inputs: StudyInputs) -> dict[ImageRegion, Delivery]:
    """List the image regions to save as evidence, each once, with the delivery holding it.

    Args:
        findings: The delivered findings: the zone region is the plan crop, the note views are
            diagram crops.
        inputs: Where each artifact comes from.

    Returns:
        The zone region, then every note view, in order, without duplicates; each mapped to the
        delivery it was first found in.
    """
    regions = {findings.zone.region: inputs.zone}
    for doc_notes in findings.notes:
        delivery = inputs.notes.model_copy(update={"artifact": inputs.notes_key(doc_notes.label)})
        for note in doc_notes.notes:
            for view in note.views:
                regions.setdefault(view, delivery)
    return regions
