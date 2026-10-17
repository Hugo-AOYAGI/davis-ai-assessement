import math
from collections.abc import Mapping, Sequence, Set
from itertools import pairwise
from typing import cast

import shapely
from shapely.geometry.base import BaseGeometry
from shapely.ops import substring

from agent.contracts.findings.site import Edge, EdgeSide
from agent.contracts.geometry import Boundary, BoundaryKind, Point, Polygon
from agent.runtime.geometry.parcels import to_shape


def site_edges(
    polygon: Polygon,
    neighbours: Mapping[str, BaseGeometry],
    *,
    snap_tolerance_m: float,
    min_shared_ratio: float,
    public: Set[str] = frozenset(),
) -> tuple[Edge, ...]:
    """Describe each edge of the site's exterior ring by what lies across it.

    An edge lying on the neighbours' limits over at least ``min_shared_ratio`` of its length
    faces a parcel, unless every neighbour listed along it is declared public; every other edge
    faces public land. A neighbour lying mostly inside the site is ignored.

    Args:
        polygon: Site polygon, in the same metric CRS as ``neighbours``.
        neighbours: Parcels around the site by id, the site's own parcels excluded.
        snap_tolerance_m: Distance within which an edge counts as lying on a neighbour's limit.
        min_shared_ratio: Share of an edge's length that must lie on neighbours' limits for the
            edge to face a parcel.
        public: Ids of neighbours the surveyor declared public land.

    Returns:
        One edge per segment of the exterior ring, in ring order. An edge lying on neighbours'
        limits lists the neighbours whose limit runs along it away from its ends (a neighbour
        only touching a corner is not listed), declared public ones included.
    """
    site = to_shape(polygon)
    zones = {
        parcel_id: _outline(shape).buffer(snap_tolerance_m)
        for parcel_id, shape in sorted(neighbours.items())
        if not _is_mostly_site(shape, site)
    }
    union = shapely.union_all(list(zones.values())) if zones else None
    edges = []
    for start, end in pairwise(polygon.exterior):
        line = shapely.LineString([start, end])
        shared = union is not None and _shared_ratio(line, union) >= min_shared_ratio
        across = _across(line, zones, snap_tolerance_m) if shared else ()
        facing_parcel = shared and not (across and set(across) <= public)
        edges.append(
            Edge(
                start=start,
                end=end,
                length_m=float(line.length),
                other_side=EdgeSide.PARCEL if facing_parcel else EdgeSide.PUBLIC_LAND,
                neighbours=across,
            )
        )
    return tuple(edges)


def label_edges(
    edges: Sequence[Edge], *, snap_tolerance_m: float, collinear_angle_deg: float
) -> tuple[Boundary, ...]:
    """Label each edge as a road, side or rear limit.

    Public land is road. Consecutive, nearly collinear parcel edges form one limit (cadastral
    limits are often split into several segments). A limit meeting a road edge at either end is a
    side limit, otherwise a rear limit. A ring of parcel edges only is all rear; a ring without
    parcel edges is all road.

    Args:
        edges: The site's edges, in ring order.
        snap_tolerance_m: Edges shorter than this never split a limit.
        collinear_angle_deg: Largest direction change between consecutive parcel edges of the
            same limit.

    Returns:
        One boundary per edge, in the same order.
    """
    segments = [(edge.start, edge.end) for edge in edges]
    shared = [edge.other_side is EdgeSide.PARCEL for edge in edges]
    kinds = _edge_kinds(segments, shared, snap_tolerance_m, collinear_angle_deg)
    return tuple(
        Boundary(kind=kind, start=start, end=end)
        for (start, end), kind in zip(segments, kinds, strict=True)
    )


def _is_mostly_site(neighbour: BaseGeometry, site: BaseGeometry) -> bool:
    """Tell whether more than half of the neighbour's area lies inside the site."""
    area = float(neighbour.area)
    overlap = float(neighbour.intersection(site).area)
    return area > 0 and 2 * overlap > area


def _outline(neighbour: BaseGeometry) -> BaseGeometry:
    """Return the limit of an areal neighbour, or the neighbour itself if it is a line."""
    if neighbour.area > 0:
        return cast("BaseGeometry", neighbour.boundary)
    return neighbour


def _shared_ratio(edge: shapely.LineString, zone: BaseGeometry) -> float:
    """Return the share of the edge's length inside ``zone`` (0 or 1 for a degenerate edge)."""
    if edge.length == 0:
        return float(edge.intersects(zone))
    return float(edge.intersection(zone).length) / float(edge.length)


def _across(
    edge: shapely.LineString, zones: Mapping[str, BaseGeometry], tolerance_m: float
) -> tuple[str, ...]:
    """List the neighbours whose limit runs along the edge, its end zones left out."""
    length = float(edge.length)
    if length > 2 * tolerance_m:
        inner = cast("BaseGeometry", substring(edge, tolerance_m, length - tolerance_m))
        return tuple(
            parcel_id
            for parcel_id, zone in zones.items()
            if float(inner.intersection(zone).length) > 0
        )
    middle = edge.interpolate(0.5, normalized=True)
    return tuple(parcel_id for parcel_id, zone in zones.items() if zone.intersects(middle))


def _edge_kinds(
    edges: Sequence[tuple[Point, Point]],
    shared: Sequence[bool],
    tolerance_m: float,
    max_turn_deg: float,
) -> list[BoundaryKind]:
    """Assign a kind to each edge from the parcel flags."""
    count = len(edges)
    if not any(shared):
        return [BoundaryKind.ROAD] * count
    if all(shared):
        return [BoundaryKind.REAR] * count
    kinds = [BoundaryKind.ROAD] * count
    for run in _separating_runs(shared):
        limits = _split_limits(run, edges, tolerance_m, max_turn_deg)
        for position, limit in enumerate(limits):
            touches_road = position in {0, len(limits) - 1}
            for index in limit:
                kinds[index] = BoundaryKind.SIDE if touches_road else BoundaryKind.REAR
    return kinds


def _separating_runs(shared: Sequence[bool]) -> list[list[int]]:
    """Group consecutive parcel edges, in cyclic ring order, between road edges.

    The walk starts just after a road edge so that no run wraps around the ring end; each run is
    therefore bounded by road edges on both sides. Requires at least one road edge.
    """
    count = len(shared)
    start = shared.index(False) + 1
    runs: list[list[int]] = []
    current: list[int] = []
    for offset in range(count):
        index = (start + offset) % count
        if shared[index]:
            current.append(index)
        elif current:
            runs.append(current)
            current = []
    return runs


def _split_limits(
    run: Sequence[int],
    edges: Sequence[tuple[Point, Point]],
    tolerance_m: float,
    max_turn_deg: float,
) -> list[list[int]]:
    """Split a run of parcel edges into limits at each change of direction."""
    limits: list[list[int]] = [[]]
    reference: Point | None = None
    for index in run:
        direction = _vector(edges[index])
        if math.hypot(*direction) >= tolerance_m:
            if reference is not None and _turn_deg(reference, direction) > max_turn_deg:
                limits.append([])
            reference = direction
        limits[-1].append(index)
    return limits


def _vector(edge: tuple[Point, Point]) -> Point:
    """Return the vector from the edge's start to its end."""
    (x0, y0), (x1, y1) = edge
    return (x1 - x0, y1 - y0)


def _turn_deg(first: Point, second: Point) -> float:
    """Return the absolute angle between two vectors, in degrees."""
    cross = first[0] * second[1] - first[1] * second[0]
    dot = first[0] * second[0] + first[1] * second[1]
    return abs(math.degrees(math.atan2(cross, dot)))
