import math
from collections.abc import Sequence

from agent.contracts.evidence import Ambiguity, Rule
from agent.contracts.findings.site import Site
from agent.contracts.findings.zone import ZoneFindings
from agent.contracts.geometry import Boundary, BoundaryKind
from agent.contracts.study import Regime
from agent.runtime.report.citations import CitationIndex
from agent.runtime.report.markdown import area, bullets, metres, number, one_line, table


def _with_refs(text: str, refs: str) -> str:
    """Append citation references to a text when there are any."""
    return f"{text} {refs}" if refs else text


def _limits(boundaries: Sequence[Boundary]) -> str:
    """Render the number and total length of the site's edges of each kind."""
    rows = []
    for kind in BoundaryKind:
        edges = [boundary for boundary in boundaries if boundary.kind is kind]
        length = sum(math.dist(edge.start, edge.end) for edge in edges)
        if edges:
            rows.append((kind.value, str(len(edges)), metres(length)))
    return table(("Kind", "Edges", "Total length"), rows)


def _public_land(site: Site) -> str:
    """Render the neighbouring parcels the surveyor declared public land, if any."""
    declared = site.choice.public_parcels
    items = (f"{p.id} (declared by the surveyor): {one_line(p.reason)}" for p in declared)
    return f"\n\n### Public land\n\n{bullets(items, empty='')}" if declared else ""


def site_section(site: Site, boundaries: Sequence[Boundary], index: CitationIndex) -> str:
    """Render the site: parcels, the surveyor's choice, public land, limits and sources.

    Args:
        site: Site built from the surveyor's parcel choice.
        boundaries: The site's edges labelled road / side / rear by the gate.
        index: Citation numbering of the report.

    Returns:
        The ``Site`` section.
    """
    facts = bullets(
        (f"Address: {one_line(site.address)}", f"Site area: {area(site.area_m2)}"), empty=""
    )
    parcels = table(
        ("Parcel", "Area (m²)"),
        ((parcel.id, number(parcel.area_m2, 1)) for parcel in site.parcels),
    )
    assumptions = bullets(site.choice.assumptions, empty="None stated.")
    sources = bullets(
        (f"{index.refs((citation,))}: {one_line(citation.quote)}" for citation in site.citations),
        empty="None.",
    )
    return (
        f"## Site\n\n{facts}\n\n### Parcels\n\n{parcels}"
        f"\n\n### Parcel choice\n\n{site.choice.rationale.strip()}{_public_land(site)}"
        f"\n\n### Assumptions\n\n{assumptions}"
        f"\n\n### Limits\n\n{_limits(boundaries)}"
        f"\n\n### Geometric sources\n\n{sources}"
    )


def _rule_items(rules: Sequence[Rule], index: CitationIndex) -> list[str]:
    """Render rules as ``**topic**: text [refs]`` list items."""
    return [
        _with_refs(f"**{rule.topic}**: {rule.text}", index.refs(rule.citations)) for rule in rules
    ]


def regime_section(regime: Regime, zone: ZoneFindings, index: CitationIndex) -> str:
    """Render the zone, the zoning plan reading, the applying legend items and the OAP.

    Args:
        regime: Regulatory regime of the study.
        zone: What the zoning analyst read on the plan.
        index: Citation numbering of the report.

    Returns:
        The ``Regulatory regime`` section.
    """
    zone_line = _with_refs(f"Zone: **{regime.zone}**", index.refs(regime.citations))
    applying = (
        table(("Legend item", "Note"), ((item.item, item.note) for item in regime.overlays))
        if regime.overlays
        else "No legend item applies to the site."
    )
    others = [item.item for item in zone.overlays if not item.applies]
    if others:
        applying += f"\n\nChecked on the plan, not applying: {'; '.join(others)}."
    oap = "OAP applicable: **yes**" if regime.oap_applicable else "OAP applicable: **no**"
    prescriptions = bullets(_rule_items(regime.oap_prescriptions, index), empty="")
    oap_block = f"{oap}\n\n{prescriptions}" if prescriptions else oap
    return (
        f"## Regulatory regime\n\n{zone_line}"
        f"\n\n### Zoning plan reading\n\nZone read on the plan: **{zone.zone}**. "
        f"{one_line(zone.rationale)}"
        f"\n\n### Applying legend items\n\n{applying}\n\n### OAP\n\n{oap_block}"
    )


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
