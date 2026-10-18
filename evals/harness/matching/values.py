"""Value normalisation and comparison for expected answers (``evals/README.md``§4)."""

import math
import re

from pydantic import JsonValue

from agent.adapters.corpus.text import fold
from evals.harness.extract import as_text

type Scalar = str | float | bool | None
type Normal = Scalar | frozenset[Scalar]
"""A normalised value: numbers as floats, strings stripped and case-folded, lists as sets."""

type Raw = JsonValue | tuple[JsonValue, ...]

_QUANTITY = re.compile(r"^([-+]?\d+(?:[.,]\d+)?)\s*(%|m²|m2|m³|m3|m)?$")
_PERCENT = 100
_EXACT = 1e-9
"""Relative tolerance of an exact match, absorbing float rounding only (0.1 * 3 vs 0.3)."""


def normalise(value: Raw) -> Normal:
    """Bring a value to the form it is compared in.

    Numbers become floats; a string holding a number with a unit is read as that number,
    ``%`` dividing it by 100 (``"20 %"`` is 0.2); other strings are stripped and case-folded
    (enum members are compared by value); lists become sets of normalised elements; ``None``,
    "not regulated", stays ``None``.

    Args:
        value: A value from an item or an output.

    Returns:
        The normalised value.
    """
    if isinstance(value, list | tuple):
        return frozenset(_scalar(element) for element in value)
    return _scalar(value)


def _scalar(value: JsonValue) -> Scalar:
    """Normalise one element; nested objects compare by their JSON text."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        return _text(value)
    return as_text(value).casefold()


def _text(value: str) -> Scalar:
    """Read a string as a number with an optional unit, else as folded-case text."""
    text = " ".join(value.split())
    quantity = _QUANTITY.match(text)
    if quantity is None:
        return text.casefold()
    number = float(quantity[1].replace(",", "."))
    return number / _PERCENT if quantity[2] == "%" else number


def same(actual: Normal, expected: Normal, tolerance: float | None = None) -> bool:
    """Compare two normalised values.

    Args:
        actual: Value from the output.
        expected: Value from the item.
        tolerance: Relative tolerance on numbers (0.02 = ±2 %); exact otherwise.

    Returns:
        Whether they match. Sets match as sets, without tolerance.
    """
    if isinstance(actual, bool) or isinstance(expected, bool):
        return actual is expected
    if isinstance(actual, float) and isinstance(expected, float):
        return math.isclose(actual, expected, rel_tol=tolerance or _EXACT, abs_tol=_EXACT)
    return actual == expected


def flatten(values: list[JsonValue]) -> list[JsonValue]:
    """Spread the elements of list values, keeping other values as they are.

    Args:
        values: Resolved values.

    Returns:
        The values, each list replaced by its elements.
    """
    return [item for value in values for item in (value if isinstance(value, list) else [value])]


def label(text: str) -> str:
    """Fold a legend label for comparison: case, accents, apostrophes and spacing ignored.

    Args:
        text: A label as printed or as reported.

    Returns:
        The folded label.
    """
    return " ".join(fold(text).split())
