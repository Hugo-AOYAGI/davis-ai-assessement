import math
from collections.abc import Callable, Sequence
from itertools import pairwise
from typing import Literal, NamedTuple, cast

import shapely
from shapely import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry

from agent.contracts.envelope import EnvelopeRules, Layout
from agent.contracts.geometry import Boundary, Point
from agent.runtime.geometry.envelope.levels import distance_at

type Cut = Literal["across_long_axis", "along_long_axis"]


def layout_heights(rules: EnvelopeRules, layout: Layout) -> tuple[float, ...]:
    """Return each building's height in layout order: the layout's, else its maximum.

    Args:
        rules: The envelope rules.
        layout: A layout naming the same buildings (see ``layout_errors``).

    Returns:
        One height per building of ``layout.order``.

    Raises:
        ValueError: If a building of the layout has no limits in the rules.
    """
    if layout.heights_m:
        return layout.heights_m
    heights = []
    for label in layout.order:
        limits = rules.limits(label)
        if limits is None or limits.max_height_m.value is None:
            msg = f"building {label!r} has no maximum height in the rules"
            raise ValueError(msg)
        heights.append(limits.max_height_m.value)
    return tuple(heights)


def part_shares(layout: Layout) -> tuple[tuple[float, ...], list[str]]:
    """Return each part's share of the usable area: ``first_share``, the rest split equally.

    Args:
        layout: The layout.

    Returns:
        One share per building of ``layout.order``, and the assumption made for more than two.
    """
    others = len(layout.order) - 1
    if not others:
        return (1.0,), []
    rest = (1 - layout.first_share) / others
    notes = (
        [f"The parts after the first share the rest of the usable area equally ({rest:.0%})."]
        if others > 1
        else []
    )
    return (layout.first_share, *(rest,) * others), notes


def part_gaps(
    rules: EnvelopeRules, layout: Layout, heights: Sequence[float]
) -> tuple[tuple[float, ...], list[str]]:
    """Return the gap between each pair of neighbouring parts, from the spacing rule.

    ``facing_windows`` selects the spacing with or without windows, the other one standing in
    when the rules lack it. A height-dependent spacing is evaluated at the taller neighbour.

    Args:
        rules: The envelope rules.
        layout: The layout.
        heights: Each building's height, in layout order.

    Returns:
        One gap per pair of neighbouring parts, and the assumptions made.
    """
    count = len(layout.order) - 1
    preferred, other = (rules.spacing_with_windows, rules.spacing_without_windows)
    if not layout.facing_windows:
        preferred, other = other, preferred
    spacing = preferred or other
    if not count:
        return (), []
    if spacing is None:
        return (0.0,) * count, ["No spacing rule between buildings: the parts only touch."]
    notes = []
    if preferred is None:
        state = "with" if layout.facing_windows else "without"
        notes.append(f"No spacing rule for facades {state} windows: the other one applies.")
    if spacing.height_ratio is not None:
        notes.append("The spacing is taken at the taller of two neighbouring buildings.")
    gaps = tuple(distance_at(spacing, max(pair)) for pair in pairwise(heights))
    return gaps, notes


class Split(NamedTuple):
    """A footprint cut into parts separated by gaps."""

    parts: tuple[BaseGeometry, ...]
    """One part per share, in order from the road side; empty when the gaps do not fit."""
    extent_m: float
    """Length of the footprint along the direction the parts follow each other."""


class _Frame(NamedTuple):
    """Coordinates along the sweep direction ``s`` and across it ``t``, and their ranges."""

    direction: Point
    normal: Point
    s_range: tuple[float, float]
    t_range: tuple[float, float]


