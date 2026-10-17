from collections import Counter
from typing import Literal, Self

from pydantic import Field, model_validator

from agent.contracts.base import Contract
from agent.contracts.evidence import Citation, Limit, Rule
from agent.contracts.findings.notes import OpenPoint
from agent.contracts.geometry import BoundaryKind, Scenario


class Distance(Contract):
    """A minimum distance, ``max(min_m, height_ratio * H)`` with H the building's height there.

    At least one of ``min_m`` and ``height_ratio`` is set.
    """

    min_m: float | None = Field(default=None, ge=0)
    """Fixed minimum in metres, e.g. 6 for "at least 6 m"; null when the rule has none."""
    height_ratio: float | None = Field(default=None, gt=0)
    """Share of the height, e.g. 0.5 for "H/2"; null when the distance does not depend on it."""
    rule: str = Field(min_length=1)
    """The rule restated, with its conditions."""
    citations: tuple[Citation, ...] = Field(min_length=1)
    """Copied exactly from the notes the rule comes from."""

    @model_validator(mode="after")
    def _has_a_term(self) -> Self:
        """Reject a distance with neither a fixed minimum nor a height ratio."""
        if self.min_m is None and self.height_ratio is None:
            msg = "a distance needs min_m, height_ratio or both"
            raise ValueError(msg)
        return self


class SetbackRule(Contract):
    """How far buildings stay from the plot limits of one kind."""

    kind: BoundaryKind
    on_limit_allowed: bool
    """Whether a building may stand right on the limit (alignment, separating limit)."""
    with_windows: Distance | None = None
    """Distance for a facade with windows (vues) facing the limit; null if the rule makes no
    such case."""
    without_windows: Distance | None = None
    """Distance for a blind facade facing the limit; null if the rule makes no such case."""

    @model_validator(mode="after")
    def _has_a_distance(self) -> Self:
        """Reject a limit that may not be built on but has no distance."""
        if not self.on_limit_allowed and self.with_windows is None and self.without_windows is None:
            msg = "a limit that may not be built on needs with_windows, without_windows or both"
            raise ValueError(msg)
        return self


class BuildingLimits(Contract):
    """The limits of one building of the program, from its destination."""

    building: str = Field(min_length=1)
    """The building's label, exactly as in the study's admissibility."""
    max_height_m: Limit
    """Maximum height for the building's destination; a value is required."""
    max_storeys: Limit
    """Maximum storeys above ground, ground floor included (R+5 = 6); reported, not used in the
    volumes."""

    @model_validator(mode="after")
    def _height_set(self) -> Self:
        """Require a positive maximum height: the volumes are computed from it."""
        if self.max_height_m.value is None or self.max_height_m.value <= 0:
            msg = "max_height_m needs a positive value; raise an open point if the notes set none"
            raise ValueError(msg)
        return self


