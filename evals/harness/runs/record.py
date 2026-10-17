"""The record of one run of the unit under test, as scorers read it and ``scores.json`` keeps it."""

from collections.abc import Sequence

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, ToolMessage
from pydantic import JsonValue

from agent.contracts.base import Contract
from evals.harness.items import Level
from evals.harness.scorers.trajectory import DELIVERING, RunCost


class RunRecord(Contract):
    """One run of the unit under test on one item; serialises to JSON with its messages."""

    item_id: str
    level: Level
    output: dict[str, JsonValue] | None
    """The delivered artifact as JSON (``site``, ``zone``, ``notes.<label>``, or the
    ``VerifiedStudy`` for e2e); ``None`` when nothing was delivered."""
    messages: tuple[AnyMessage, ...] = ()
    """What ``score_trajectory`` reads: the messages of each sub-agent run in completion order
    (e2e only), then the unit's own (for e2e, the orchestrator's), so that its last ``submit_*``
    call comes last."""
    subagent_runs: tuple[str, ...] = ()
    """Names of the sub-agent runs whose messages open ``messages``, in that order."""
    cost: RunCost
    """Priced usage of every model call of the run, and its wall time."""
    wall_time_s: float
    rejections: tuple[str, ...] = ()
    """Error replies of ``submit_*`` and ``revise_*`` tools (``<tool>: <reply>``), truncated,
    in order."""
    error: str | None = None
    """The exception that ended the run, as ``<type>: <message>``; the record then holds what
    was captured before it."""


def rejections(messages: Sequence[BaseMessage], max_chars: int) -> tuple[str, ...]:
    """List the error replies of ``submit_*`` and ``revise_*`` tools (rejected submissions).

    Args:
        messages: A run's messages.
        max_chars: Length kept of each reply.

    Returns:
        ``<tool>: <reply>`` per rejected submission, in order.
    """
    names = {
        call["id"]: call["name"]
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    }
    return tuple(
        f"{names[message.tool_call_id]}: {message.text[:max_chars]}"
        for message in messages
        if isinstance(message, ToolMessage)
        and message.status == "error"
        and names.get(message.tool_call_id, "").startswith(DELIVERING)
    )
