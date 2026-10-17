from collections.abc import Mapping
from string import Template
from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool, ToolException

from agent.contracts.base import Contract

DESCRIPTION = """Load a playbook: the step-by-step recipe for a kind of task.

When the user's request matches a playbook below, call this tool with its name before doing
anything else, then follow the returned steps.

Available playbooks:
{listing}"""


class Playbook(Contract):
    """A task recipe read from ``prompts/playbooks/``."""

    description: str
    """When to use it, shown to the model in the tool description."""
    text: str
    """The recipe, in Markdown; ``$language`` is substituted on loading."""


def load_playbook_tool(playbooks: Mapping[str, Playbook], language: str) -> BaseTool:
    """Build the ``load_playbook`` tool, which returns a playbook's text on demand.

    Args:
        playbooks: Playbooks by name.
        language: Language of the study's free text, substituted for ``$language``.

    Returns:
        A tool replying with the playbook's text, or with the available names.

    Raises:
        ValueError: If ``playbooks`` is empty.
    """
    if not playbooks:
        msg = "load_playbook needs at least one playbook"
        raise ValueError(msg)
    texts = {
        name: Template(playbook.text).safe_substitute(language=language)
        for name, playbook in playbooks.items()
    }
    listing = "\n".join(
        f"- `{name}`: {playbook.description}" for name, playbook in playbooks.items()
    )

    def load(name: Annotated[str, "Playbook name, from the list above."]) -> str:
        """Return the playbook's text."""
        if name not in texts:
            msg = f"No playbook named {name!r}. Available playbooks: {', '.join(sorted(texts))}."
            raise ToolException(msg)
        return texts[name]

    return StructuredTool.from_function(
        func=load,
        name="load_playbook",
        description=DESCRIPTION.format(listing=listing),
        handle_tool_error=True,
    )
