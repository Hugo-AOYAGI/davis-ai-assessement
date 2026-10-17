from agent.contracts.envelope import EnvelopeStudy, Layout
from agent.contracts.geometry import BuildingMassing, Level, Scenario
from agent.runtime.report.markdown import area, metres, number

BOUND_TITLES = {
    "largest": "largest (each limit at its smallest allowed distance)",
    "windows": "windows (facades with windows facing every limit)",
}


def volume(value: float) -> str:
    """Format a volume in cubic metres.

    Args:
        value: Volume in m³.

    Returns:
        E.g. ``12000 m³``.
    """
    return f"{number(value, 1)} m³"


def describe_levels(levels: tuple[Level, ...]) -> str:
    """Describe a massing's slices, e.g. ``0-8 m: 600 m²; 8-9 m: 560 m²``.

    Args:
        levels: The slices, bottom first.

    Returns:
        One ``from-to m: area`` entry per slice, or ``none``.
    """
    return (
        "; ".join(
            f"{number(level.from_m, 2)}-{number(level.to_m, 2)} m: {area(level.area_m2)}"
            for level in levels
        )
        or "none"
    )


def _building(massing: BuildingMassing) -> str:
    """Describe one building of a scenario on one line."""
    if not massing.levels:
        return f"- {massing.building}: nothing can be built (height {metres(massing.max_height_m)})"
    stacked = "" if len(massing.levels) == 1 else f"; levels {describe_levels(massing.levels)}"
    return (
        f"- {massing.building}: ground {area(massing.footprint_area_m2)}, height "
        f"{metres(massing.max_height_m)}, volume {volume(massing.volume_m3)}{stacked}"
    )


def _layout(layout: Layout) -> str:
    """Describe the layout choices in a few words."""
    heights = (
        ", ".join(
            f"{label} {metres(height)}"
            for label, height in zip(layout.order, layout.heights_m, strict=True)
        )
        if layout.heights_m
        else "the maximums"
    )
    windows = "yes" if layout.facing_windows else "no"
    return (
        f"cut {layout.cut}, first share {number(layout.first_share, 2)}, order "
        f"{' then '.join(layout.order)}, facing windows {windows}, heights {heights}"
    )


def _scenario(title: str, scenario: Scenario) -> str:
    """Describe one scenario: its footprint, buildings, fit, warnings and assumptions."""
    lines = [
        f"{title}: ground footprint after setbacks {area(scenario.footprint_area_m2)}; "
        f"the buildings {'fit' if scenario.fits else 'DO NOT FIT'}",
        *(_building(massing) for massing in scenario.buildings),
        f"- total volume: {volume(scenario.total_volume_m3)}",
    ]
    lines += [f"- WARNING: {warning}" for warning in scenario.warnings]
    lines += [f"- assumption: {assumption}" for assumption in scenario.assumptions]
    return "\n".join(lines)


def describe_envelope(study: EnvelopeStudy) -> str:
    """Write the envelope figures as short text, for the model that submitted or reports them.

    Args:
        study: The computed envelope.

    Returns:
        The site and green areas, then each bound and the proposal: per building the ground area,
        height and volume (and the levels when setbacks grow with the height), whether the
        buildings fit, the warnings and the assumptions.
    """
    green = "not set" if study.min_green_area_m2 is None else area(study.min_green_area_m2)
    blocks = [
        f"Site area: {area(study.site_area_m2)}; minimum green area: {green}",
        *(_scenario(f"Bound {BOUND_TITLES[bound.name]}", bound) for bound in study.bounds),
        _scenario(f"Proposal ({_layout(study.layout)})", study.proposal),
    ]
    if study.open_points:
        blocks.append(
            "Open points:\n" + "\n".join(f"- {point.question}" for point in study.open_points)
        )
    return "\n\n".join(blocks)
