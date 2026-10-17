import asyncio
import base64
from collections.abc import Awaitable, Callable, Sequence
from typing import override

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AnyMessage

from agent.adapters.images.store import ImageStore
from agent.observability.logs import get_logger
from agent.tools.images.blocks import text_block

logger = get_logger(__name__)

_PNG = "image/png"
_GONE = "This image is no longer available; call the tool again to see it."


def inline_images(messages: Sequence[AnyMessage], store: ImageStore) -> list[AnyMessage]:
    """Replace every image block referencing the store by the same image as base64 data.

    Args:
        messages: The conversation sent to the model.
        store: The store whose references are inlined; other URLs are left as they are.

    Returns:
        The messages, where those holding no reference of the store are the same objects and
        the others are copies. A reference whose file is gone becomes a text block saying so.
    """
    inlined: list[AnyMessage] = []
    for message in messages:
        content = message.content
        if isinstance(content, list) and any(_reference(block, store) for block in content):
            blocks = [_inline(block, store) for block in content]
            message = message.model_copy(update={"content": blocks})  # noqa: PLW2901
        inlined.append(message)
    return inlined


def _reference(block: object, store: ImageStore) -> str | None:
    """Return the URL of an image block referencing the store, else ``None``."""
    if not isinstance(block, dict) or block.get("type") != "image":
        return None
    url = block.get("url")
    return url if isinstance(url, str) and store.owns(url) else None


def _inline(block: object, store: ImageStore) -> object:
    """Turn a reference of the store into a base64 image block; leave other blocks as is."""
    if (url := _reference(block, store)) is None:
        return block
    png = store.read(url)
    if png is None:
        logger.warning("image %s is no longer in the store; the model is told so", url)
        return text_block(_GONE)
    return {"type": "image", "base64": base64.b64encode(png).decode("ascii"), "mime_type": _PNG}


class InlineImagesMiddleware(AgentMiddleware):
    """Gives the model the bytes of the images that tool replies only reference.

    Image tools store their PNGs in an ``ImageStore`` and reply with a short URL, so the graph
    state, its checkpoints and the stream to the chat UI carry references instead of
    megabytes of base64 at every step. Before each model call this middleware swaps the
    references for the image data in the request only: the state is never changed, and the
    model still sees every image.
    """

    def __init__(self, store: ImageStore) -> None:
        """Keep the store whose references are inlined.

        Args:
            store: The store the image tools write to.
        """
        super().__init__()
        self._store = store

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Call the model with the referenced images inlined.

        Args:
            request: The model request, whose messages may reference stored images.
            handler: The next step of the model call.

        Returns:
            The model response.
        """
        return handler(request.override(messages=inline_images(request.messages, self._store)))

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Call the model with the referenced images inlined, reading files off the event loop.

        Args:
            request: The model request, whose messages may reference stored images.
            handler: The next step of the model call.

        Returns:
            The model response.
        """
        messages = await asyncio.to_thread(inline_images, request.messages, self._store)
        return await handler(request.override(messages=messages))
