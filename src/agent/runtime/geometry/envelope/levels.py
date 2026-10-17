import math
from collections.abc import Callable, Sequence
from enum import StrEnum
from itertools import pairwise
from typing import NamedTuple

from shapely import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry

from agent.contracts.envelope import Distance, EnvelopeRules, SetbackRule
from agent.contracts.geometry import Boundary, BoundaryKind, BuildingMassing, Level
from agent.runtime.geometry.envelope.shapes import largest_part, set_back
from agent.runtime.report.markdown import area, percent


class Bound(StrEnum):
    """Which distance each limit keeps in a bound (and in the proposal, built on ``windows``)."""

    LARGEST = "largest"
    """Each limit at its smallest allowed distance, 0 where building on it is allowed."""
    WINDOWS = "windows"
    """Each limit at its distance for a facade with windows, else without, else 0 if allowed."""


def distance_at(distance: Distance, height: float) -> float:
    """Return ``max(min_m, height_ratio x height)``, a missing term counting as 0.

    Args:
        distance: The rule.
        height: Height of the building at that point, in metres.

    Returns:
        The distance in metres.
    """
    return max(distance.min_m or 0.0, (distance.height_ratio or 0.0) * height)


def setback_at(rule: SetbackRule, bound: Bound, height: float) -> float:
    """Return the distance a limit keeps at a height, in a bound.

    Args:
        rule: The setback rule of the limit's kind.
        bound: Which distance applies.
        height: The height, in metres.

    Returns:
        The distance in metres.
    """
    options = [d for d in (rule.with_windows, rule.without_windows) if d is not None]
    if bound is Bound.LARGEST:
        if rule.on_limit_allowed or not options:
            return 0.0
        return min(distance_at(option, height) for option in options)
    if options:
        return distance_at(options[0], height)
    return 0.0


class SetBackSite:
    """The site minus the setbacks of one bound, at any height, each distinct case built once."""

    def __init__(
        self,
        site: BaseGeometry,
        boundaries: Sequence[Boundary],
        rules: EnvelopeRules,
        bound: Bound,
        quad_segs: int,
    ) -> None:
        """Keep what the allowed footprint is computed from.

        Args:
            site: The site geometry.
            boundaries: Its labelled edges.
            rules: The envelope rules, one setback per kind.
            bound: Which distance applies to each limit.
            quad_segs: Segments per quarter circle in the round buffers.
        """
        self._site = site
        self._boundaries = tuple(boundaries)
        self._rules = {rule.kind: rule for rule in rules.setbacks}
        self._bound = bound
        self._quad_segs = quad_segs
        self._cache: dict[tuple[float, ...], BaseGeometry] = {}

    def at(self, height: float) -> BaseGeometry:
        """Return the allowed footprint at a height.

        Args:
            height: The height, in metres.

        Returns:
            The site minus each limit's distance at that height.
        """
        distances = {
            kind: setback_at(self._rules[kind], self._bound, height) for kind in BoundaryKind
        }
        key = tuple(distances[kind] for kind in BoundaryKind)
        if key not in self._cache:
            self._cache[key] = set_back(self._site, self._boundaries, distances, self._quad_segs)
        return self._cache[key]


class Rise(NamedTuple):
    """A footprint raised to a height, slice by slice."""

    footprint: ShapelyPolygon | None
    """The lowest slice's footprint; ``None`` when nothing can be built."""
    levels: tuple[Level, ...]
    left_out: bool
    """Whether a slice lost parts of its footprint, only the largest being kept."""


def _slices(height: float, step_m: float) -> list[tuple[float, float]]:
    """Cut ``[0, height]`` into slices of ``step_m``, the last one possibly shorter."""
    count = math.ceil(height / step_m)
    bounds = [min(index * step_m, height) for index in range(count + 1)]
    return [(bottom, top) for bottom, top in pairwise(bounds) if top > bottom]


