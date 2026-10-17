"""The plan drawn by ``preview_envelope``: the proposal over the parcel-scale map."""

import math
from collections.abc import Sequence
from itertools import pairwise

import shapely
from pydantic import Field
from shapely import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry

from agent.adapters.geo.imagery import Outline, OutlineStyle, Pixel, Rgb
from agent.contracts.base import Contract
from agent.contracts.geometry import Boundary, BoundaryKind, BuildingMassing, Polygon
from agent.runtime.geometry.parcels import to_shape
from agent.runtime.geometry.projection import Bounds, fit_half_width, square_around, to_pixels
from agent.tools.envelope.compute import SiteEnvelope

type Size = tuple[int, int]


class PlanSettings(Contract):
    """How the preview plan is framed and coloured."""

    kind: str = Field(min_length=1)
    """Imagery kind drawn under the plan, e.g. ``map``."""
    parcel_margin_ratio: float = Field(ge=0)
    """Margin around the site, as a share of its extent (as ``site_view`` at ``parcel`` scale)."""
    min_half_width_m: float = Field(gt=0)
    image_px: int = Field(gt=0)
    style: OutlineStyle
    """Line width, font and label background."""
    fill_opacity: float = Field(ge=0, le=1)
    limit_rgbs: dict[BoundaryKind, Rgb]
    """Colour of the site's limits, per kind."""
    setback_rgb: Rgb
    """Fill of the setback strip, between the limits and the ground footprint."""
    building_rgbs: tuple[Rgb, ...] = Field(min_length=1)
    """Fills of the buildings, in layout order, reused when there are more buildings."""
    gap_rgb: Rgb
    """Colour of the lines measuring the gap between buildings."""


def plan_bounds(polygon: Polygon, settings: PlanSettings) -> Bounds:
    """Return the square ground box of the plan, the site with a margin.

    Args:
        polygon: The site polygon.
        settings: Framing knobs.

    Returns:
        The box, in the site's CRS.
    """
    min_x, min_y, max_x, max_y = to_shape(polygon).bounds
    half = fit_half_width(
        (min_x, min_y, max_x, max_y), settings.parcel_margin_ratio, settings.min_half_width_m
    )
    return square_around(((min_x + max_x) / 2, (min_y + max_y) / 2), half)


def plan_outlines(
    computed: SiteEnvelope, polygon: Polygon, bounds: Bounds, settings: PlanSettings
) -> list[Outline]:
    """Draw the proposal: setback strip, buildings, gaps, then the limits by kind.

    Args:
        computed: The labelled edges and the envelope.
        polygon: The site polygon.
        bounds: Ground box of the image.
        settings: Colours and size.

    Returns:
        The outlines, bottom first.
    """
    size = (settings.image_px, settings.image_px)
    proposal = computed.study.proposal
    ground = None if proposal.footprint is None else to_shape(proposal.footprint)
    strip = to_shape(polygon) if ground is None else to_shape(polygon).difference(ground)
    outlines = [_area("", strip, settings.setback_rgb, bounds=bounds, size=size, settings=settings)]
    built = [massing for massing in proposal.buildings if massing.footprint is not None]
    for index, massing in enumerate(built):
        colour = settings.building_rgbs[index % len(settings.building_rgbs)]
        label = f"{massing.building} {massing.max_height_m:g} m"
        outlines.append(
            _area(label, _shape(massing), colour, bounds=bounds, size=size, settings=settings)
        )
    outlines += [
        _gap(_shape(first), _shape(second), bounds, size, settings)
        for first, second in pairwise(built)
    ]
    outlines += [
        Outline(
            label="",
            rings=(tuple(to_pixels([boundary.start, boundary.end], bounds, size)),),
            anchor=(0.0, 0.0),
            rgb=settings.limit_rgbs[boundary.kind],
            closed=False,
        )
        for boundary in computed.boundaries
    ]
    return outlines


