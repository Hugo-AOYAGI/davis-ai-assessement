"""The revise tool: corrections to a rejected submission, instead of the complete result again."""

from collections.abc import Callable, Sequence
from typing import cast

from langchain.tools import ToolRuntime
from langchain_core.messages import AnyMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command
from pydantic import JsonValue, ValidationError

from agent.contracts.revision import Revision
from agent.runtime.submissions.edits import EditError, apply_edits
from agent.tools.submit.artifacts import ArtifactsState
from agent.tools.submit.replies import (
    DRAFT,
    SUBMISSION,
    error_reply,
    format_validation,
    reply_artifact,
    revise_name,
)

type Deliver = Callable[[dict[str, JsonValue], ToolRuntime[None, ArtifactsState]], Command[str]]
"""The submit pipeline: validate the arguments, finalize, store and reply (or reject)."""


def find_draft(messages: Sequence[AnyMessage], name: str) -> dict[str, JsonValue] | None:
    """Find the draft left by the latest reply of a submit tool (or of its revise tool).

    Args:
        messages: The agent's messages.
        name: Submit tool name.

    Returns:
        The rejected arguments, or ``None`` when the latest reply accepted the submission or
        there was no submission yet.
    """
    for message in reversed(messages):
        artifact = message.artifact if isinstance(message, ToolMessage) else None
        if isinstance(artifact, dict) and artifact.get(SUBMISSION) == name:
            draft = artifact.get(DRAFT)
            return cast("dict[str, JsonValue]", draft) if isinstance(draft, dict) else None
    return None


def revise_tool(name: str, deliver: Deliver) -> BaseTool:
    """Build the companion of a submit tool, which applies edits to its last rejected draft.

    The draft is read from the latest rejection reply in the agent's own messages, so nothing is
    added to the state. The edited arguments then go through the submit pipeline: a rejection
    carries them as the new draft, an acceptance stores the artifact.

    Args:
        name: Submit tool name, e.g. ``submit_notes`` (the tool is named ``revise_notes``).
        deliver: The submit tool's pipeline.

    Returns:
        The revise tool, whose argument schema is ``Revision``.
    """
    revise = revise_name(name)

    def run(runtime: ToolRuntime[None, ArtifactsState], **arguments: JsonValue) -> Command[str]:
        """Apply the edits to the draft and submit the result."""
        tool_call_id = runtime.tool_call_id or ""
        draft = find_draft(runtime.state["messages"], name)
        if draft is None:
            content = f"Nothing to revise: call {name} with the complete result."
            return error_reply(content, tool_call_id)
        try:
            revision = Revision.model_validate(arguments)
            edited = apply_edits(draft, revision.edits)
        except (ValidationError, EditError) as error:
            errors = (
                format_validation(error) if isinstance(error, ValidationError) else error.errors
            )
            lines = "\n".join(f"- {line}" for line in errors)
            content = (
                f"{revise} applied no edit and nothing was stored; the {name} draft is unchanged. "
                f"Fix these edits (paths refer to the rejected draft) and call {revise} again:\n"
                f"{lines}"
            )
            return error_reply(content, tool_call_id, reply_artifact(name, draft))
        return deliver(edited, runtime)

    return StructuredTool(
        name=revise,
        description=_describe(name, revise),
        args_schema=Revision.model_json_schema(),
        func=run,
    )


def _describe(name: str, revise: str) -> str:
    """Write the revise tool description the model reads."""
    return (
        f"Fix a rejected {name} by sending only the changes, instead of the complete result "
        f"again. The draft is your last {name} call as rejected, with the edits of your "
        f"earlier {revise} calls applied.\n\n"
        "Each edit names a `path` listed in the rejection reply: dotted field names and 0-based "
        "list indices, e.g. `notes.1.citations.3.quote`. Give either:\n"
        "- `value`: the new value at that path (it replaces the current value, adds a missing "
        "field, or appends when the index equals the list's length);\n"
        "- `remove: true`: deletes that field or list item.\n"
        "Every path refers to the draft as rejected: removing an item does not shift the "
        "indices of your other edits. An empty `edits` list checks the draft again unchanged "
        "(e.g. once a missing artifact has been delivered).\n\n"
        f"The edited result is checked like a new {name} call: if it is rejected again, fix the "
        f"new errors with {revise} (their paths refer to the edited draft); once the reply says "
        "it was accepted, it is stored.\n\n"
        'Example: {"edits": [{"path": "notes.1.citations.3.quote", "value": "exact text from '
        'the page"}, {"path": "notes.4.citations.0", "remove": true}]}'
    )
