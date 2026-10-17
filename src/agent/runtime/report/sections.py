from collections.abc import Sequence

from agent.contracts.evidence import Ambiguity, Rule
from agent.contracts.findings.regulation import Admissibility, ParkingBasis, ParkingRule
from agent.contracts.findings.site import SiteContext
from agent.contracts.study import Regime
from agent.runtime.report.citations import CitationIndex
from agent.runtime.report.markdown import area, bullets, number, one_line, table

BASIS_LABELS = {
    ParkingBasis.FLOOR_AREA_M2: "m² of floor area",
    ParkingBasis.UNIT: "unit",
    ParkingBasis.OTHER: "(other basis)",
}


def _with_refs(text: str, refs: str) -> str:
    """Append citation references to a text when there are any."""
    return f"{text} {refs}" if refs else text


def site_section(site: SiteContext, index: CitationIndex) -> str:
    """Render the site: address, parcels, area, method, assumptions and geometric sources.

    Args:
        site: Site context accepted by the gate.
        index: Citation numbering of the report.

    Returns:
        The ``Site`` section.
    """
    facts = bullets(
        (
            f"Address: {one_line(site.address)}",
            f"Site area: {area(site.area_m2)}",
            f"Identification method: {site.method}",
        ),
        empty="",
    )
    parcels = table(
        ("Parcel", "Area (m²)"),
        ((parcel.id, number(parcel.area_m2, 1)) for parcel in site.parcels),
    )
    assumptions = bullets(site.assumptions, empty="None stated.")
    sources = bullets(
        (f"{index.refs((citation,))}: {one_line(citation.quote)}" for citation in site.citations),
        empty="None.",
    )
    return (
        f"## Site\n\n{facts}\n\n### Parcels\n\n{parcels}\n\n### Assumptions\n\n{assumptions}"
        f"\n\n### Geometric sources\n\n{sources}"
    )


def _rule_items(rules: Sequence[Rule], index: CitationIndex) -> list[str]:
    """Render rules as ``**topic**: text [refs]`` list items."""
    return [
        _with_refs(f"**{rule.topic}**: {rule.text}", index.refs(rule.citations)) for rule in rules
    ]


def regime_section(regime: Regime, index: CitationIndex) -> str:
    """Render the zone, the overlays checked and the OAP.

    Args:
        regime: Regulatory regime of the study.
        index: Citation numbering of the report.

    Returns:
        The ``Regulatory regime`` section.
    """
    zone = _with_refs(f"Zone: **{regime.zone}**", index.refs(regime.citations))
    overlays = (
        table(
            ("Overlay", "Applies", "Rationale", "Sources"),
            (
                (o.name, "yes" if o.applies else "no", o.rationale, index.refs(o.citations))
                for o in regime.overlays
            ),
        )
        if regime.overlays
        else "No overlay checked."
    )
    oap = "OAP applicable: **yes**" if regime.oap_applicable else "OAP applicable: **no**"
    prescriptions = bullets(_rule_items(regime.oap_prescriptions, index), empty="")
    oap_block = f"{oap}\n\n{prescriptions}" if prescriptions else oap
    return f"## Regulatory regime\n\n{zone}\n\n### Overlays\n\n{overlays}\n\n### OAP\n\n{oap_block}"


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


def conditions_section(rules: Sequence[Rule], index: CitationIndex) -> str:
    """Render the other feasibility conditions, one item per rule.

    Args:
        rules: Conditions of the study.
        index: Citation numbering of the report.

    Returns:
        The ``Other conditions`` section.
    """
    items = bullets(_rule_items(rules, index), empty="No other condition recorded.")
    return f"## Other conditions\n\n{items}"


def _ambiguity(position: int, ambiguity: Ambiguity, index: CitationIndex) -> str:
    """Render one ambiguity as a numbered item with its details."""
    details = [
        f"Options: {'; '.join(ambiguity.options)}" if ambiguity.options else "",
        f"Chosen: {ambiguity.chosen}",
        f"Rationale: {ambiguity.rationale}",
        f"Resolved by: {ambiguity.resolved_by.value}",
        f"Sources: {index.refs(ambiguity.citations)}" if ambiguity.citations else "",
    ]
    lines = "\n".join(f"   - {one_line(detail)}" for detail in details if detail)
    return f"{position}. **{one_line(ambiguity.question)}**\n{lines}"


def ambiguities_section(ambiguities: Sequence[Ambiguity], index: CitationIndex) -> str:
    """Render each ambiguity: question, options, choice, rationale and who settled it.

    Args:
        ambiguities: Ambiguities of the study.
        index: Citation numbering of the report.

    Returns:
        The ``Ambiguities`` section.
    """
    if not ambiguities:
        return "## Ambiguities\n\nNone recorded."
    items = "\n".join(
        _ambiguity(position, ambiguity, index)
        for position, ambiguity in enumerate(ambiguities, start=1)
    )
    return f"## Ambiguities\n\n{items}"