def rise(
    region: ShapelyPolygon | None,
    height: float,
    allowed: Callable[[float], BaseGeometry],
    *,
    step_m: float,
    min_area_m2: float,
) -> Rise:
    """Raise a ground region to a height, keeping at each slice what the setbacks allow.

    Each slice's footprint is the region within the allowed footprint at the slice's top, the
    most restrictive height of the slice. Consecutive slices of the same area merge, so fixed
    setbacks give one slice. The rise stops at the first empty slice.

    Args:
        region: The ground region given to the building, ``None`` when it has none.
        height: The building's height.
        allowed: Allowed footprint at a height.
        step_m: Slice thickness.
        min_area_m2: Footprint parts smaller than this are slivers.

    Returns:
        The footprint and the levels.
    """
    if region is None:
        return Rise(None, (), left_out=False)
    footprint: ShapelyPolygon | None = None
    levels: list[Level] = []
    left_out = False
    for bottom, top in _slices(height, step_m):
        piece, dropped = largest_part(region.intersection(allowed(top)), min_area_m2)
        left_out = left_out or dropped
        if piece is None:
            break
        if footprint is None:
            footprint = piece
        area = float(piece.area)
        if levels and levels[-1].area_m2 == area:
            levels[-1] = levels[-1].model_copy(update={"to_m": top})
        else:
            levels.append(Level(from_m=bottom, to_m=top, area_m2=area))
    return Rise(footprint, tuple(levels), left_out)


def volume(levels: Sequence[Level]) -> float:
    """Return the volume of stacked levels.

    Args:
        levels: The levels.

    Returns:
        Sum of area times thickness, in cubic metres.
    """
    return sum(level.area_m2 * (level.to_m - level.from_m) for level in levels)


class Cap(NamedTuple):
    """The largest total ground area the rules allow, and which rule sets it."""

    area_m2: float
    reason: str


def ground_cap(rules: EnvelopeRules, site_area_m2: float) -> Cap | None:
    """Return the smaller of the footprint-ratio cap and the site area minus the green area.

    Args:
        rules: The envelope rules.
        site_area_m2: The site area.

    Returns:
        The cap, ``None`` when neither ratio is set.
    """
    caps = []
    ratio = rules.max_footprint_ratio.value
    if ratio is not None:
        caps.append(Cap(ratio * site_area_m2, f"the footprint ratio cap ({percent(ratio)})"))
    green = rules.min_green_ratio.value
    if green is not None:
        caps.append(
            Cap(
                (1 - green) * site_area_m2,
                f"the site area minus the minimum green area ({percent(green)})",
            )
        )
    return min(caps, key=_cap_area) if caps else None


def _cap_area(cap: Cap) -> float:
    """Return a cap's area, to compare caps."""
    return cap.area_m2


def scale_together(
    massings: Sequence[BuildingMassing], cap: Cap | None
) -> tuple[list[BuildingMassing], list[str]]:
    """Scale every building's areas down by one factor when their total ground area is capped.

    Args:
        massings: The buildings of one scenario (or one alternative of a bound).
        cap: The ground-area cap, ``None`` when there is none.

    Returns:
        The massings, scaled when needed, and the assumption recorded when they are.
    """
    total = sum(massing.footprint_area_m2 for massing in massings)
    if cap is None or total <= cap.area_m2:
        return list(massings), []
    factor = cap.area_m2 / total
    note = (
        f"Ground area {area(total)} exceeds {cap.reason}, {area(cap.area_m2)}: every building's "
        f"areas are scaled by {factor:.3f}; the footprints show where to build, not how much."
    )
    return [_scale(massing, factor) for massing in massings], [note]


def _scale(massing: BuildingMassing, factor: float) -> BuildingMassing:
    """Scale a massing's ground area, level areas and volume by a factor."""
    levels = tuple(
        level.model_copy(update={"area_m2": level.area_m2 * factor}) for level in massing.levels
    )
    return massing.model_copy(
        update={
            "footprint_area_m2": massing.footprint_area_m2 * factor,
            "levels": levels,
            "volume_m3": massing.volume_m3 * factor,
        }
    )