class EnvelopeRules(Contract):
    """The rules the envelope is computed from, every value cited from the notes."""

    setbacks: tuple[SetbackRule, ...]
    """Exactly one rule per limit kind: road, side and rear."""
    buildings: tuple[BuildingLimits, ...] = Field(min_length=1)
    """One entry per building of the program."""
    spacing_with_windows: Distance | None = None
    """Distance between two buildings on one plot when a facing facade has windows."""
    spacing_without_windows: Distance | None = None
    """Distance between two buildings on one plot when no facing facade has windows."""
    max_footprint_ratio: Limit
    """Maximum built footprint as a share of the site area (emprise au sol), in [0, 1]."""
    min_green_ratio: Limit
    """Minimum green or open space as a share of the site area, in [0, 1]."""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Require one setback per kind, distinct building labels and ratios in [0, 1]."""
        errors = []
        kinds = Counter(rule.kind for rule in self.setbacks)
        for kind in BoundaryKind:
            if kinds[kind] != 1:
                errors.append(f"setbacks: {kinds[kind]} rules for kind {kind.value}, expected 1")
        labels = Counter(limits.building for limits in self.buildings)
        errors += [f"buildings: label {label!r} repeated" for label, n in labels.items() if n > 1]
        for name in ("max_footprint_ratio", "min_green_ratio"):
            value = getattr(self, name).value
            if value is not None and not 0 <= value <= 1:
                errors.append(f"{name}: ratios must be between 0 and 1 (20 % is 0.2)")
        if errors:
            raise ValueError("; ".join(errors))
        return self

    def limits(self, building: str) -> BuildingLimits | None:
        """Return the limits of a building, ``None`` for an unknown label.

        Args:
            building: A building label.

        Returns:
            Its limits.
        """
        return next((entry for entry in self.buildings if entry.building == building), None)


class OapChoice(Contract):
    """An OAP prescription the layout follows, and how."""

    prescription: Rule
    """The prescription, its citations copied exactly from the OAP notes."""
    how: str = Field(min_length=1)
    """How the layout follows it, e.g. "residence_jeunes_actifs at 15 m (R+4)"."""


class Layout(Contract):
    """Your design choices for placing the buildings inside the envelope (none set by the PLU)."""

    cut: Literal["across_long_axis", "along_long_axis"]
    """How the ground footprint is divided between buildings, relative to its long axis."""
    first_share: float = Field(gt=0, lt=1)
    """Share of the usable ground area given to the first part (ignored for one building)."""
    order: tuple[str, ...] = Field(min_length=1)
    """Building labels, first part first; part 1 is the one nearer the road."""
    facing_windows: bool
    """Whether a facing facade between two buildings has windows: spacing_with_windows applies."""
    heights_m: tuple[float, ...] = ()
    """One height per building of ``order``, each at most its maximum; empty for the maximums."""
    oap: tuple[OapChoice, ...] = ()
    """The OAP prescriptions the layout follows."""
    reasons: str = Field(min_length=1)
    """Why this layout: the cut, the shares, the order, the heights."""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Require distinct labels, positive heights and one height per building when given."""
        errors = []
        if len(set(self.order)) != len(self.order):
            errors.append("order: each building appears once")
        if self.heights_m and len(self.heights_m) != len(self.order):
            errors.append("heights_m: give one height per building of order, or none")
        if any(height <= 0 for height in self.heights_m):
            errors.append("heights_m: heights must be positive")
        if errors:
            raise ValueError("; ".join(errors))
        return self


def layout_errors(rules: EnvelopeRules, layout: Layout) -> tuple[str, ...]:
    """Check a layout against the rules: the same buildings, no height above its maximum.

    Args:
        rules: The envelope rules.
        layout: The layout placing their buildings.

    Returns:
        One ``field.path: message`` line per problem, empty when the layout is consistent.
    """
    declared = [entry.building for entry in rules.buildings]
    errors = [
        f"layout.order: {label!r} is not a building of rules.buildings ({', '.join(declared)})"
        for label in layout.order
        if label not in declared
    ]
    errors += [
        f"layout.order: building {label!r} of rules.buildings is missing"
        for label in declared
        if label not in layout.order
    ]
    for position, (label, height) in enumerate(zip(layout.order, layout.heights_m, strict=False)):
        limits = rules.limits(label)
        ceiling = None if limits is None else limits.max_height_m.value
        if ceiling is not None and height > ceiling:
            errors.append(
                f"layout.heights_m.{position}: {height:g} m is above the maximum height of "
                f"{label!r} ({ceiling:g} m)"
            )
    return tuple(errors)


class EnvelopeSubmission(Contract):
    """The envelope rules read from the notes, your layout of the buildings, and open points."""

    rules: EnvelopeRules
    layout: Layout
    open_points: tuple[OpenPoint, ...] = ()
    """Rules you need that the notes do not give or leave unclear; never guess a value."""

    @model_validator(mode="after")
    def _layout_fits_rules(self) -> Self:
        """Reject a layout naming other buildings than the rules, or too tall."""
        errors = layout_errors(self.rules, self.layout)
        if errors:
            raise ValueError("; ".join(errors))
        return self


class EnvelopeStudy(Contract):
    """The ``envelope`` artifact: the architect's submission and what code computed from it."""

    rules: EnvelopeRules
    layout: Layout
    site_area_m2: float = Field(gt=0)
    min_green_area_m2: float | None = Field(ge=0)
    bounds: tuple[Scenario, ...]
    """``largest`` and ``windows``, from the rules alone."""
    proposal: Scenario
    """From the rules and the layout."""
    open_points: tuple[OpenPoint, ...] = ()
