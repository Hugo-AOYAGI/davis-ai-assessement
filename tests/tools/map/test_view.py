import base64

import pymupdf
import pytest

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def view_map(map_tools):
    return map_tools["view_map"]


@pytest.fixture
def artifacts(site_data):
    return {"site": site_data}


def decode(block) -> pymupdf.Pixmap:
    assert block["type"] == "image"
    assert block["mime_type"] == "image/png"
    png = base64.b64decode(block["base64"])
    assert png.startswith(PNG_SIGNATURE)
    return pymupdf.Pixmap(png)


def test_schema_hides_runtime(view_map):
    schema = view_map.tool_call_schema.model_json_schema()
    assert set(schema["properties"]) == {"half_width_m", "east_m", "north_m"}
    assert "zoom out" in view_map.description


def test_default_view(view_map, artifacts, invoke, map_cfg):
    message = invoke(view_map, {}, artifacts)
    text, image = message.content
    assert text["type"] == "text"
    caption = text["text"]
    for expected in [
        "`plu_reglement_graphique`, page 1",
        "half-width 150 m",
        "north up",
        "RGB (0, 229, 255)",
        "91272000CR0247",
        "12 control points",
    ]:
        assert expected in caption
    picture = decode(image)
    limit = map_cfg.subagents.zoning_map_reader.tools[0].max_output_px
    assert max(picture.width, picture.height) <= limit
    assert picture.width == picture.height


def test_half_width_is_clamped(view_map, artifacts, invoke):
    message = invoke(view_map, {"half_width_m": 5000}, artifacts)
    assert "half-width 1500 m, clamped from the requested 5000 m" in message.content[0]["text"]
    picture = decode(message.content[1])
    assert max(picture.width, picture.height) == 1200


def test_pan(view_map, artifacts, invoke):
    message = invoke(view_map, {"east_m": 300, "north_m": -200}, artifacts)
    assert "300 m east and -200 m north" in message.content[0]["text"]
    assert len(message.content) == 2


def test_crop_off_plan(view_map, artifacts, invoke):
    message = invoke(view_map, {"east_m": 100000}, artifacts)
    (block,) = message.content
    assert "entirely outside" in block["text"]


def test_missing_site(view_map, invoke):
    message = invoke(view_map, {}, None)
    (block,) = message.content
    assert block["type"] == "text"
    assert "site_locator" in block["text"]
    assert message.status == "success"
