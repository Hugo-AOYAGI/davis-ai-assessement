from collections.abc import Callable, Sequence

from agent.contracts.envelope import Distance, EnvelopeRules, EnvelopeStudy
from agent.contracts.evidence import Limit
from agent.contracts.geometry import Scenario
from agent.contracts.study import Admissibility, ParkingBasis, ParkingRule
from agent.runtime.geometry.envelope.summary import BOUND_TITLES, describe_levels, volume
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


def _value(limit: Limit, fmt: Callable[[float], str]) -> str:
    """Format a limit's value, or ``not set`` when the documents set none."""
    return NOT_SET if limit.value is None else fmt(limit.value)


def _distance(distance: Distance | None) -> str:
    """Render a distance as its formula and rule, e.g. ``max(4 m, 0.5 x H): H/2, min 4 m``."""
    if distance is None:
        return NONE
    terms = [metres(distance.min_m)] if distance.min_m is not None else []
    terms += (
        [f"{number(distance.height_ratio, 3)} x H"] if distance.height_ratio is not None else []
    )
    formula = terms[0] if len(terms) == 1 else f"max({', '.join(terms)})"
    return f"{formula}: {distance.rule}"


def _distance_refs(distances: Sequence[Distance | None], index: CitationIndex) -> str:
    """Render the references of several distances."""
    return index.refs(c for distance in distances if distance for c in distance.citations)


def _rules(rules: EnvelopeRules, index: CitationIndex) -> str:
    """Render the setbacks, the building limits and the other limits the envelope rests on."""
    setbacks = table(
        ("Limit", "On the limit", "With windows", "Without windows", "Sources"),
        (
            (
                rule.kind.value,
                "allowed" if rule.on_limit_allowed else "not allowed",
                _distance(rule.with_windows),
                _distance(rule.without_windows),
                _distance_refs((rule.with_windows, rule.without_windows), index),
            )
            for rule in rules.setbacks
        ),
    )
    buildings = table(
        ("Building", "Maximum height", "Maximum storeys", "Rule", "Sources"),
        (
            (
                entry.building,
                _value(entry.max_height_m, metres),
                _value(entry.max_storeys, lambda value: number(value, 1)),
                entry.max_height_m.rule,
                index.refs((*entry.max_height_m.citations, *entry.max_storeys.citations)),
            )
            for entry in rules.buildings
        ),
    )
    spacings = (
        ("Spacing, facing windows", rules.spacing_with_windows),
        ("Spacing, no facing window", rules.spacing_without_windows),
    )
    ratios = (
        ("Maximum footprint ratio", rules.max_footprint_ratio),
        ("Minimum green ratio", rules.min_green_ratio),
    )
    others = table(
        ("Limit", "Value", "Sources"),
        (
            *((label, _distance(d), _distance_refs((d,), index)) for label, d in spacings),
            *(
                (label, f"{_value(limit, percent)}: {limit.rule}", index.refs(limit.citations))
                for label, limit in ratios
            ),
        ),
    )
    return "\n\n".join((setbacks, buildings, others))


def _massings(scenario: Scenario) -> str:
    """Render one row per building of a scenario."""
    rows = (
        (
            massing.building,
            area(massing.footprint_area_m2),
            metres(massing.max_height_m),
            volume(massing.volume_m3),
            describe_levels(massing.levels),
            "yes" if massing.levels and scenario.fits else "no",
        )
        for massing in scenario.buildings
    )
    headers = ("Building", "Ground area", "Height", "Volume", "Levels", "Fits")
    lines = (
        f"Ground footprint after setbacks: {area(scenario.footprint_area_m2)}. "
        f"Total volume: {volume(scenario.total_volume_m3)}."
    )
    warnings = bullets((f"**Warning**: {line}" for line in scenario.warnings), empty="")
    return "\n\n".join(block for block in (lines, table(headers, rows), warnings) if block)


def _proposal(envelope: EnvelopeStudy, index: CitationIndex) -> str:
    """Render the proposal: its massings, the layout's reasons and its OAP choices."""
    layout = envelope.layout
    choices = bullets(
        (
            f"**{choice.prescription.topic}**: {choice.prescription.text} Followed by: "
            f"{choice.how} {index.refs(choice.prescription.citations)}".rstrip()
            for choice in layout.oap
        ),
        empty="None recorded.",
    )
    windows = "with" if layout.facing_windows else "without"
    return (
        f"Cut {layout.cut.replace('_', ' ')}, first share {percent(layout.first_share)}, "
        f"order {', '.join(layout.order)}, facing facades {windows} windows."
        f"\n\n{_massings(envelope.proposal)}\n\n**Reasons**: {layout.reasons.strip()}"
        f"\n\n**OAP prescriptions followed**:\n\n{choices}"
    )


def envelope_section(envelope: EnvelopeStudy | None, index: CitationIndex) -> str:
    """Render the envelope: its rules, a table per bound, the proposal and the assumptions.

    Args:
        envelope: The recomputed envelope, absent for a wholly prohibited program.
        index: Citation numbering of the report.

    Returns:
        The ``Envelope`` section.
    """
    if envelope is None:
        return "## Envelope\n\nNo envelope computed: every proposed building use is prohibited."
    green = NONE if envelope.min_green_area_m2 is None else area(envelope.min_green_area_m2)
    bounds = "\n\n".join(
        f"### Bound: {BOUND_TITLES[bound.name]}\n\n{_massings(bound)}" for bound in envelope.bounds
    )
    notes = (*envelope.proposal.assumptions, *(a for b in envelope.bounds for a in b.assumptions))
    assumptions = bullets(dict.fromkeys(notes), empty="None stated.")
    return (
        f"## Envelope\n\nSite area: {area(envelope.site_area_m2)}. Minimum green area: {green}."
        f"\n\n### Rules\n\n{_rules(envelope.rules, index)}\n\n{bounds}"
        f"\n\n### Proposal\n\n{_proposal(envelope, index)}"
        f"\n\n### Envelope assumptions\n\n{assumptions}"
    )
