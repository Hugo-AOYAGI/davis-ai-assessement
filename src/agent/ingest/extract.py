from collections.abc import Mapping, Sequence
from pathlib import Path

import pymupdf

from agent.contracts.base import Contract
from agent.contracts.inputs.corpus import Page
from agent.ingest.rules import Line

type _Span = Mapping[str, object]


class Extraction(Contract):
    """Text extracted from one PDF."""

    pages: tuple[Page, ...]
    lines: tuple[Line, ...]
    """Non-blank lines of every page, in page and reading order."""


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


def extract_document(path: Path, doc: str) -> Extraction:
    """Extract the per-page text and lines of a PDF.

    Pages without a text layer (scans, raster plans) get an empty text; their images are
    rendered on demand by the image tools, not stored at ingestion.

    Args:
        path: The PDF.
        doc: Document id.

    Returns:
        The extraction.
    """
    pages: list[Page] = []
    lines: list[Line] = []
    with pymupdf.open(path) as document:
        for index, page in enumerate(document):
            number = index + 1
            found = page_lines(page, number)
            text = "\n".join(line.text for line in found)
            pages.append(Page(doc=doc, number=number, text=text))
            lines.extend(found)
    return Extraction(pages=tuple(pages), lines=tuple(lines))
