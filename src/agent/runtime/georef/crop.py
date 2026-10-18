import math

import numpy as np
from shapely.geometry import MultiPolygon, Polygon

from agent.contracts.inputs.georeference import AffineMatrix
from agent.runtime.georef.affine import Points, apply
from agent.runtime.images.boxes import OverviewScale, PixelBox


class OffPlanError(ValueError):
    """The site does not lie on the plan page."""


def site_rings(site: Polygon | MultiPolygon, matrix: AffineMatrix) -> list[Points]:
    """Exterior and interior rings of a ground shape, mapped to plan pixels.

    Args:
        site: The site in ground coordinates (e.g. the union of its parcels).
        matrix: Ground to full-resolution plan pixel transform.

    Returns:
        One closed ring per boundary, shape ``(n, 2)`` each, in full-resolution pixels.
    """
    parts = site.geoms if isinstance(site, MultiPolygon) else (site,)
    rings = [ring for part in parts for ring in (part.exterior, *part.interiors)]
    return [apply(matrix, np.asarray(ring.coords)[:, :2]) for ring in rings]


def crop_region(rings: list[Points], margin_px: float, scale: OverviewScale) -> PixelBox:
    """Square overview region holding projected rings with a margin around them.

    The square is centred on the rings' bounding box, its half-side the box's longer half-side
    plus the margin, then rounded outwards to whole overview pixels and clipped to the page.

    Args:
        rings: Rings in full-resolution pixels (see :func:`site_rings`).
        margin_px: Margin on each side, in full-resolution pixels.
        scale: Full-resolution and overview sizes of the page.

    Returns:
        The region in overview coordinates.

    Raises:
        OffPlanError: If no ring point lies on the page or nothing of the square remains.
    """
    points = np.concatenate(rings)
    low, high = points.min(axis=0), points.max(axis=0)
    full_width, full_height = scale.full
    if high[0] < 0 or high[1] < 0 or low[0] > full_width or low[1] > full_height:
        msg = "the site lies outside the plan page"
        raise OffPlanError(msg)
    centre = (low + high) / 2
    half = float((high - low).max()) / 2 + margin_px
    ratio_x = scale.overview[0] / full_width
    ratio_y = scale.overview[1] / full_height
    x0 = max(0, math.floor((centre[0] - half) * ratio_x))
    y0 = max(0, math.floor((centre[1] - half) * ratio_y))
    x1 = min(scale.overview[0], math.ceil((centre[0] + half) * ratio_x))
    y1 = min(scale.overview[1], math.ceil((centre[1] + half) * ratio_y))
    if x1 <= x0 or y1 <= y0:
        msg = "the site lies outside the plan page"
        raise OffPlanError(msg)
    return PixelBox(x0=x0, y0=y0, x1=x1, y1=y1)
