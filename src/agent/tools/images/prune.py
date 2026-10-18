from collections.abc import Awaitable, Callable, Sequence
from typing import override

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AnyMessage

from agent.tools.images.blocks import text_block

_IMAGE_TYPES = frozenset({"image", "image_url"})
"""Block types carrying an image: standard ``image`` (url, base64 or file id) and OpenAI-style
``image_url``; Anthropic-native ``image`` blocks (with a ``source``) share the first type."""


def prune_images(messages: Sequence[AnyMessage], keep: int) -> list[AnyMessage]:
    """Keep the images of the last ``keep`` messages holding any; replace older ones by text.

    Each dropped image block becomes a text block naming where it came from (the tool name of
    a tool reply, else the message type) and telling the model to call the tool again. Other
    blocks, such as an image's caption, are kept.

    Args:
        messages: The conversation sent to the model.
        keep: How many of the latest messages holding images keep them; ``0`` drops them all.

    Returns:
        The messages, where those left unchanged are the same objects and the others are
        copies; the input messages are never modified.
    """
    with_images = [index for index, message in enumerate(messages) if _has_image(message)]
    dropped = set(with_images[: max(len(with_images) - keep, 0)])
    return [
        _drop_images(message) if index in dropped else message
        for index, message in enumerate(messages)
    ]


def _is_image(block: object) -> bool:
    """Tell whether a content block is an image block."""
    return isinstance(block, dict) and block.get("type") in _IMAGE_TYPES


def _has_image(message: AnyMessage) -> bool:
    """Tell whether a message's content holds an image block."""
    content = message.content
    return isinstance(content, list) and any(_is_image(block) for block in content)


def _drop_images(message: AnyMessage) -> AnyMessage:
    """Copy a message with each image block replaced by a short text notice."""
    label = getattr(message, "name", None) or message.type
    notice = text_block(f"[image dropped to save context: {label}; call the tool again to see it]")
    blocks = [notice if _is_image(block) else block for block in message.content]
    return message.model_copy(update={"content": blocks})


class PruneImagesMiddleware(AgentMiddleware):
    """Shows the model only the images of the latest messages that hold any.

    Agents that look at plans zoom again and again; every image stays in the conversation, and
    a long session outgrows the model's request size. Before each model call this middleware
    replaces the images of older messages by a text notice, in the request only: the graph
    state, the chat UI and run records keep every image. Listed before
    ``InlineImagesMiddleware``, it also spares reading the dropped images from disk.
    """

    def __init__(self, keep: int) -> None:
        """Keep how many image-holding messages keep their images.

        Args:
            keep: How many of the latest messages holding images keep them.

        Raises:
            ValueError: If ``keep`` is negative.
        """
        super().__init__()
        if keep < 0:
            msg = f"keep must be at least 0, got {keep}"
            raise ValueError(msg)
        self._keep = keep

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Call the model with the older images replaced by text.

        Args:
            request: The model request.
            handler: The next step of the model call.

        Returns:
            The model response.
        """
        return handler(request.override(messages=prune_images(request.messages, self._keep)))

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Call the model with the older images replaced by text.

        Args:
            request: The model request.
            handler: The next step of the model call.

        Returns:
            The model response.
        """
        return await handler(request.override(messages=prune_images(request.messages, self._keep)))
