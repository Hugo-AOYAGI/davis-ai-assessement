from agent.adapters.images.store import ImageStore

type ContentBlock = dict[str, str]
"""A tool-result content block (``text`` or ``image``) as LangChain passes it to the model."""

_PNG = "image/png"


def text_block(text: str) -> ContentBlock:
    """Wrap text as a content block.

    Args:
        text: The text.

    Returns:
        A ``text`` block.
    """
    return {"type": "text", "text": text}


def image_block(store: ImageStore, png: bytes) -> ContentBlock:
    """Store a PNG and wrap its reference as an image content block.

    The block references the stored PNG, so the graph state and the stream carry a short URL
    instead of the image; ``InlineImagesMiddleware`` gives the model the bytes at each call.

    Args:
        store: Where the PNG is stored.
        png: PNG bytes.

    Returns:
        An ``image`` block whose ``url`` references the stored PNG.
    """
    return {"type": "image", "url": store.put(png), "mime_type": _PNG}
