from pydantic import Field

from agent.contracts.base import Contract
from agent.contracts.evidence import Ambiguity, ImageRegion


class LegendItem(Contract):
    """One item of the zoning plan legend, checked against the site."""

    item: str = Field(min_length=1)
    """The legend label exactly as printed on the plan."""
    applies: bool
    """Whether the item affects the site; ``false`` records that it was checked and does not."""
    note: str = Field(min_length=1)
    """What you saw on the plan that supports ``applies``."""


class ZoneFindings(Contract):
    """What the zoning plan says about the site: its zone and the legend items affecting it."""

    zone: str = Field(min_length=1)
    """Zone code as printed on the plan, e.g. `UMG`."""
    overlays: tuple[LegendItem, ...] = Field(min_length=1)
    """One entry per legend item other than the zones, whether it applies or not."""
    rationale: str = Field(min_length=1)
    """How you found the site on the plan (landmarks, road layout, labels) and read its zone."""
    region: ImageRegion
    """The last region you zoomed on, holding the site: it is saved as the evidence crop."""
    ambiguities: tuple[Ambiguity, ...] = ()
    """Unclear readings, e.g. a zone boundary crossing the site."""
