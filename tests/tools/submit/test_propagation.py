from collections.abc import Iterator, Mapping
from typing import override

from deepagents import SubAgent, create_deep_agent
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import JsonValue

from agent.contracts.evidence import Ambiguity
from agent.contracts.findings.notes import DocNotes
from agent.tools.submit.artifacts import ArtifactData, ArtifactsMiddleware, read_artifact
from agent.tools.submit.factory import DONE, SubmissionRejected, submit_tool, submit_tools


class ScriptedModel(GenericFakeChatModel):
    """Fake chat model replaying scripted messages, accepting any tool binding."""

    @override
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


def scripted(*messages: AIMessage) -> ScriptedModel:
    replies: Iterator[AIMessage] = iter(messages)
    return ScriptedModel(messages=replies)


def call(name: str, args: dict[str, JsonValue], call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def test_agent_corrects_rejected_submission(notes_tool, notes_args, bad_notes_args):
    model = scripted(
        call("submit_notes", bad_notes_args, "bad"),
        call("submit_notes", notes_args, "good"),
        AIMessage(content="done"),
    )
    agent = create_agent(model=model, tools=[notes_tool], middleware=[ArtifactsMiddleware()])
    state = agent.invoke({"messages": [HumanMessage("analyse the OAP")]})

    stored = state["artifacts"]["notes.oap"]
    assert DocNotes.model_validate(stored) == DocNotes.model_validate(notes_args)
    replies = {m.tool_call_id: m for m in state["messages"] if isinstance(m, ToolMessage)}
    assert replies["bad"].status == "error"
    assert "notes.0.text: Field required" in replies["bad"].content
    assert "notes.0.citations.0: Value error" in replies["bad"].content
    assert replies["good"].content == f"notes.oap accepted.\n\n{DONE}"


FIXES: dict[str, JsonValue] = {
    "edits": [
        {"path": "notes.0.text", "value": "The site lies inside the Joliot Curie OAP perimeter."},
        {"path": "notes.0.citations.0.page", "value": 33},
    ]
}


def test_agent_revises_rejected_submission(notes_args, bad_notes_args):
    model = scripted(
        call("submit_notes", bad_notes_args, "bad"),
        call("revise_notes", FIXES, "fix"),
        AIMessage(content="done"),
    )
    tools = submit_tools(name="submit_notes", artifact="notes.{label}", contract=DocNotes)
    agent = create_agent(model=model, tools=tools, middleware=[ArtifactsMiddleware()])
    state = agent.invoke({"messages": [HumanMessage("analyse the OAP")]})

    stored = state["artifacts"]["notes.oap"]
    assert DocNotes.model_validate(stored) == DocNotes.model_validate(notes_args)
    replies = {m.tool_call_id: m for m in state["messages"] if isinstance(m, ToolMessage)}
    assert replies["bad"].status == "error"
    assert replies["bad"].artifact["draft"] == bad_notes_args
    assert replies["fix"].content == f"notes.oap accepted.\n\n{DONE}"


def test_revised_subagent_artifact_reaches_parent(notes_args, bad_notes_args):
    parent = scripted(
        call("task", {"description": "analyse the OAP", "subagent_type": "worker"}, "t1"),
        AIMessage(content="parent done"),
    )
    child = scripted(
        call("submit_notes", bad_notes_args, "s1"),
        call("revise_notes", FIXES, "r1"),
        AIMessage(content="child done"),
    )
    agent = create_deep_agent(
        model=parent,
        system_prompt="x",
        middleware=[ArtifactsMiddleware()],
        subagents=[
            SubAgent(
                name="worker",
                description="d",
                system_prompt="y",
                model=child,
                tools=submit_tools(
                    name="submit_notes", artifact="notes.{label}", contract=DocNotes
                ),
                middleware=[ArtifactsMiddleware()],
            )
        ],
    )
    state = agent.invoke({"messages": [HumanMessage("go")]})

    stored = state["artifacts"]["notes.oap"]
    assert DocNotes.model_validate(stored) == DocNotes.model_validate(notes_args)
    replies = {m.tool_call_id: m.content for m in state["messages"] if isinstance(m, ToolMessage)}
    assert replies == {"t1": "child done"}


NOTE: dict[str, JsonValue] = {
    "question": "Is the OAP binding?",
    "chosen": "compatibility only",
    "rationale": "OAP prescriptions are orientations.",
    "resolved_by": "agent",
}


def needs_oap(submission: Ambiguity, artifacts: Mapping[str, ArtifactData]) -> Ambiguity:
    if read_artifact(artifacts, "notes.oap", DocNotes) is None:
        raise SubmissionRejected(["notes.oap missing"])
    return submission


def test_subagent_artifact_reaches_parent(notes_args):
    parent = scripted(
        call("task", {"description": "analyse the OAP", "subagent_type": "worker"}, "t1"),
        call("submit_note", NOTE, "n1"),
        AIMessage(content="parent done"),
    )
    child = scripted(
        call("submit_notes", notes_args, "s1"),
        AIMessage(content="child done"),
    )
    agent = create_deep_agent(
        model=parent,
        tools=[
            submit_tool(name="submit_note", artifact="note", contract=Ambiguity, finalize=needs_oap)
        ],
        system_prompt="x",
        middleware=[ArtifactsMiddleware()],
        subagents=[
            SubAgent(
                name="worker",
                description="d",
                system_prompt="y",
                model=child,
                tools=[
                    submit_tool(name="submit_notes", artifact="notes.{label}", contract=DocNotes)
                ],
                middleware=[ArtifactsMiddleware()],
            )
        ],
    )
    state = agent.invoke({"messages": [HumanMessage("go")]})

    stored = state["artifacts"]["notes.oap"]
    assert DocNotes.model_validate(stored) == DocNotes.model_validate(notes_args)
    assert Ambiguity.model_validate(state["artifacts"]["note"]) == Ambiguity.model_validate(NOTE)
    replies = {m.tool_call_id: m.content for m in state["messages"] if isinstance(m, ToolMessage)}
    assert replies == {"t1": "child done", "n1": f"note accepted.\n\n{DONE}"}
    assert state["messages"][-1].content == "parent done"
