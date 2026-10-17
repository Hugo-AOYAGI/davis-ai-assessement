from collections.abc import Sequence
from typing import NamedTuple

from pydantic import NonNegativeFloat, PositiveFloat, PositiveInt
from shapely import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry

from agent.contracts.base import Contract
from agent.contracts.envelope import EnvelopeRules, EnvelopeStudy, Layout
from agent.contracts.findings.notes import OpenPoint
from agent.contracts.geometry import Boundary, BoundaryKind, BuildingMassing, Polygon, Scenario
from agent.runtime.geometry.envelope.levels import (
    Bound,
    Cap,
    Rise,
    SetBackSite,
    ground_cap,
    rise,
    scale_together,
    volume,
)
from agent.runtime.geometry.envelope.shapes import largest_part, site_shape, to_contract
from agent.runtime.geometry.envelope.split import (
    layout_heights,
    part_gaps,
    part_shares,
    split_footprint,
)

LEFT_OUT = "Where setbacks split a footprint into several pieces, only the largest is kept."
NOTHING_LEFT = "Setbacks consume the whole site: no buildable footprint remains."
BOUND_NOTES = {
    Bound.LARGEST: "Each limit at its smallest allowed distance, 0 where building on it is "
    "allowed: the legal maximum.",
    Bound.WINDOWS: "Every facade facing a limit has windows: each limit at its distance with "
    "windows (else without, else 0 where building on it is allowed).",
}
ALTERNATIVES = (
    "One massing per maximum height, each over the whole footprint: they are alternatives, not "
    "added up; the total is the largest."
)


class EnvelopeSettings(Contract):
    """Knobs of the envelope computation (``policies.envelope``)."""

    level_step_m: PositiveFloat
    """Thickness of the slices a massing is cut into."""
    quad_segs: PositiveInt
    """Segments per quarter circle in the round setback buffers."""
    min_area_m2: NonNegativeFloat
    """Footprint parts smaller than this are discarded as slivers."""
    cut_tolerance_m: PositiveFloat
    """Precision of the cut positions when the footprint is split between buildings."""


class _Context(NamedTuple):
    """What every scenario is computed from."""

    site: BaseGeometry
    crs: str
    boundaries: tuple[Boundary, ...]
    rules: EnvelopeRules
    settings: EnvelopeSettings
    cap: Cap | None


def compute_envelope_study(  # noqa: PLR0913 - the architect's submission, plus the settings
    polygon: Polygon,
    boundaries: Sequence[Boundary],
    rules: EnvelopeRules,
    layout: Layout,
    *,
    settings: EnvelopeSettings,
    open_points: Sequence[OpenPoint] = (),
) -> EnvelopeStudy:
    """Compute the bounds and the proposal from the site, the rules and the layout.

    The bounds (``largest``, ``windows``) come from the rules alone; the proposal splits the
    ``windows`` ground footprint between the buildings as the layout says. Every massing is
    sliced at ``settings.level_step_m``; ground areas above the footprint-ratio or green cap are
    scaled down. ``preview_envelope``, ``submit_envelope`` and ``submit_study`` all call this.

    Args:
        polygon: The site polygon, in a metric CRS.
        boundaries: The site's edges labelled road / side / rear.
        rules: The envelope rules.
        layout: The layout of the buildings; its labels and heights must agree with ``rules``
            (``layout_errors``).
        settings: Computation knobs.
        open_points: The architect's open points, stored as they are.

    Returns:
        The envelope study.

    Raises:
        ValueError: If a building of the layout has no maximum height in the rules.
    """
    site = site_shape(polygon)
    site_area = float(site.area)
    green = rules.min_green_ratio.value
    context = _Context(
        site, polygon.crs, tuple(boundaries), rules, settings, ground_cap(rules, site_area)
    )
    return EnvelopeStudy(
        rules=rules,
        layout=layout,
        site_area_m2=site_area,
        min_green_area_m2=None if green is None else green * site_area,
        bounds=tuple(_bound(context, bound) for bound in Bound),
        proposal=_proposal(context, layout),
        open_points=tuple(open_points),
    )


def _ground(context: _Context, bound: Bound) -> tuple[SetBackSite, ShapelyPolygon | None, bool]:
    """Return the set-back site of a bound and its ground footprint."""
    allowed = SetBackSite(
        context.site, context.boundaries, context.rules, bound, context.settings.quad_segs
    )
    ground, left_out = largest_part(allowed.at(0.0), context.settings.min_area_m2)
    return allowed, ground, left_out


