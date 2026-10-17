import pymupdf

from agent.runtime.images.boxes import PixelBox, Size
from agent.runtime.images.rulers import Ruler

RULER_BAND_PX = 40
"""Width of the ruler bands drawn along the top and left edges of a view."""
_TICK_PX = 8
_FONT_PX = 11
_LABEL_GAP_PX = 2
_INK = (0.0, 0.0, 0.0)


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
    image: pymupdf.Pixmap, box: PixelBox, rulers: tuple[Ruler, Ruler], *, step_px: int
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
        shape = page.new_shape()
        _draw_horizontal(shape, horizontal, step_px)
        _draw_vertical(shape, vertical, step_px)
        shape.commit()
        return bytes(page.get_pixmap(alpha=False).tobytes("png"))


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
