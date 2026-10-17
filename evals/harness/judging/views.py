"""What the judge reads of an output, rendered compactly per level (``docs/EVALS.md`` §4).

- zoning: the zone, every legend item checked, the rationale and the ambiguities;
- doc: the numbered notes and the open points (citations are checked in code, not by the judge);
- e2e: the study's Markdown report, as an architect reads it, with its citations table.
"""

from collections.abc import Sequence

from agent.contracts.base import Contract
from agent.contracts.evidence import Ambiguity
from agent.contracts.findings.notes import DocNotes, OpenPoint
from agent.contracts.findings.zone import ZoneFindings
from agent.contracts.study import VerifiedStudy
from agent.runtime.report.render import render_report

_NONE = "none"
_OPTIONS = " | "


class ViewSettings(Contract):
    """How a study is rendered for the judge (``eval.judge.views``)."""

    max_quote_chars: int
    """Quotes are cut beyond this length in the report's citations table."""
    crops_link_base: str
    """Directory the report links evidence crops from (the judge does not open them)."""


def zone_view(zone: ZoneFindings) -> str:
    """Render zoning findings: zone, legend items, rationale, ambiguities.

    Args:
        zone: The zoning analyst's findings.

    Returns:
        Plain text.
    """
    items = [
        f"- [{'applies' if item.applies else 'does not apply'}] {item.item}: {item.note}"
        for item in zone.overlays
    ]
    return "\n".join(
        (
            f"Zone: {zone.zone}",
            "Legend items:",
            *items,
            f"Rationale: {zone.rationale}",
            "Ambiguities:",
            *_ambiguities(zone.ambiguities),
        )
    )


def numbered_notes(notes: DocNotes) -> str:
    """Render the notes alone, numbered from 1, for the ``covers`` question.

    Args:
        notes: A doc analyst's notes.

    Returns:
        One ``[n] (topic) text`` paragraph per note, in order.
    """
    return "\n\n".join(
        f"[{number}] ({note.topic}) {note.text}" for number, note in enumerate(notes.notes, start=1)
    )


def notes_view(notes: DocNotes) -> str:
    """Render the notes and the open points.

    Args:
        notes: A doc analyst's notes.

    Returns:
        Plain text.
    """
    return "\n\n".join(
        (
            f"Notes ({notes.label}):",
            numbered_notes(notes),
            "Open points:",
            "\n".join(_open_points(notes.open_points)) or _NONE,
        )
    )


def study_view(verified: VerifiedStudy, settings: ViewSettings) -> str:
    """Render an accepted study as its Markdown report.

    Args:
        verified: The accepted study.
        settings: Report settings.

    Returns:
        The report.
    """
    return render_report(
        verified,
        max_quote_chars=settings.max_quote_chars,
        crops_link_base=settings.crops_link_base,
    )


def _ambiguities(ambiguities: Sequence[Ambiguity]) -> list[str]:
    """One line per ambiguity: question, options, choice and rationale."""
    if not ambiguities:
        return [f"- {_NONE}"]
    return [
        f"- {a.question} (options: {_OPTIONS.join(a.options) or _NONE}) "
        f"chosen: {a.chosen}; rationale: {a.rationale}"
        for a in ambiguities
    ]


def _open_points(points: Sequence[OpenPoint]) -> list[str]:
    """One line per open point: question, options and why it is open."""
    return [
        f"- {point.question} (options: {_OPTIONS.join(point.options) or _NONE}) why: {point.why}"
        for point in points
    ]
