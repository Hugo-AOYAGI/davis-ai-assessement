import json
from typing import cast

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.types import Command
from pydantic import JsonValue

from agent.contracts.evidence import SourceKind
from agent.contracts.findings.site import EdgeSide, ParcelChoice, Site
from agent.tools.geo.site import parcel_finalizer, summarize_site
from agent.tools.submit.artifacts import read_artifact
from agent.tools.submit.factory import submit_tool

LABEL = "4 Rue Joliot-curie 91190 Gif-sur-Yvette"
PLOT, STRIP = "91272000CR0247", "91272000CR0249"
STREET_M = 91
CHOICE: dict[str, JsonValue] = {
    "address": LABEL,
    "parcel_ids": [PLOT],
    "rationale": "Address point 2.5 m from CR0247; CR0249 (1.8 m) is a 116 m2 strip.",
    "assumptions": ["Cadastre is current."],
}


def make_submit(surveyor) -> BaseTool:
    return submit_tool(
        name="submit_parcel",
        artifact="site",
        contract=ParcelChoice,
        finalize=parcel_finalizer(surveyor),
        summarize=summarize_site,
    )


def runtime() -> ToolRuntime:
    return ToolRuntime(
        state={"messages": []},
        context=None,
        config={},
        stream_writer=lambda _: None,
        tool_call_id="1",
        store=None,
    )


def invoke(tool: BaseTool, args: dict[str, JsonValue]) -> Command[str]:
    result = tool.invoke(
        {"type": "tool_call", "id": "1", "name": tool.name, "args": {**args, "runtime": runtime()}}
    )
    assert isinstance(result, Command)
    return cast("Command[str]", result)


def reply(command: Command[str]) -> ToolMessage:
    update = command.update
    assert isinstance(update, dict)
    (message,) = update["messages"]
    assert isinstance(message, ToolMessage)
    return message


def test_submit_schema(surveyor):
    submit = make_submit(surveyor)
    assert submit.name == "submit_parcel"
    assert set(submit.args) == {
        "address",
        "parcel_ids",
        "rationale",
        "assumptions",
        "public_parcels",
    }


def test_submit_stores_the_site(surveyor):
    command = invoke(make_submit(surveyor), CHOICE)
    update = command.update
    assert isinstance(update, dict)
    site = read_artifact(update["artifacts"], "site", Site)
    assert site is not None
    assert site.address == LABEL
    assert site.choice == ParcelChoice.model_validate(CHOICE)
    assert [parcel.id for parcel in site.parcels] == [PLOT]
    assert site.area_m2 == pytest.approx(5952, abs=2)
    assert {edge.other_side for edge in site.edges} == {EdgeSide.PARCEL}
    assert [c.doc for c in site.citations] == ["geoplateforme-geocodage", "apicarto-cadastre"]
    assert all(c.source_kind is SourceKind.GEOMETRIC for c in site.citations)


def test_submit_reply_summarises_the_site(surveyor):
    message = reply(invoke(make_submit(surveyor), {**CHOICE, "parcel_ids": [PLOT, STRIP]}))
    head, body = str(message.content).split("\n\n", 1)
    assert head == "site accepted."
    summary = json.loads(body)
    assert summary["address"] == LABEL
    assert summary["area_m2"] == pytest.approx(6071, abs=2)
    assert summary["parcels"] == [
        {"id": PLOT, "contenance_m2": 5960},
        {"id": STRIP, "contenance_m2": 116},
    ]
    assert summary["edges"]["public_land"]["length_m"] == pytest.approx(91, abs=2)
    assert summary["neighbours"] == ["91272000CR0227", "91272000CR0256"]
    assert summary["public_parcels"] == []


def test_submit_with_a_declared_public_strip(surveyor):
    declared: list[JsonValue] = [{"id": STRIP, "reason": "116 m2 strip; aerial shows pavement."}]
    message = reply(invoke(make_submit(surveyor), {**CHOICE, "public_parcels": declared}))
    summary = json.loads(str(message.content).split("\n\n", 1)[1])
    assert summary["public_parcels"] == declared
    assert summary["edges"]["public_land"]["length_m"] == pytest.approx(STREET_M, abs=2)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"address": "4 rue Joliot Curie"}, "exactly as geocode returned it"),
        ({"parcel_ids": ["91272000CR9999"]}, "not in the cadastre"),
        ({"parcel_ids": [PLOT, "91272000CR0215"]}, "separate parts"),
        (
            {"parcel_ids": [PLOT, STRIP], "public_parcels": [{"id": STRIP, "reason": "verge"}]},
            f"public_parcels.0.id: {STRIP} is in parcel_ids",
        ),
        (
            {"public_parcels": [{"id": "91272000CR0215", "reason": "verge"}]},
            "public_parcels.0.id: 91272000CR0215 does not lie along an edge of the site",
        ),
    ],
)
def test_submit_rejections(surveyor, changes, message):
    command = invoke(make_submit(surveyor), {**CHOICE, **changes})
    message_out = reply(command)
    assert message_out.status == "error"
    assert "submit_parcel rejected" in str(message_out.content)
    assert message in str(message_out.content)
    update = command.update
    assert isinstance(update, dict)
    assert "artifacts" not in update


def test_submit_service_error_is_rejected(broken_surveyor):
    message = reply(invoke(make_submit(broken_surveyor), CHOICE))
    assert message.status == "error"
    assert "503" in str(message.content)
    assert "submit the same choice again" in str(message.content)
