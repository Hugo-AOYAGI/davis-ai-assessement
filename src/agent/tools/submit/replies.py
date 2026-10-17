"""Replies of the submit and revise tools, and the draft they carry for the revise tool."""

from collections.abc import Mapping, Sequence

from langchain_core.messages import ToolMessage
from langgraph.types import Command
from pydantic import JsonValue, ValidationError

SUBMISSION = "submission"
"""Key of a reply's ``artifact`` naming the submit tool the reply belongs to."""

DRAFT = "draft"
"""Key of a rejection's ``artifact`` holding the rejected arguments, the revise tool's base."""

_PREFIX = "submit_"


def revise_name(name: str) -> str:
    """Name the revise tool of a submit tool: ``submit_notes`` gives ``revise_notes``.

    Args:
        name: Submit tool name.

    Returns:
        ``name`` with its ``submit_`` prefix replaced by ``revise_``, else ``revise_<name>``.
    """
    return f"revise_{name.removeprefix(_PREFIX)}"


def reply_artifact(name: str, draft: Mapping[str, JsonValue] | None = None) -> dict[str, JsonValue]:
    """Build the ``artifact`` of a submit or revise reply (never sent to the model).

    Args:
        name: Submit tool name.
        draft: The rejected arguments; ``None`` for an accepted submission.

    Returns:
        ``{"submission": name}``, plus ``"draft"`` when the submission was rejected.
    """
    if draft is None:
        return {SUBMISSION: name}
    return {SUBMISSION: name, DRAFT: dict(draft)}


def format_validation(error: ValidationError) -> list[str]:
    """Render pydantic errors as ``field.path: message`` lines.

    Args:
        error: The validation error.

    Returns:
        One line per error, its path dotted as the revise tool expects it.
    """
    return [
        f"{'.'.join(str(part) for part in detail['loc']) or '(whole result)'}: {detail['msg']}"
        for detail in error.errors(include_url=False)
    ]


def error_reply(
    content: str, tool_call_id: str, artifact: Mapping[str, JsonValue] | None = None
) -> Command[str]:
    """Reply with an error ``ToolMessage``, storing nothing.

    Args:
        content: What the model reads.
        tool_call_id: Id of the call answered.
        artifact: The reply's artifact, if any.

    Returns:
        The command adding the message.
    """
    message = ToolMessage(
        content,
        tool_call_id=tool_call_id,
        status="error",
        artifact=None if artifact is None else dict(artifact),
    )
    return Command[str](update={"messages": [message]})


def rejection(
    name: str, errors: Sequence[str], tool_call_id: str, draft: Mapping[str, JsonValue]
) -> Command[str]:
    """Reject a submission: list the errors and keep the draft for the revise tool.

    Args:
        name: Submit tool name.
        errors: One actionable message per problem.
        tool_call_id: Id of the submit or revise call answered.
        draft: The arguments that were checked.

    Returns:
        The command adding the error message, whose artifact carries the draft.
    """
    lines = "\n".join(f"- {line}" for line in errors)
    content = (
        f"{name} rejected, nothing was stored. Fix these errors with {revise_name(name)}, "
        f"sending only the changed fields (or call {name} again with the complete result):\n"
        f"{lines}"
    )
    return error_reply(content, tool_call_id, reply_artifact(name, draft))
