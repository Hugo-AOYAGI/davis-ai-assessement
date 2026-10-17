from pathlib import Path

import pymupdf


def page_count(path: Path) -> int:
    """Number of pages of a PDF."""
    with pymupdf.open(path) as document:
        return int(document.page_count)


def page_image(
    path: Path, page: int, *, render_dpi: int, scan_min_coverage: float
) -> pymupdf.Pixmap:
    """Full-resolution image of a PDF page.

    A scanned page (an embedded image covering most of the page) yields that image decoded
    without resampling, so pixel coordinates measured on it stay valid. Any other page is
    rendered.

    Args:
        path: The PDF.
        page: 1-based page index.
        render_dpi: Resolution at which pages that are not scans are rendered.
        scan_min_coverage: Share of the page area an image must cover to make it a scan.

    Returns:
        The image as an RGB pixmap without alpha.

    Raises:
        ValueError: If the page does not exist.
    """
    with pymupdf.open(path) as document:
        if not 1 <= page <= document.page_count:
            msg = f"{path.name} has {document.page_count} pages, page {page} requested"
            raise ValueError(msg)
        source = document[page - 1]
        xref = _scan_xref(source, scan_min_coverage)
        if xref is None:
            return _rgb(source.get_pixmap(dpi=render_dpi, alpha=False))
        return _rgb(pymupdf.Pixmap(document, xref))


def _scan_xref(page: pymupdf.Page, min_coverage: float) -> int | None:
    """Xref of the embedded image covering the most of the page, if it covers enough."""
    covers = [
        (_coverage(pymupdf.Rect(info["bbox"]), page.rect), int(info["xref"]))
        for info in page.get_image_info(xrefs=True)
        if info["xref"]
    ]
    cover, xref = max(covers, default=(0.0, 0))
    return xref if covers and cover >= min_coverage else None


def _coverage(rect: pymupdf.Rect, page_rect: pymupdf.Rect) -> float:
    """Share of the page area covered by a rectangle."""
    clipped = rect & page_rect
    if clipped.is_empty:
        return 0.0
    return float(clipped.get_area()) / float(page_rect.get_area())


def _rgb(pixmap: pymupdf.Pixmap) -> pymupdf.Pixmap:
    """Convert to RGB without alpha when needed."""
    if pixmap.alpha:
        pixmap = pymupdf.Pixmap(pixmap, 0)
    if pixmap.colorspace is None or pixmap.colorspace.n != pymupdf.csRGB.n:
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)
    return pixmap
