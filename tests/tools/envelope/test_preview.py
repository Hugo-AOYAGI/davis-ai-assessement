from pathlib import Path

import pymupdf
import pytest
from langgraph.types import Command

from agent.adapters.images.store import ImageStore
from agent.tools.envelope.preview import preview_envelope_tool


@pytest.fixture
def make_preview(geometry, settings, plan, tmp_path):
    def build(imagery):
        return preview_envelope_tool(
            site="site", geometry=geometry, settings=settings, imagery=imagery, plan=plan,
            store=ImageStore(directory=tmp_path, url_prefix="/images")
        )

    return build


@pytest.fixture
def preview(make_preview, invoke):
    def run(imagery, args, artifacts):
        return invoke(make_preview(imagery), args, artifacts)

    return run


@pytest.fixture
def artifacts(site):
    return {"site": site.model_dump(mode="json")}


def test_schema_is_the_draft(make_preview, imagery):
    tool = make_preview(imagery)
    assert tool.name == "preview_envelope"
    schema = tool.tool_call_schema
    assert isinstance(schema, dict)
    assert set(schema["properties"]) == {"rules", "layout"}
    assert "runtime" not in schema["properties"]
    assert "only submit_envelope delivers" in " ".join(tool.description.split())


def test_preview_returns_figures_and_plan_and_stores_nothing(
    preview, imagery, reply, draft_args, artifacts, tmp_path
):
    result = preview(imagery, draft_args, artifacts)
    assert not isinstance(result, Command)
    message = reply(result)
    assert message.status != "error"
    figures, caption, image = message.content
    assert figures["text"].startswith("Preview only, nothing was stored.")
    for line in (
        "Site limits as labelled by code: road 60.0 m (1 edge), side 60.0 m (2 edges), rear "
        "60.0 m (1 edge)",
        "Site area: 1800 m²",
        "Bound largest",
        "Proposal (cut across_long_axis",
        "- RSE: ground",
        "the buildings fit",
    ):
        assert line in figures["text"]
    assert "Plan of the proposal on the `map` imagery" in caption["text"]
    assert "north up" in caption["text"]
    pixmap = pymupdf.Pixmap(str(tmp_path / Path(image["url"]).name))
    assert (pixmap.width, pixmap.height) == (200, 200)


def test_plan_fills_the_buildings_and_the_setback_strip(
    preview, imagery, reply, draft_args, artifacts, tmp_path
):
    _, _, image = reply(preview(imagery, draft_args, artifacts)).content
    pixmap = pymupdf.Pixmap(str(tmp_path / Path(image["url"]).name))
    colours = {pixmap.pixel(x, y) for x in range(0, 200, 2) for y in range(0, 200, 2)}
    assert {(0, 160, 70), (0, 170, 200), (230, 0, 0)} <= colours


def test_map_failure_draws_on_white(preview, broken_imagery, reply, draft_args, artifacts):
    _, caption, image = reply(preview(broken_imagery, draft_args, artifacts)).content
    assert "white background (the map could not be fetched" in caption["text"]
    assert image["type"] == "image"


def test_invalid_draft_lists_field_errors(preview, imagery, reply, draft_args, artifacts):
    draft_args["layout"] = {**draft_args["layout"], "first_share": 1.5, "order": ["RSE", "X"]}
    message = reply(preview(imagery, draft_args, artifacts))
    assert message.status == "error"
    assert message.content.startswith("preview_envelope rejected.")
    assert "- layout.first_share: Input should be less than 1" in message.content


def test_layout_naming_other_buildings_is_rejected(preview, imagery, reply, draft_args, artifacts):
    draft_args["layout"] = {**draft_args["layout"], "order": ["RSE", "X"]}
    message = reply(preview(imagery, draft_args, artifacts))
    assert message.status == "error"
    assert "layout.order: 'X' is not a building of rules.buildings" in message.content


def test_missing_site_is_an_error(preview, imagery, reply, draft_args):
    message = reply(preview(imagery, draft_args, {}))
    assert message.status == "error"
    assert "no `site` artifact in state" in message.content


def test_unknown_imagery_kind_fails_at_build_time(geometry, settings, plan, imagery, tmp_path):
    with pytest.raises(ValueError, match="no layer for kind 'relief'"):
        preview_envelope_tool(
            site="site",
            store=ImageStore(directory=tmp_path, url_prefix="/images"),
            geometry=geometry,
            settings=settings,
            imagery=imagery,
            plan=plan.model_copy(update={"kind": "relief"}),
        )
