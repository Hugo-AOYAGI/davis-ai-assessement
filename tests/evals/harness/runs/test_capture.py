from typing import override

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool

from evals.harness.runs.capture import RunCapture


class ScriptedModel(GenericFakeChatModel):
    @override
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


@tool
def read_pages(doc: str, start: int, end: int) -> str:
    """Read pages."""
    return "page text"


def subagent(name: str, replies: list[AIMessage]):
    graph = create_agent(model=ScriptedModel(messages=iter(replies)), tools=[read_pages], name=name)
    return graph.with_config({"run_name": name, "metadata": {"lc_agent_name": name}})


def reading_agent(name: str):
    call = {"name": "read_pages", "args": {"doc": "d", "start": 1, "end": 2}, "id": "c1"}
    return subagent(name, [AIMessage("", tool_calls=[call]), AIMessage("done")])


def test_captures_each_delegated_run_with_its_messages():
    surveyor = reading_agent("surveyor")
    doc_analyst = reading_agent("doc_analyst")
    other = reading_agent("helper")

    def orchestrator(_):
        for graph, task in ((surveyor, "locate"), (other, "help"), (doc_analyst, "read")):
            graph.invoke({"messages": [HumanMessage(task)]})
        return "ok"

    capture = RunCapture(["surveyor", "doc_analyst"])
    RunnableLambda(orchestrator).invoke(None, config={"callbacks": [capture], "run_name": "study"})
    runs = capture.runs
    assert [run.name for run in runs] == ["surveyor", "doc_analyst"]
    messages = runs[0].messages
    assert [type(m) for m in messages] == [HumanMessage, AIMessage, ToolMessage, AIMessage]
    assert messages[0].content == "locate"
    reply = messages[1]
    assert isinstance(reply, AIMessage)
    assert reply.tool_calls[0]["name"] == "read_pages"


def test_failed_run_keeps_its_input():
    failing = subagent("surveyor", [])

    def orchestrator(_):
        with pytest.raises(Exception):  # noqa: B017
            failing.invoke({"messages": [HumanMessage("locate")]})
        return "ok"

    capture = RunCapture(["surveyor"])
    RunnableLambda(orchestrator).invoke(None, config={"callbacks": [capture]})
    assert len(capture.runs) == 1
    assert capture.runs[0].name == "surveyor"
    assert capture.runs[0].messages[0].content == "locate"


def test_failed_graph_preserves_completed_model_and_tool_messages():
    call = {"name": "read_pages", "args": {"doc": "d", "start": 1, "end": 2}, "id": "c1"}
    graph = subagent("surveyor", [AIMessage("", tool_calls=[call])])
    capture = RunCapture(["surveyor"])
    with pytest.raises(RuntimeError, match="StopIteration"):
        graph.invoke({"messages": [HumanMessage("locate")]}, config={"callbacks": [capture]})
    assert capture.runs == ()
    assert [type(message) for message in capture.messages] == [HumanMessage, AIMessage, ToolMessage]
    assert capture.messages[-1].content == "page text"


def test_failed_delegation_keeps_completed_tool_messages_separate_from_parent():
    call = {"name": "read_pages", "args": {"doc": "d", "start": 1, "end": 2}, "id": "c1"}
    graph = subagent("surveyor", [AIMessage("", tool_calls=[call])])

    def orchestrator(_):
        graph.invoke({"messages": [HumanMessage("locate")]})

    capture = RunCapture(["surveyor"])
    with pytest.raises(RuntimeError, match="StopIteration"):
        RunnableLambda(orchestrator).invoke(
            {"messages": [HumanMessage("study")]}, config={"callbacks": [capture]}
        )
    assert [message.content for message in capture.messages] == ["study"]
    assert [type(message) for message in capture.runs[0].messages] == [
        HumanMessage,
        AIMessage,
        ToolMessage,
    ]


def test_delegation_through_a_tool_keeps_its_own_history():
    graph = reading_agent("doc_analyst")

    @tool
    def delegate(request: str) -> str:
        """Ask the document analyst to read."""
        graph.invoke({"messages": [HumanMessage(request)]})
        return "delegated"

    def orchestrator(_):
        return delegate.invoke({"request": "read rules"})

    capture = RunCapture(["doc_analyst"])
    RunnableLambda(orchestrator).invoke(
        {"messages": [HumanMessage("study")]}, config={"callbacks": [capture]}
    )
    assert [message.content for message in capture.messages] == ["study"]
    assert [run.name for run in capture.runs] == ["doc_analyst"]
    assert capture.runs[0].messages[0].content == "read rules"
    assert capture.runs[0].messages[-1].content == "done"
