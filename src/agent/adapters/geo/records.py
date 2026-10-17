from collections.abc import Mapping, Sequence

import shapely
from shapely.geometry.base import BaseGeometry

from agent.adapters.geo.cadastre import CadastralParcel
from agent.adapters.geo.geocoder import AddressCandidate
from agent.contracts.base import Contract
from agent.contracts.evidence import Citation, SourceKind
from agent.contracts.findings.site import Parcel
from agent.contracts.geometry import Boundary, Polygon

type Located = tuple[CadastralParcel, BaseGeometry]
"""A cadastre record with its geometry in the metric CRS."""


class SiteError(ValueError):
    """A site request the agent can fix (wrong label, unknown or disjoint parcels...).

    The message is written for the model: it says what is wrong and how to fix it.
    """


class ParcelCandidate(Contract):
    """A cadastral parcel near an address point, with clues to tell the plot from strips."""

    id: str
    """Cadastral id (``idu``), e.g. ``91272000CR0247``."""
    contenance_m2: float | None
    """Legal area recorded in the cadastre, when known."""
    distance_m: float
    """Distance from the address point to the parcel, in metres (0 when it contains it)."""
    contains_point: bool
    """Whether the parcel contains the address point."""
    mean_width_m: float
    """Twice the area over the perimeter: about the width of a long thin parcel, so a value
    near or below one metre flags a strip rather than a building plot."""
    touches: tuple[str, ...]
    """Ids of the other candidates adjacent to this one."""


class NeighbourParcel(Contract):
    """A parcel adjacent to the site."""

    id: str
    """Cadastral id (``idu``)."""
    contenance_m2: float | None
    """Legal area recorded in the cadastre, when known."""
    shared_length_m: float
    """Length of the site's exterior lying along this parcel, in metres."""
    mean_width_m: float
    """Twice the area over the perimeter; near or below one metre flags a strip."""
    public: bool
    """Whether the agent declared it public space (its limits with the site face the road)."""


class SiteDraft(Contract):
    """A site computed from an address and a parcel selection, before the agent submits it."""

    address: AddressCandidate
    """The geocoder record the address label matched."""
    parcels: tuple[Parcel, ...]
    """Selected parcels, polygons in the metric CRS."""
    polygon: Polygon
    """Union of the selected parcels, in the metric CRS."""
    area_m2: float
    """Area of ``polygon``."""
    boundaries: tuple[Boundary, ...]
    """Every edge of the polygon's exterior ring, typed road / side / rear."""
    nearest_boundary: Boundary
    """Edge of the exterior ring closest to the address point."""
    nearest_distance_m: float
    """Distance from the address point to ``nearest_boundary``, in metres."""
    neighbours: tuple[NeighbourParcel, ...]
    """Parcels adjacent to the site, public ones included."""
    citations: tuple[Citation, ...]
    """Geometric sources: the geocoder record, then one cadastre record per parcel used."""


def mean_width(shape: BaseGeometry) -> float:
    """Return twice the area over the perimeter: about the width of a long thin shape."""
    return 2 * float(shape.area) / float(shape.length) if shape.length else 0.0


def adjacent_ids(
    parcel_id: str, located: Mapping[str, Located], tolerance_m: float
) -> tuple[str, ...]:
    """Return the ids of the other parcels within ``tolerance_m`` of a parcel, sorted.

    Args:
        parcel_id: Id of the parcel, a key of ``located``.
        located: Parcels by id, geometries in a metric CRS.
        tolerance_m: Largest gap between adjacent parcels.

    Returns:
        The adjacent ids.
    """
    shape = located[parcel_id][1]
    return tuple(
        sorted(
            other_id
            for other_id, (_, other) in located.items()
            if other_id != parcel_id and shape.distance(other) <= tolerance_m
        )
    )


def neighbour_records(
    neighbours: Mapping[str, Located],
    exterior: BaseGeometry,
    public: Mapping[str, None],
    tolerance_m: float,
) -> tuple[NeighbourParcel, ...]:
    """Describe the neighbours of a site, longest shared limit first.

    Args:
        neighbours: Neighbouring parcels by id, geometries in the site's metric CRS.
        exterior: Exterior ring of the site.
        public: Ids declared public space.
        tolerance_m: Distance within which the site's exterior lies along a neighbour.

    Returns:
        One record per neighbour.
    """
    records = [
        NeighbourParcel(
            id=parcel_id,
            contenance_m2=parcel.contenance_m2,
            shared_length_m=float(exterior.intersection(shape.boundary.buffer(tolerance_m)).length),
            mean_width_m=mean_width(shape),
            public=parcel_id in public,
        )
        for parcel_id, (parcel, shape) in neighbours.items()
    ]
    return tuple(sorted(records, key=lambda record: (-record.shared_length_m, record.id)))


def nearest_boundary(
    boundaries: Sequence[Boundary], point: shapely.Point
) -> tuple[Boundary, float]:
    """Return the boundary closest to a point, and its distance.

    Args:
        boundaries: Typed edges of a site, at least one.
        point: Point in the same metric CRS.

    Returns:
        The nearest boundary and its distance in metres.
    """
    distances = [
        (float(shapely.LineString((b.start, b.end)).distance(point)), b) for b in boundaries
    ]
    distance, boundary = min(distances, key=lambda pair: pair[0])
    return boundary, distance


def address_citation(candidate: AddressCandidate, source: str) -> Citation:
    """Cite a geocoder record.

    Args:
        candidate: The geocoder match.
        source: Name of the geocoding service.

    Returns:
        A geometric citation quoting the record's label, key and coordinates.
    """
    quote = (
        f"label={candidate.label}; id={candidate.ban_id}; "
        f"lon={candidate.longitude}; lat={candidate.latitude}"
    )
    return Citation(doc=source, quote=quote, source_kind=SourceKind.GEOMETRIC)


def parcel_citation(parcel: CadastralParcel, source: str) -> Citation:
    """Cite a cadastre record.

    Args:
        parcel: The cadastral parcel.
        source: Name of the cadastre service.

    Returns:
        A geometric citation quoting the parcel id and its contenance.
    """
    quote = f"idu={parcel.id}; contenance={_format_area(parcel.contenance_m2)}"
    return Citation(doc=source, quote=quote, source_kind=SourceKind.GEOMETRIC)


def _format_area(area_m2: float | None) -> str:
    """Render a contenance as the cadastre states it (whole square metres when integral)."""
    if area_m2 is None:
        return "unknown"
    return str(int(area_m2)) if area_m2.is_integer() else str(area_m2)
