from collections.abc import Iterator, Mapping

from pydantic import BaseModel

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
