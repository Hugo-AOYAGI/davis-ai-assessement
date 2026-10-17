from collections.abc import Iterator
from typing import override

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from agent.llm.truncation import OutputCapMiddleware, cut_off_notices, stopped_at_output_cap

CUT = {"stop_reason": "max_tokens"}


class ScriptedModel(GenericFakeChatModel):
    @override
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


def scripted(*messages: AIMessage) -> ScriptedModel:
    replies: Iterator[AIMessage] = iter(messages)
    return ScriptedModel(messages=replies)


def truncated_call() -> AIMessage:
    return AIMessage(
        content="",
        invalid_tool_calls=[
            {
                "type": "invalid_tool_call",
                "name": "submit",
                "args": '{"text": "abc',
                "id": "t1",
                "error": None,
            }
        ],
        response_metadata=CUT,
    )


@tool
def submit(text: str) -> str:
    """Submit the text."""
    return f"accepted {text}"


def test_stop_reason_detection():
    assert stopped_at_output_cap(AIMessage("x", response_metadata=CUT))
    assert not stopped_at_output_cap(AIMessage("x", response_metadata={"stop_reason": "end_turn"}))
    assert not stopped_at_output_cap(AIMessage("x"))


def test_every_tool_call_gets_an_error_result():
    message = truncated_call()
    message.tool_calls = [{"name": "submit", "args": {}, "id": "t0", "type": "tool_call"}]
    notices = cut_off_notices(message)
    assert [n.tool_call_id for n in notices if isinstance(n, ToolMessage)] == ["t0", "t1"]
    assert all(isinstance(n, ToolMessage) and n.status == "error" for n in notices)
    assert "cut off" in str(notices[0].content)


def test_reply_without_tool_calls_gets_a_user_message():
    [notice] = cut_off_notices(AIMessage("half a sentence", response_metadata=CUT))
    assert isinstance(notice, HumanMessage)
    assert "cut off" in str(notice.content)


def test_agent_retries_after_a_truncated_tool_call():
    model = scripted(
        truncated_call(),
        AIMessage(content="", tool_calls=[{"name": "submit", "args": {"text": "ok"}, "id": "t2"}]),
        AIMessage(content="done"),
    )
    agent = create_agent(model=model, tools=[submit], middleware=[OutputCapMiddleware()])
    state = agent.invoke({"messages": [HumanMessage("go")]})

    replies = {m.tool_call_id: m for m in state["messages"] if isinstance(m, ToolMessage)}
    assert replies["t1"].status == "error"
    assert "not run" in str(replies["t1"].content)
    assert replies["t2"].content == "accepted ok"
    assert state["messages"][-1].content == "done"


def test_truncated_valid_call_is_not_run():
    model = scripted(
        AIMessage(
            content="",
            tool_calls=[{"name": "submit", "args": {"text": "partial"}, "id": "t1"}],
            response_metadata=CUT,
        ),
        AIMessage(content="done"),
    )
    agent = create_agent(model=model, tools=[submit], middleware=[OutputCapMiddleware()])
    state = agent.invoke({"messages": [HumanMessage("go")]})

    results = [m for m in state["messages"] if isinstance(m, ToolMessage)]
    assert [m.status for m in results] == ["error"]
    assert state["messages"][-1].content == "done"
