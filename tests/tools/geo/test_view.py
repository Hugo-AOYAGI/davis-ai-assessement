import base64

import pymupdf
import pytest

from agent.tools.geo.view import site_view_tool

PLOT, STRIP = "91272000CR0247", "91272000CR0249"


@pytest.fixture
def make_view(style):
    def build(surveyor, imagery, half_widths_m=None, image_px=64):
        return site_view_tool(
            surveyor=surveyor,
            imagery=imagery,
            half_widths_m=half_widths_m or {"town": 1500, "neighbourhood": 250},
            parcel_margin_ratio=0.3,
            min_half_width_m=40,
            image_px=image_px,
            style=style,
        )

    return build


def test_schema(make_view, surveyor, imagery):
    tool = make_view(surveyor, imagery)
    assert tool.name == "site_view"
    schema = tool.tool_call_schema.model_json_schema()
    assert set(schema["properties"]) == {"ids", "kind", "scale"}
    assert schema["required"] == ["ids", "kind"]
    assert "not what planning rules allow" in tool.description


@pytest.mark.parametrize(
    ("kind", "layer"),
    [("aerial", "ORTHOIMAGERY.ORTHOPHOTOS"), ("map", "GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2")],
)
def test_parcel_view_returns_caption_and_image(make_view, surveyor, imagery, kind, layer):
    caption, image = make_view(surveyor, imagery).invoke(
        {"ids": [PLOT, STRIP], "kind": kind, "scale": "parcel"}
    )
    text = caption["text"]
    assert "scale `parcel`: 141 m x 141 m, 2.21 m per pixel, north up" in text
    assert f"{PLOT}, {STRIP}" in text
    assert f"layer {layer}" in text
    assert "Geometric source, not regulatory" in text
    assert image["type"] == "image"
    pixmap = pymupdf.Pixmap(base64.b64decode(image["base64"]))
    assert (pixmap.width, pixmap.height) == (64, 64)


@pytest.mark.parametrize(
    ("scale", "side"), [("town", "3000 m x 3000 m"), ("neighbourhood", "500 m x 500 m")]
)
def test_fixed_scales(make_view, surveyor, imagery, scale, side):
    caption, _ = make_view(surveyor, imagery).invoke({"ids": [PLOT], "kind": "map", "scale": scale})
    assert side in caption["text"]


def test_unknown_parcel_is_a_message(make_view, surveyor, imagery):
    (block,) = make_view(surveyor, imagery).invoke({"ids": ["91272000CR9999"], "kind": "aerial"})
    assert block["text"].startswith("site_view failed:")
    assert "not in the cadastre" in block["text"]


def test_imagery_failure_is_a_message(make_view, surveyor, broken_imagery):
    (block,) = make_view(surveyor, broken_imagery).invoke({"ids": [PLOT], "kind": "aerial"})
    assert block["text"].startswith("site_view failed:")
    assert "503" in block["text"]


def test_missing_settings_are_rejected(make_view, surveyor, imagery):
    with pytest.raises(ValueError, match="neighbourhood"):
        make_view(surveyor, imagery, half_widths_m={"town": 1500})


def test_image_size_is_capped(make_view, surveyor, imagery):
    with pytest.raises(ValueError, match="2000"):
        make_view(surveyor, imagery, image_px=2048)
