from collections.abc import Iterator, Mapping
from typing import override

from deepagents import SubAgent, create_deep_agent
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import JsonValue

from agent.contracts.evidence import Ambiguity
from agent.contracts.findings.oap import OAPFindings
from agent.tools.submit.artifacts import ArtifactData, ArtifactsMiddleware, read_artifact
from agent.tools.submit.factory import SubmissionRejected, submit_tool


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


def test_agent_corrects_rejected_submission(oap_tool, oap_args, bad_oap_args):
    model = scripted(
        call("submit_oap_findings", bad_oap_args, "bad"),
        call("submit_oap_findings", oap_args, "good"),
        AIMessage(content="done"),
    )
    agent = create_agent(model=model, tools=[oap_tool], middleware=[ArtifactsMiddleware()])
    state = agent.invoke({"messages": [HumanMessage("analyse the OAP")]})

    stored = state["artifacts"]["oap_findings"]
    assert OAPFindings.model_validate(stored) == OAPFindings.model_validate(oap_args)
    replies = {m.tool_call_id: m for m in state["messages"] if isinstance(m, ToolMessage)}
    assert replies["bad"].status == "error"
    assert "rationale: Field required" in replies["bad"].content
    assert "citations.0: Value error" in replies["bad"].content
    assert replies["good"].content == "oap_findings accepted."


NOTE: dict[str, JsonValue] = {
    "question": "Is the OAP binding?",
    "chosen": "compatibility only",
    "rationale": "OAP prescriptions are orientations.",
    "resolved_by": "agent",
}


def needs_oap(submission: Ambiguity, artifacts: Mapping[str, ArtifactData]) -> Ambiguity:
    if read_artifact(artifacts, "oap_findings", OAPFindings) is None:
        raise SubmissionRejected(["oap_findings missing"])
    return submission


def test_subagent_artifact_reaches_parent(oap_args):
    parent = scripted(
        call("task", {"description": "analyse the OAP", "subagent_type": "worker"}, "t1"),
        call("submit_note", NOTE, "n1"),
        AIMessage(content="parent done"),
    )
    child = scripted(
        call("submit_oap_findings", oap_args, "s1"),
        AIMessage(content="child done"),
    )
    agent = create_deep_agent(
        model=parent,
        tools=[submit_tool("note", Ambiguity, finalize=needs_oap)],
        system_prompt="x",
        middleware=[ArtifactsMiddleware()],
        subagents=[
            SubAgent(
                name="worker",
                description="d",
                system_prompt="y",
                model=child,
                tools=[submit_tool("oap_findings", OAPFindings)],
                middleware=[ArtifactsMiddleware()],
            )
        ],
    )
    state = agent.invoke({"messages": [HumanMessage("go")]})

    stored = state["artifacts"]["oap_findings"]
    assert OAPFindings.model_validate(stored) == OAPFindings.model_validate(oap_args)
    assert Ambiguity.model_validate(state["artifacts"]["note"]) == Ambiguity.model_validate(NOTE)
    replies = {m.tool_call_id: m.content for m in state["messages"] if isinstance(m, ToolMessage)}
    assert replies == {"t1": "child done", "n1": "note accepted."}
    assert state["messages"][-1].content == "parent done"
