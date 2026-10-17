import math
from collections.abc import Sequence
from itertools import pairwise
from typing import cast

import shapely
from shapely.geometry.base import BaseGeometry

from agent.contracts.geometry import Boundary, BoundaryKind, Point, Polygon
from agent.runtime.geometry.parcels import to_shape

type _Edge = tuple[Point, Point]


def classify_boundaries(
    site: Polygon,
    neighbours: Sequence[BaseGeometry],
    snap_tolerance_m: float,
    min_shared_ratio: float,
    collinear_angle_deg: float,
) -> tuple[Boundary, ...]:
    """Type each edge of the site's exterior ring as a road, side or rear limit.

    An edge shared with a neighbouring parcel is a separating limit; every other edge faces the
    road. Consecutive, nearly collinear separating edges form one limit (cadastral limits are
    often split into several segments). A separating limit is a side limit when it meets a road
    edge at either end, a rear limit otherwise.

    Args:
        site: Site polygon, in the same metric CRS as ``neighbours``.
        neighbours: Parcels around the site, the site's own parcels excluded. A neighbour lying
            mostly inside the site is ignored.
        snap_tolerance_m: Distance within which an edge counts as lying on a neighbour's limit;
            edges shorter than this never split a limit.
        min_shared_ratio: Share of an edge's length that must lie on a neighbour's limit for the
            edge to be a separating limit.
        collinear_angle_deg: Largest direction change between consecutive separating edges of
            the same limit.

    Returns:
        One boundary per edge of the exterior ring, in ring order; ``start`` and ``end`` are the
        ring's vertices.
    """
    edges = tuple(pairwise(site.exterior))
    shared = _shared_edges(to_shape(site), edges, neighbours, snap_tolerance_m, min_shared_ratio)
    kinds = _edge_kinds(edges, shared, snap_tolerance_m, collinear_angle_deg)
    return tuple(
        Boundary(kind=kind, start=start, end=end)
        for (start, end), kind in zip(edges, kinds, strict=True)
    )


def _shared_edges(
    site: shapely.Polygon,
    edges: Sequence[_Edge],
    neighbours: Sequence[BaseGeometry],
    tolerance_m: float,
    min_ratio: float,
) -> list[bool]:
    """Flag the edges lying on a neighbour's limit over at least ``min_ratio`` of their length."""
    limits = [_outline(n) for n in neighbours if not _is_mostly_site(n, site)]
    if not limits:
        return [False] * len(edges)
    zone = shapely.union_all(limits).buffer(tolerance_m)
    return [_shared_ratio(shapely.LineString(edge), zone) >= min_ratio for edge in edges]


def _is_mostly_site(neighbour: BaseGeometry, site: shapely.Polygon) -> bool:
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


def _edge_kinds(
    edges: Sequence[_Edge], shared: Sequence[bool], tolerance_m: float, max_turn_deg: float
) -> list[BoundaryKind]:
    """Assign a kind to each edge from the shared flags."""
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
    """Group consecutive shared edges, in cyclic ring order, between road edges.

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
    run: Sequence[int], edges: Sequence[_Edge], tolerance_m: float, max_turn_deg: float
) -> list[list[int]]:
    """Split a run of separating edges into limits at each change of direction."""
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


def _vector(edge: _Edge) -> Point:
    """Return the vector from the edge's start to its end."""
    (x0, y0), (x1, y1) = edge
    return (x1 - x0, y1 - y0)


def _turn_deg(first: Point, second: Point) -> float:
    """Return the absolute angle between two vectors, in degrees."""
    cross = first[0] * second[1] - first[1] * second[0]
    dot = first[0] * second[0] + first[1] * second[1]
    return abs(math.degrees(math.atan2(cross, dot)))
