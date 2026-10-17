import pytest
from hydra.utils import instantiate
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage

from agent.contracts.evidence import Citation, SourceKind
from agent.contracts.findings.site import Parcel, SiteContext
from agent.contracts.geometry import Boundary, BoundaryKind, Envelope, Polygon
from agent.tools.envelope.compute import compute_envelope_tool

SQUARE = ((0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0), (0.0, 0.0))
KINDS = (BoundaryKind.ROAD, BoundaryKind.SIDE, BoundaryKind.REAR, BoundaryKind.SIDE)


@pytest.fixture
def site():
    polygon = Polygon(crs="EPSG:2154", exterior=SQUARE)
    return SiteContext(
        address="1 rue de test",
        longitude=2.16,
        latitude=48.71,
        parcels=(Parcel(id="91272000AB0001", area_m2=1200, polygon=polygon),),
        polygon=polygon,
        area_m2=1200,
        boundaries=tuple(
            Boundary(kind=kind, start=start, end=end)
            for kind, start, end in zip(KINDS, SQUARE[:-1], SQUARE[1:], strict=True)
        ),
        method="test",
        citations=(Citation(doc="cadastre", quote="AB0001", source_kind=SourceKind.GEOMETRIC),),
    )


@pytest.fixture
def args():
    citation = {"doc": "plu", "page": 327, "quote": "5 mètres", "source_kind": "regulatory"}

    def limit(value):
        return {
            "value": value,
            "rule": "see article",
            "citations": [] if value is None else [citation],
        }

    return {
        "setback_road_m": limit(5),
        "setback_side_m": limit(3),
        "setback_rear_m": limit(4),
        "max_height_m": limit(10),
        "max_storeys": limit(None),
        "max_footprint_ratio": limit(0.4),
        "min_green_ratio": limit(0.2),
    }


@pytest.fixture
def tool():
    return compute_envelope_tool(site_artifact="site", quad_segs=8, min_area_m2=1.0)


def invoke(tool, args, artifacts=None):
    state = {"messages": [], **({"artifacts": artifacts} if artifacts is not None else {})}
    runtime = ToolRuntime(
        state=state,
        context=None,
        config={},
        stream_writer=lambda _: None,
        tool_call_id="1",
        store=None,
    )
    message = tool.invoke(
        {"type": "tool_call", "id": "1", "name": tool.name, "args": {**args, "runtime": runtime}}
    )
    assert isinstance(message, ToolMessage)
    assert message.tool_call_id == "1"
    return message


def test_schema_hides_runtime(tool):
    assert tool.name == "compute_envelope"
    assert "submit_study recomputes" in tool.description
    assert "runtime" not in tool.tool_call_schema["properties"]


def test_site_present_returns_envelope(tool, args, site):
    message = invoke(tool, args, artifacts={"site": site.model_dump(mode="json")})
    assert message.status == "success"
    envelope = Envelope.model_validate_json(message.content)
    assert envelope.footprint_area_m2 == pytest.approx(34 * 21)
    assert envelope.max_footprint_area_m2 == pytest.approx(480)
    assert envelope.max_volume_m3 == pytest.approx(4800)


def test_site_missing_returns_error(tool, args):
    message = invoke(tool, args)
    assert message.status == "error"
    assert "site_locator" in message.content
    assert "submit_site" in message.content


def test_invalid_parameters_return_field_errors(tool, args, site):
    del args["max_height_m"]
    args["setback_road_m"] = {"value": 5, "rule": "see article"}
    message = invoke(tool, args, artifacts={"site": site.model_dump(mode="json")})
    assert message.status == "error"
    assert "max_height_m: Field required" in message.content
    assert "setback_road_m: Value error, a limit with a value needs" in message.content


def test_hydra_instantiates_tool():
    tool = instantiate(
        {
            "_target_": "agent.tools.envelope.compute.compute_envelope_tool",
            "site_artifact": "site",
            "quad_segs": 8,
            "min_area_m2": 1.0,
        }
    )
    assert tool.name == "compute_envelope"
