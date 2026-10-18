from collections.abc import Iterable, Mapping, Sequence
from typing import cast

import shapely
from shapely import LineString
from shapely import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry, BaseMultipartGeometry

from agent.contracts.geometry import Boundary, BoundaryKind, Point, Polygon


def site_shape(polygon: Polygon) -> BaseGeometry:
    """Build the shapely geometry of the site, repaired when invalid.

    Args:
        polygon: The site polygon.

    Returns:
        A valid geometry covering it.
    """
    shape = ShapelyPolygon(polygon.exterior, polygon.holes)
    return shape if shape.is_valid else cast("BaseGeometry", shapely.make_valid(shape))


def set_back(
    site: BaseGeometry,
    boundaries: Sequence[Boundary],
    distances: Mapping[BoundaryKind, float],
    quad_segs: int,
) -> BaseGeometry:
    """Remove from the site every point closer to a boundary than its kind's distance.

    Args:
        site: The site geometry.
        boundaries: The site's edges labelled road / side / rear.
        distances: Distance kept from each kind of limit, in metres.
        quad_segs: Segments per quarter circle in the round buffers.

    Returns:
        What remains of the site.
    """
    # Round caps: a setback is a minimum distance to any point of the limit, ends included.
    buffers = [
        LineString([boundary.start, boundary.end]).buffer(
            distances[boundary.kind], quad_segs=quad_segs
        )
        for boundary in boundaries
        if distances[boundary.kind] > 0
    ]
    if not buffers:
        return site
    return cast("BaseGeometry", site.difference(shapely.union_all(buffers)))


def _polygons(geometry: BaseGeometry) -> list[ShapelyPolygon]:
    """Flatten a geometry into its polygons, dropping points and lines."""
    if isinstance(geometry, ShapelyPolygon):
        return [] if geometry.is_empty else [geometry]
    if isinstance(geometry, BaseMultipartGeometry):
        return [polygon for part in geometry.geoms for polygon in _polygons(part)]
    return []


def largest_part(geometry: BaseGeometry, min_area_m2: float) -> tuple[ShapelyPolygon | None, bool]:
    """Keep the largest polygon of a geometry, ignoring slivers.

    Args:
        geometry: Any geometry, possibly multi-part.
        min_area_m2: Parts smaller than this are slivers.

    Returns:
        The largest part (``None`` when only slivers remain), and whether other parts that are
        not slivers were left out.
    """
    parts = sorted(
        (part for part in _polygons(geometry) if part.area >= min_area_m2),
        key=lambda part: part.area,
        reverse=True,
    )
    if not parts:
        return None, False
    return parts[0], len(parts) > 1


def trim_area(polygon: ShapelyPolygon, target_m2: float, tolerance_m: float) -> BaseGeometry:
    """Keep at most a target area by clipping from the polygon's western side.

    Intersections preserve containment even for concave polygons and holes. Bisection retains
    the smaller side of the target; the positional tolerance can leave a small unused area.

    Args:
        polygon: The footprint to reduce.
        target_m2: Maximum area to retain.
        tolerance_m: Precision of the clipping line.

    Returns:
        The clipped geometry, possibly disconnected or empty.
    """
    if target_m2 <= 0:
        return ShapelyPolygon()
    if target_m2 >= polygon.area:
        return polygon
    x_min, y_min, x_max, y_max = polygon.bounds
    low, high = x_min, x_max
    while high - low > tolerance_m:
        middle = (low + high) / 2
        clipped = polygon.intersection(shapely.box(x_min, y_min, middle, y_max))
        low, high = (middle, high) if clipped.area <= target_m2 else (low, middle)
    return cast("BaseGeometry", polygon.intersection(shapely.box(x_min, y_min, low, y_max)))


def _ring(coords: Iterable[tuple[float, ...]]) -> tuple[Point, ...]:
    """Convert shapely ring coordinates to a closed tuple of points."""
    points = tuple((float(x), float(y)) for x, y, *_ in coords)
    return points if points[0] == points[-1] else (*points, points[0])


def to_contract(polygon: ShapelyPolygon | None, crs: str) -> Polygon | None:
    """Convert a shapely polygon to the contract polygon in the given CRS.

    Args:
        polygon: The polygon, or ``None``.
        crs: CRS identifier of its coordinates.

    Returns:
        The contract polygon, ``None`` for ``None``.
    """
    if polygon is None:
        return None
    return Polygon(
        crs=crs,
        exterior=_ring(polygon.exterior.coords),
        holes=tuple(_ring(interior.coords) for interior in polygon.interiors),
    )
