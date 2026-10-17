from collections.abc import Sequence

from langchain_core.tools import BaseTool, ToolException

from agent.tools.regulation.render import (
    CITATION_HINT,
    document_outline,
    outline,
    render_pages,
    render_section,
    render_sections,
    sub_sections,
    truncate,
)
from agent.tools.regulation.source import (
    CorpusSource,
    RetrievalMode,
    as_tool,
    lookup_errors,
    require_positive,
)

_ZONE = {
    RetrievalMode.NAVIGATION: (
        "Open the chapter of a zone in the PLU regulation (e.g. zone UMG, sector Moulon). "
        "Returns the chapter's introduction, an outline of its articles "
        "(`- <section id> | <title> | <pages>`), then an outline of the general sections that "
        "apply in every zone (general provisions, lexique). Then read articles with "
        "read_article, any listed section with read_section, and defined terms with "
        f"get_definition. {CITATION_HINT}"
    ),
    RetrievalMode.FULL_SECTIONS: (
        "Read the whole chapter of a zone in the PLU regulation in one call (e.g. zone UMG, "
        "sector Moulon): its introduction and every article with all sub-sections, followed by "
        "the general sections that apply in every zone (general provisions, lexique). A reply "
        f"too long is cut; read the rest with read_article or read_section. {CITATION_HINT}"
    ),
}
_ARTICLE = (
    "Read one article of a zone chapter of the PLU regulation with all its sub-sections, e.g. "
    f"zone UMG article 10 for heights or article 12 for car parking. {CITATION_HINT}"
)
_SECTION = {
    RetrievalMode.NAVIGATION: (
        "Read one section by id (ids come from list_sections, read_zone and search): its own "
        "text, then an outline of its direct sub-sections, which you read with further "
        f"read_section calls. {CITATION_HINT}"
    ),
    RetrievalMode.FULL_SECTIONS: (
        "Read one section by id (ids come from list_sections, read_zone and search), with all "
        f"its sub-sections. {CITATION_HINT}"
    ),
}
_PAGES = (
    "Read raw pages of a document as extracted, running headers and footers included, at most "
    "{max_pages} pages per call. Use it to check a quote before citing it, to see the text "
    "around a passage, or to read pages no section covers. Raster pages (plans, scans) have no "
    f"text. {CITATION_HINT}"
)


def list_sections_tool(*, corpus: CorpusSource) -> BaseTool:
    """Build the ``list_sections`` tool, the table of contents of the corpus.

    Args:
        corpus: The corpus to read.

    Returns:
        The tool.
    """

    def list_sections(doc: str | None = None, parent: str | None = None) -> str:
        """Browse the table of contents of the corpus documents, one level at a time.

        Without arguments, lists every document (id, kind, title, page count) with its
        top-level sections, one per line: `- <section id> | <title> | <pages>`, followed by
        `| <n> sub-sections` when it has some. Pass a section id as `parent` to list its
        sub-sections, or read it with read_section. The document id is the `doc` of citations.

        Args:
            doc: A document id: list only that document.
            parent: A section id: list its direct sub-sections instead.
        """
        index = corpus.index()
        with lookup_errors():
            if parent is not None:
                return sub_sections(index.section(parent), index)
            documents = index.documents() if doc is None else [index.document(doc)]
            return "\n\n".join(document_outline(document, index) for document in documents)

    return as_tool(list_sections)