def _raise(
    context: _Context, allowed: SetBackSite, region: ShapelyPolygon | None, height: float
) -> Rise:
    """Raise a region to a height within a bound's setbacks."""
    settings = context.settings
    return rise(
        region,
        height,
        allowed.at,
        step_m=settings.level_step_m,
        min_area_m2=settings.min_area_m2,
    )


def _massing(context: _Context, building: str, raised: Rise, height: float) -> BuildingMassing:
    """Turn a rise into a building massing."""
    return BuildingMassing(
        building=building,
        footprint=to_contract(raised.footprint, context.crs),
        footprint_area_m2=raised.levels[0].area_m2 if raised.levels else 0.0,
        max_height_m=height,
        levels=raised.levels,
        volume_m3=volume(raised.levels),
    )


def _bound(context: _Context, bound: Bound) -> Scenario:
    """Compute one bound: a massing per maximum height over the whole ground footprint."""
    allowed, ground, left_out = _ground(context, bound)
    bands: dict[float, list[str]] = {}
    for limits in context.rules.buildings:
        bands.setdefault(limits.max_height_m.value or 0.0, []).append(limits.building)
    massings, notes = [], [BOUND_NOTES[bound]]
    for height, labels in bands.items():
        raised = _raise(context, allowed, ground, height)
        left_out = left_out or raised.left_out
        scaled, cap_notes = scale_together(
            [_massing(context, ", ".join(labels), raised, height)], context.cap
        )
        massings.extend(scaled)
        notes.extend(cap_notes)
    notes += [ALTERNATIVES] if len(bands) > 1 else []
    notes += [LEFT_OUT] if left_out else []
    fits = all(massing.levels for massing in massings)
    return Scenario(
        name=bound.value,
        footprint=to_contract(ground, context.crs),
        footprint_area_m2=0.0 if ground is None else float(ground.area),
        buildings=tuple(massings),
        fits=fits,
        total_volume_m3=max((massing.volume_m3 for massing in massings), default=0.0),
        assumptions=tuple(dict.fromkeys(notes)),
        warnings=() if fits else (NOTHING_LEFT,),
    )


def _proposal(context: _Context, layout: Layout) -> Scenario:
    """Compute the proposal: the ``windows`` ground footprint split between the buildings."""
    allowed, ground, left_out = _ground(context, Bound.WINDOWS)
    heights = layout_heights(context.rules, layout)
    shares, share_notes = part_shares(layout)
    gaps, gap_notes = part_gaps(context.rules, layout, heights)
    notes, warnings = [BOUND_NOTES[Bound.WINDOWS], *share_notes, *gap_notes], []
    parts: tuple[BaseGeometry | None, ...] = (None,) * len(layout.order)
    if ground is None:
        warnings.append(NOTHING_LEFT)
    else:
        road = [edge for edge in context.boundaries if edge.kind is BoundaryKind.ROAD]
        split = split_footprint(
            ground,
            road,
            cut=layout.cut,
            shares=shares,
            gaps=gaps,
            tolerance_m=context.settings.cut_tolerance_m,
        )
        if split.parts:
            parts = split.parts
        else:
            warnings.append(
                f"The spacing between buildings ({', '.join(f'{gap:g} m' for gap in gaps)}) "
                f"does not fit across the footprint ({split.extent_m:.1f} m along the cut)."
            )
    massings = []
    for label, part, height in zip(layout.order, parts, heights, strict=True):
        region, dropped = (None, False) if part is None else _region(context, part)
        raised = _raise(context, allowed, region, height)
        left_out = left_out or dropped or raised.left_out
        massings.append(_massing(context, label, raised, height))
        if ground is not None and parts[0] is not None and not raised.levels:
            warnings.append(f"{label}: its part of the footprint is empty.")
    scaled, cap_notes = scale_together(massings, context.cap)
    notes += [*cap_notes, *([LEFT_OUT] if left_out else [])]
    return Scenario(
        name="proposal",
        footprint=to_contract(ground, context.crs),
        footprint_area_m2=0.0 if ground is None else float(ground.area),
        buildings=tuple(scaled),
        fits=not warnings,
        total_volume_m3=sum(massing.volume_m3 for massing in scaled),
        assumptions=tuple(notes),
        warnings=tuple(warnings),
    )


def _region(context: _Context, part: BaseGeometry) -> tuple[ShapelyPolygon | None, bool]:
    """Keep the largest piece of a building's part."""
    return largest_part(part, context.settings.min_area_m2)
