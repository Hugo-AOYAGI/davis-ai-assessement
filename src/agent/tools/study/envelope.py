"""The ``submit_study`` gate's checks of the architect's ``envelope`` artifact."""

from collections.abc import Iterable

from pydantic import BaseModel

from agent.contracts.base import Contract
from agent.contracts.envelope import EnvelopeStudy, layout_errors
from agent.contracts.evidence import Citation
from agent.contracts.findings.notes import DocNotes
from agent.contracts.study import Study
from agent.runtime.citations.collect import collect_citations
from agent.runtime.citations.normalise import normalise
from agent.tools.study.inputs import Findings, StudyInputs
from agent.tools.study.messages import source

type _Key = tuple[str, int | None, str]


class EnvelopeCitations(Contract):
    """Wraps the envelope so that its citation paths read ``envelope.<field>``."""

    envelope: EnvelopeStudy


def envelope_errors(study: Study, findings: Findings, inputs: StudyInputs) -> list[str]:
    """Check the envelope against the notes and the study.

    Every citation of the envelope rules must be one of a notes artifact's (any label: `rules`,
    `destinations`, or a label re-asked such as `rules_parking`), every citation of the layout's
    OAP choices one of the ``oap`` notes (same document, page and quote, compared after
    normalisation). The layout must name the buildings of the rules, each no taller than its
    maximum, and the rules' buildings must be those of the study's admissibility.

    Args:
        study: The submitted study.
        findings: The delivered findings, with the envelope.
        inputs: Where the notes are stored, the producers and the label of the OAP notes.

    Returns:
        One ``field.path: message`` line per problem, empty when the envelope is consistent.
    """
    envelope = findings.envelope
    producer = inputs.envelope.producer
    every_key = f"a `{inputs.notes_key('<label>')}` artifact"
    oap_key = f"`{inputs.notes_key(inputs.oap_label)}`"
    oap = [notes for notes in findings.notes if notes.label == inputs.oap_label]
    errors = _foreign("envelope.rules", envelope.rules, findings.notes, every_key, producer)
    errors += _foreign("envelope.layout", envelope.layout, oap, oap_key, producer)
    errors += [
        f"envelope.{line}. Delegate to {producer} again with the buildings' maximum heights."
        for line in layout_errors(envelope.rules, envelope.layout)
    ]
    errors += _building_errors(study, envelope, producer)
    return errors


def _key(citation: Citation) -> _Key:
    """Return what two citations must share to count as the same: document, page, quote."""
    return citation.doc, citation.page, normalise(citation.quote)


def _foreign(
    prefix: str, part: BaseModel, notes: Iterable[DocNotes], key: str, producer: str
) -> list[str]:
    """List the citations of a part of the envelope that the notes do not hold.

    ``key`` names the notes in the message, e.g. ``a `notes.<label>` artifact``.
    """
    allowed = {
        _key(citation) for doc_notes in notes for _, citation in collect_citations(doc_notes)
    }
    return [
        f"{prefix}.{path} ({source(citation)}): not a citation of {key}. Delegate to "
        f"{producer} again: every citation must be copied exactly from {key}."
        for path, citation in collect_citations(part)
        if _key(citation) not in allowed
    ]


def _labels(labels: Iterable[str]) -> str:
    """Render labels for a message."""
    return ", ".join(f"{label!r}" for label in labels) or "none"


def _building_errors(study: Study, envelope: EnvelopeStudy, producer: str) -> list[str]:
    """Require the envelope's buildings to be the study's admissibility buildings."""
    studied = [entry.building for entry in study.admissibility]
    limited = [limits.building for limits in envelope.rules.buildings]
    if sorted(studied) == sorted(limited):
        return []
    return [
        f"envelope.rules.buildings: buildings {_labels(limited)} do not match admissibility "
        f"buildings {_labels(studied)}. Use the same labels in admissibility and in the task "
        f"given to {producer}, one entry per building, and delegate to {producer} again if its "
        "labels must change."
    ]
