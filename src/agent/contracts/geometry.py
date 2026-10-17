from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from agent.contracts.base import Contract
from agent.contracts.evidence import Limit

type Point = tuple[float, float]


class Polygon(Contract):
    """A planar polygon in a projected CRS whose unit is the metre."""

    crs: str = Field(min_length=1)
    """CRS identifier, e.g. ``EPSG:2154``."""
    exterior: tuple[Point, ...] = Field(min_length=4)
    """Closed ring: the first and last points are equal."""
    holes: tuple[tuple[Point, ...], ...] = ()

    @model_validator(mode="after")
    def _rings_closed(self) -> Self:
        """Reject rings whose first and last points differ."""
        for ring in (self.exterior, *self.holes):
            if ring[0] != ring[-1]:
                msg = "polygon rings must be closed"
                raise ValueError(msg)
        return self


class BoundaryKind(StrEnum):
    """Type of a parcel limit, which selects the applicable setback rule."""

    ROAD = "road"
    """Along a public or private road or public space (alignement)."""
    SIDE = "side"
    """Separating limit that meets the road (limite séparative latérale)."""
    REAR = "rear"
    """Separating limit that does not meet the road (fond de parcelle)."""


class Boundary(Contract):
    """One edge of the site polygon's exterior ring, with its type."""

    kind: BoundaryKind
    start: Point
    end: Point


class EnvelopeParameters(Contract):
    """Rule values the envelope is computed from. Distances in metres, ratios in [0, 1]."""

    setback_road_m: Limit
    """Minimum distance from road limits."""
    setback_side_m: Limit
    """Minimum distance from side limits."""
    setback_rear_m: Limit
    """Minimum distance from rear limits."""
    max_height_m: Limit
    """Maximum building height, measured as the zone regulation defines it."""
    max_storeys: Limit
    """Maximum number of storeys above ground, ground floor included (R+5 = 6)."""
    max_footprint_ratio: Limit
    """Maximum built footprint as a share of the site area (emprise au sol)."""
    min_green_ratio: Limit
    """Minimum green or open space as a share of the site area."""

    @model_validator(mode="after")
    def _ratios_in_range(self) -> Self:
        """Reject ratios outside [0, 1]."""
        for limit in (self.max_footprint_ratio, self.min_green_ratio):
            if limit.value is not None and not 0 <= limit.value <= 1:
                msg = "ratios must be between 0 and 1"
                raise ValueError(msg)
        return self


class Envelope(Contract):
    """Prism envelope computed by deterministic code from the site and the parameters."""

    site_area_m2: float = Field(gt=0)
    footprint: Polygon | None
    """Site polygon minus setbacks; ``None`` when nothing remains."""
    footprint_area_m2: float = Field(ge=0)
    """Area of ``footprint``."""
    max_footprint_area_m2: float = Field(ge=0)
    """Smaller of ``footprint_area_m2`` and the footprint ratio applied to the site area."""
    min_green_area_m2: float | None = Field(ge=0)
    max_height_m: float | None = Field(gt=0)
    max_volume_m3: float | None = Field(ge=0)
    """``max_footprint_area_m2`` x ``max_height_m``; ``None`` without a height limit."""
    assumptions: tuple[str, ...] = ()
