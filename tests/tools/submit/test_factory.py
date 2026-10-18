from collections.abc import Mapping
from typing import cast

import pytest
from hydra.utils import instantiate
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.types import Command
from pydantic import JsonValue

from agent.contracts.findings.notes import DocNotes
from agent.contracts.findings.site import ParcelChoice
from agent.tools.submit.artifacts import ArtifactData, Artifacts
from agent.tools.submit.factory import DONE, SubmissionRejected, submit_tool


def runtime(artifacts: Artifacts | None = None) -> ToolRuntime:
    state = {"messages": [], **({"artifacts": artifacts} if artifacts is not None else {})}
    return ToolRuntime(
        state=state,
        context=None,
        config={},
        stream_writer=lambda _: None,
        tool_call_id="1",
        store=None,
    )


def invoke(
    tool: BaseTool, args: dict[str, JsonValue], artifacts: Artifacts | None = None
) -> Command[str]:
    result = tool.invoke(
        {
            "type": "tool_call",
            "id": "1",
            "name": tool.name,
            "args": {**args, "runtime": runtime(artifacts)},
        }
    )
    assert isinstance(result, Command)
    return cast("Command[str]", result)


def only_message(command: Command[str]) -> ToolMessage:
    update = command.update
    assert isinstance(update, dict)
    (message,) = update["messages"]
    assert isinstance(message, ToolMessage)
    assert message.tool_call_id == "1"
    return message


def test_schema_and_description_come_from_contract(notes_tool):
    assert notes_tool.name == "submit_notes"
    assert "Cited notes on what the documents say" in notes_tool.description
    assert "submit_notes again" in notes_tool.description
    schema = notes_tool.tool_call_schema
    assert isinstance(schema, dict)
    assert set(schema["properties"]) == set(DocNotes.model_fields)
    assert "runtime" not in schema["properties"]
    assert schema["properties"]["topics"]["description"].startswith("The topic checklist")


def test_valid_submission_is_stored_under_formatted_key(notes_tool, notes_args):
    command = invoke(notes_tool, notes_args)
    stored = command.update["artifacts"]["notes.oap"]
    assert DocNotes.model_validate(stored) == DocNotes.model_validate(notes_args)
    assert only_message(command).content == f"notes.oap accepted.\n\n{DONE}"


def test_plain_key_is_used_as_is(notes_args):
    tool = submit_tool(name="submit_notes", artifact="notes", contract=DocNotes)
    command = invoke(tool, notes_args)
    assert set(command.update["artifacts"]) == {"notes"}


def test_unknown_placeholder_is_refused():
    with pytest.raises(ValueError, match="requires plain placeholders"):
        submit_tool(name="submit_notes", artifact="notes.{kind}", contract=DocNotes)


def test_invalid_submission_returns_field_errors(notes_tool, bad_notes_args):
    command = invoke(notes_tool, bad_notes_args)
    assert "artifacts" not in command.update
    message = only_message(command)
    assert message.status == "error"
    assert "submit_notes rejected, nothing was stored." in message.content
    assert "notes.0.text: Field required" in message.content
    assert "notes.0.citations.0: Value error, a regulatory citation needs a page" in (
        message.content
    )


def tag_site(submission: DocNotes, artifacts: Mapping[str, ArtifactData]) -> DocNotes:
    if "site" not in artifacts:
        raise SubmissionRejected(["submit the site first", "then resubmit"])
    return submission.model_copy(update={"label": f"{submission.label}_{artifacts['site']['id']}"})


def count_notes(stored: DocNotes) -> str:
    return f"{len(stored.notes)} note(s) on {stored.label}"


def test_finalize_stores_finalized_object(notes_args):
    tool = submit_tool(
        name="submit_notes", artifact="notes.{label}", contract=DocNotes, finalize=tag_site
    )
    command = invoke(tool, notes_args, artifacts={"site": {"id": "ab0123"}})
    assert command.update["artifacts"]["notes.oap"]["label"] == "oap_ab0123"


def test_finalize_rejection_returns_errors(notes_args):
    tool = submit_tool(
        name="submit_notes", artifact="notes.{label}", contract=DocNotes, finalize=tag_site
    )
    command = invoke(tool, notes_args)
    assert "artifacts" not in command.update
    message = only_message(command)
    assert message.status == "error"
    assert "- submit the site first\n- then resubmit" in message.content


def test_summary_follows_acceptance(notes_args):
    tool = submit_tool(
        name="submit_notes",
        artifact="notes.{label}",
        contract=DocNotes,
        finalize=tag_site,
        summarize=count_notes,
    )
    command = invoke(tool, notes_args, artifacts={"site": {"id": "ab0123"}})
    assert only_message(command).content == (
        f"notes.oap accepted.\n\n1 note(s) on oap_ab0123\n\n{DONE}"
    )


def test_submission_rejected_keeps_errors():
    with pytest.raises(SubmissionRejected) as info:
        raise SubmissionRejected(["a", "b"])
    assert info.value.errors == ("a", "b")


def test_hydra_instantiates_tool():
    tool = instantiate(
        {
            "_target_": "agent.tools.submit.factory.submit_tool",
            "name": "submit_parcel",
            "artifact": "site",
            "contract": {
                "_target_": "hydra.utils.get_class",
                "path": "agent.contracts.findings.site.ParcelChoice",
            },
        }
    )
    assert tool.name == "submit_parcel"
    assert set(tool.tool_call_schema["properties"]) == set(ParcelChoice.model_fields)


@pytest.mark.parametrize(
    "artifact",
    [
        "notes.{label!r}",
        "notes.{label:>12}",
        "notes.{label[0]}",
        "notes.{missing}",
        "notes.{}",
        "notes.{label",
    ],
)
def test_artifact_template_rejects_non_plain_fields(artifact):
    with pytest.raises(ValueError):
        submit_tool(name="submit_notes", artifact=artifact, contract=DocNotes)
