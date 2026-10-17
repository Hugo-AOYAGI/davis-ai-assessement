from collections.abc import Mapping
from typing import Any, cast

import pytest
from hydra.utils import instantiate
from langchain.tools import ToolRuntime
from langchain_core.messages import AnyMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.types import Command
from pydantic import JsonValue

from agent.contracts.findings.notes import DocNotes
from agent.tools.submit.artifacts import ArtifactData
from agent.tools.submit.factory import SubmissionRejected, submit_tools
from agent.tools.submit.replies import revise_name

TEXT_PATH = "notes.0.text"
PAGE_PATH = "notes.0.citations.0.page"


class Session:
    """Runs tool calls in sequence, threading messages and artifacts like the agent loop."""

    def __init__(self, tools: list[BaseTool], artifacts: dict[str, ArtifactData] | None = None):
        self.tools = {tool.name: tool for tool in tools}
        self.messages: list[AnyMessage] = []
        self.artifacts: dict[str, ArtifactData] = dict(artifacts or {})
        self.calls = 0

    def call(self, name: str, args: dict[str, JsonValue]) -> ToolMessage:
        self.calls += 1
        call_id = str(self.calls)
        runtime = ToolRuntime(
            state={"messages": list(self.messages), "artifacts": dict(self.artifacts)},
            context=None,
            config={},
            stream_writer=lambda _: None,
            tool_call_id=call_id,
            store=None,
        )
        result = self.tools[name].invoke(
            {"type": "tool_call", "id": call_id, "name": name, "args": {**args, "runtime": runtime}}
        )
        assert isinstance(result, Command)
        update = cast("dict[str, Any]", cast("Command[str]", result).update)
        (message,) = update["messages"]
        assert isinstance(message, ToolMessage)
        self.messages.append(message)
        self.artifacts.update(update.get("artifacts", {}))
        return message

    def revise(self, *edits: dict[str, JsonValue]) -> ToolMessage:
        return self.call("revise_notes", {"edits": list(edits)})


def make_tools(**kwargs) -> list[BaseTool]:
    return submit_tools(name="submit_notes", artifact="notes.{label}", contract=DocNotes, **kwargs)


@pytest.fixture
def session() -> Session:
    return Session(make_tools())


def test_pair_of_tools():
    submit, revise = make_tools()
    assert (submit.name, revise.name) == ("submit_notes", "revise_notes")
    assert "revise_notes, sending only the changed fields" in submit.description
    assert "notes.1.citations.3.quote" in revise.description
    assert "`remove: true`" in revise.description
    schema = revise.tool_call_schema
    assert isinstance(schema, dict)
    assert set(schema["properties"]) == {"edits"}


def test_revise_name():
    assert revise_name("submit_study") == "revise_study"
    assert revise_name("deliver") == "revise_deliver"


def test_rejection_carries_the_draft(session, bad_notes_args):
    reply = session.call("submit_notes", bad_notes_args)
    assert reply.status == "error"
    assert reply.artifact == {"submission": "submit_notes", "draft": bad_notes_args}
    assert "Fix these errors with revise_notes, sending only the changed fields" in reply.content
    assert "(or call submit_notes again with the complete result)" in reply.content


def test_acceptance_carries_no_draft(session, notes_args):
    reply = session.call("submit_notes", notes_args)
    assert reply.content == "notes.oap accepted."
    assert reply.artifact == {"submission": "submit_notes"}


def test_nothing_to_revise_without_a_rejection(session):
    reply = session.revise({"path": TEXT_PATH, "value": "x"})
    assert reply.status == "error"
    assert reply.content == "Nothing to revise: call submit_notes with the complete result."
    assert session.artifacts == {}


def test_nothing_to_revise_after_acceptance(session, notes_args, bad_notes_args):
    session.call("submit_notes", bad_notes_args)
    session.call("submit_notes", notes_args)
    assert session.revise({"path": TEXT_PATH, "value": "x"}).content.startswith("Nothing")


def test_revision_fixing_the_errors_is_stored(session, notes_args, bad_notes_args):
    session.call("submit_notes", bad_notes_args)
    reply = session.revise(
        {"path": TEXT_PATH, "value": "Inside the perimeter."},
        {"path": PAGE_PATH, "value": 33},
    )
    assert reply.content == "notes.oap accepted."
    assert reply.artifact == {"submission": "submit_notes"}
    stored = DocNotes.model_validate(session.artifacts["notes.oap"])
    assert stored.notes[0].text == "Inside the perimeter."
    assert stored.notes[0].citations[0].page == 33


