"""What the ``submit_study`` gate reads from the artifacts delivered by the sub-agents."""

from collections.abc import Iterable, Mapping, Sequence
from typing import NamedTuple, Self

from pydantic import Field, model_validator

from agent.contracts.base import Contract
from agent.contracts.envelope import EnvelopeStudy
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
    """Where the gate finds the site, the zone, the notes and the envelope the study rests on."""

    site: Delivery
    zone: Delivery
    notes: Delivery
    envelope: Delivery
    labels: tuple[str, ...]
    """Labels of the notes every study needs, e.g. ``rules``, ``oap`` and ``destinations``."""
    oap_label: str
    """Label of the notes every citation of the layout's OAP choices must come from."""

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

    def notes_labels(self, keys: Iterable[str]) -> list[str]:
        """List the labels of the notes artifacts among artifact keys.

        Args:
            keys: Artifact keys, e.g. ``site``, ``notes.rules``, ``notes.rules_parking``.

        Returns:
            The labels of the keys the notes template matches, e.g. ``rules``, ``rules_parking``.
        """
        prefix, suffix = self.notes.artifact.split("{label}")
        return [
            key[len(prefix) : len(key) - len(suffix)]
            for key in keys
            if len(key) > len(prefix) + len(suffix)
            and key.startswith(prefix)
            and key.endswith(suffix)
        ]


class Findings(NamedTuple):
    """The delivered artifacts a study is checked and completed with."""

    site: Site
    zone: ZoneFindings
    notes: tuple[DocNotes, ...]
    """Every notes artifact present: the required labels in order, then the others by label."""
    envelope: EnvelopeStudy


def read_findings(artifacts: Mapping[str, ArtifactData], inputs: StudyInputs) -> Findings:
    """Read the site, the zone, every notes artifact and the envelope from the artifacts.

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
    envelope = read_artifact(artifacts, inputs.envelope.artifact, EnvelopeStudy)
    others = sorted(set(inputs.notes_labels(artifacts)) - set(inputs.labels))
    keys = {label: inputs.notes_key(label) for label in (*inputs.labels, *others)}
    notes = {label: read_artifact(artifacts, key, DocNotes) for label, key in keys.items()}
    deliveries = ((inputs.site, site), (inputs.zone, zone), (inputs.envelope, envelope))
    errors = [
        describe_missing_artifact(delivery.artifact, delivery.producer)
        for delivery, found in deliveries
        if found is None
    ]
    errors += [
        describe_missing_notes(keys[label], label, inputs.notes.producer)
        for label, found in notes.items()
        if found is None
    ]
    if errors or site is None or zone is None or envelope is None:
        raise SubmissionRejected(errors)
    found = tuple(doc_notes for doc_notes in notes.values() if doc_notes is not None)
    return Findings(site, zone, found, envelope)


def fold(question: str) -> str:
    """Fold case and whitespace, so that a copied question matches its original.

    Args:
        question: A question as written.

    Returns:
        The question lower-cased, on one line, with single spaces.
    """
    return " ".join(question.split()).casefold()


def unmatched_open_points(
    study: Study, sources: Mapping[str, Sequence[OpenPoint]]
) -> list[tuple[str, OpenPoint]]:
    """List the open points of the artifacts that no ambiguity of the study answers.

    An open point is answered by an ambiguity whose question is the same text, case and
    whitespace aside.

    Args:
        study: The submitted study.
        sources: The open points of each artifact, by artifact key (``notes.rules``,
            ``envelope``...).

    Returns:
        ``(artifact key, open point)`` pairs, in artifact and open point order.
    """
    answered = {fold(ambiguity.question) for ambiguity in study.ambiguities}
    return [
        (key, point)
        for key, points in sources.items()
        for point in points
        if fold(point.question) not in answered
    ]


def open_points(findings: Findings, inputs: StudyInputs) -> dict[str, tuple[OpenPoint, ...]]:
    """Gather the open points the study must answer: every notes artifact's and the envelope's.

    Args:
        findings: The delivered findings.
        inputs: Where each artifact is stored.

    Returns:
        The open points by artifact key.
    """
    points = {inputs.notes_key(notes.label): notes.open_points for notes in findings.notes}
    points[inputs.envelope.artifact] = findings.envelope.open_points
    return points


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
