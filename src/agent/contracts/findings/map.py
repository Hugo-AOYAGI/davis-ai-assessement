from pydantic import Field

from agent.contracts.base import Contract
from agent.contracts.evidence import Ambiguity, Citation


class Overlay(Contract):
    """A plan feature checked against the site: protected element, risk area, reserved site..."""

    name: str = Field(min_length=1)
    """Legend label of the feature."""
    applies: bool
    """``False`` records that the feature was checked and does not affect the site."""
    rationale: str = Field(min_length=1)
    citations: tuple[Citation, ...] = ()


class MapFindings(Contract):
    """What the zoning plan says about the site."""

    zone: str = Field(min_length=1)
    """Zone code as printed on the plan, e.g. ``UMG``."""
    overlays: tuple[Overlay, ...]
    within_oap: bool | None
    """Whether the site lies inside an OAP perimeter drawn on the plan; ``None`` if unreadable."""
    rationale: str = Field(min_length=1)
    """How the site was located on the plan (landmarks, legend items)."""
    citations: tuple[Citation, ...] = Field(min_length=1)
    ambiguities: tuple[Ambiguity, ...] = ()