def plan_caption(bounds: Bounds, settings: PlanSettings, failure: str | None) -> str:
    """Say what the plan shows and how to read it.

    Args:
        bounds: Ground box of the image.
        settings: Colours and size.
        failure: Why the map could not be fetched, ``None`` when it was.

    Returns:
        The caption.
    """
    side = bounds[2] - bounds[0]
    limits = ", ".join(
        f"{kind.value} {_rgb(settings.limit_rgbs[kind])}" for kind in settings.limit_rgbs
    )
    under = (
        f"a white background (the map could not be fetched: {failure})"
        if failure is not None
        else f"the `{settings.kind}` imagery of site_view"
    )
    return (
        f"Plan of the proposal on {under}: {side:.0f} m x {side:.0f} m, "
        f"{side / settings.image_px:.2f} m per pixel, north up. Site limits by kind: {limits}. "
        f"Setback strip (the site minus the proposal's ground footprint) filled "
        f"{_rgb(settings.setback_rgb)}. Each building's ground part is filled and labelled with "
        f"its name and height; {_rgb(settings.gap_rgb)} lines measure the gaps between buildings."
    )


def describe_limits(boundaries: Sequence[Boundary]) -> str:
    """Sum the site's limits by kind, as the gate labels them.

    Args:
        boundaries: The labelled edges.

    Returns:
        E.g. ``Site limits as labelled by code: road 52.0 m (1 edge), side 60.0 m (2 edges)``.
    """
    parts = []
    for kind in BoundaryKind:
        edges = [boundary for boundary in boundaries if boundary.kind is kind]
        if edges:
            length = sum(math.dist(edge.start, edge.end) for edge in edges)
            parts.append(f"{kind.value} {length:.1f} m ({len(edges)} edge{'s' * (len(edges) > 1)})")
    return f"Site limits as labelled by code: {', '.join(parts)}"


def _shape(massing: BuildingMassing) -> BaseGeometry:
    """Return a building's ground part as a shapely geometry."""
    return ShapelyPolygon() if massing.footprint is None else to_shape(massing.footprint)


def _rings(geometry: BaseGeometry, bounds: Bounds, size: Size) -> tuple[tuple[Pixel, ...], ...]:
    """Convert every ring of a geometry's polygons to image pixels."""
    polygons = [part for part in shapely.get_parts(geometry) if isinstance(part, ShapelyPolygon)]
    return tuple(
        tuple(to_pixels(ring.coords, bounds, size))
        for polygon in polygons
        for ring in (polygon.exterior, *polygon.interiors)
    )


def _area(  # noqa: PLR0913 - one filled shape and how to draw it
    label: str,
    geometry: BaseGeometry,
    colour: Rgb,
    *,
    bounds: Bounds,
    size: Size,
    settings: PlanSettings,
) -> Outline:
    """Fill a geometry, its label at a point inside it."""
    point = geometry.representative_point() if not geometry.is_empty else shapely.Point(0, 0)
    return Outline(
        label=label,
        rings=_rings(geometry, bounds, size),
        anchor=to_pixels([(point.x, point.y)], bounds, size)[0],
        rgb=colour,
        fill_rgb=colour,
        fill_opacity=settings.fill_opacity,
    )


def _gap(
    first: BaseGeometry, second: BaseGeometry, bounds: Bounds, size: Size, settings: PlanSettings
) -> Outline:
    """Draw the shortest line between two buildings, labelled with its length."""
    line = shapely.shortest_line(first, second)
    middle = line.interpolate(0.5, normalized=True)
    return Outline(
        label=f"gap {line.length:.1f} m",
        rings=(tuple(to_pixels(line.coords, bounds, size)),),
        anchor=to_pixels([(middle.x, middle.y)], bounds, size)[0],
        rgb=settings.gap_rgb,
        closed=False,
    )


def _rgb(colour: Rgb) -> str:
    """Render a colour for the caption."""
    red, green, blue = colour
    return f"RGB ({red}, {green}, {blue})"