def test_rejected_revision_becomes_the_new_draft(session, bad_notes_args):
    session.call("submit_notes", bad_notes_args)
    reply = session.revise({"path": TEXT_PATH, "value": "Inside the perimeter."})
    assert reply.status == "error"
    assert reply.content.startswith("submit_notes rejected, nothing was stored.")
    assert "notes.0.citations.0: Value error" in reply.content
    assert "notes.0.text" not in reply.content
    assert reply.artifact["draft"]["notes"][0]["text"] == "Inside the perimeter."
    reply = session.revise({"path": PAGE_PATH, "value": 33})
    assert reply.content == "notes.oap accepted."
    assert session.artifacts["notes.oap"]["notes"][0]["text"] == "Inside the perimeter."


def test_invalid_edits_keep_the_draft(session, bad_notes_args):
    session.call("submit_notes", bad_notes_args)
    reply = session.revise({"path": "notes.4.text", "value": "x"}, {"path": "label"})
    assert reply.status == "error"
    assert "revise_notes applied no edit and nothing was stored" in reply.content
    assert "- notes.4.text: notes has 1 items, no index 4" in reply.content
    assert "- label: give a value, or remove: true" in reply.content
    assert reply.artifact == {"submission": "submit_notes", "draft": bad_notes_args}
    reply = session.revise({"path": TEXT_PATH, "value": "x"}, {"path": PAGE_PATH, "value": 33})
    assert reply.content == "notes.oap accepted."


def test_malformed_revision_keeps_the_draft(session, bad_notes_args):
    session.call("submit_notes", bad_notes_args)
    reply = session.call("revise_notes", {"edits": [{"value": 1}]})
    assert "edits.0.path: Field required" in reply.content
    assert reply.artifact == {"submission": "submit_notes", "draft": bad_notes_args}


def test_empty_revision_checks_the_draft_again(notes_args):
    session = Session(make_tools(finalize=needs_site))
    session.call("submit_notes", notes_args)
    session.artifacts["site"] = {"id": "ab0123"}
    assert session.revise().content == "notes.oap accepted."
    assert session.artifacts["notes.oap"]["label"] == "oap_ab0123"


def needs_site(submission: DocNotes, artifacts: Mapping[str, ArtifactData]) -> DocNotes:
    if "site" not in artifacts:
        raise SubmissionRejected(["submit the site first"])
    return submission.model_copy(update={"label": f"{submission.label}_{artifacts['site']['id']}"})


def test_finalize_runs_on_revised_arguments(notes_args):
    session = Session(make_tools(finalize=needs_site), artifacts={"site": {"id": "ab0123"}})
    session.call("submit_notes", {**notes_args, "notes": []})
    reply = session.revise({"path": "notes", "value": notes_args["notes"]})
    assert reply.content == "notes.oap accepted."
    assert session.artifacts["notes.oap"]["label"] == "oap_ab0123"


def test_key_placeholder_follows_the_revised_field(session, notes_args):
    session.call("submit_notes", {**notes_args, "label": "Bad Label"})
    reply = session.revise({"path": "label", "value": "rules"})
    assert reply.content == "notes.rules accepted."
    assert set(session.artifacts) == {"notes.rules"}


def test_drafts_of_other_submit_tools_are_ignored(bad_notes_args):
    other = submit_tools(name="submit_other", artifact="other", contract=DocNotes)
    session = Session([*make_tools(), *other])
    session.call("submit_notes", bad_notes_args)
    session.call("submit_other", bad_notes_args)
    assert session.call("revise_other", {"edits": []}).artifact["submission"] == "submit_other"
    reply = session.revise({"path": TEXT_PATH, "value": "x"}, {"path": PAGE_PATH, "value": 33})
    assert reply.content == "notes.oap accepted."


def test_hydra_instantiates_the_pair():
    tools = instantiate(
        {
            "_target_": "agent.tools.submit.factory.submit_tools",
            "name": "submit_parcel",
            "artifact": "site",
            "contract": {
                "_target_": "hydra.utils.get_class",
                "path": "agent.contracts.findings.site.ParcelChoice",
            },
        }
    )
    assert [tool.name for tool in tools] == ["submit_parcel", "revise_parcel"]
