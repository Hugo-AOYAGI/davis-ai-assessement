from typing import override

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool

from evals.harness.runs.capture import SubagentCapture


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

    capture = SubagentCapture(["surveyor", "doc_analyst"])
    RunnableLambda(orchestrator).invoke(None, config={"callbacks": [capture], "run_name": "study"})
    runs = capture.runs
    assert [run.name for run in runs] == ["surveyor", "doc_analyst"]
    messages = runs[0].messages
    assert [type(m) for m in messages] == [HumanMessage, AIMessage, ToolMessage, AIMessage]
    assert messages[0].content == "locate"
    reply = messages[1]
    assert isinstance(reply, AIMessage)
    assert reply.tool_calls[0]["name"] == "read_pages"


def test_failed_run_is_not_kept():
    failing = subagent("surveyor", [])

    def orchestrator(_):
        with pytest.raises(Exception):  # noqa: B017
            failing.invoke({"messages": [HumanMessage("locate")]})
        return "ok"

    capture = SubagentCapture(["surveyor"])
    RunnableLambda(orchestrator).invoke(None, config={"callbacks": [capture]})
    assert capture.runs == ()
