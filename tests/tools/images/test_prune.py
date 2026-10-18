import asyncio

import pytest
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.tools.images.prune import PruneImagesMiddleware, prune_images

URL = {"type": "image", "url": "/images/a.png", "mime_type": "image/png"}
BASE64 = {"type": "image", "base64": "AAAA", "mime_type": "image/png"}
IMAGE_URL = {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}
NATIVE = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "A"}}


def caption(text="caption"):
    return {"type": "text", "text": text}


def block(message, index):
    item = message.content[index]
    assert isinstance(item, dict)
    return item


def reply(name, *blocks, call_id="1"):
    return ToolMessage([caption(name), *blocks], tool_call_id=call_id, name=name)


def conversation():
    return [
        HumanMessage("look"),
        reply("view_image", URL, call_id="1"),
        AIMessage("zooming"),
        reply("zoom", BASE64, call_id="2"),
        ToolMessage("text only", tool_call_id="3", name="list_documents"),
        reply("site_view", IMAGE_URL, call_id="4"),
    ]


def test_keeps_last_n_and_replaces_older_images():
    messages = conversation()
    pruned = prune_images(messages, keep=2)
    first = pruned[1]
    assert first is not messages[1]
    assert first.content[0] == caption("view_image")
    notice = block(first, 1)
    assert notice["type"] == "text"
    assert "image dropped to save context: view_image" in notice["text"]
    assert "call the tool again" in notice["text"]
    assert isinstance(first, ToolMessage)
    assert first.tool_call_id == "1"
    assert pruned[3] is messages[3]
    assert pruned[5] is messages[5]


def test_text_only_messages_are_the_same_objects():
    messages = conversation()
    pruned = prune_images(messages, keep=1)
    for index in (0, 2, 4):
        assert pruned[index] is messages[index]


def test_input_is_not_mutated():
    messages = conversation()
    before = [message.model_copy(deep=True) for message in messages]
    prune_images(messages, keep=0)
    assert messages == before


def test_keep_zero_drops_every_format():
    messages = [reply("zoom", URL, BASE64, IMAGE_URL, NATIVE), HumanMessage([caption(), URL])]
    pruned = prune_images(messages, keep=0)
    for message in pruned:
        assert all(block(message, index)["type"] == "text" for index in range(len(message.content)))
    assert "image dropped to save context: human" in block(pruned[1], 1)["text"]


def test_fewer_images_than_keep_changes_nothing():
    messages = conversation()
    pruned = prune_images(messages, keep=4)
    assert all(after is before for after, before in zip(pruned, messages, strict=True))


def make_request():
    return ModelRequest(model=GenericFakeChatModel(messages=iter([])), messages=conversation())


def test_middleware_prunes_only_the_request():
    request = make_request()
    seen = []

    def handler(passed):
        seen.append(passed.messages)
        return ModelResponse(result=[AIMessage("done")])

    response = PruneImagesMiddleware(1).wrap_model_call(request, handler)
    assert response.result[0].content == "done"
    assert seen[0][1].content[1]["type"] == "text"
    assert seen[0][5].content[1] == IMAGE_URL
    assert request.messages[1].content[1] == URL


def test_async_middleware_prunes_the_request():
    request = make_request()

    async def handler(passed):
        assert passed.messages[3].content[1]["type"] == "text"
        return ModelResponse(result=[AIMessage("done")])

    response = asyncio.run(PruneImagesMiddleware(1).awrap_model_call(request, handler))
    assert response.result[0].content == "done"
    assert request.messages[3].content[1] == BASE64


def test_negative_keep_is_rejected():
    with pytest.raises(ValueError, match="keep"):
        PruneImagesMiddleware(-1)
