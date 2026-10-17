from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from agent.contracts.base import Contract
from agent.contracts.evidence import Citation, SourceKind
from agent.contracts.geometry import Point, Polygon


class PublicParcel(Contract):
    """A neighbouring parcel you judge to be public land despite its cadastral number."""

    id: str = Field(min_length=1)
    """Cadastral id of a parcel lying along an edge of the site, e.g. `91272000CR0249`."""
    reason: str = Field(min_length=1)
    """The evidence: shape, size, position, and what the aerial photo shows."""


class ParcelChoice(Contract):
    """The cadastral parcels you chose as the site, and why."""

    address: str = Field(min_length=1)
    """The address label exactly as geocode returned it."""
    parcel_ids: tuple[str, ...] = Field(min_length=1)
    """Cadastral ids of the parcels forming the site, as returned by find_parcels
    (14 characters, e.g. `91272000CR0247`). Several ids must form one connected site."""
    rationale: str = Field(min_length=1)
    """Why these parcels: the evidence used, and the nearby candidates set aside with the reason
    for each."""
    assumptions: tuple[str, ...] = ()
    """Every choice a reviewer could dispute, one sentence each (e.g. that adjacent parcels form
    one landholding)."""
    public_parcels: tuple[PublicParcel, ...] = ()
    """Neighbouring parcels you judge to be public land (e.g. a thin strip of pavement or verge
    between the site and the road). An edge facing only such parcels faces public land."""


class EdgeSide(StrEnum):
    """What lies across an edge of the site."""

    PARCEL = "parcel"
    """Another cadastral parcel."""
    PUBLIC_LAND = "public_land"
    """Land without a parcel number, or parcels the surveyor declared public: usually a road or a
    public space."""


class Edge(Contract):
    """One edge of the site polygon's exterior ring, as a neutral fact (no legal label)."""

    start: Point
    end: Point
    length_m: float = Field(ge=0)
    other_side: EdgeSide
    neighbours: tuple[str, ...] = ()
    """Ids of the parcels across the edge; for public land, only parcels declared public."""


class Parcel(Contract):
    """A cadastral parcel."""

    id: str = Field(min_length=1)
    """Cadastral id: INSEE code, prefix, section and number, e.g. ``91272000AB0123``."""
    area_m2: float = Field(gt=0)
    """Area recorded in the cadastre (contenance)."""
    polygon: Polygon


class Site(Contract):
    """The land under study, built by code from a ``ParcelChoice``."""

    address: str = Field(min_length=1)
    """Address as normalised by the geocoder."""
    longitude: float
    """Geocoded point, WGS84."""
    latitude: float
    """Geocoded point, WGS84."""
    choice: ParcelChoice
    parcels: tuple[Parcel, ...] = Field(min_length=1)
    polygon: Polygon
    """Union of the parcels: the site the envelope is computed on."""
    area_m2: float = Field(gt=0)
    """Area of ``polygon``."""
    edges: tuple[Edge, ...] = Field(min_length=1)
    """Every edge of the polygon's exterior ring, in ring order."""
    citations: tuple[Citation, ...] = Field(min_length=1)
    """Geometric sources (geocoder, cadastre) backing the site."""

    @model_validator(mode="after")
    def _citations_geometric(self) -> Self:
        """Reject regulatory citations: the site rests on geometric data only."""
        if any(c.source_kind is not SourceKind.GEOMETRIC for c in self.citations):
            msg = "site citations must be geometric sources"
            raise ValueError(msg)
        return self
