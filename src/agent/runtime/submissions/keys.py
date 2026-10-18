"""Validate artifact keys before factories start accepting submissions."""

from collections.abc import Iterable
from string import Formatter


def placeholders(template: str, allowed: Iterable[str]) -> tuple[str, ...]:
    """Read simple named placeholders, rejecting lookups, conversions and formatting.

    Args:
        template: An artifact key template.
        allowed: Top-level fields available to fill the key.

    Returns:
        Placeholder names in their occurrence order.

    Raises:
        ValueError: If the template contains unsupported formatting or unknown fields.
    """
    allowed = frozenset(allowed)
    fields = []
    for _, field, specification, conversion in Formatter().parse(template):
        if field is None:
            continue
        if field not in allowed or bool(specification) or conversion is not None:
            msg = f"artifact {template!r} requires plain placeholders from {sorted(allowed)}"
            raise ValueError(msg)
        fields.append(field)
    return tuple(fields)
