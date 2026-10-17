from typing import Annotated

import pymupdf
from pydantic import Field

from agent.contracts.base import Contract
from agent.runtime.georef.crop import PixelBox, output_size
from agent.runtime.georef.project import Ring

type Channel = Annotated[int, Field(ge=0, le=255)]
_CHANNEL_MAX = 255


class Outline(Contract):
    """Closed polylines stroked over a crop, e.g. the site boundary."""

    rings: tuple[Ring, ...]
    """Rings as ``(column, row)`` at the raster's native size (not crop-relative)."""
    rgb: tuple[Channel, Channel, Channel]
    """Stroke colour, 0-255 per channel."""
    width_px: float = Field(gt=0)
    """Stroke width in output pixels."""


def render_crop(
    image: pymupdf.Pixmap,
    box: PixelBox,
    *,
    max_output_px: int,
    max_upscale: float,
    outline: Outline | None = None,
) -> bytes:
    """Cut a box out of a raster, rescale it for display and optionally stroke an outline.

    The crop is drawn on a temporary PDF page the size of the output, so MuPDF does the
    resampling and the vector stroking; no imaging library is needed.

    Args:
        image: The full raster at native size.
        box: Pixels to keep; must lie inside ``image``.
        max_output_px: Upper bound of the output's long edge.
        max_upscale: Upper bound of the enlargement over native pixels.
        outline: Rings to stroke, in native raster coordinates.

    Returns:
        The rendered crop as PNG bytes.

    Raises:
        ValueError: If ``box`` exceeds the raster.
    """
    if box.x1 > image.width or box.y1 > image.height or box.x0 < 0 or box.y0 < 0:
        msg = f"box {box.as_list()} exceeds the {image.width}x{image.height} raster"
        raise ValueError(msg)
    crop = pymupdf.Pixmap(image, image.width, image.height, pymupdf.IRect(*box.as_list()))
    crop.set_origin(0, 0)
    width, height = output_size(box, max_output_px, max_upscale)
    with pymupdf.open() as document:
        page = document.new_page(width=width, height=height)
        page.insert_image(page.rect, pixmap=crop)
        if outline is not None:
            _stroke(page, outline, box, (width / box.width, height / box.height))
        return bytes(page.get_pixmap().tobytes("png"))


def _stroke(
    page: pymupdf.Page, outline: Outline, box: PixelBox, scale: tuple[float, float]
) -> None:
    """Stroke each ring, mapped from native raster pixels to output pixels."""
    shape = page.new_shape()
    for ring in outline.rings:
        shape.draw_polyline(
            [pymupdf.Point((x - box.x0) * scale[0], (y - box.y0) * scale[1]) for x, y in ring]
        )
        shape.finish(
            color=tuple(channel / _CHANNEL_MAX for channel in outline.rgb),
            width=outline.width_px,
            closePath=True,
        )
    shape.commit()
