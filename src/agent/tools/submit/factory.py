import inspect
from collections.abc import Callable, Mapping, Sequence
from string import Formatter
from typing import cast

from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command
from pydantic import JsonValue, ValidationError

from agent.contracts.base import Contract
from agent.tools.submit.artifacts import ArtifactData, ArtifactsState
from agent.tools.submit.replies import format_validation, rejection, reply_artifact, revise_name
from agent.tools.submit.revise import Deliver, revise_tool

type Finalizer[C: Contract, S: Contract] = Callable[[C, Mapping[str, ArtifactData]], S]
"""Turns a validated submission into the object to store, given the current artifacts.

It may raise ``SubmissionRejected`` to send errors back to the model without storing anything.
"""

type Summarizer[S: Contract] = Callable[[S], str]
"""Writes what the model should read back about the stored object (e.g. computed figures)."""


class SubmissionRejected(Exception):  # noqa: N818
    """A finalizer refused a valid submission; its errors are sent back to the model."""

    def __init__(self, errors: Sequence[str]) -> None:
        """Keep the errors to report.

        Args:
            errors: One actionable message per problem, written for the model.
        """
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def submit_tool[C: Contract, S: Contract](
    *,
    name: str,
    artifact: str,
    contract: type[C],
    finalize: Finalizer[C, S] | None = None,
    summarize: Summarizer[S] | None = None,
) -> BaseTool:
    """Build the tool through which an agent delivers its result.

    The tool's argument schema is the contract's JSON schema, so the model passes the contract
    fields as top-level arguments and reads their docstrings as descriptions. Validation happens
    inside the tool: a rejected submission returns an error ``ToolMessage`` listing every
    ``field.path: message`` and stores nothing, its ``artifact`` keeping the rejected arguments
    as the draft the revise tool edits (see ``submit_tools``); an accepted one is stored as JSON
    in the ``artifacts`` state under its key, and the reply says ``<key> accepted.``.

    Args:
        name: Tool name, e.g. ``submit_notes``.
        artifact: State key of the stored result. It may hold ``{field}`` placeholders filled
            from the submission's top-level fields, e.g. ``notes.{label}``.
        contract: Contract the submission must satisfy.
        finalize: Optional hook turning the validated submission into the stored object
            (e.g. ``Study`` into ``VerifiedStudy``), with access to the current artifacts.
        summarize: Optional hook whose text, written from the stored object, follows the
            ``<key> accepted.`` reply.

    Returns:
        A tool to add to the agent that produces the artifact.

    Raises:
        ValueError: If ``artifact`` names a placeholder that is not a field of ``contract``.
    """
    _check_placeholders(artifact, contract)
    deliver = _pipeline(name, artifact, contract, finalize, summarize)
    return _submit(name, contract, deliver)


def submit_tools[C: Contract, S: Contract](
    *,
    name: str,
    artifact: str,
    contract: type[C],
    finalize: Finalizer[C, S] | None = None,
    summarize: Summarizer[S] | None = None,
) -> list[BaseTool]:
    """Build the submit tool and its revise tool (``submit_notes`` and ``revise_notes``).

    After a rejection the model sends only edits to the rejected draft to the revise tool,
    which runs them through the same pipeline (validation, ``finalize``, storage, ``summarize``)
    instead of making the model re-emit the complete result. Arguments as in ``submit_tool``.

    Returns:
        ``[submit, revise]``, to add to the agent that produces the artifact.

    Raises:
        ValueError: If ``artifact`` names a placeholder that is not a field of ``contract``.
    """
    _check_placeholders(artifact, contract)
    deliver = _pipeline(name, artifact, contract, finalize, summarize)
    return [_submit(name, contract, deliver), revise_tool(name, deliver)]


def _pipeline[C: Contract, S: Contract](
    name: str,
    artifact: str,
    contract: type[C],
    finalize: Finalizer[C, S] | None,
    summarize: Summarizer[S] | None,
) -> Deliver:
    """Build the pipeline shared by the submit and revise tools: check, store, reply."""

    def deliver(
        arguments: dict[str, JsonValue], runtime: ToolRuntime[None, ArtifactsState]
    ) -> Command[str]:
        """Validate, optionally finalize, and store the submission, or reject it as a draft."""
        tool_call_id = runtime.tool_call_id or ""
        try:
            submission = contract.model_validate(arguments)
        except ValidationError as error:
            return rejection(name, format_validation(error), tool_call_id, arguments)
        if finalize is None:
            stored = cast("S", submission)
        else:
            try:
                stored = finalize(submission, runtime.state.get("artifacts", {}))
            except SubmissionRejected as rejected:
                return rejection(name, rejected.errors, tool_call_id, arguments)
        key = artifact.format_map(dict(submission))
        reply = f"{key} accepted."
        if summarize is not None:
            reply = f"{reply}\n\n{summarize(stored)}"
        message = ToolMessage(reply, tool_call_id=tool_call_id, artifact=reply_artifact(name))
        return Command[str](
            update={"artifacts": {key: stored.model_dump(mode="json")}, "messages": [message]}
        )

    return deliver


def _submit(name: str, contract: type[Contract], deliver: Deliver) -> BaseTool:
    """Wrap the pipeline in the submit tool, whose arguments are the contract's fields."""

    def submit(runtime: ToolRuntime[None, ArtifactsState], **arguments: JsonValue) -> Command[str]:
        """Validate, optionally finalize, and store the submission."""
        return deliver(arguments, runtime)

    return StructuredTool(
        name=name,
        description=_describe(name, contract),
        args_schema=contract.model_json_schema(),
        func=submit,
    )


def _check_placeholders(artifact: str, contract: type[Contract]) -> None:
    """Reject artifact key templates naming anything but a top-level contract field."""
    fields = {field for _, field, _, _ in Formatter().parse(artifact) if field is not None}
    unknown = sorted(fields - set(contract.model_fields))
    if unknown:
        msg = f"artifact {artifact!r} names {unknown}, not fields of {contract.__name__}"
        raise ValueError(msg)


def _describe(name: str, contract: type[Contract]) -> str:
    """Write the tool description the model reads, from the contract's docstring."""
    summary = inspect.getdoc(contract) or contract.__name__
    return (
        f"Deliver your final result: {summary}\n\n"
        "This is the only way to hand your result back. Pass every field of the result as a "
        "top-level argument. The submission is validated: if it is rejected, nothing is stored "
        "and the reply lists each problem as `field.path: message`; fix them with "
        f"{revise_name(name)}, sending only the changed fields (calling {name} again with the "
        "complete result also works, but is much slower). Your task is done only once the reply "
        "says the result was accepted."
    )
