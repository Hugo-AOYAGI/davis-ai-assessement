"""Whether the elements a key resolves to meet a fact's expectation (answer-correct)."""

from collections.abc import Callable, Sequence
from typing import NamedTuple

from pydantic import JsonValue

from evals.harness.extract import Resolved, as_text
from evals.harness.items import KeyFact, Scalar
from evals.harness.matching.values import Normal, flatten, label, normalise, same


class Outcome(NamedTuple):
    """Answer-correctness of one fact, with what was found."""

    correct: bool
    detail: str


def evaluate(fact: KeyFact, elements: Sequence[Resolved]) -> Outcome:
    """Check the resolved elements against the fact's single expectation.

    - ``expect`` / ``any_of``: at least one element, and one accepted value that every element
      matches (several elements disagreeing is hedging, hence wrong);
    - ``expect_none_of``: no element (nor list item) matches a listed value;
    - ``at_least``: count of elements, list values counting their items;
    - ``present`` / ``absent``: legend items reported with ``applies: true`` (strings count as
      applying), labels compared ignoring case and accents.

    Args:
        fact: The expected answer.
        elements: What its key resolves to in the output.

    Returns:
        Whether the fact is answer-correct, and a one-line detail.
    """
    values = [element.value for element in elements]
    given = fact.model_fields_set
    checks: dict[str, Callable[[], Outcome]] = {
        "expect": lambda: _one_of(values, (fact.expect,), fact.tolerance),
        "any_of": lambda: _one_of(values, fact.any_of or (), fact.tolerance),
        "expect_none_of": lambda: _none_of(values, fact.expect_none_of or ()),
        "at_least": lambda: _at_least(values, fact.at_least or 0),
    }
    for kind, check in checks.items():
        if kind in given:
            return check()
    return _legend(values, fact.present or (), fact.absent or ())


def _one_of(
    values: list[JsonValue],
    accepted: Sequence[Scalar | tuple[Scalar, ...]],
    tolerance: float | None,
) -> Outcome:
    """Correct when some accepted value is matched by every resolved value."""
    found = _show(values)
    if not values:
        return Outcome(False, "nothing resolved")
    actual = [normalise(value) for value in values]
    for option in accepted:
        expected = normalise(option)
        if all(same(value, expected, tolerance) for value in actual):
            return Outcome(True, f"got {found}")
    return Outcome(False, f"got {found}, expected {_show(list(accepted))}")


def _none_of(values: list[JsonValue], forbidden: Sequence[Scalar]) -> Outcome:
    """Correct when no resolved value, nor any item of a resolved list, is forbidden."""
    banned: list[Normal] = [normalise(value) for value in forbidden]
    hits = [
        value for value in flatten(values) if any(same(normalise(value), bad) for bad in banned)
    ]
    if hits:
        return Outcome(False, f"forbidden value(s) {_show(hits)}")
    return Outcome(True, f"got {_show(values)}")


def _at_least(values: list[JsonValue], minimum: int) -> Outcome:
    """Correct when the resolved elements, list items counted one by one, reach ``minimum``."""
    count = len(flatten(values))
    return Outcome(count >= minimum, f"{count} element(s), at least {minimum} expected")


def _legend(values: list[JsonValue], present: Sequence[str], absent: Sequence[str]) -> Outcome:
    """Correct when every ``present`` label applies and no ``absent`` label does."""
    applying = {label(name) for name in _applying(flatten(values))}
    missing = [name for name in present if label(name) not in applying]
    wrong = [name for name in absent if label(name) in applying]
    problems = [f"missing {name!r}" for name in missing] + [
        f"wrongly applies {name!r}" for name in wrong
    ]
    if problems:
        return Outcome(False, "; ".join(problems))
    return Outcome(True, f"{len(applying)} legend item(s) apply")


def _applying(items: list[JsonValue]) -> list[str]:
    """Labels of the legend items reported as applying (``LegendItem`` objects or labels)."""
    labels: list[str] = []
    for item in items:
        if isinstance(item, str):
            labels.append(item)
        elif isinstance(item, dict) and item.get("applies", True) is True:
            labels.append(as_text(item.get("item")))
    return labels


def _show(values: Sequence[JsonValue | Scalar | tuple[Scalar, ...]]) -> str:
    """Render values for a detail line."""
    return "[" + ", ".join(as_text(list(v) if isinstance(v, tuple) else v) for v in values) + "]"
