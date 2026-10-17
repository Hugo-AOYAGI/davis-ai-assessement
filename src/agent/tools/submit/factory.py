import inspect
from collections.abc import Callable, Mapping, Sequence

from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command
from pydantic import JsonValue, ValidationError

from agent.contracts.base import Contract
from agent.tools.submit.artifacts import ArtifactData, ArtifactsState

type Finalizer[C: Contract] = Callable[[C, Mapping[str, ArtifactData]], Contract]
"""Turns a validated submission into the object to store, given the current artifacts.

It may raise ``SubmissionRejected`` to send errors back to the model without storing anything.
"""


class SubmissionRejected(Exception):  # noqa: N818
    """A finalizer refused a valid submission; its errors are sent back to the model."""

    def __init__(self, errors: Sequence[str]) -> None:
        """Keep the errors to report.

        Args:
            errors: One actionable message per problem, written for the model.
        """
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def submit_tool[C: Contract](
    artifact: str, contract: type[C], finalize: Finalizer[C] | None = None
) -> BaseTool:
    """Build the ``submit_<artifact>`` tool through which an agent delivers its result.

    The tool's argument schema is the contract's JSON schema, so the model passes the contract
    fields as top-level arguments and reads their docstrings as descriptions. Validation happens
    inside the tool: a rejected submission returns an error ``ToolMessage`` listing every
    ``field.path: message`` and stores nothing; an accepted one is stored in the ``artifacts``
    state key as JSON.

    Args:
        artifact: Artifact name, used as the state key and in the tool name.
        contract: Contract the submission must satisfy.
        finalize: Optional hook turning the validated submission into the stored object
            (e.g. ``Study`` into ``VerifiedStudy``), with access to the current artifacts.

    Returns:
        A tool to add to the agent that produces the artifact.
    """
    name = f"submit_{artifact}"

    def submit(runtime: ToolRuntime[None, ArtifactsState], **arguments: JsonValue) -> Command[str]:
        """Validate, optionally finalize, and store the submission."""
        tool_call_id = runtime.tool_call_id or ""
        try:
            submission = contract.model_validate(arguments)
        except ValidationError as error:
            return _reject(name, _format_validation(error), tool_call_id)
        stored: Contract = submission
        if finalize is not None:
            try:
                stored = finalize(submission, runtime.state.get("artifacts", {}))
            except SubmissionRejected as rejection:
                return _reject(name, rejection.errors, tool_call_id)
        return Command[str](
            update={
                "artifacts": {artifact: stored.model_dump(mode="json")},
                "messages": [ToolMessage(f"{artifact} accepted.", tool_call_id=tool_call_id)],
            }
        )

    return StructuredTool(
        name=name,
        description=_describe(name, artifact, contract),
        args_schema=contract.model_json_schema(),
        func=submit,
    )


def _describe(name: str, artifact: str, contract: type[Contract]) -> str:
    """Write the tool description the model reads, from the contract's docstring."""
    summary = inspect.getdoc(contract) or contract.__name__
    return (
        f"Deliver your final result ({artifact}): {summary}\n\n"
        "This is the only way to hand your result back. Pass every field of the result as a "
        "top-level argument. The submission is validated: if it is rejected, the reply lists "
        f"each problem as `field.path: message`; fix them and call {name} again with the "
        f"complete result. Your task is done only once the reply says `{artifact} accepted`."
    )


def _format_validation(error: ValidationError) -> list[str]:
    """Render pydantic errors as ``field.path: message`` lines."""
    return [
        f"{'.'.join(str(part) for part in detail['loc']) or '(whole result)'}: {detail['msg']}"
        for detail in error.errors(include_url=False)
    ]


def _reject(name: str, errors: Sequence[str], tool_call_id: str) -> Command[str]:
    """Reply with the errors as an error ``ToolMessage``, storing nothing."""
    lines = "\n".join(f"- {line}" for line in errors)
    content = f"{name} rejected, nothing was stored. Fix these errors and resubmit:\n{lines}"
    message = ToolMessage(content, tool_call_id=tool_call_id, status="error")
    return Command[str](update={"messages": [message]})
