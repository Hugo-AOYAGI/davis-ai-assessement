from collections.abc import Iterator
from typing import override

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import JsonValue

from agent.contracts.inputs.clarification import ClarificationRequest
from agent.tools.interaction.ask import ask_user_tool

QUESTION: dict[str, JsonValue] = {
    "id": "units",
    "text": "How many housing units?",
    "kind": "program_fact",
    "why": "Parking depends on it.",
    "options": ["40", "60"],
    "recommended": "40",
}
QUESTIONS: dict[str, JsonValue] = {"questions": [QUESTION]}


class ScriptedModel(GenericFakeChatModel):
    """Fake chat model replaying scripted messages, accepting any tool binding."""

    @override
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


def agent_asking(args: dict[str, JsonValue]):
    replies: Iterator[AIMessage] = iter(
        [
            AIMessage(content="", tool_calls=[{"name": "ask_user", "args": args, "id": "a1"}]),
            AIMessage("done"),
        ]
    )
    return create_agent(
        model=ScriptedModel(messages=replies),
        tools=[ask_user_tool()],
        checkpointer=InMemorySaver(),
    )


def tool_reply(state) -> ToolMessage:
    [message] = [m for m in state["messages"] if isinstance(m, ToolMessage)]
    return message


def test_interrupt_then_resume():
    agent = agent_asking(QUESTIONS)
    config: RunnableConfig = {"configurable": {"thread_id": "t1"}}

    first = agent.invoke({"messages": [HumanMessage("study this site")]}, config)
    [pending] = first["__interrupt__"]
    assert pending.value["action_requests"][0]["args"] == {"units": "40"}
    assert ClarificationRequest.model_validate(pending.value["clarification"]) == (
        ClarificationRequest.model_validate(QUESTIONS)
    )
    assert not any(isinstance(m, ToolMessage) for m in first["messages"])

    resume = {"decisions": [{"type": "edit", "edited_action": {"args": {"units": "60"}}}]}
    final = agent.invoke(Command(resume=resume), config)
    reply = tool_reply(final)
    assert reply.status == "success"
    assert "- units: 60" in reply.content
    assert final["messages"][-1].content == "done"


def test_invalid_questions_do_not_interrupt():
    bad: dict[str, JsonValue] = {"questions": [{**QUESTION, "recommended": "50"}]}
    agent = agent_asking(bad)
    state = agent.invoke({"messages": [HumanMessage("go")]}, {"configurable": {"thread_id": "t2"}})
    assert "__interrupt__" not in state
    reply = tool_reply(state)
    assert reply.status == "error"
    assert "questions.0: Value error, recommended must be one of options" in reply.content
