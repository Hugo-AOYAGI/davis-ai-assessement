from typing import Self

from pydantic import Field, model_validator

from agent.contracts.base import Contract
from agent.contracts.evidence import Citation, ImageRegion

_LABEL = r"^[a-z][a-z0-9_]*$"


class Note(Contract):
    """What the documents say on one topic, faithfully restated and cited."""

    topic: str = Field(min_length=1)
    """One of the task's topics."""
    text: str = Field(min_length=1)
    """What the documents say, with conditions, exceptions and cross-references; no verdict
    of your own."""
    citations: tuple[Citation, ...] = Field(min_length=1)
    """Quotes copied exactly from the pages read; each is verified."""
    views: tuple[ImageRegion, ...] = ()
    """Diagram regions the note relies on, in view_image overview coordinates."""


class OpenPoint(Contract):
    """A question the documents leave open, for the orchestrator to settle."""

    question: str = Field(min_length=1)
    """The question, self-contained and precise: it is copied as is into the study."""
    options: tuple[str, ...] = ()
    """The plausible readings or answers."""
    why: str = Field(min_length=1)
    """Why the documents do not settle it."""
    citations: tuple[Citation, ...] = ()


class DocNotes(Contract):
    """Cited notes on what the documents say for the task's aim, and the points left open."""

    label: str = Field(pattern=_LABEL)
    """The task's label, copied from it (e.g. `rules`)."""
    topics: tuple[str, ...] = ()
    """The topic checklist of your task, copied from it; every topic needs at least one note."""
    notes: tuple[Note, ...] = Field(min_length=1)
    open_points: tuple[OpenPoint, ...] = ()

    @model_validator(mode="after")
    def _topics_covered(self) -> Self:
        """When topics are given, require a note per topic and no note outside them."""
        if not self.topics:
            return self
        noted = {note.topic for note in self.notes}
        missing = [topic for topic in self.topics if topic not in noted]
        extra = sorted(noted - set(self.topics))
        errors = [f"no note for topic '{topic}'" for topic in missing]
        errors += [f"topic '{topic}' is not in topics" for topic in extra]
        if errors:
            raise ValueError("; ".join(errors))
        return self
