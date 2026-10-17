from collections.abc import Callable, Sequence

from agent.contracts.evidence import Limit
from agent.contracts.geometry import Envelope, EnvelopeParameters
from agent.contracts.study import Admissibility, ParkingBasis, ParkingRule
from agent.runtime.report.citations import CitationIndex
from agent.runtime.report.markdown import NONE, area, bullets, metres, number, percent, table

NOT_SET = "not set"
BASIS_LABELS = {
    ParkingBasis.FLOOR_AREA_M2: "m² of floor area",
    ParkingBasis.UNIT: "unit",
    ParkingBasis.OTHER: "(other basis)",
}


def admissibility_section(entries: Sequence[Admissibility], index: CitationIndex) -> str:
    """Render one row per building with its destination and verdict.

    Args:
        entries: Admissibility of each building of the program.
        index: Citation numbering of the report.

    Returns:
        The ``Program admissibility`` section.
    """
    rows = (
        (
            entry.building,
            entry.stated_use,
            entry.destination,
            entry.verdict.value,
            "\n".join(entry.conditions) or "none",
            index.refs(entry.citations),
        )
        for entry in entries
    )
    headers = ("Building", "Stated use", "Destination", "Verdict", "Conditions", "Sources")
    return f"## Program admissibility\n\n{table(headers, rows)}"


def _ratio(rule: ParkingRule) -> str:
    """Render a parking ratio, e.g. ``1 space per 150 m² of floor area``."""
    spaces = number(rule.spaces, 2)
    noun = "space" if rule.spaces == 1 else "spaces"
    per = "" if rule.per == 1 else f"{number(rule.per, 2)} "
    return f"{spaces} {noun} per {per}{BASIS_LABELS[rule.basis]}"


def parking_section(rules: Sequence[ParkingRule], index: CitationIndex) -> str:
    """Render the parking requirement of each use.

    Args:
        rules: Parking rules of the study.
        index: Citation numbering of the report.

    Returns:
        The ``Parking`` section.
    """
    if not rules:
        return "## Parking\n\nNo parking requirement recorded."
    rows = ((rule.use, _ratio(rule), rule.rule, index.refs(rule.citations)) for rule in rules)
    return f"## Parking\n\n{table(('Use', 'Ratio', 'Rule', 'Sources'), rows)}"


def _storeys(value: float) -> str:
    """Format a number of storeys."""
    return number(value, 1)


def _volume(value: float) -> str:
    """Format a volume in cubic metres."""
    return f"{number(value, 1)} m³"


def _value(limit: Limit, fmt: Callable[[float], str]) -> str:
    """Format a limit's value, or ``not set`` when the documents set none."""
    return NOT_SET if limit.value is None else fmt(limit.value)


def _optional(value: float | None, fmt: Callable[[float], str]) -> str:
    """Format a computed value, or a dash when it could not be computed."""
    return NONE if value is None else fmt(value)


def _parameters(parameters: EnvelopeParameters, index: CitationIndex) -> str:
    """Render the rule values the envelope is computed from."""
    limits: tuple[tuple[str, Limit, Callable[[float], str]], ...] = (
        ("Setback from road limits", parameters.setback_road_m, metres),
        ("Setback from side limits", parameters.setback_side_m, metres),
        ("Setback from rear limits", parameters.setback_rear_m, metres),
        ("Maximum height", parameters.max_height_m, metres),
        ("Maximum storeys", parameters.max_storeys, _storeys),
        ("Maximum footprint ratio", parameters.max_footprint_ratio, percent),
        ("Minimum green ratio", parameters.min_green_ratio, percent),
    )
    rows = (
        (label, _value(limit, fmt), limit.rule, index.refs(limit.citations))
        for label, limit, fmt in limits
    )
    return table(("Parameter", "Value", "Rule", "Sources"), rows)


def _computed(envelope: Envelope) -> str:
    """Render the values computed by the gate."""
    footprint = area(envelope.footprint_area_m2)
    if envelope.footprint is None:
        footprint = f"{footprint} (nothing remains after setbacks)"
    rows = (
        ("Site area", area(envelope.site_area_m2)),
        ("Buildable footprint after setbacks", footprint),
        ("Maximum footprint area", area(envelope.max_footprint_area_m2)),
        ("Minimum green area", _optional(envelope.min_green_area_m2, area)),
        ("Maximum height", _optional(envelope.max_height_m, metres)),
        ("Maximum volume", _optional(envelope.max_volume_m3, _volume)),
    )
    return table(("Quantity", "Value"), rows)


def envelope_section(
    parameters: EnvelopeParameters, envelope: Envelope, index: CitationIndex
) -> str:
    """Render the envelope parameters, the computed envelope and its assumptions.

    Args:
        parameters: Rule values stated in the study.
        envelope: Envelope computed by the gate from the site and the parameters.
        index: Citation numbering of the report.

    Returns:
        The ``Envelope`` section.
    """
    assumptions = bullets(envelope.assumptions, empty="None stated.")
    return (
        f"## Envelope\n\n### Parameters\n\n{_parameters(parameters, index)}"
        f"\n\n### Computed envelope\n\n{_computed(envelope)}"
        f"\n\n### Envelope assumptions\n\n{assumptions}"
    )
