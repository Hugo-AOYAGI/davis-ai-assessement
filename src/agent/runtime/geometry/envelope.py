from collections.abc import Iterable, Mapping
from typing import cast

import shapely
from shapely import LineString
from shapely import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry, BaseMultipartGeometry

from agent.contracts.evidence import Limit
from agent.contracts.findings.site import SiteContext
from agent.contracts.geometry import (
    Boundary,
    BoundaryKind,
    Envelope,
    EnvelopeParameters,
    Point,
    Polygon,
)


def compute_envelope(
    site: SiteContext, parameters: EnvelopeParameters, *, quad_segs: int, min_area_m2: float
) -> Envelope:
    """Compute the prism envelope: the site minus its setbacks, capped by the ratios and height.

    Each boundary is set back by the distance of its kind (road, side, rear). A limit whose value
    is ``None`` is treated as absent (no setback, no cap) and recorded in ``assumptions``.

    Args:
        site: The site, with its polygon and typed boundaries.
        parameters: Rule values the envelope is computed from.
        quad_segs: Segments per quarter circle in the round setback buffers.
        min_area_m2: Footprint parts smaller than this are discarded as slivers.

    Returns:
        The envelope, with every assumption made while computing it.
    """
    site_shape = _site_shape(site.polygon)
    site_area = float(site_shape.area)
    setbacks, setback_notes = _setbacks(parameters)
    remaining = _set_back(site_shape, site.boundaries, setbacks, quad_segs)
    footprint, part_notes = _largest_part(remaining, min_area_m2)
    footprint_area = 0.0 if footprint is None else float(footprint.area)
    max_footprint, ratio_notes = _max_footprint(
        parameters.max_footprint_ratio, site_area, footprint_area
    )
    min_green, green_notes = _min_green(parameters.min_green_ratio, site_area, max_footprint)
    max_height, max_volume, height_notes = _height(parameters.max_height_m, max_footprint)
    return Envelope(
        site_area_m2=site_area,
        footprint=None if footprint is None else _to_contract(footprint, site.polygon.crs),
        footprint_area_m2=footprint_area,
        max_footprint_area_m2=max_footprint,
        min_green_area_m2=min_green,
        max_height_m=max_height,
        max_volume_m3=max_volume,
        assumptions=(
            *setback_notes,
            *part_notes,
            *ratio_notes,
            *green_notes,
            *height_notes,
        ),
    )


def _site_shape(polygon: Polygon) -> BaseGeometry:
    """Build the shapely geometry of the site, repaired when invalid."""
    shape = ShapelyPolygon(polygon.exterior, polygon.holes)
    return shape if shape.is_valid else cast("BaseGeometry", shapely.make_valid(shape))


def _setbacks(parameters: EnvelopeParameters) -> tuple[dict[BoundaryKind, float], list[str]]:
    """Resolve the setback distance of each boundary kind, missing ones counting as zero."""
    limits = {
        BoundaryKind.ROAD: parameters.setback_road_m,
        BoundaryKind.SIDE: parameters.setback_side_m,
        BoundaryKind.REAR: parameters.setback_rear_m,
    }
    notes = [
        f"No {kind} setback set: {kind} limits not set back."
        for kind, limit in limits.items()
        if limit.value is None
    ]
    return {kind: limit.value or 0.0 for kind, limit in limits.items()}, notes


def _set_back(
    site_shape: BaseGeometry,
    boundaries: Iterable[Boundary],
    setbacks: Mapping[BoundaryKind, float],
    quad_segs: int,
) -> BaseGeometry:
    """Remove from the site every point closer to a boundary than that boundary's setback."""
    # Round caps: a setback is a minimum distance to any point of the limit, ends included.
    buffers = [
        LineString([boundary.start, boundary.end]).buffer(
            setbacks[boundary.kind], quad_segs=quad_segs
        )
        for boundary in boundaries
        if setbacks[boundary.kind] > 0
    ]
    if not buffers:
        return site_shape
    return cast("BaseGeometry", site_shape.difference(shapely.union_all(buffers)))


def _polygons(geometry: BaseGeometry) -> list[ShapelyPolygon]:
    """Flatten a geometry into its polygons, dropping points and lines."""
    if isinstance(geometry, ShapelyPolygon):
        return [] if geometry.is_empty else [geometry]
    if isinstance(geometry, BaseMultipartGeometry):
        return [polygon for part in geometry.geoms for polygon in _polygons(part)]
    return []


def _largest_part(
    geometry: BaseGeometry, min_area_m2: float
) -> tuple[ShapelyPolygon | None, list[str]]:
    """Keep the largest polygon of the set-back site, ignoring slivers.

    The envelope contract holds a single polygon, so other parts are left out and reported.
    """
    parts = sorted(
        (part for part in _polygons(geometry) if part.area >= min_area_m2),
        key=lambda part: part.area,
        reverse=True,
    )
    if not parts:
        return None, ["Setbacks consume the whole site: no buildable footprint remains."]
    if len(parts) == 1:
        return parts[0], []
    left_out = sum(part.area for part in parts[1:])
    note = (
        f"Setbacks split the footprint into {len(parts)} parts: kept the largest, "
        f"leaving out {left_out:.1f} m² in {len(parts) - 1} smaller part(s)."
    )
    return parts[0], [note]


def _max_footprint(
    ratio: Limit, site_area: float, footprint_area: float
) -> tuple[float, list[str]]:
    """Cap the footprint area by the footprint ratio, when one is set."""
    if ratio.value is None:
        return footprint_area, ["No footprint ratio set: footprint limited by setbacks only."]
    return min(footprint_area, ratio.value * site_area), []


def _min_green(
    ratio: Limit, site_area: float, max_footprint: float
) -> tuple[float | None, list[str]]:
    """Compute the minimum green area, flagging when it leaves less room than the footprint."""
    if ratio.value is None:
        return None, ["No green ratio set: no minimum green area."]
    green = ratio.value * site_area
    if site_area - max_footprint >= green:
        return green, []
    note = (
        f"The minimum green area ({green:.1f} m²) leaves at most {site_area - green:.1f} m² "
        f"unplanted, less than the maximum footprint ({max_footprint:.1f} m²): "
        "the green requirement further limits the footprint."
    )
    return green, [note]


def _height(height: Limit, max_footprint: float) -> tuple[float | None, float | None, list[str]]:
    """Return the height limit and the prism volume, both ``None`` without a height limit."""
    if height.value is None:
        return None, None, ["No height limit set: height and volume left open."]
    return height.value, max_footprint * height.value, []


def _ring(coords: Iterable[tuple[float, ...]]) -> tuple[Point, ...]:
    """Convert shapely ring coordinates to a closed tuple of points."""
    points = tuple((float(x), float(y)) for x, y, *_ in coords)
    return points if points[0] == points[-1] else (*points, points[0])


def _to_contract(polygon: ShapelyPolygon, crs: str) -> Polygon:
    """Convert a shapely polygon to the contract polygon in the given CRS."""
    return Polygon(
        crs=crs,
        exterior=_ring(polygon.exterior.coords),
        holes=tuple(_ring(interior.coords) for interior in polygon.interiors),
    )
