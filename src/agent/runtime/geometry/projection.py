from collections.abc import Iterable
from functools import cache
from typing import cast

import shapely
from pyproj import Transformer
from shapely.geometry.base import BaseGeometry

type Bounds = tuple[float, float, float, float]
"""Axis-aligned box ``(min_x, min_y, max_x, max_y)`` in a metric CRS."""


@cache
def _transformer(source_crs: str, target_crs: str) -> Transformer:
    """Return the transformer for a CRS pair, built once (construction is costly).

    ``always_xy`` keeps the x/y order (longitude/latitude for geographic CRS) whatever the
    axis order declared by the CRS.
    """
    return Transformer.from_crs(source_crs, target_crs, always_xy=True)


def to_crs[G: BaseGeometry](geometry: G, source_crs: str, target_crs: str) -> G:
    """Reproject a geometry, keeping its type.

    Args:
        geometry: Geometry whose coordinates are x/y (longitude/latitude) in ``source_crs``.
        source_crs: CRS of the input, e.g. ``EPSG:4326``.
        target_crs: CRS of the output, e.g. ``EPSG:2154``.

    Returns:
        The same geometry with coordinates expressed in ``target_crs``.
    """
    transformer = _transformer(source_crs, target_crs)
    return cast("G", shapely.transform(geometry, transformer.transform, interleaved=False))


def square_around(centre: tuple[float, float], half_width_m: float) -> Bounds:
    """Return the square of half-side ``half_width_m`` centred on a point.

    Args:
        centre: Centre ``(x, y)`` in a metric CRS.
        half_width_m: Half the side of the square, in metres.

    Returns:
        The square's bounds.
    """
    x, y = centre
    return (x - half_width_m, y - half_width_m, x + half_width_m, y + half_width_m)


def fit_half_width(bounds: Bounds, margin_ratio: float, min_half_width_m: float) -> float:
    """Return the half-side of a square holding ``bounds`` with a margin around it.

    Args:
        bounds: Box to show.
        margin_ratio: Margin added on each side, as a share of the box's longer side.
        min_half_width_m: Smallest half-side returned.

    Returns:
        The half-side, in metres.
    """
    min_x, min_y, max_x, max_y = bounds
    side = max(max_x - min_x, max_y - min_y)
    return max(side / 2 + margin_ratio * side, min_half_width_m)


def to_pixels(
    points: Iterable[tuple[float, float]], bounds: Bounds, size_px: tuple[int, int]
) -> list[tuple[float, float]]:
    """Map metric points to pixel positions of an image covering ``bounds``, north up.

    Args:
        points: Points ``(x, y)`` in the metric CRS of ``bounds``.
        bounds: Ground box the image covers.
        size_px: Image ``(width, height)`` in pixels.

    Returns:
        Pixel ``(column, row)`` positions, origin at the top-left corner.
    """
    min_x, min_y, max_x, max_y = bounds
    width, height = size_px
    scale_x, scale_y = width / (max_x - min_x), height / (max_y - min_y)
    return [((x - min_x) * scale_x, (max_y - y) * scale_y) for x, y in points]
