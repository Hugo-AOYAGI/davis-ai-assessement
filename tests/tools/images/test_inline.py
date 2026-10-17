import asyncio
import base64

from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.tools.images.blocks import image_block, text_block
from agent.tools.images.inline import InlineImagesMiddleware, inline_images

PNG = b"\x89PNG\r\n\x1a\nfake image"
OTHER = {"type": "image", "url": "https://example.com/plan.png", "mime_type": "image/png"}


def tool_reply(*blocks):
    return ToolMessage(list(blocks), tool_call_id="1", name="view_image")


def test_references_are_inlined(store):
    reply = tool_reply(text_block("caption"), image_block(store, PNG))
    (inlined,) = inline_images([reply], store)
    caption, image = inlined.content
    assert caption == {"type": "text", "text": "caption"}
    assert image == {
        "type": "image",
        "base64": base64.b64encode(PNG).decode("ascii"),
        "mime_type": "image/png",
    }
    assert isinstance(inlined, ToolMessage)
    assert inlined.tool_call_id == "1"
    assert reply.content[1]["url"].startswith("/images/")


def test_messages_without_references_are_the_same_objects(store):
    messages = [HumanMessage("hi"), AIMessage("ok"), tool_reply(text_block("x"), OTHER)]
    inlined = inline_images(messages, store)
    assert all(after is before for after, before in zip(inlined, messages, strict=True))


def test_other_urls_are_left_untouched(store):
    reply = tool_reply(OTHER, image_block(store, PNG))
    (inlined,) = inline_images([reply], store)
    assert inlined.content[0] == OTHER
    assert "base64" in inlined.content[1]


def test_missing_file_becomes_a_text_block(store):
    block = image_block(store, PNG)
    store.path(block["url"].rsplit("/", 1)[1]).unlink()
    (inlined,) = inline_images([tool_reply(block)], store)
    (notice,) = inlined.content
    assert isinstance(notice, dict)
    assert notice["type"] == "text"
    assert "no longer available" in notice["text"]


def make_request(store):
    messages = [HumanMessage("look"), tool_reply(image_block(store, PNG))]
    return ModelRequest(model=GenericFakeChatModel(messages=iter([])), messages=messages)


def test_middleware_inlines_only_the_request(store):
    request = make_request(store)
    seen = []

    def handler(passed):
        seen.append(passed.messages)
        return ModelResponse(result=[AIMessage("done")])

    response = InlineImagesMiddleware(store).wrap_model_call(request, handler)
    assert response.result[0].content == "done"
    assert "base64" in seen[0][1].content[0]
    assert seen[0][0] is request.messages[0]
    assert "url" in request.messages[1].content[0]


def test_async_middleware_inlines_the_request(store):
    request = make_request(store)

    async def handler(passed):
        assert "base64" in passed.messages[1].content[0]
        return ModelResponse(result=[AIMessage("done")])

    middleware = InlineImagesMiddleware(store)
    response = asyncio.run(middleware.awrap_model_call(request, handler))
    assert response.result[0].content == "done"
    assert "url" in request.messages[1].content[0]
