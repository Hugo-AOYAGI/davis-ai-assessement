import math

import pymupdf
from pydantic import Field

from agent.contracts.base import Contract
from agent.runtime.images.boxes import OverviewScale, PixelBox, Size, scaled_size
from agent.runtime.images.rulers import Ruler

RULER_BAND_PX = 40
"""Width of the ruler bands drawn along the top and left edges of a view."""
_TICK_PX = 8
_FONT_PX = 11
_LABEL_GAP_PX = 2
_INK = (0.0, 0.0, 0.0)
_PAPER = (1.0, 1.0, 1.0)
_CHANNEL_MAX = 255
_SHRINK_SLACK = 0.9
"""Extra shrink on each retry, since PNG size is only roughly proportional to area."""
_MIN_SIDE_PX = 64


class LineStyle(Contract):
    """How overlay lines are drawn."""

    rgb: tuple[int, int, int]
    """Line colour, 0-255 per channel."""
    width_px: float = Field(gt=0)
    """Line width in output pixels."""


class Overlay(Contract):
    """Closed rings drawn over a view, e.g. a site outline."""

    rings: tuple[tuple[tuple[float, float], ...], ...]
    """Rings in full-resolution pixel coordinates of the page image."""
    style: LineStyle


def crop_png(image: pymupdf.Pixmap, box: PixelBox, size: Size) -> bytes:
    """Cut a box out of a raster and encode it as PNG, downscaled to ``size`` when smaller.

    Args:
        image: The full raster.
        box: Pixels to keep; must lie inside ``image``.
        size: Output ``(width, height)``; never larger than ``box``.

    Returns:
        PNG bytes.

    Raises:
        ValueError: If ``box`` exceeds the raster.
    """
    return bytes(_crop(image, box, size).tobytes("png"))


def render_view(
    image: pymupdf.Pixmap,
    box: PixelBox,
    rulers: tuple[Ruler, Ruler],
    *,
    step_px: int,
    overlay: Overlay | None = None,
) -> bytes:
    """Draw a box of a raster with labelled rulers on its top and left edges.

    The content is scaled to the rulers' lengths and drawn on a temporary PDF page whose size in
    points equals the output size in pixels, so MuPDF does the resampling and the drawing; no
    imaging library is needed.

    Args:
        image: The full raster.
        box: Pixels to show; must lie inside ``image``.
        rulers: Horizontal and vertical rulers; their lengths set the content size.
        step_px: Wanted spacing between ticks, in output pixels.
        overlay: Rings drawn over the content, clipped to it, if any.

    Returns:
        PNG bytes of ``RULER_BAND_PX`` plus the content size on each axis.

    Raises:
        ValueError: If ``box`` exceeds the raster.
    """
    horizontal, vertical = rulers
    width, height = horizontal.length, vertical.length
    content = _crop(image, box, (width, height))
    with pymupdf.open() as document:
        page = document.new_page(width=RULER_BAND_PX + width, height=RULER_BAND_PX + height)
        page.insert_image(
            pymupdf.Rect(
                RULER_BAND_PX, RULER_BAND_PX, RULER_BAND_PX + width, RULER_BAND_PX + height
            ),
            pixmap=content,
            keep_proportion=False,
        )
        if overlay is not None:
            _draw_overlay(page, box, (width, height), overlay)
        shape = page.new_shape()
        _draw_horizontal(shape, horizontal, step_px)
        _draw_vertical(shape, vertical, step_px)
        shape.commit()
        return bytes(page.get_pixmap(alpha=False).tobytes("png"))


