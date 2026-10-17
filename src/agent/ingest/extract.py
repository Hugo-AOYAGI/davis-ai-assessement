from collections.abc import Mapping, Sequence
from pathlib import Path

import pymupdf

from agent.adapters.corpus.store import image_path
from agent.contracts.base import Contract
from agent.contracts.inputs.corpus import Page
from agent.ingest.rules import Line

type _Span = Mapping[str, object]


class Extraction(Contract):
    """Text and images extracted from one PDF."""

    pages: tuple[Page, ...]
    lines: tuple[Line, ...]
    """Non-blank lines of every page, in page and reading order."""
    raster_pages: int
    """Pages without text whose embedded image was stored natively."""
    figure_pages: int
    """Pages with text and images, rendered to PNG."""


def _line(spans: Sequence[_Span], page: int, bbox: Sequence[float]) -> Line | None:
    """Build a ``Line`` from PyMuPDF spans.

    Args:
        spans: The ``spans`` of one ``get_text("dict")`` line.
        page: 1-based page number.
        bbox: The line's bounding box.

    Returns:
        The line, or ``None`` when it holds only blanks.
    """
    texts = [str(span["text"]) for span in spans]
    first = next((index for index, text in enumerate(texts) if text.strip()), None)
    if first is None:
        return None
    font = str(spans[first]["font"])
    lead: list[str] = []
    for span, text in zip(spans[first:], texts[first:], strict=True):
        if str(span["font"]) != font:
            break
        lead.append(text)
    size = spans[first]["size"]
    return Line(
        page=page,
        text="".join(texts).rstrip(),
        x0=bbox[0],
        y0=bbox[1],
        size=size if isinstance(size, float) else 0.0,
        font=font,
        lead="".join(lead).strip(),
    )


def page_lines(page: pymupdf.Page, number: int) -> list[Line]:
    """Extract the non-blank lines of a page in reading order.

    The ``dict`` mode sorted by position is used because plain text mode misorders title
    pages and places footers near the top.

    Args:
        page: A PyMuPDF page.
        number: Its 1-based number.

    Returns:
        The lines.
    """
    lines: list[Line] = []
    for block in page.get_text("dict", sort=True)["blocks"]:
        for raw in block.get("lines", []):
            line = _line(raw["spans"], number, raw["bbox"])
            if line is not None:
                lines.append(line)
    return lines


def _store_native(document: pymupdf.Document, page: pymupdf.Page, target: Path) -> Path | None:
    """Write the largest embedded image of a page without re-encoding it.

    Args:
        document: The open PDF.
        page: The page.
        target: Path without suffix; the native extension is appended.

    Returns:
        The written file, or ``None`` when the page has no image.
    """
    images = page.get_images(full=True)
    if not images:
        return None
    xref = max(images, key=lambda image: image[2] * image[3])[0]
    extracted = document.extract_image(xref)
    path = target.with_suffix(f".{extracted['ext']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(extracted["image"])
    return path


def _render(page: pymupdf.Page, path: Path, dpi: int) -> Path:
    """Render a page to PNG.

    Args:
        page: The page.
        path: Output file.
        dpi: Rendering resolution.

    Returns:
        The written file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    page.get_pixmap(dpi=dpi).save(path)
    return path


def extract_document(
    path: Path, doc: str, directory: Path, *, figures: bool, dpi: int
) -> Extraction:
    """Extract per-page text, lines and images of a PDF.

    Pages without text are raster pages: their largest embedded image is stored natively.
    With ``figures``, pages that have text and images are rendered to PNG as well.

    Args:
        path: The PDF.
        doc: Document id, used for image paths.
        directory: Corpus directory receiving ``images/<doc>/``.
        figures: Whether to render text pages that contain images.
        dpi: Resolution of rendered figure pages.

    Returns:
        The extraction.
    """
    pages: list[Page] = []
    lines: list[Line] = []
    raster = figure = 0
    with pymupdf.open(path) as document:
        for index, page in enumerate(document):
            number = index + 1
            found = page_lines(page, number)
            image: Path | None = None
            if not found:
                image = _store_native(document, page, image_path(directory, doc, number, "img"))
                raster += image is not None
            elif figures and page.get_images():
                image = _render(page, image_path(directory, doc, number, "png"), dpi)
                figure += 1
            text = "\n".join(line.text for line in found)
            pages.append(Page(doc=doc, number=number, text=text, image=image))
            lines.extend(found)
    return Extraction(
        pages=tuple(pages), lines=tuple(lines), raster_pages=raster, figure_pages=figure
    )