def split_footprint(  # noqa: PLR0913 - the footprint, then one argument per layout choice
    footprint: ShapelyPolygon,
    road: Sequence[Boundary],
    *,
    cut: Cut,
    shares: Sequence[float],
    gaps: Sequence[float],
    tolerance_m: float,
) -> Split:
    """Cut a footprint into parts of given shares of its usable area, separated by gaps.

    The cut lines are perpendicular to the long axis of the footprint's minimum rotated
    rectangle (``across_long_axis``) or parallel to it (``along_long_axis``). Parts follow each
    other from the side nearer the road edges. The usable area is the footprint minus the gaps;
    part ``i`` gets ``shares[i]`` of it.

    Args:
        footprint: The ground footprint.
        road: The road edges of the site; the first part is placed on their side.
        cut: Orientation of the cut lines.
        shares: Share of the usable area of each part, summing to 1.
        gaps: Width of the gap after each part but the last.
        tolerance_m: Precision of the cut positions.

    Returns:
        The parts, or none when the gaps take the whole extent.
    """
    frame = _frame(footprint, road, cut)
    low, high = frame.s_range
    extent = high - low
    if len(shares) == 1:
        return Split((footprint,), extent)
    if sum(gaps) >= extent:
        return Split((), extent)
    width = frame.t_range[1] - frame.t_range[0]

    def band(start: float, end: float) -> BaseGeometry:
        """Return the footprint between two positions along the sweep direction."""
        return cast("BaseGeometry", footprint.intersection(_strip(frame, start, end)))

    def place(usable: float) -> tuple[list[tuple[float, float]], float]:
        """Place the parts for a usable area, returning their spans and the last part's excess."""
        spans: list[tuple[float, float]] = []
        start = low
        for share, gap in zip(shares[:-1], gaps, strict=True):
            end = _solve(
                lambda s, a=start: float(band(a, s).area), share * usable, start, high, tolerance_m
            )
            spans.append((start, end))
            start = min(end + gap, high)
        spans.append((start, high))
        return spans, float(band(start, high).area) - shares[-1] * usable

    below, above = 0.0, float(footprint.area)
    while above - below > tolerance_m * width:
        middle = (below + above) / 2
        below, above = (middle, above) if place(middle)[1] > 0 else (below, middle)
    spans, _ = place(below)
    return Split(tuple(band(start, end) for start, end in spans), extent)


def _solve(
    grow: Callable[[float], float], target: float, low: float, high: float, tolerance_m: float
) -> float:
    """Find by bisection the position where an increasing function reaches a target."""
    while high - low > tolerance_m:
        middle = (low + high) / 2
        low, high = (middle, high) if grow(middle) < target else (low, middle)
    return (low + high) / 2


def _frame(footprint: ShapelyPolygon, road: Sequence[Boundary], cut: Cut) -> _Frame:
    """Orient the sweep along or across the long axis, starting from the road side."""
    rectangle = shapely.oriented_envelope(footprint)
    (x0, y0), (x1, y1), (x2, y2), *_ = rectangle.exterior.coords
    first, second = (x1 - x0, y1 - y0), (x2 - x1, y2 - y1)
    long_axis = first if math.hypot(*first) >= math.hypot(*second) else second
    length = math.hypot(*long_axis)
    along = (long_axis[0] / length, long_axis[1] / length)
    direction = along if cut == "across_long_axis" else (-along[1], along[0])
    if _road_ahead(footprint, road, direction):
        direction = (-direction[0], -direction[1])
    normal = (-direction[1], direction[0])
    points = list(footprint.exterior.coords)
    s_values = [_dot(point, direction) for point in points]
    t_values = [_dot(point, normal) for point in points]
    return _Frame(direction, normal, (min(s_values), max(s_values)), (min(t_values), max(t_values)))


def _road_ahead(footprint: ShapelyPolygon, road: Sequence[Boundary], direction: Point) -> bool:
    """Tell whether the road edges lie ahead of the footprint's centroid along a direction."""
    lengths = [math.dist(edge.start, edge.end) for edge in road]
    total = sum(lengths)
    if total == 0:
        return False
    middle = [
        (sum(w * (e.start[i] + e.end[i]) / 2 for w, e in zip(lengths, road, strict=True)) / total)
        for i in (0, 1)
    ]
    centroid = footprint.centroid
    offset = (middle[0] - centroid.x, middle[1] - centroid.y)
    return _dot(offset, direction) > 0


def _strip(frame: _Frame, start: float, end: float) -> ShapelyPolygon:
    """Return the quadrilateral between two sweep positions, wider than the footprint."""
    if end <= start:
        return ShapelyPolygon()
    t_low, t_high = frame.t_range
    margin = t_high - t_low
    corners = (
        (start, t_low - margin),
        (end, t_low - margin),
        (end, t_high + margin),
        (start, t_high + margin),
    )
    return ShapelyPolygon([_point(frame, s, t) for s, t in corners])


def _point(frame: _Frame, s: float, t: float) -> Point:
    """Convert sweep coordinates back to plane coordinates."""
    (dx, dy), (nx, ny) = frame.direction, frame.normal
    return (s * dx + t * nx, s * dy + t * ny)


def _dot(first: Sequence[float], second: Point) -> float:
    """Return the dot product of two plane vectors."""
    return first[0] * second[0] + first[1] * second[1]
