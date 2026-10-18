import re
from datetime import date

import httpx
import numpy as np
import pymupdf
import pytest
from langchain_core.messages import ToolMessage

from agent.adapters.georef.store import save_georeference
from agent.adapters.http import CachedHttp
from agent.adapters.images.pages import PageImages
from agent.adapters.images.render import LineStyle
from agent.adapters.images.store import ImageStore
from agent.contracts.inputs.georeference import PlanGeoreference
from agent.runtime.geometry.parcels import to_shape
from agent.tools.images.view import zoom_tool
from agent.tools.plan.site import plan_site_tool
from tests.tools.geo.conftest import make_surveyor, route

PLOT = "91272000CR0247"
FULL = (1200, 600)
RED = (255, 0, 0)
GREY = (200, 200, 200)


@pytest.fixture
def pages(tmp_path):
    width, height = FULL
    array = np.full((height, width, 3), 200, dtype=np.uint8)
    with pymupdf.open() as document:
        scan = document.new_page(width=300, height=150)
        scan.insert_image(
            scan.rect, pixmap=pymupdf.Pixmap(pymupdf.csRGB, width, height, array.tobytes(), 0)
        )
        document.save(tmp_path / "plan.pdf")
    return PageImages(
        documents=[{"id": "plan", "path": "plan.pdf"}],
        root=tmp_path,
        render_dpi=72,
        max_image_px=440,
        max_upscale=2.0,
        ruler_step_px=100,
        crop_max_px=500,
        cache_size=2,
        scan_min_coverage=0.8,
        max_image_bytes=4_000_000,
    )


@pytest.fixture
def store(tmp_path):
    return ImageStore(directory=tmp_path / "images", url_prefix="/images")


@pytest.fixture
def georef_path(tmp_path, surveyor):
    centre = to_shape(surveyor.parcels([PLOT])[0].polygon).centroid
    georef = PlanGeoreference(
        document="plan",
        page=1,
        image_width=FULL[0],
        image_height=FULL[1],
        crs="EPSG:2154",
        matrix=(1.0, 0.0, 600 - centre.x, 0.0, -1.0, 300 + centre.y),
        pixels_per_metre=1.0,
        iou=0.99,
        mean_error_m=3.0,
        max_error_m=20.0,
        boundary_source="test",
        created=date(2026, 10, 18),
    )
    path = tmp_path / "georef.json"
    save_georeference(georef, path)
    return path


@pytest.fixture
def surveyor(tmp_path):
    return make_surveyor(CachedHttp(tmp_path / "cache", 5, httpx.MockTransport(route)))


def build(surveyor, pages, store, path):
    return plan_site_tool(
        surveyor=surveyor,
        pages=pages,
        store=store,
        georeference=path,
        close_margin_m=20,
        context_margin_m=200,
        context_max_px=300,
        max_upscale=4.0,
        uncertainty_factor=2.0,
        style=LineStyle(rgb=RED, width_px=1.5),
    )


def invoke(tool, **args):
    message = tool.invoke({"type": "tool_call", "id": "1", "name": tool.name, "args": args})
    assert isinstance(message, ToolMessage)
    return message


def regions(text):
    return [
        [int(value) for value in found.split(", ")]
        for found in re.findall(r"region \[(\d+, \d+, \d+, \d+)\]", text)
    ]


def red_pixels(store, block):
    pixmap = pymupdf.Pixmap(store.read(block["url"]))
    rgb = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.stride)
    rgb = rgb[:, : pixmap.width * 3].reshape(pixmap.height, pixmap.width, 3).astype(int)
    return int(((rgb[..., 0] > 200) & (rgb[..., 1] < 120) & (rgb[..., 2] < 120)).sum())


def test_plan_site_returns_two_outlined_crops_and_their_regions(
    surveyor, pages, store, georef_path
):
    reply = invoke(build(surveyor, pages, store, georef_path), ids=[PLOT])
    assert reply.status != "error"
    caption, close, context = reply.content
    text = caption["text"]
    assert text.startswith(f"Site {PLOT} on plan p.1, outlined in RGB (255, 0, 0).")
    assert "±6 m" in text
    assert "close-up (site + 20 m)" in text
    assert "context (site + 200 m)" in text
    close_region, context_region = regions(text)
    assert context_region[0] <= close_region[0] < close_region[2] <= context_region[2]
    assert context_region[1] <= close_region[1] < close_region[3] <= context_region[3]
    assert red_pixels(store, close) > 0
    assert red_pixels(store, context) > 0
    zoom = zoom_tool(pages=pages, store=store)
    for region in (close_region, context_region):
        assert invoke(zoom, doc="plan", page=1, region=region).status != "error"
        assert red_pixels(store, invoke(zoom, doc="plan", page=1, region=region).content[1]) == 0


def test_close_up_is_centred_on_the_projected_parcel(surveyor, pages, store, georef_path):
    reply = invoke(build(surveyor, pages, store, georef_path), ids=[PLOT])
    x0, y0, x1, y1 = regions(reply.content[0]["text"])[0]
    parcel = to_shape(surveyor.parcels([PLOT])[0].polygon)
    min_x, min_y, max_x, max_y = parcel.bounds
    centre = parcel.centroid
    ratio = FULL[0] / 400
    u = 600 + (min_x + max_x) / 2 - centre.x
    v = 300 + centre.y - (min_y + max_y) / 2
    half = (max(max_x - min_x, max_y - min_y) / 2 + 20) / ratio
    assert (x0 + x1) / 2 == pytest.approx(u / ratio, abs=1)
    assert (y0 + y1) / 2 == pytest.approx(v / ratio, abs=1)
    assert (x1 - x0) / 2 == pytest.approx(half, abs=1)


def test_missing_georeference_tells_how_to_build_it(surveyor, pages, store, tmp_path):
    reply = invoke(build(surveyor, pages, store, tmp_path / "none.json"), ids=[PLOT])
    assert reply.status == "error"
    assert "uv run python -m agent.entrypoints.ingest georef" in reply.content


def test_unknown_parcel_is_a_tool_error(surveyor, pages, store, georef_path):
    reply = invoke(build(surveyor, pages, store, georef_path), ids=["91272000ZZ9999"])
    assert reply.status == "error"


def test_description_mentions_regions_and_zoom(surveyor, pages, store, georef_path):
    tool = build(surveyor, pages, store, georef_path)
    assert tool.name == "plan_site"
    assert "submit_zone" in tool.description
    assert "zoom" in tool.description
