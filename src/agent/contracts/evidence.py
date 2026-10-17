from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from agent.contracts.base import Contract


class SourceKind(StrEnum):
    """Whether a source may justify a regulatory conclusion."""

    REGULATORY = "regulatory"
    """A corpus document (regulatory text, zoning plan, OAP)."""
    GEOMETRIC = "geometric"
    """Public non-regulatory data used to locate the parcel (address geocoder, cadastre)."""


class Citation(Contract):
    """A verbatim excerpt supporting a claim."""

    doc: str = Field(min_length=1)
    """Corpus document id for regulatory sources, data source name for geometric ones."""
    page: int | None = Field(default=None, ge=1)
    """1-based PDF page index (not the printed page number). Required for regulatory sources."""
    article: str | None = None
    """Article or section reference, e.g. ``UMG 10`` or ``Lexique - Emprise au sol``."""
    quote: str = Field(min_length=1)
    """Text copied exactly from the page (or the data record). It is verified automatically."""
    source_kind: SourceKind

    @model_validator(mode="after")
    def _regulatory_has_page(self) -> Self:
        """Reject regulatory citations without a page, since they cannot be verified."""
        if self.source_kind is SourceKind.REGULATORY and self.page is None:
            msg = "a regulatory citation needs a page"
            raise ValueError(msg)
        return self


class CitationCheck(Contract):
    """Result of verifying one citation against the corpus."""

    citation: Citation
    verified: bool
    score: float = Field(ge=0, le=1)
    """Best similarity between the normalised quote and the page text."""
    matched_page: int | None = None
    """Page holding the best match, when it differs from the cited page."""
    text_verifiable: bool = True
    """False for a citation of a document without a text layer (a raster plan): its quote, a
    legend label, is not checked; ``verified`` is then False and ``score`` 0."""


class Rule(Contract):
    """A rule as stated in the documents, restated in free text."""

    topic: str = Field(min_length=1)
    """Short subject, e.g. ``access``, ``networks``, ``architecture``."""
    text: str = Field(min_length=1)
    """The rule restated faithfully, with its conditions and exceptions."""
    citations: tuple[Citation, ...] = Field(min_length=1)


class Limit(Contract):
    """A numeric limit drawn from a rule. The unit is given by the field holding it."""

    value: float | None
    """Resolved value, or ``None`` when the documents set no such limit."""
    rule: str = Field(min_length=1)
    """The rule the value comes from, including any formula or condition (e.g. ``H/2, min 4 m``)."""
    citations: tuple[Citation, ...] = ()

    @model_validator(mode="after")
    def _value_is_cited(self) -> Self:
        """Require a citation whenever a value is asserted."""
        if self.value is not None and not self.citations:
            msg = "a limit with a value needs at least one citation"
            raise ValueError(msg)
        return self


class Resolution(StrEnum):
    """Who settled an ambiguity."""

    USER = "user"
    """Answered by the user through ``ask_user``."""
    AGENT = "agent"
    """Chosen and justified by the agent."""


class Ambiguity(Contract):
    """A point the documents leave open, and how it was settled."""

    question: str = Field(min_length=1)
    options: tuple[str, ...] = ()
    """Interpretations that were considered."""
    chosen: str = Field(min_length=1)
    """The interpretation used in the study."""
    rationale: str = Field(min_length=1)
    resolved_by: Resolution
    citations: tuple[Citation, ...] = ()


type PixelBounds = tuple[int, int, int, int]
"""``(x0, y0, x1, y1)``: columns ``x0`` to ``x1`` and rows ``y0`` to ``y1``, end-exclusive."""


def _check_bounds(bounds: PixelBounds) -> None:
    """Reject boxes that are empty or start at a negative coordinate.

    Raises:
        ValueError: With a message stating the expected form.
    """
    x0, y0, x1, y1 = bounds
    if not (0 <= x0 < x1 and 0 <= y0 < y1):
        msg = f"[{x0}, {y0}, {x1}, {y1}] is not a box: it needs x1 > x0 >= 0 and y1 > y0 >= 0"
        raise ValueError(msg)


class ImageRegion(Contract):
    """A rectangle of a corpus page image, located on the page's view_image overview."""

    doc: str = Field(min_length=1)
    """Corpus document id, as listed by list_documents."""
    page: int = Field(ge=1)
    """1-based PDF page index (not the printed page number)."""
    region: PixelBounds
    """[x0, y0, x1, y1] in the pixel coordinates of the view_image overview, as read on its
    rulers (zoom images carry the same rulers)."""

    @model_validator(mode="after")
    def _region_is_box(self) -> Self:
        """Reject empty or negative regions."""
        _check_bounds(self.region)
        return self


class StoredCrop(Contract):
    """A page image region saved at full resolution as evidence."""

    region: ImageRegion
    """The region as given, in overview coordinates."""
    pixels: PixelBounds
    """[x0, y0, x1, y1] of the crop in the full-resolution page image."""
    path: str = Field(min_length=1)
    """PNG file, POSIX path relative to the project root."""

    @model_validator(mode="after")
    def _pixels_is_box(self) -> Self:
        """Reject empty or negative pixel boxes."""
        _check_bounds(self.pixels)
        return self
