from collections.abc import Sequence
from functools import cache

import shapely
from pyproj import Transformer

from agent.contracts.geometry import Point, Polygon
from agent.runtime.georef.affine import AffineTransform

type Ring = tuple[Point, ...]


@cache
def _transformer(source: str, target: str) -> Transformer:
    """Build (once) a transformer taking and returning ``(x, y)`` / ``(lon, lat)`` order."""
    return Transformer.from_crs(source, target, always_xy=True)


def _reproject_ring(ring: Sequence[Point], transformer: Transformer) -> Ring:
    """Reproject the points of one ring."""
    xs, ys = transformer.transform([x for x, _ in ring], [y for _, y in ring])
    return tuple((float(x), float(y)) for x, y in zip(xs, ys, strict=True))


def to_crs(polygon: Polygon, crs: str) -> Polygon:
    """Reproject a polygon.

    Args:
        polygon: The polygon, in any CRS pyproj knows.
        crs: Target CRS, e.g. ``EPSG:2154``.

    Returns:
        The polygon in ``crs``; the same object when it is already there.
    """
    if polygon.crs == crs:
        return polygon
    transformer = _transformer(polygon.crs, crs)
    return Polygon(
        crs=crs,
        exterior=_reproject_ring(polygon.exterior, transformer),
        holes=tuple(_reproject_ring(hole, transformer) for hole in polygon.holes),
    )


def centroid(polygon: Polygon) -> Point:
    """Area centroid of a polygon, in its own CRS.

    Args:
        polygon: A polygon in a projected CRS.

    Returns:
        ``(x, y)`` of the centroid.
    """
    point = shapely.Polygon(polygon.exterior, polygon.holes).centroid
    return float(point.x), float(point.y)


def pixel_rings(polygon: Polygon, transform: AffineTransform, crs: str) -> tuple[Ring, ...]:
    """Project a polygon onto a georeferenced raster.

    Args:
        polygon: The polygon, in any CRS; it is reprojected to ``crs`` first if needed.
        transform: World to pixel transform of the raster.
        crs: CRS the transform expects.

    Returns:
        The exterior ring then the holes, as ``(column, row)`` at the raster's native size.
    """
    projected = to_crs(polygon, crs)
    return tuple(transform.to_pixel(ring) for ring in (projected.exterior, *projected.holes))