def render_within(  # noqa: PLR0913 - the view, its overlay and its budget
    image: pymupdf.Pixmap,
    box: PixelBox,
    scale: OverviewScale,
    size: Size,
    *,
    step_px: int,
    max_bytes: int,
    overlay: Overlay | None = None,
) -> tuple[bytes, Size]:
    """Render a view with rulers in overview coordinates, shrinking it until its PNG fits.

    A dense plan crop can encode to more bytes than the model API accepts. Each retry draws
    the same box smaller, with rulers recomputed for the new size, so overview coordinates
    read on the image stay valid.

    Args:
        image: The full raster.
        box: Full-resolution pixels to show.
        scale: Full-resolution and overview sizes of the page, for the rulers.
        size: Wanted content ``(width, height)``.
        step_px: Wanted spacing between ruler ticks, in output pixels.
        max_bytes: Upper bound of the PNG size, in bytes.
        overlay: Rings drawn over the content, if any.

    Returns:
        The PNG bytes and the content size they were drawn at (ruler bands excluded).

    Raises:
        ValueError: If the view cannot fit the byte budget at the minimum content size.
    """
    while True:
        rulers = scale.rulers(box, size)
        png = render_view(image, box, rulers, step_px=step_px, overlay=overlay)
        if len(png) <= max_bytes:
            return png, size
        if max(size) <= _MIN_SIDE_PX:
            msg = f"view needs {len(png)} bytes at minimum size, exceeding {max_bytes} bytes"
            raise ValueError(msg)
        size = scaled_size(size, math.sqrt(max_bytes / len(png)) * _SHRINK_SLACK)


def _crop(image: pymupdf.Pixmap, box: PixelBox, size: Size) -> pymupdf.Pixmap:
    """Cut a box out of a raster, downscaled to ``size`` when it is not larger than the box."""
    if box.x1 > image.width or box.y1 > image.height:
        msg = f"box {box.as_list()} exceeds the {image.width}x{image.height} raster"
        raise ValueError(msg)
    crop = pymupdf.Pixmap(image, image.width, image.height, pymupdf.IRect(*box.as_list()))
    crop.set_origin(0, 0)
    width, height = size
    if (width, height) != (box.width, box.height) and width <= box.width and height <= box.height:
        crop = pymupdf.Pixmap(crop, width, height, None)
    return crop


def _draw_overlay(page: pymupdf.Page, box: PixelBox, size: Size, overlay: Overlay) -> None:
    """Draw closed rings given in full-resolution pixels over a view, blanking the ruler bands."""
    band = RULER_BAND_PX
    scale_x, scale_y = size[0] / box.width, size[1] / box.height
    shape = page.new_shape()
    for ring in overlay.rings:
        points = [
            pymupdf.Point(band + (u - box.x0) * scale_x, band + (v - box.y0) * scale_y)
            for u, v in ring
        ]
        shape.draw_polyline(points)
    colour = tuple(channel / _CHANNEL_MAX for channel in overlay.style.rgb)
    shape.finish(color=colour, width=overlay.style.width_px, closePath=True)
    right, bottom = band + size[0], band + size[1]
    for margin in (pymupdf.Rect(0, 0, right, band), pymupdf.Rect(0, 0, band, bottom)):
        shape.draw_rect(margin)
    shape.finish(color=None, fill=_PAPER, width=0)
    shape.commit()


def _draw_horizontal(shape: pymupdf.Shape, ruler: Ruler, step_px: int) -> None:
    """Draw the top ruler: an edge line, ticks and their labels."""
    band = RULER_BAND_PX
    shape.draw_line((band, band), (band + ruler.length, band))
    for position, value in ruler.ticks(step_px):
        x = band + position
        shape.draw_line((x, band - _TICK_PX), (x, band))
        shape.insert_text(
            (x + _LABEL_GAP_PX, band - _TICK_PX), str(value), fontsize=_FONT_PX, color=_INK
        )
    shape.finish(color=_INK, width=1)


def _draw_vertical(shape: pymupdf.Shape, ruler: Ruler, step_px: int) -> None:
    """Draw the left ruler: an edge line, ticks and their labels."""
    band = RULER_BAND_PX
    shape.draw_line((band, band), (band, band + ruler.length))
    for position, value in ruler.ticks(step_px):
        y = band + position
        shape.draw_line((band - _TICK_PX, y), (band, y))
        shape.insert_text((_LABEL_GAP_PX, y + _FONT_PX), str(value), fontsize=_FONT_PX, color=_INK)
    shape.finish(color=_INK, width=1)
