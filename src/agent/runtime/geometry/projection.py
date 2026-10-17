from functools import cache
from typing import cast

import shapely
from pyproj import Transformer
from shapely.geometry.base import BaseGeometry


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
