from collections.abc import Iterator, Mapping

from pydantic import BaseModel, JsonValue

from agent.contracts.evidence import Citation


def collect_citations(model: BaseModel) -> tuple[tuple[str, Citation], ...]:
    """List every citation held anywhere in a model, with its dotted path.

    Fields are walked in declaration order, through nested models, lists, tuples and dicts. A
    citation is not descended into.

    Args:
        model: Any pydantic model, typically a ``Study``.

    Returns:
        ``(path, citation)`` pairs, e.g. ``("envelope.max_height_m.citations.0", citation)``.
    """
    return tuple(_walk(model, ()))


def _walk(value: object, path: tuple[str, ...]) -> Iterator[tuple[str, Citation]]:
    """Yield the citations found in ``value``, located under ``path``."""
    if isinstance(value, Citation):
        yield ".".join(path), value
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from _walk(getattr(value, name), (*path, name))
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield from _walk(item, (*path, str(key)))
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            yield from _walk(item, (*path, str(index)))


def collect_json_citations(value: JsonValue, path: str) -> Iterator[tuple[str, Citation]]:
    """List every citation held in JSON data, such as a stored artifact, with its dotted path.

    A citation is any object with a ``quote`` and a ``source_kind``; it is not descended into.

    Args:
        value: JSON data, e.g. a contract dumped with ``model_dump(mode="json")``.
        path: Dotted path of ``value`` itself, prefixed to the paths found inside it.

    Yields:
        ``(path, citation)`` pairs, e.g. ``("zone.ambiguities.0.citations.0", citation)``.
    """
    if isinstance(value, dict):
        if "quote" in value and "source_kind" in value:
            yield path, Citation.model_validate(value)
            return
        items = list(value.items())
    elif isinstance(value, list):
        items = [(str(index), item) for index, item in enumerate(value)]
    else:
        return
    for key, item in items:
        yield from collect_json_citations(item, f"{path}.{key}")
