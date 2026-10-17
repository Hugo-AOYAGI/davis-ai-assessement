from collections.abc import Mapping, Sequence

import shapely
from shapely.geometry.base import BaseGeometry

from agent.adapters.geo.cadastre import CadastralParcel
from agent.adapters.geo.geocoder import AddressCandidate
from agent.contracts.base import Contract
from agent.contracts.evidence import Citation, SourceKind
from agent.contracts.findings.site import Edge, EdgeSide
from agent.runtime.geometry.parcels import mean_width, shared_length, touching

type Located = tuple[CadastralParcel, BaseGeometry]
"""A cadastre record with its geometry in the metric CRS."""


class SurveySettings(Contract):
    """Knobs of the site surveyor."""

    crs: str
    """Metric CRS of the site geometry, e.g. ``EPSG:2154``."""
    geographic_crs: str
    """CRS of the services' coordinates, e.g. ``EPSG:4326``."""
    decimals: int
    """Decimals kept on the site's coordinates."""
    grid_size_m: float
    """Precision grid of the parcel union, in metres."""
    max_sliver_area_m2: float
    """Holes and parts below this area are dropped from the union."""
    neighbour_buffer_m: float
    """Distance around the site within which parcels are neighbours."""
    snap_tolerance_m: float
    """Distance within which two limits count as shared."""
    min_shared_ratio: float
    """Share of an edge that must lie on neighbours' limits to face a parcel."""
    geocoder_source: str
    """Source name cited for the geocoder record."""
    cadastre_source: str
    """Source name cited for the cadastre records."""


class SiteError(ValueError):
    """A parcel request the agent can fix (wrong label, unknown or disjoint parcels...).

    The message is written for the model: it says what is wrong and how to fix it.
    """


class ParcelFacts(Contract):
    """A cadastral parcel, with clues to tell a building plot from a strip."""

    id: str
    """Cadastral id (``idu``), e.g. ``91272000CR0247``."""
    contenance_m2: float | None
    """Legal area recorded in the cadastre, when known."""
    mean_width_m: float
    """Twice the area over the perimeter: about the width of a long thin parcel, so a value
    near or below one metre flags a strip rather than a building plot."""
    distance_m: float
    """Distance from the address point to the parcel, in metres (0 when it contains it)."""
    touches: tuple[str, ...]
    """Ids of the other parcels of the same listing adjacent to this one."""


class ParcelCandidate(ParcelFacts):
    """A cadastral parcel near an address point."""

    contains_point: bool
    """Whether the parcel contains the address point."""


class EdgeTotal(Contract):
    """Edges of a site's exterior facing one kind of land."""

    other_side: EdgeSide
    count: int
    length_m: float


class NeighbourFacts(Contract):
    """A parcel around a site."""

    id: str
    contenance_m2: float | None
    shared_length_m: float
    """Length of the site's exterior lying along this parcel."""
    mean_width_m: float


class ParcelsDescription(Contract):
    """Facts about a parcel selection, to judge whether it forms the site."""

    parcels: tuple[ParcelFacts, ...]
    one_piece: bool
    """Whether the selected parcels form one connected polygon."""
    part_areas_m2: tuple[float, ...] = ()
    """Area of each separate part when the selection is not one piece, else empty."""
    area_m2: float | None = None
    """Area of the union, when one piece."""
    distance_m: float | None = None
    """Distance from the address point to the union, when one piece."""
    edges: tuple[EdgeTotal, ...] = ()
    """Exterior edges grouped by what lies across them, when one piece."""
    neighbours: tuple[NeighbourFacts, ...] = ()
    """Parcels around the union, longest shared limit first, when one piece."""


def parcel_facts(
    located: Mapping[str, Located], point: shapely.Point, tolerance_m: float
) -> tuple[ParcelFacts, ...]:
    """Describe each parcel of a selection.

    Args:
        located: Selected parcels by id, geometries in a metric CRS.
        point: Address point, in the same CRS.
        tolerance_m: Largest gap between parcels that touch.

    Returns:
        One record per parcel, in the selection's order.
    """
    touches = touching({pid: shape for pid, (_, shape) in located.items()}, tolerance_m)
    return tuple(
        ParcelFacts(
            id=pid,
            contenance_m2=parcel.contenance_m2,
            mean_width_m=mean_width(shape),
            distance_m=float(shape.distance(point)),
            touches=touches[pid],
        )
        for pid, (parcel, shape) in located.items()
    )


def unique_ids(parcel_ids: Sequence[str]) -> list[str]:
    """Drop duplicate ids, keeping the order.

    Raises:
        SiteError: If no id is given.
    """
    unique = list(dict.fromkeys(parcel_ids))
    if not unique:
        msg = "no parcel id given: pass at least one cadastral id from find_parcels"
        raise SiteError(msg)
    return unique


def edge_totals(edges: Sequence[Edge]) -> tuple[EdgeTotal, ...]:
    """Count and measure a site's edges per kind of land across them.

    Args:
        edges: The site's edges.

    Returns:
        One total per ``EdgeSide``, in enumeration order.
    """
    return tuple(
        EdgeTotal(
            other_side=side,
            count=sum(1 for edge in edges if edge.other_side is side),
            length_m=sum(edge.length_m for edge in edges if edge.other_side is side),
        )
        for side in EdgeSide
    )


def neighbour_facts(
    neighbours: Mapping[str, Located], site: shapely.Polygon, tolerance_m: float
) -> tuple[NeighbourFacts, ...]:
    """Describe the parcels around a site, longest shared limit first.

    Args:
        neighbours: Neighbouring parcels by id, geometries in the site's metric CRS.
        site: The site polygon.
        tolerance_m: Distance within which the site's exterior lies along a neighbour.

    Returns:
        One record per neighbour.
    """
    records = [
        NeighbourFacts(
            id=parcel_id,
            contenance_m2=parcel.contenance_m2,
            shared_length_m=shared_length(site, shape, tolerance_m),
            mean_width_m=mean_width(shape),
        )
        for parcel_id, (parcel, shape) in neighbours.items()
    ]
    return tuple(sorted(records, key=lambda record: (-record.shared_length_m, record.id)))


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
