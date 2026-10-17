from typing import cast

import httpx
import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from agent.adapters.geo.imagery import ImageryClient, OutlineStyle, blank_image
from agent.adapters.http import CachedHttp
from agent.contracts.envelope import BuildingLimits, Distance, EnvelopeRules, Layout, SetbackRule
from agent.contracts.evidence import Citation, Limit, SourceKind
from agent.contracts.findings.site import Edge, EdgeSide, Parcel, ParcelChoice, Site
from agent.contracts.geometry import BoundaryKind, Polygon
from agent.runtime.geometry.envelope.study import EnvelopeSettings
from agent.tools.envelope.compute import GeometrySettings
from agent.tools.envelope.plan import PlanSettings

RECTANGLE = ((0.0, 0.0), (60.0, 0.0), (60.0, 30.0), (0.0, 30.0), (0.0, 0.0))
SIDES = (EdgeSide.PUBLIC_LAND, EdgeSide.PARCEL, EdgeSide.PARCEL, EdgeSide.PARCEL)
CADASTRE = Citation(doc="cadastre", quote="91272000AB0123", source_kind=SourceKind.GEOMETRIC)
UMG = Citation(doc="plu_reglement", page=326, quote="20 mètres", source_kind=SourceKind.REGULATORY)
GEOMETRY = GeometrySettings(snap_tolerance_m=0.5, collinear_angle_deg=20)
SETTINGS = EnvelopeSettings(level_step_m=1, quad_segs=8, min_area_m2=1, cut_tolerance_m=0.01)
IMAGE_PX = 200
STYLE = OutlineStyle(rgb=(230, 0, 0), width_px=2, font_px=8, label_background_rgb=(255, 255, 255))
PLAN = PlanSettings(
    kind="map",
    parcel_margin_ratio=0.3,
    min_half_width_m=40,
    image_px=IMAGE_PX,
    style=STYLE,
    fill_opacity=1.0,
    limit_rgbs={
        BoundaryKind.ROAD: (0, 90, 220),
        BoundaryKind.SIDE: (240, 130, 0),
        BoundaryKind.REAR: (150, 0, 170),
    },
    setback_rgb=(230, 0, 0),
    building_rgbs=((0, 160, 70), (0, 170, 200)),
    gap_rgb=(0, 0, 0),
)


@pytest.fixture
def site():
    polygon = Polygon(crs="EPSG:2154", exterior=RECTANGLE)
    return Site(
        address="4 Rue Joliot Curie 91190 Gif-sur-Yvette",
        longitude=2.16,
        latitude=48.71,
        choice=ParcelChoice(
            address="4 Rue Joliot Curie 91190 Gif-sur-Yvette",
            parcel_ids=("91272000AB0123",),
            rationale="Only parcel at the address.",
        ),
        parcels=(Parcel(id="91272000AB0123", area_m2=1800, polygon=polygon),),
        polygon=polygon,
        area_m2=1800,
        edges=tuple(
            Edge(start=start, end=end, length_m=1, other_side=side)
            for side, start, end in zip(SIDES, RECTANGLE[:-1], RECTANGLE[1:], strict=True)
        ),
        citations=(CADASTRE,),
    )


def distance(min_m):
    return Distance(min_m=min_m, rule="see article", citations=(UMG,))


def limit(value):
    return Limit(value=value, rule="see article", citations=() if value is None else (UMG,))


@pytest.fixture
def rules():
    return EnvelopeRules(
        setbacks=(
            SetbackRule(kind=BoundaryKind.ROAD, on_limit_allowed=True, with_windows=distance(1)),
            SetbackRule(kind=BoundaryKind.SIDE, on_limit_allowed=False, with_windows=distance(4)),
            SetbackRule(kind=BoundaryKind.REAR, on_limit_allowed=False, with_windows=distance(4)),
        ),
        buildings=(
            BuildingLimits(building="RSE", max_height_m=limit(25), max_storeys=limit(None)),
            BuildingLimits(building="RJA", max_height_m=limit(20), max_storeys=limit(6)),
        ),
        spacing_with_windows=distance(10),
        spacing_without_windows=distance(6),
        max_footprint_ratio=limit(None),
        min_green_ratio=limit(0.2),
    )


@pytest.fixture
def layout():
    return Layout(
        cut="across_long_axis",
        first_share=0.5,
        order=("RSE", "RJA"),
        facing_windows=True,
        reasons="Two halves, RSE on the road side.",
    )


@pytest.fixture
def draft_args(rules, layout):
    return {"rules": rules.model_dump(mode="json"), "layout": layout.model_dump(mode="json")}


def route(request: httpx.Request) -> httpx.Response:
    params = request.url.params
    size = (int(params["WIDTH"]), int(params["HEIGHT"]))
    return httpx.Response(200, content=blank_image(size), headers={"content-type": "image/png"})


def make_imagery(http: CachedHttp) -> ImageryClient:
    return ImageryClient(
        url="https://data.geopf.fr/wms-r/wms",
        http=http,
        version="1.3.0",
        crs="EPSG:2154",
        media_type="image/png",
        layers={"map": "GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2", "aerial": "ORTHOIMAGERY.ORTHOPHOTOS"},
        source="IGN Géoplateforme WMS",
    )


@pytest.fixture
def transport():
    return httpx.MockTransport(route)


@pytest.fixture
def imagery(tmp_path, transport):
    return make_imagery(CachedHttp(tmp_path, 5, transport))


@pytest.fixture
def broken_imagery(tmp_path):
    def unavailable(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="maintenance")

    return make_imagery(CachedHttp(tmp_path / "broken", 5, httpx.MockTransport(unavailable)))


@pytest.fixture
def geometry():
    return GEOMETRY


@pytest.fixture
def settings():
    return SETTINGS


@pytest.fixture
def plan():
    return PLAN


def _runtime(artifacts):
    return ToolRuntime(
        state={"messages": [], "artifacts": artifacts},
        context=None,
        config={},
        stream_writer=lambda _: None,
        tool_call_id="1",
        store=None,
    )


@pytest.fixture
def invoke():
    def run(tool, args, artifacts):
        call = {"type": "tool_call", "id": "1", "name": tool.name}
        return tool.invoke({**call, "args": {**args, "runtime": _runtime(artifacts)}})

    return run


@pytest.fixture
def reply():
    def only(result):
        if isinstance(result, Command):
            (result,) = cast("Command[str]", result).update["messages"]
        assert isinstance(result, ToolMessage)
        return result

    return only
