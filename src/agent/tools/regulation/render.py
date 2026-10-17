from collections.abc import Sequence

from agent.adapters.corpus.index import CorpusIndex
from agent.contracts.inputs.corpus import Document, Page, Section

ANCHOR_CHARS = 12
"""Lines shorter than this (bullets, lone numbers) are too common to place on a page by search;
they stay on the page of the line before them."""

CITATION_HINT = (
    "Text is split by `--- <doc> p.<page> ---` markers. To cite a passage, give the doc id and "
    "page of the nearest marker above it and copy the quote verbatim from the text. The marker "
    "page is the PDF page index; never cite a page number printed in a page header or footer, "
    "which may differ."
)

RASTER_PAGE = "(no text layer: raster page)"


def marker(doc: str, page: int) -> str:
    """Return the line announcing the page the following text is on."""
    return f"--- {doc} p.{page} ---"


def page_range(start: int, end: int) -> str:
    """Return ``p.<start>-<end>``, or ``p.<start>`` for a single page."""
    return f"p.{start}" if start == end else f"p.{start}-{end}"


def paginate(section: Section, index: CorpusIndex) -> list[tuple[int, str]]:
    """Split a section's text into consecutive chunks, each on one page.

    Each line long enough to be distinctive is searched in the page texts: first on the current
    page after the previous match, then on the following pages of the section; the first page
    holding it becomes current. Short lines and lines found nowhere stay on the current page,
    as do lines of pages missing from the corpus.

    Args:
        section: A corpus section.
        index: The corpus index, for the page texts.

    Returns:
        ``(page, text)`` chunks in text order; empty when the section has no text.
    """
    if not section.text.strip():
        return []
    texts = _page_texts(section, index)
    current, cursor = section.page_start, 0
    chunks: list[tuple[int, list[str]]] = []
    for line in section.text.split("\n"):
        anchor = line.strip()
        if len(anchor) >= ANCHOR_CHARS:
            current, cursor = _locate(anchor, texts, current, cursor, section.page_end)
        if chunks and chunks[-1][0] == current:
            chunks[-1][1].append(line)
        else:
            chunks.append((current, [line]))
    return [(page, "\n".join(lines)) for page, lines in chunks]


def render_section(section: Section, index: CorpusIndex) -> str:
    """Render a section's own text: a heading line, then each page chunk after its marker.

    Args:
        section: A corpus section.
        index: The corpus index, for the page texts.

    Returns:
        ``## <heading path> [<id>, <pages>]`` followed by the marked chunks.
    """
    lines = [heading(section)]
    for page, text in paginate(section, index):
        lines += [marker(section.doc, page), text]
    return "\n".join(lines)


def render_sections(sections: Sequence[Section], index: CorpusIndex) -> str:
    """Render several sections with :func:`render_section`, separated by a blank line."""
    return "\n\n".join(render_section(section, index) for section in sections)


def render_pages(pages: Sequence[Page]) -> str:
    """Render raw pages, each after its marker; raster pages say they have no text."""
    return "\n".join(
        f"{marker(page.doc, page.number)}\n{page.text.strip() or RASTER_PAGE}" for page in pages
    )


def heading(section: Section) -> str:
    """Return ``## <heading path> [<id>, <pages>]``."""
    path = " > ".join(section.heading_path)
    return f"## {path} [{section.id}, {page_range(section.page_start, section.page_end)}]"


def outline(sections: Sequence[Section], index: CorpusIndex) -> str:
    """List sections as ``- <id> | <title> | <pages>``, plus their sub-section count if any.

    Args:
        sections: Sections to list.
        index: The corpus index, to count sub-sections.

    Returns:
        One line per section.
    """
    lines = []
    for section in sections:
        line = (
            f"- {section.id} | {section.heading_path[-1]} | "
            f"{page_range(section.page_start, section.page_end)}"
        )
        count = len(index.children(section.id))
        lines.append(f"{line} | {count} sub-sections" if count else line)
    return "\n".join(lines)


def document_outline(document: Document, index: CorpusIndex) -> str:
    """Describe a document (id, kind, title, page count) and outline its top-level sections."""
    title = f"# {document.id} ({document.kind}): {document.title}, {document.page_count} pages"
    top = [section for section in index.sections(document.id) if index.parent(section.id) is None]
    listing = outline(top, index) if top else "(no sections)"
    return f"{title}\n{listing}"


def sub_sections(section: Section, index: CorpusIndex) -> str:
    """Outline a section's direct sub-sections, or say it has none."""
    children = index.children(section.id)
    if not children:
        return f"{section.id} has no sub-sections; read it with read_section."
    listing = outline(children, index)
    return f"Sub-sections of {section.id} ({section.heading_path[-1]}):\n{listing}"


def truncate(text: str, max_chars: int, hint: str) -> str:
    """Cut text at the last line break within ``max_chars`` and say how to read the rest.

    Args:
        text: The reply.
        max_chars: Longest text kept.
        hint: What the model should call to read what was cut.

    Returns:
        The text unchanged when short enough, else its head and a truncation notice.
    """
    if len(text) <= max_chars:
        return text
    cut = text.rfind("\n", 0, max_chars)
    head = text[: cut if cut > 0 else max_chars]
    return f"{head}\n[truncated: reply limited to {max_chars} characters. {hint}]"


def _page_texts(section: Section, index: CorpusIndex) -> dict[int, str]:
    """Return the text of each page the section spans, skipping pages missing from the corpus."""
    texts: dict[int, str] = {}
    for number in range(section.page_start, section.page_end + 1):
        try:
            texts[number] = index.page(section.doc, number).text
        except LookupError:
            continue
    return texts


def _locate(
    anchor: str, texts: dict[int, str], current: int, cursor: int, last: int
) -> tuple[int, int]:
    """Find the page holding a line, from the cursor on the current page, then on later pages.

    Returns:
        The page and the cursor just after the match; unchanged when the line is not found.
    """
    found = texts.get(current, "").find(anchor, cursor)
    if found >= 0:
        return current, found + len(anchor)
    for page in range(current + 1, last + 1):
        found = texts.get(page, "").find(anchor)
        if found >= 0:
            return page, found + len(anchor)
    return current, cursor
