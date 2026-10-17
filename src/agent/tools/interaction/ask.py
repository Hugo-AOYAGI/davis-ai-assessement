from langchain_core.tools import BaseTool, StructuredTool, ToolException
from langgraph.types import interrupt
from pydantic import JsonValue, ValidationError

from agent.contracts.inputs.clarification import ClarificationRequest
from agent.tools.interaction.exchange import (
    ACTION_NAME,
    describe_reply,
    interrupt_payload,
    read_reply,
)

DESCRIPTION = """Ask the user a batch of questions and wait for their answers.

Use it for facts only the user knows (program facts: number of buildings, floor areas, unit
counts, financing...) and for readings of the regulation the user may want to settle, always
with your recommended option. Put all your questions in one call. For each question give a
short stable id, the question, its kind, why the study depends on it, the options, and the
option you recommend (one of the options).

The reply lists the user's answer for each question id. Answers come from the user: an
ambiguity they settle is recorded with resolved_by: user. For a question left unanswered,
choose the answer yourself, justify it, and record it as an ambiguity with resolved_by: agent."""


def ask_user_tool() -> BaseTool:
    """Build the ``ask_user`` tool, which pauses the run until the user answers.

    The run stops on a LangGraph ``interrupt`` whose value is built by ``interrupt_payload``;
    it continues when resumed with ``Command(resume=...)`` (accepted values: see
    ``read_reply``). This needs a checkpointer, which the Agent Server provides.

    Returns:
        A tool whose arguments are a ``ClarificationRequest`` and whose reply lists the answers.
    """

    def ask(**arguments: JsonValue) -> str:
        """Validate the questions, interrupt the run, and report the user's answers."""
        try:
            request = ClarificationRequest.model_validate(arguments)
        except ValidationError as error:
            lines = "\n".join(f"- {line}" for line in _format_validation(error))
            msg = f"Invalid questions. Fix these errors and call again:\n{lines}"
            raise ToolException(msg) from error
        resume = interrupt(interrupt_payload(request))
        return describe_reply(request, read_reply(request, resume))

    return StructuredTool(
        name=ACTION_NAME,
        description=DESCRIPTION,
        args_schema=ClarificationRequest.model_json_schema(),
        func=ask,
        handle_tool_error=True,
    )


def _format_validation(error: ValidationError) -> list[str]:
    """Render pydantic errors as ``field.path: message`` lines."""
    return [
        f"{'.'.join(str(part) for part in detail['loc']) or '(all questions)'}: {detail['msg']}"
        for detail in error.errors(include_url=False)
    ]
