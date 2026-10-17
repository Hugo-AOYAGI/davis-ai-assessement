"""Task texts of the component levels, written as the orchestrator writes them (playbook §2-3).

A sub-agent knows nothing but its task text, so a component item's input is rendered into the
same fields, with the same words, as the orchestrator's delegation.
"""

from collections.abc import Sequence
from string import Template

from agent.contracts.base import Contract
from evals.harness.items import DocInput, SurveyorInput, ZoningInput

type ComponentInput = SurveyorInput | ZoningInput | DocInput
"""The input of a component item."""

_LIST = ", "
_LEGEND = "; "
"""Legend labels may hold commas, so they are separated by semicolons."""


class TaskWords(Contract):
    """Words filled in where an item leaves a field empty (``eval.eval_tasks.texts``)."""

    none: str
    """An empty list (topics, legend items, facts, parcel ids)."""
    no_program: str
    """A surveyor task without a program."""
    all_documents: str
    """A doc task without a ``documents`` restriction."""


def task_text(task: ComponentInput, template: str, *, words: TaskWords, language: str) -> str:
    """Render the task text a component item's sub-agent receives.

    Args:
        task: The item's input.
        template: The level's task template (``eval.eval_tasks.templates``), with ``$`` fields.
        words: Words standing for empty fields.
        language: Language of the free text (``agent.language``), as in the playbook.

    Returns:
        The task text.

    Raises:
        KeyError: If the template uses a field the level does not fill.
    """
    return Template(template).substitute(_fields(task, words), language=language)


def _fields(task: ComponentInput, words: TaskWords) -> dict[str, str]:
    """Map the template fields of a level to the item's input."""
    if isinstance(task, SurveyorInput):
        return {"address": task.address, "program": task.program or words.no_program}
    if isinstance(task, ZoningInput):
        return {
            "address": task.address,
            "parcel_ids": _join(task.parcel_ids, words.none),
            "program": task.program,
        }
    context = task.context
    return {
        "label": task.label,
        "aim": task.aim,
        "documents": _join(task.documents, words.all_documents),
        "topics": _join(tuple(f"`{topic}`" for topic in task.topics), words.none),
        "zone": context.zone,
        "legend_items": _join(context.legend_items, words.none, _LEGEND),
        "parcel_ids": _join(context.parcel_ids, words.none),
        "program": context.program,
        "facts": _join(context.facts, words.none, _LEGEND),
    }


def _join(values: Sequence[str], empty: str, separator: str = _LIST) -> str:
    """Join list values on one line, or stand ``empty`` for an empty list."""
    return separator.join(values) if values else empty
