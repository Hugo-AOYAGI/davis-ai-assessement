import base64

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


def image_block(png: bytes) -> ContentBlock:
    """Wrap a PNG as an inline image content block.

    Args:
        png: PNG bytes.

    Returns:
        An ``image`` block carrying the base64 data.
    """
    return {"type": "image", "base64": base64.b64encode(png).decode("ascii"), "mime_type": _PNG}
