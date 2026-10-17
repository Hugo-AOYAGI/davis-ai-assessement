"""Apply a model's corrections to a rejected submission, given as path edits."""

import copy
from collections import defaultdict
from collections.abc import Mapping, Sequence
from itertools import combinations

from pydantic import JsonValue

from agent.contracts.revision import Edit

type Segment = str | int
"""An object key or a list index."""

type Location = tuple[Segment, ...]
"""A path resolved against the draft: keys for objects, indices for lists."""

_ROOT = "the result"


class EditError(Exception):
    """Edits that cannot be applied; nothing was changed."""

    def __init__(self, errors: Sequence[str]) -> None:
        """Keep the errors to report.

        Args:
            errors: One ``path: message`` line per bad edit, written for the model.
        """
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


class _PathError(Exception):
    """A path that does not resolve in the draft."""


def apply_edits(draft: Mapping[str, JsonValue], edits: Sequence[Edit]) -> dict[str, JsonValue]:
    """Apply edits to a copy of the draft, every path referring to the draft as given.

    Edits with a value come first: each replaces the value at its path, adds a missing object
    key, or appends when its index is the list's length (several appends to one list take the
    following indices). Removals follow, in descending path order, so that removing an item
    never shifts the index another edit named. Edits may not overlap (one path inside another).

    Args:
        draft: The rejected submission, as JSON.
        edits: The corrections.

    Returns:
        The edited copy; the draft itself is left untouched.

    Raises:
        EditError: With one line per bad edit (no value nor removal, both, overlapping or
            unresolvable path); nothing is applied.
    """
    root: dict[str, JsonValue] = copy.deepcopy(dict(draft))
    errors = _shape_errors(edits)
    located: list[tuple[Edit, Location]] = []
    for edit in edits:
        try:
            located.append((edit, _locate(root, edit.path, open_end=edit.sets)))
        except _PathError as error:
            errors.append(f"{edit.path}: {error}")
    errors += _overlap_errors(located) + _append_errors(root, located)
    if errors:
        raise EditError(errors)
    for edit, location in sorted(
        ((edit, location) for edit, location in located if edit.sets), key=lambda item: item[1]
    ):
        _put(root, location, copy.deepcopy(edit.value))
    for location in sorted((location for edit, location in located if not edit.sets), reverse=True):
        _delete(root, location)
    return root


def _shape_errors(edits: Sequence[Edit]) -> list[str]:
    """Report edits carrying neither a value nor a removal, or both."""
    errors: list[str] = []
    for edit in edits:
        if edit.sets and edit.remove:
            errors.append(f"{edit.path}: give a value or remove: true, not both")
        elif not edit.sets and not edit.remove:
            errors.append(f"{edit.path}: give a value, or remove: true")
    return errors


def _overlap_errors(located: Sequence[tuple[Edit, Location]]) -> list[str]:
    """Report overlaps using resolved indices, so ``0`` and ``00`` name the same item."""
    errors: list[str] = []
    for (first, a), (second, b) in combinations(located, 2):
        if a == b:
            errors.append(f"{first.path}: edited twice")
        elif a[: len(b)] == b or b[: len(a)] == a:
            inner, outer = (first, second) if len(a) > len(b) else (second, first)
            errors.append(f"{inner.path}: inside {outer.path}, which another edit changes")
    return errors


def _locate(root: JsonValue, path: str, *, open_end: bool) -> Location:
    """Resolve a dotted path; with ``open_end`` its last step may be a new key or an append."""
    segments = path.split(".")
    location: list[Segment] = []
    node = root
    for depth, segment in enumerate(segments):
        where = ".".join(segments[:depth]) or _ROOT
        last = depth == len(segments) - 1
        step, node = _step(node, segment, where, open_end=open_end and last)
        location.append(step)
    return tuple(location)


def _step(
    node: JsonValue, segment: str, where: str, *, open_end: bool
) -> tuple[Segment, JsonValue]:
    """Take one path step from ``node`` (found at ``where``)."""
    if not segment:
        msg = f"empty step after {where}"
        raise _PathError(msg)
    if isinstance(node, dict):
        if segment not in node and not open_end:
            msg = f"{where} has no field '{segment}'"
            raise _PathError(msg)
        return segment, node.get(segment)
    if isinstance(node, list):
        if not (segment.isascii() and segment.isdigit()):
            msg = f"{where} is a list: '{segment}' is not an index"
            raise _PathError(msg)
        index = int(segment)
        if index < len(node):
            return index, node[index]
        if not open_end:
            msg = f"{where} has {len(node)} items, no index {index}"
            raise _PathError(msg)
        return index, None
    msg = f"{where} is a value, not an object or a list"
    raise _PathError(msg)


def _append_errors(root: JsonValue, located: Sequence[tuple[Edit, Location]]) -> list[str]:
    """Require appends to one list to take the indices right after its last item."""
    appends: defaultdict[Location, list[tuple[int, str]]] = defaultdict(list)
    for edit, location in located:
        parent, index = _get(root, location[:-1]), location[-1]
        if isinstance(parent, list) and isinstance(index, int) and index >= len(parent):
            appends[location[:-1]].append((index, edit.path))
    errors: list[str] = []
    for parent_location, indices in appends.items():
        parent = _get(root, parent_location)
        size = len(parent) if isinstance(parent, list) else 0
        for expected, (index, path) in enumerate(sorted(indices), start=size):
            if index != expected:
                where = path.rpartition(".")[0] or _ROOT
                errors.append(
                    f"{path}: {where} has {size} items, append at index {expected}, not {index}"
                )
    return errors


def _get(root: JsonValue, location: Location) -> JsonValue:
    """Return the value at a resolved location."""
    node = root
    for step in location:
        node = _child(node, step)
    return node


def _child(node: JsonValue, step: Segment) -> JsonValue:
    """Return the value under one key or index of a resolved location."""
    if isinstance(node, list) and isinstance(step, int):
        return node[step]
    if isinstance(node, dict) and isinstance(step, str):
        return node[step]
    msg = f"cannot step into {type(node).__name__} with {step!r}"
    raise TypeError(msg)


def _put(root: JsonValue, location: Location, value: JsonValue) -> None:
    """Set, add or append ``value`` at a resolved location."""
    parent, step = _get(root, location[:-1]), location[-1]
    if isinstance(parent, list) and isinstance(step, int):
        if step == len(parent):
            parent.append(value)
        else:
            parent[step] = value
    elif isinstance(parent, dict) and isinstance(step, str):
        parent[step] = value


def _delete(root: JsonValue, location: Location) -> None:
    """Remove the value at a resolved location."""
    parent, step = _get(root, location[:-1]), location[-1]
    if isinstance(parent, list) and isinstance(step, int):
        del parent[step]
        return
    if isinstance(parent, dict) and isinstance(step, str):
        del parent[step]
