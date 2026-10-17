import json
from typing import cast

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.types import Command
from pydantic import JsonValue

from agent.contracts.evidence import SourceKind
from agent.contracts.findings.site import SiteContext
from agent.contracts.geometry import BoundaryKind
from agent.tools.geo.site import SiteSelection, preview_site_tool, site_finalizer
from agent.tools.submit.artifacts import read_artifact
from agent.tools.submit.factory import submit_tool

LABEL = "4 Rue Joliot-curie 91190 Gif-sur-Yvette"
PLOT, STRIP = "91272000CR0247", "91272000CR0249"
SELECTION: dict[str, JsonValue] = {
    "address": LABEL,
    "parcel_ids": [PLOT],
    "public_parcel_ids": [STRIP],
    "method": "Geocoded the address, retained the plot nearest to the point.",
    "assumptions": ["CR0249 is a strip along the street, declared public space."],
}


@pytest.fixture
def submit(surveyor) -> BaseTool:
    return submit_tool("site", SiteSelection, finalize=site_finalizer(surveyor))


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


def test_preview_schema(surveyor):
    tool = preview_site_tool(surveyor)
    assert tool.name == "preview_site"
    properties = tool.args
    assert set(properties) == {"address", "parcel_ids", "public_parcel_ids"}
    assert "geocode_address" in properties["address"]["description"]
    assert "nearest_boundary" in tool.description


def test_preview_with_public_strip(surveyor):
    summary = json.loads(
        preview_site_tool(surveyor).invoke(
            {"address": LABEL, "parcel_ids": [PLOT], "public_parcel_ids": [STRIP]}
        )
    )
    assert summary["area_m2"] == pytest.approx(5952, abs=2)
    assert summary["parcels"] == [{"id": PLOT, "contenance_m2": 5960}]
    assert set(summary["boundaries"]) == {"road", "side", "rear"}
    assert summary["boundaries"]["road"]["length_m"] == pytest.approx(91, abs=2)
    assert summary["boundaries"]["rear"]["edges"] > 0
    assert summary["nearest_boundary"] == {"kind": "road", "distance_m": 2.5}
    strip = summary["neighbours"][0]
    assert strip["id"] == STRIP
    assert strip["public"] is True
    assert strip["mean_width_m"] <= 1
    assert set(strip) == {"id", "contenance_m2", "shared_length_m", "mean_width_m", "public"}


def test_preview_without_public_strip_is_enclosed(surveyor):
    summary = json.loads(
        preview_site_tool(surveyor).invoke({"address": LABEL, "parcel_ids": [PLOT]})
    )
    assert summary["nearest_boundary"]["kind"] == "rear"
    assert summary["boundaries"]["road"] == {"length_m": 0, "edges": 0}


def test_preview_error_is_a_message(surveyor):
    reply_text = preview_site_tool(surveyor).invoke({"address": "4 rue", "parcel_ids": [PLOT]})
    assert reply_text.startswith("preview_site failed:")
    assert "exactly as geocode_address returned it" in reply_text


def test_submit_schema(submit):
    assert submit.name == "submit_site"
    properties = submit.tool_call_schema["properties"]
    assert set(properties) == {
        "address",
        "parcel_ids",
        "public_parcel_ids",
        "method",
        "assumptions",
    }
    assert "runtime" not in properties
    assert "computed from them" in submit.description


def test_submit_stores_site_context(submit):
    command = invoke(submit, SELECTION)
    assert reply(command).content == "site accepted."
    update = command.update
    assert isinstance(update, dict)
    site = read_artifact(update["artifacts"], "site", SiteContext)
    assert site is not None
    assert site.address == LABEL
    assert (site.longitude, site.latitude) == (2.165254, 48.709836)
    assert [parcel.id for parcel in site.parcels] == [PLOT]
    assert site.area_m2 == pytest.approx(5952, abs=2)
    assert site.polygon.crs == "EPSG:2154"
    assert {b.kind for b in site.boundaries} == set(BoundaryKind)
    assert site.method == SELECTION["method"]
    assert site.assumptions == ("CR0249 is a strip along the street, declared public space.",)
    assert [c.doc for c in site.citations] == [
        "geoplateforme-geocodage",
        "apicarto-cadastre",
        "apicarto-cadastre",
    ]
    assert all(c.source_kind is SourceKind.GEOMETRIC for c in site.citations)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"address": "4 rue Joliot Curie"}, "exactly as geocode_address returned it"),
        ({"parcel_ids": [PLOT, "91272000CR0215"], "public_parcel_ids": []}, "separate parts"),
    ],
)
def test_submit_rejections(submit, changes, message):
    command = invoke(submit, {**SELECTION, **changes})
    message_out = reply(command)
    assert message_out.status == "error"
    assert "submit_site rejected" in str(message_out.content)
    assert message in str(message_out.content)
    update = command.update
    assert isinstance(update, dict)
    assert "artifacts" not in update


def test_submit_service_error_is_rejected(broken_surveyor):
    tool = submit_tool("site", SiteSelection, finalize=site_finalizer(broken_surveyor))
    message = reply(invoke(tool, SELECTION))
    assert message.status == "error"
    assert "503" in str(message.content)
