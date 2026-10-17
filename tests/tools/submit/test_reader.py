import json

from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage

from agent.tools.submit.reader import read_artifact_tool


def invoke(name, artifacts=None):
    state = {"messages": [], **({"artifacts": artifacts} if artifacts is not None else {})}
    runtime = ToolRuntime(
        state=state,
        context=None,
        config={},
        stream_writer=lambda _: None,
        tool_call_id="1",
        store=None,
    )
    tool = read_artifact_tool()
    message = tool.invoke(
        {
            "type": "tool_call",
            "id": "1",
            "name": tool.name,
            "args": {"name": name, "runtime": runtime},
        }
    )
    assert isinstance(message, ToolMessage)
    return message


def test_schema_hides_runtime():
    tool = read_artifact_tool()
    assert tool.name == "read_artifact"
    assert list(tool.args) == ["name"]
    assert "verbatim" in tool.description


def test_returns_artifact_json():
    data = {"applicable": True, "name": "Joliot Curie", "rationale": "Déjà vu."}
    message = invoke("oap_findings", {"oap_findings": data, "site": {"area_m2": 1}})
    assert message.status == "success"
    assert json.loads(message.content) == data
    assert "Déjà" in message.content


def test_unknown_name_lists_available():
    message = invoke("study", {"site": {}, "oap_findings": {}})
    assert message.status == "error"
    assert "No artifact named 'study'" in message.content
    assert "Available artifacts: oap_findings, site." in message.content


def test_no_artifact_yet():
    message = invoke("site")
    assert message.status == "error"
    assert "No artifact has been delivered yet" in message.content
