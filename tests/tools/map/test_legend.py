import base64

import pymupdf
from langchain_core.messages import ToolMessage


def test_legend_returns_one_image_per_panel(map_tools):
    tool = map_tools["view_legend"]
    assert tool.tool_call_schema.model_json_schema()["properties"] == {}
    message = tool.invoke({"type": "tool_call", "id": "1", "name": tool.name, "args": {}})
    assert isinstance(message, ToolMessage)
    text, *images = message.content
    assert "`plu_reglement_graphique`, page 1: 2 panels" in text["text"]
    assert len(images) == 2
    for block in images:
        picture = pymupdf.Pixmap(base64.b64decode(block["base64"]))
        assert max(picture.width, picture.height) <= 1400
