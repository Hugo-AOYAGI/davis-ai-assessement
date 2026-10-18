"""Resolve a fact key (``evals/README.md``§2) against an output, with the citations backing it.

Grammar: dotted field names, each optionally followed by list selectors, e.g.
``study.admissibility[building~"Jeunes Actifs"].verdict`` or ``edges[other_side=public_land]``.

- ``[field=value]`` keeps the list elements whose ``field`` equals ``value`` exactly;
- ``[field~"text"]`` keeps those whose ``field`` contains ``text``, ignoring case and accents.

A field reached through a list without a selector is read on every element, so a key may resolve
to several elements. A key ending on a list (``choice.parcel_ids``) resolves to one element whose
value is that list.
"""

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from typing import Literal, NamedTuple

from pydantic import BaseModel, JsonValue, TypeAdapter

from agent.adapters.corpus.text import fold
from agent.contracts.base import Contract
from agent.contracts.evidence import Citation, Limit

type Output = BaseModel | Mapping[str, JsonValue]
"""An output contract, or the same data as JSON."""

_NAME = re.compile(r"[A-Za-z_]\w*")
_SELECTOR = re.compile(r'\[\s*(?P<field>[A-Za-z_]\w*)\s*(?P<op>=|~)\s*(?P<value>"[^"]*"|[^\]"]*)\]')
_LIMIT_FIELDS = frozenset(Limit.model_fields)
_JSON: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


class Selector(NamedTuple):
    """A list filter: ``=`` exact value, ``~`` case- and accent-insensitive substring."""

    field: str
    op: Literal["=", "~"]
    value: str


class Segment(NamedTuple):
    """One dotted step of a key: a field name and the selectors applied to its list."""

    name: str
    selectors: tuple[Selector, ...]


class Resolved(Contract):
    """One element a key resolves to."""

    path: str
    """Dotted path of the element in the output, list indices included."""
    value: JsonValue
    """The element; for a ``Limit``, its ``value``."""
    citations: tuple[Citation, ...]
    """The ``Limit``'s own citations, otherwise those of the nearest enclosing object that has
    a ``citations`` field; empty when there is none."""


class KeyPathError(ValueError):
    """A key that does not parse, or names a field the output does not have."""


class _Node(NamedTuple):
    """A value reached while walking a key, with its location and inherited citations."""

    path: str
    value: JsonValue
    citations: tuple[Citation, ...]


def parse_key(key: str) -> tuple[Segment, ...]:
    """Parse a fact key into its segments.

    Args:
        key: E.g. ``study.admissibility[building~"Sociale"].verdict``.

    Returns:
        The segments, in order.

    Raises:
        KeyPathError: When the key does not follow the grammar.
    """
    segments: list[Segment] = []
    position = 0
    while True:
        name = _NAME.match(key, position)
        if name is None:
            msg = f"invalid key {key!r}: a field name is expected at position {position}"
            raise KeyPathError(msg)
        position = name.end()
        selectors: list[Selector] = []
        while (selector := _SELECTOR.match(key, position)) is not None:
            value = selector["value"].strip()
            op: Literal["=", "~"] = "=" if selector["op"] == "=" else "~"
            selectors.append(Selector(selector["field"], op, value.strip('"')))
            position = selector.end()
        segments.append(Segment(name.group(), tuple(selectors)))
        if position == len(key):
            return tuple(segments)
        if key[position] != ".":
            msg = f"invalid key {key!r}: '.' or '[' expected at position {position}"
            raise KeyPathError(msg)
        position += 1


def resolve(output: Output, key: str) -> list[Resolved]:
    """Resolve a key against an output.

    Args:
        output: An output contract, or its JSON form.
        key: A fact key, see the module docstring.

    Returns:
        The elements the key selects, empty when a selector matches nothing or the key runs
        through a ``null``.

    Raises:
        KeyPathError: When the key does not parse, names a field the output does not have, or
            applies a selector to something that is not a list.
    """
    data = _JSON.validate_python(
        output.model_dump(mode="json") if isinstance(output, BaseModel) else output
    )
    nodes = [_Node("", data, _citations(data, ()))]
    for segment in parse_key(key):
        nodes = [child for node in nodes for child in _step(node, segment, key)]
    return [_finish(node) for node in nodes]


def _step(node: _Node, segment: Segment, key: str) -> Iterator[_Node]:
    """Read one segment on a node, fanning out over lists."""
    if node.value is None:
        return
    if isinstance(node.value, list):
        for index, element in enumerate(node.value):
            child = _Node(_join(node.path, index), element, _citations(element, node.citations))
            yield from _step(child, segment, key)
        return
    if not isinstance(node.value, dict) or segment.name not in node.value:
        msg = f"key {key!r}: no field {segment.name!r} at {node.path or 'the root'}"
        raise KeyPathError(msg)
    value = node.value[segment.name]
    child = _Node(_join(node.path, segment.name), value, _citations(value, node.citations))
    if segment.selectors:
        yield from _select(child, segment.selectors, key)
    else:
        yield child


def _select(node: _Node, selectors: Sequence[Selector], key: str) -> Iterator[_Node]:
    """Keep the elements of a list node that pass every selector; nothing from a ``null``."""
    if node.value is None:
        return
    if not isinstance(node.value, list):
        msg = f"key {key!r}: {node.path} is not a list, it cannot take a selector"
        raise KeyPathError(msg)
    for index, element in enumerate(node.value):
        if all(_selects(element, selector, key) for selector in selectors):
            yield _Node(_join(node.path, index), element, _citations(element, node.citations))


def _selects(element: JsonValue, selector: Selector, key: str) -> bool:
    """Tell whether a list element passes a selector."""
    if not isinstance(element, dict) or selector.field not in element:
        msg = f"key {key!r}: list elements have no field {selector.field!r}"
        raise KeyPathError(msg)
    text = as_text(element[selector.field])
    if selector.op == "=":
        return text == selector.value
    return fold(selector.value) in fold(text)


def _citations(value: JsonValue, inherited: tuple[Citation, ...]) -> tuple[Citation, ...]:
    """Return the citations of ``value`` when it has a ``citations`` field, else ``inherited``."""
    citations = value.get("citations") if isinstance(value, dict) else None
    if isinstance(citations, list):
        return tuple(Citation.model_validate(item) for item in citations)
    return inherited


def _finish(node: _Node) -> Resolved:
    """Turn a reached node into a resolved element, reading a ``Limit`` as its value."""
    value = node.value
    if isinstance(value, dict) and set(value) == _LIMIT_FIELDS:
        return Resolved(
            path=_join(node.path, "value"), value=value["value"], citations=node.citations
        )
    return Resolved(path=node.path, value=value, citations=node.citations)


def _join(path: str, part: str | int) -> str:
    """Append a field name or list index to a dotted path."""
    return f"{path}.{part}" if path else str(part)


def as_text(value: JsonValue) -> str:
    """Render a JSON scalar as the text a selector or a label compares with.

    Args:
        value: Any JSON value.

    Returns:
        Strings as they are, whole floats without ``.0``, other values as JSON.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return json.dumps(value, ensure_ascii=False)
