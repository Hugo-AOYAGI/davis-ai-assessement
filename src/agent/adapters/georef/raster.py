from collections.abc import Sequence

import numpy as np
import pymupdf
from numpy.typing import NDArray

from agent.adapters.images.render import crop_png
from agent.runtime.georef.affine import Points
from agent.runtime.georef.mask import Mask
from agent.runtime.images.boxes import PixelBox, Size

type Colour = tuple[float, float, float]
"""RGB, each channel in ``[0, 1]``."""


def pixmap_array(pixmap: pymupdf.Pixmap) -> NDArray[np.uint8]:
    """Copy an RGB pixmap without alpha into an array of shape ``(height, width, 3)``.

    Raises:
        ValueError: If the pixmap does not have three channels.
    """
    if pixmap.n != 3:  # noqa: PLR2004 - RGB
        msg = f"expected an RGB pixmap without alpha, got {pixmap.n} channels"
        raise ValueError(msg)
    rows = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.stride)
    return rows[:, : pixmap.width * 3].reshape(pixmap.height, pixmap.width, 3).copy()


def mask_png(mask: Mask) -> bytes:
    """Encode a mask as a black and white PNG (white inside)."""
    grey = np.ascontiguousarray(mask.astype(np.uint8) * 255)
    height, width = grey.shape
    pixmap = pymupdf.Pixmap(pymupdf.csGRAY, width, height, grey.tobytes(), False)
    return bytes(pixmap.tobytes("png"))


def outlined_png(  # noqa: PLR0913 - drawing options
    image: pymupdf.Pixmap,
    box: PixelBox,
    size: Size,
    outlines: Sequence[Points],
    *,
    colour: Colour,
    line_px: float,
) -> bytes:
    """Cut a box out of a raster, downscale it and draw closed outlines on it.

    Args:
        image: The full-resolution raster.
        box: Pixels to show; must lie inside ``image``.
        size: Output ``(width, height)``; never larger than ``box``.
        outlines: Closed rings in full-resolution pixel coordinates, shape ``(n, 2)`` each.
        colour: Outline colour.
        line_px: Outline width in output pixels.

    Returns:
        PNG bytes of ``size``.
    """
    width, height = size
    scale_x, scale_y = width / box.width, height / box.height
    with pymupdf.open() as document:
        page = document.new_page(width=width, height=height)
        page.insert_image(page.rect, stream=crop_png(image, box, size), keep_proportion=False)
        shape = page.new_shape()
        for ring in outlines:
            points = [
                pymupdf.Point((u - box.x0) * scale_x, (v - box.y0) * scale_y) for u, v in ring
            ]
            shape.draw_polyline(points)
        shape.finish(color=colour, width=line_px, closePath=True)
        shape.commit()
        return bytes(page.get_pixmap(alpha=False).tobytes("png"))
