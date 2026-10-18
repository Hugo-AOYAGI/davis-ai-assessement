import pytest
from langchain_core.messages import ToolMessage

from agent.tools.interaction.playbook import Playbook, load_playbook_tool

PLAYBOOKS = {
    "study": Playbook(description="Full study.", text="Write in $language. Costs $5 or $$."),
    "memo": Playbook(description="Short memo.", text="Memo."),
}


@pytest.fixture
def tool():
    return load_playbook_tool(PLAYBOOKS, "French")


def test_description_lists_playbooks(tool):
    assert tool.name == "load_playbook"
    assert "- `study`: Full study.\n- `memo`: Short memo." in tool.description


def test_language_is_substituted(tool):
    assert tool.invoke({"name": "study"}) == "Write in French. Costs $5 or $."
    assert tool.invoke({"name": "memo"}) == "Memo."


def test_unknown_name_lists_playbooks(tool):
    message = tool.invoke(
        {"type": "tool_call", "id": "1", "name": tool.name, "args": {"name": "x"}}
    )
    assert isinstance(message, ToolMessage)
    assert message.status == "error"
    assert "No playbook named 'x'. Available playbooks: memo, study." in message.content


def test_empty_playbooks_rejected():
    with pytest.raises(ValueError, match="at least one playbook"):
        load_playbook_tool({}, "English")


def test_configured_topic_lists_are_substituted():
    book = Playbook(
        description="Study.", text="Topics: $topics", lists={"topics": ("height", "parking")}
    )
    assert (
        load_playbook_tool({"study": book}, "English").invoke({"name": "study"})
        == "Topics: `height`, `parking`"
    )
