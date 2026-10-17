from pydantic import Field

from agent.contracts.base import Contract
from agent.contracts.evidence import Citation
from agent.contracts.geometry import Boundary, Polygon


class Parcel(Contract):
    """A cadastral parcel."""

    id: str = Field(min_length=1)
    """Cadastral id: INSEE code, prefix, section and number, e.g. ``91272000AB0123``."""
    area_m2: float = Field(gt=0)
    """Area recorded in the cadastre (contenance)."""
    polygon: Polygon


class SiteContext(Contract):
    """The land under study: geocoded address, parcels and typed boundaries."""

    address: str = Field(min_length=1)
    """Address as normalised by the geocoder."""
    longitude: float
    """Geocoded point, WGS84."""
    latitude: float
    """Geocoded point, WGS84."""
    parcels: tuple[Parcel, ...] = Field(min_length=1)
    polygon: Polygon
    """Union of the parcels: the site the envelope is computed on."""
    area_m2: float = Field(gt=0)
    """Area of ``polygon``."""
    boundaries: tuple[Boundary, ...] = Field(min_length=1)
    """Every edge of the polygon's exterior ring, typed road / side / rear."""
    method: str = Field(min_length=1)
    """How the site was identified (geocoding, parcel selection, boundary typing)."""
    assumptions: tuple[str, ...] = ()
    citations: tuple[Citation, ...] = Field(min_length=1)
    """Geometric sources (geocoder, cadastre) backing the site."""
