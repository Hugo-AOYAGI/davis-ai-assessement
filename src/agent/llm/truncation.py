from typing import override

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from agent.observability.logs import get_logger

logger = get_logger(__name__)

_MAX_TOKENS_STOP = "max_tokens"
"""Anthropic ``stop_reason`` of a reply cut off by the node's ``max_tokens``."""

_CUT_OFF = "Your reply was cut off: it reached the output token limit before its end."
_RETRY = "Send it again, shorter: keep each text brief and leave out anything not needed."
_CALL_NOT_RUN = f"{_CUT_OFF} This tool call was not run, its arguments are incomplete. {_RETRY}"
_REPLY_CUT = f"{_CUT_OFF} {_RETRY}"


def stopped_at_output_cap(message: AIMessage) -> bool:
    """Tell whether a model reply stopped because it reached the output token cap.

    Args:
        message: A chat model reply.

    Returns:
        ``True`` when the provider reports ``stop_reason == "max_tokens"``.
    """
    stop_reason: object = message.response_metadata.get("stop_reason")
    return stop_reason == _MAX_TOKENS_STOP


def cut_off_notices(message: AIMessage) -> list[AnyMessage]:
    """Build the messages telling the model its reply was cut off.

    A truncated tool call may hold partial arguments (or none), so none of the reply's tool
    calls is run: each one, valid or not, gets an error result instead. A reply without tool
    calls gets a single user message.

    Args:
        message: The reply that stopped at the output cap.

    Returns:
        One error ``ToolMessage`` per tool call of the reply, or one ``HumanMessage``.
    """
    calls: list[tuple[str | None, str | None]] = [
        (call["id"], call["name"]) for call in message.tool_calls
    ]
    calls += [(call.get("id"), call.get("name")) for call in message.invalid_tool_calls]
    notices: list[AnyMessage] = [
        ToolMessage(_CALL_NOT_RUN, tool_call_id=call_id, name=name, status="error")
        for call_id, name in calls
        if call_id is not None
    ]
    return notices or [HumanMessage(_REPLY_CUT)]


class OutputCapMiddleware(AgentMiddleware):
    """Sends a reply cut off at the output token cap back to the model, asking for a shorter one.

    Without it a truncated tool call (unparseable arguments) ends the agent loop silently, with
    an empty reply and no artifact.
    """

    @hook_config(can_jump_to=["model"])
    @override
    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, object] | None:
        """Answer every tool call of a cut-off reply with an error and call the model again.

        Args:
            state: The agent state, whose last message is the model's reply.
            runtime: The graph runtime, unused.

        Returns:
            The notices and a jump back to the model, or ``None`` when the reply is complete.
        """
        message = state["messages"][-1]
        if not isinstance(message, AIMessage) or not stopped_at_output_cap(message):
            return None
        notices = cut_off_notices(message)
        logger.warning(
            "reply cut off at the output cap; model asked to retry (%d notices)", len(notices)
        )
        return {"messages": notices, "jump_to": "model"}