def read_zone_tool(
    *, corpus: CorpusSource, mode: str, general_sections: Sequence[str], max_chars: int
) -> BaseTool:
    """Build the ``read_zone`` tool, the entry point into a zone chapter of the regulation.

    Args:
        corpus: The corpus to read.
        mode: A ``RetrievalMode`` value: outline the articles, or return them all.
        general_sections: Ids of the sections applying in every zone, read with each chapter.
        max_chars: Longest reply.

    Returns:
        The tool.
    """
    retrieval = RetrievalMode(mode)
    require_positive(max_chars=max_chars)
    general = tuple(general_sections)

    def read_zone(zone: str, sector: str | None = None) -> str:
        """Open the chapter of a zone.

        Args:
            zone: Zone code as printed on the zoning plan, e.g. `UMG`.
            sector: Sector name, needed when the zone code exists in several sectors.
        """
        index = corpus.index()
        with lookup_errors():
            head = index.zone(zone, sector)
            if retrieval is RetrievalMode.FULL_SECTIONS:
                parts = [index.subtree(head.id), *(index.subtree(key) for key in general)]
                text = "\n\n".join(render_sections(part, index) for part in parts)
                return truncate(text, max_chars, "Read the rest with read_article or read_section.")
            articles = outline(index.children(head.id), index)
            shared = outline([index.section(key) for key in general], index)
            text = (
                f"{render_section(head, index)}\n\n"
                f"Articles (read one with read_article or read_section):\n{articles}\n\n"
                "General sections, applying in every zone (read them with read_section, defined "
                f"terms with get_definition):\n{shared}"
            )
            return truncate(text, max_chars, "Read the articles with read_article.")

    return as_tool(read_zone, _ZONE[retrieval])


def read_article_tool(*, corpus: CorpusSource, max_chars: int) -> BaseTool:
    """Build the ``read_article`` tool, reading one article of a zone chapter.

    Args:
        corpus: The corpus to read.
        max_chars: Longest reply.

    Returns:
        The tool.
    """
    require_positive(max_chars=max_chars)

    def read_article(zone: str, article: str, sector: str | None = None) -> str:
        """Read one article of a zone chapter.

        Args:
            zone: Zone code as printed on the zoning plan, e.g. `UMG`.
            article: Article number, e.g. `10`.
            sector: Sector name, needed when the zone code exists in several sectors.
        """
        index = corpus.index()
        with lookup_errors():
            head = index.article(zone, article, sector)
            text = render_sections(index.subtree(head.id), index)
        return truncate(text, max_chars, "Read its sub-sections or pages with read_section.")

    return as_tool(read_article, _ARTICLE)


def read_section_tool(*, corpus: CorpusSource, mode: str, max_chars: int) -> BaseTool:
    """Build the ``read_section`` tool, reading any section by id.

    Args:
        corpus: The corpus to read.
        mode: A ``RetrievalMode`` value: own text and outline, or the whole subtree.
        max_chars: Longest reply.

    Returns:
        The tool.
    """
    retrieval = RetrievalMode(mode)
    require_positive(max_chars=max_chars)

    def read_section(section_id: str) -> str:
        """Read one section by id.

        Args:
            section_id: Section id, e.g. `plu_reglement/titre-i/2`.
        """
        index = corpus.index()
        with lookup_errors():
            section = index.section(section_id)
            if retrieval is RetrievalMode.FULL_SECTIONS:
                text = render_sections(index.subtree(section.id), index)
                return truncate(text, max_chars, "Read its sub-sections one by one.")
            text = render_section(section, index)
            children = index.children(section.id)
            if children:
                text += f"\n\nSub-sections (read with read_section):\n{outline(children, index)}"
        return truncate(text, max_chars, "Read the remaining pages with read_pages.")

    return as_tool(read_section, _SECTION[retrieval])


def read_pages_tool(*, corpus: CorpusSource, max_pages: int, max_chars: int) -> BaseTool:
    """Build the ``read_pages`` tool, reading raw page text.

    Args:
        corpus: The corpus to read.
        max_pages: Most pages per call.
        max_chars: Longest reply.

    Returns:
        The tool.
    """
    require_positive(max_pages=max_pages, max_chars=max_chars)

    def read_pages(doc: str, start: int, end: int) -> str:
        """Read raw pages.

        Args:
            doc: Document id, e.g. `plu_reglement`.
            start: First page (1-based PDF page, as in the markers).
            end: Last page, included.
        """
        if end - start + 1 > max_pages:
            msg = (
                f"At most {max_pages} pages per call, and {start}-{end} is {end - start + 1}. "
                f"Read {start}-{start + max_pages - 1} first, then continue."
            )
            raise ToolException(msg)
        with lookup_errors():
            pages = corpus.index().pages(doc, start, end)
        return truncate(render_pages(pages), max_chars, "Ask for fewer pages.")

    return as_tool(read_pages, _PAGES.format(max_pages=max_pages))
