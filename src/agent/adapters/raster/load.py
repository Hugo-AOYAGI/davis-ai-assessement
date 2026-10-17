from pathlib import Path

import pymupdf

_PDF_SUFFIX = ".pdf"


def load_raster(path: Path, page: int) -> pymupdf.Pixmap:
    """Load a raster map at its native resolution.

    A PDF yields the largest image embedded in the given page (a scanned plan is one image per
    page), decoded without resampling, so pixel coordinates measured on it stay valid. Any other
    file is opened as an image and ``page`` is ignored.

    Args:
        path: A PDF or an image file (PNG, JPEG...).
        page: 1-based page index, for PDFs.

    Returns:
        The image as an RGB pixmap without alpha.

    Raises:
        ValueError: If the PDF page does not exist or holds no image.
    """
    if path.suffix.lower() != _PDF_SUFFIX:
        return _rgb(pymupdf.Pixmap(str(path)))
    with pymupdf.open(path) as document:
        if not 1 <= page <= document.page_count:
            msg = f"{path.name} has {document.page_count} pages, page {page} requested"
            raise ValueError(msg)
        images = document[page - 1].get_images(full=True)
        if not images:
            msg = f"page {page} of {path.name} holds no embedded image"
            raise ValueError(msg)
        xref = max(images, key=lambda image: image[2] * image[3])[0]
        return _rgb(pymupdf.Pixmap(document, xref))


def _rgb(pixmap: pymupdf.Pixmap) -> pymupdf.Pixmap:
    """Convert to RGB without alpha when needed."""
    if pixmap.alpha:
        pixmap = pymupdf.Pixmap(pixmap, 0)
    if pixmap.colorspace is None or pixmap.colorspace.n != pymupdf.csRGB.n:
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)
    return pixmap
