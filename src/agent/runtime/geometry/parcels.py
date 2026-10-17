from collections.abc import Iterable, Sequence
from typing import cast

import shapely
from shapely.geometry.base import BaseGeometry

from agent.contracts.geometry import Point, Polygon


class DisjointParcelsError(ValueError):
    """The selected parcels do not form one connected polygon."""

    def __init__(self, part_areas_m2: Sequence[float]) -> None:
        """Build the message from the area of each separate part.

        Args:
            part_areas_m2: Area of each connected part left after the union, in square metres.
        """
        self.part_areas_m2 = tuple(part_areas_m2)
        areas = ", ".join(f"{area:.1f} m2" for area in self.part_areas_m2)
        super().__init__(
            f"The selected parcels form {len(self.part_areas_m2)} separate parts ({areas}) "
            "instead of one connected site. Select only adjacent parcels, or add the parcel "
            "that links them."
        )


def polygon_from_rings(
    polygons: Sequence[Sequence[Sequence[Point]]],
) -> shapely.Polygon | shapely.MultiPolygon:
    """Build a shapely geometry from MultiPolygon coordinates.

    Args:
        polygons: Polygons, each a list of rings (the first is the exterior, the others
            holes), each ring a list of x/y points.

    Returns:
        A ``Polygon`` when there is one polygon, a ``MultiPolygon`` otherwise.

    Raises:
        ValueError: ``polygons`` is empty.
    """
    if not polygons:
        msg = "no polygon coordinates given"
        raise ValueError(msg)
    shapes = [shapely.Polygon(rings[0], rings[1:]) for rings in polygons]
    return shapes[0] if len(shapes) == 1 else shapely.MultiPolygon(shapes)


def union_parcels(
    parcels: Sequence[BaseGeometry], grid_size_m: float, max_sliver_area_m2: float
) -> shapely.Polygon:
    """Merge adjacent parcels into one site polygon.

    The union snaps coordinates to a ``grid_size_m`` grid and closes gaps narrower than twice
    that size, which removes the digitising noise between parcels that share a limit. Holes and
    parts smaller than ``max_sliver_area_m2`` are such noise too and are dropped.

    Args:
        parcels: Parcel geometries in a metric CRS.
        grid_size_m: Precision grid in metres.
        max_sliver_area_m2: Holes and parts below this area are discarded.

    Returns:
        The site polygon, exterior counter-clockwise, without repeated vertices.

    Raises:
        ValueError: Nothing with an area remains.
        DisjointParcelsError: More than one part remains.
    """
    merged = _close_gaps(shapely.union_all(list(parcels), grid_size=grid_size_m), grid_size_m)
    parts = [
        _drop_small_holes(part, max_sliver_area_m2)
        for part in _polygon_parts(merged)
        if part.area >= max_sliver_area_m2
    ]
    if not parts:
        msg = "the selected parcels have no area"
        raise ValueError(msg)
    if len(parts) > 1:
        raise DisjointParcelsError([part.area for part in parts])
    return _normalise(parts[0])


def to_contract(polygon: shapely.Polygon, crs: str, decimals: int) -> Polygon:
    """Convert a shapely polygon to the ``Polygon`` contract.

    Args:
        polygon: Polygon in ``crs``.
        crs: CRS identifier stored in the contract.
        decimals: Number of decimals kept on each coordinate.

    Returns:
        The contract polygon: exterior counter-clockwise, rings closed and without consecutive
        duplicate points after rounding.
    """
    oriented = _normalise(polygon)
    return Polygon(
        crs=crs,
        exterior=_ring(oriented.exterior.coords, decimals),
        holes=tuple(_ring(hole.coords, decimals) for hole in oriented.interiors),
    )


def to_shape(polygon: Polygon) -> shapely.Polygon:
    """Convert a ``Polygon`` contract to a shapely polygon."""
    return shapely.Polygon(polygon.exterior, polygon.holes)


def _close_gaps(geometry: BaseGeometry, grid_size_m: float) -> BaseGeometry:
    """Close gaps narrower than ``2 * grid_size_m`` (morphological closing).

    Grid snapping alone leaves a gap open when a grid midline falls inside it.
    """
    grown = shapely.buffer(geometry, grid_size_m, join_style="mitre")
    closed = shapely.buffer(grown, -grid_size_m, join_style="mitre")
    return cast("BaseGeometry", shapely.set_precision(closed, grid_size_m))


def _polygon_parts(geometry: BaseGeometry) -> list[shapely.Polygon]:
    """Return the polygons of a possibly multi-part geometry."""
    return [part for part in shapely.get_parts(geometry) if isinstance(part, shapely.Polygon)]


def _drop_small_holes(polygon: shapely.Polygon, min_area_m2: float) -> shapely.Polygon:
    """Return the polygon without the holes smaller than ``min_area_m2``."""
    holes = [hole for hole in polygon.interiors if shapely.Polygon(hole).area >= min_area_m2]
    return shapely.Polygon(polygon.exterior, holes)


def _normalise(polygon: shapely.Polygon) -> shapely.Polygon:
    """Orient the exterior counter-clockwise and remove repeated vertices."""
    oriented = shapely.orient_polygons(shapely.remove_repeated_points(polygon))
    return shapely.Polygon(oriented.exterior, oriented.interiors)


def _ring(coords: Iterable[tuple[float, ...]], decimals: int) -> tuple[Point, ...]:
    """Round a ring's points, drop consecutive duplicates and close it."""
    points: list[Point] = []
    for x, y, *_ in coords:
        point = (round(x, decimals), round(y, decimals))
        if not points or points[-1] != point:
            points.append(point)
    if points[0] != points[-1]:
        points.append(points[0])
    return tuple(points)
