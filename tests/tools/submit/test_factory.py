from collections.abc import Mapping
from typing import cast

import pytest
from hydra.utils import instantiate
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.types import Command
from pydantic import JsonValue

from agent.contracts.findings.oap import OAPFindings
from agent.contracts.findings.site import SiteContext
from agent.tools.submit.artifacts import ArtifactData, Artifacts
from agent.tools.submit.factory import SubmissionRejected, submit_tool


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


def test_schema_and_description_come_from_contract(oap_tool):
    assert oap_tool.name == "submit_oap_findings"
    assert "Whether an OAP covers the site" in oap_tool.description
    schema = oap_tool.tool_call_schema
    assert isinstance(schema, dict)
    assert set(schema["properties"]) == set(OAPFindings.model_fields)
    assert "runtime" not in schema["properties"]
    assert schema["properties"]["name"]["description"].startswith("Title of the applicable OAP")


def test_valid_submission_is_stored(oap_tool, oap_args):
    command = invoke(oap_tool, oap_args)
    stored = command.update["artifacts"]["oap_findings"]
    assert OAPFindings.model_validate(stored) == OAPFindings.model_validate(oap_args)
    assert only_message(command).content == "oap_findings accepted."


def test_invalid_submission_returns_field_errors(oap_tool, bad_oap_args):
    command = invoke(oap_tool, bad_oap_args)
    assert "artifacts" not in command.update
    message = only_message(command)
    assert message.status == "error"
    assert "rationale: Field required" in message.content
    assert "citations.0: Value error, a regulatory citation needs a page" in message.content


def site_name(submission: OAPFindings, artifacts: Mapping[str, ArtifactData]) -> OAPFindings:
    if "site" not in artifacts:
        raise SubmissionRejected(["submit the site first", "then resubmit"])
    return submission.model_copy(update={"name": f"{submission.name} @ {artifacts['site']['id']}"})


def test_finalize_stores_finalized_object(oap_args):
    tool = submit_tool("oap_findings", OAPFindings, finalize=site_name)
    command = invoke(tool, oap_args, artifacts={"site": {"id": "AB0123"}})
    assert command.update["artifacts"]["oap_findings"]["name"] == "Joliot Curie @ AB0123"


def test_finalize_rejection_returns_errors(oap_args):
    tool = submit_tool("oap_findings", OAPFindings, finalize=site_name)
    command = invoke(tool, oap_args)
    assert "artifacts" not in command.update
    message = only_message(command)
    assert message.status == "error"
    assert "- submit the site first\n- then resubmit" in message.content


def test_submission_rejected_keeps_errors():
    with pytest.raises(SubmissionRejected) as info:
        raise SubmissionRejected(["a", "b"])
    assert info.value.errors == ("a", "b")


def test_hydra_instantiates_tool():
    tool = instantiate(
        {
            "_target_": "agent.tools.submit.factory.submit_tool",
            "artifact": "site",
            "contract": {
                "_target_": "hydra.utils.get_class",
                "path": "agent.contracts.findings.site.SiteContext",
            },
        }
    )
    assert tool.name == "submit_site"
    assert set(tool.tool_call_schema["properties"]) == set(SiteContext.model_fields)
