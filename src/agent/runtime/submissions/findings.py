"""Consistency between a final study and the zoning findings it relies on."""

from agent.contracts.findings.zone import ZoneFindings
from agent.contracts.study import Study


def findings_errors(study: Study, zone: ZoneFindings) -> list[str]:
    """Require the zone, applying overlays and unresolved readings to survive synthesis.

    Overlay wording is matched by its legend label. The explanatory note may be rewritten.
    Questions and zone codes tolerate differences in case and whitespace.

    Args:
        study: The submitted study.
        zone: Delivered zoning findings.

    Returns:
        Actionable field errors, empty when the findings are preserved.
    """
    errors = []
    if _fold(study.regime.zone) != _fold(zone.zone):
        errors.append(f"regime.zone: must match zoning findings {zone.zone!r}.")
    expected = {_fold(item.item) for item in zone.overlays if item.applies}
    actual = {_fold(item.item) for item in study.regime.overlays if item.applies}
    if actual != expected or any(not item.applies for item in study.regime.overlays):
        labels = [item.item for item in zone.overlays if item.applies]
        errors.append(f"regime.overlays: must contain exactly the applying zoning items: {labels}.")
    answered = {_fold(point.question) for point in study.ambiguities}
    errors.extend(
        f"ambiguities: retain zoning question {point.question!r} and explain its resolution."
        for point in zone.ambiguities
        if _fold(point.question) not in answered
    )
    return errors


def _fold(text: str) -> str:
    """Normalize case and whitespace without changing the meaning of a label or question."""
    return " ".join(text.split()).casefold()
