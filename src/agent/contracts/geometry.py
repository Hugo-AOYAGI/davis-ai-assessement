from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from agent.contracts.base import Contract

type Point = tuple[FiniteFloat, FiniteFloat]
type Ring = Annotated[tuple[Point, ...], Field(min_length=4)]


class Polygon(Contract):
    """A planar polygon in a projected CRS whose unit is the metre."""

    crs: str = Field(min_length=1)
    """CRS identifier, e.g. ``EPSG:2154``."""
    exterior: Ring
    """Closed ring: the first and last points are equal."""
    holes: tuple[Ring, ...] = ()

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


class Level(Contract):
    """One horizontal slice of a building's massing."""

    from_m: float = Field(ge=0)
    to_m: float = Field(gt=0)
    area_m2: float = Field(ge=0)
    """Floor area of the slice: the allowed footprint at its top."""

    @model_validator(mode="after")
    def _rises(self) -> Self:
        """Reject a slice whose top is not above its bottom."""
        if self.to_m <= self.from_m:
            msg = "a level's to_m must be above its from_m"
            raise ValueError(msg)
        return self


class BuildingMassing(Contract):
    """One building's allowed volume, computed by code."""

    building: str = Field(min_length=1)
    """Building label; in a bound, the labels sharing one maximum height, comma-separated."""
    footprint: Polygon | None
    """Its ground footprint; ``None`` when nothing remains for it."""
    footprint_area_m2: float = Field(ge=0)
    """Ground area, after any cap scaling."""
    max_height_m: float = Field(gt=0)
    levels: tuple[Level, ...]
    """One slice for a prism, several when setbacks grow with the height."""
    volume_m3: float = Field(ge=0)


class Scenario(Contract):
    """The massing of the buildings in one scenario."""

    name: Literal["largest", "windows", "proposal"]
    footprint: Polygon | None
    """The plot minus the setbacks at ground level; ``None`` when nothing remains."""
    footprint_area_m2: float = Field(ge=0)
    """Area of ``footprint``, before any cap."""
    buildings: tuple[BuildingMassing, ...]
    fits: bool
    """Whether every building has room, with the required spacing."""
    total_volume_m3: float = Field(ge=0)
    """Sum of the buildings' volumes; in a bound, the largest alternative."""
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    """Why the buildings do not fit, when they do not."""
