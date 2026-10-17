from collections.abc import Generator
from contextlib import contextmanager

from langchain_core.tools import BaseTool, StructuredTool, ToolException
from pydantic import ValidationError

from agent.adapters.images.pages import PageImages, RegionError, RenderedImage
from agent.adapters.images.render import RULER_BAND_PX
from agent.contracts.evidence import ImageRegion
from agent.tools.images.blocks import ContentBlock, image_block, text_block


def view_image_tool(*, pages: PageImages) -> BaseTool:
    """Build the ``view_image`` tool, showing a whole corpus page as an image.

    Args:
        pages: The corpus page images.

    Returns:
        The tool.
    """

    def view_image(doc: str, page: int) -> list[ContentBlock]:
        """Look at a page of a corpus document as an image: a plan, a diagram, a scanned page.

        Returns the whole page downscaled to fit (the overview), with pixel rulers along the
        top and left edges. These overview coordinates are the only ones you use: a region
        passed to zoom or submitted as evidence is [x0, y0, x1, y1] read on these rulers. Small
        labels, hatchings and line styles of a large plan are not legible on the overview: zoom
        on them, again and again if needed. When a page has a text layer, read and cite its
        text with read_pages; images are for what the text cannot show.

        Args:
            doc: Document id, as listed by list_documents.
            page: 1-based PDF page index (not the number printed on the page).
        """
        with _region_errors():
            view = pages.overview(doc, page)
        width, height = view.overview_size
        caption = (
            f"Overview of {doc} p.{page}: {width}x{height} px in overview coordinates; the full "
            f"page is {view.full_size[0]}x{view.full_size[1]} px. The rulers give overview "
            "coordinates: read a region [x0, y0, x1, y1] on them and pass it to zoom."
        )
        return [text_block(caption), image_block(view.png)]

    return StructuredTool.from_function(view_image, parse_docstring=True, handle_tool_error=True)


def zoom_tool(*, pages: PageImages) -> BaseTool:
    """Build the ``zoom`` tool, showing a region of a corpus page in detail.

    Args:
        pages: The corpus page images.

    Returns:
        The tool.
    """

    def zoom(doc: str, page: int, region: list[int]) -> list[ContentBlock]:
        """Look at a region of a page in detail, cut from the full-resolution image.

        The zoomed image carries rulers in the same overview coordinates as view_image, so you
        never lose your place: read a smaller region on it and zoom again until labels are
        legible. The reply says how much the region is enlarged and when the page's full
        resolution is reached (zooming further then only enlarges pixels).

        Args:
            doc: Document id, as listed by list_documents.
            page: 1-based PDF page index (not the number printed on the page).
            region: [x0, y0, x1, y1] in overview coordinates of view_image, as read on the
                rulers, with x1 > x0 and y1 > y0.
        """
        with _region_errors():
            area = ImageRegion.model_validate({"doc": doc, "page": page, "region": region})
            view = pages.zoom(area)
        return [text_block(_zoom_caption(area, view)), image_block(view.png)]

    return StructuredTool.from_function(zoom, parse_docstring=True, handle_tool_error=True)


def _zoom_caption(area: ImageRegion, view: RenderedImage) -> str:
    """Say what the zoom shows, how enlarged it is, and whether full resolution is reached."""
    x0, _, x1, _ = area.region
    shown = view.image_size[0] - RULER_BAND_PX
    enlargement = shown / (x1 - x0)
    native = (x1 - x0) * view.full_size[0] / view.overview_size[0]
    limit = " This is the page's full resolution or more." if shown >= native else ""
    return (
        f"Zoom on {area.doc} p.{area.page}, region {list(area.region)} in overview coordinates, "
        f"enlarged {enlargement:.1f}x over the overview.{limit} The rulers still give overview "
        "coordinates."
    )


@contextmanager
def _region_errors() -> Generator[None]:
    """Turn invalid pages and regions into tool errors the model reads and can act on."""
    try:
        yield
    except ValidationError as error:
        details = "; ".join(str(detail["msg"]) for detail in error.errors(include_url=False))
        raise ToolException(details) from error
    except RegionError as error:
        raise ToolException(str(error)) from error
