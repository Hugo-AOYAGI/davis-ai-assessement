from collections.abc import Mapping, Sequence
from enum import StrEnum

from langchain_core.tools import BaseTool, ToolException

from agent.adapters.corpus.index import CorpusIndex
from agent.contracts.inputs.corpus import Document
from agent.tools.documents.render import (
    CITATION_HINT,
    document_outline,
    outline,
    render_pages,
    render_section,
    render_sections,
    sub_sections,
    truncate,
)
from agent.tools.documents.source import (
    CorpusSource,
    RetrievalMode,
    as_tool,
    lookup_errors,
    require_positive,
)


class LegalForce(StrEnum):
    """How strictly a building project must follow a document."""

    CONFORMITY = "conformity"
    COMPATIBILITY = "compatibility"


_FORCE = {
    LegalForce.CONFORMITY: "the project must follow the document exactly, rule by rule.",
    LegalForce.COMPATIBILITY: (
        "the project must not contradict the document's orientations: it is followed in "
        "spirit, not to the letter."
    ),
}
_SECTION = {
    RetrievalMode.NAVIGATION: (
        "Read one section by id (ids come from list_sections and search): its own text, then an "
        "outline of its direct sub-sections, which you read with further read_section calls. "
        f"{CITATION_HINT}"
    ),
    RetrievalMode.FULL_SECTIONS: (
        "Read one section by id (ids come from list_sections and search) with all its "
        "sub-sections, e.g. a whole zone chapter or the whole glossary in one call. "
        f"{CITATION_HINT}"
    ),
}
_PAGES = (
    "Read raw pages of a document as extracted, running headers and footers included, at most "
    "{max_pages} pages per call. Use it to check a quote before citing it, to see the text "
    "around a passage, or to read pages no section covers. Pages without a text layer (plans, "
    f"scans) are read with view_image. {CITATION_HINT}"
)


def list_documents_tool(
    *, corpus: CorpusSource, documents: Sequence[Mapping[str, object]]
) -> BaseTool:
    """Build the ``list_documents`` tool, the catalogue of corpus documents.

    Args:
        corpus: The corpus to read.
        documents: The ``corpus.documents`` config entries; their ``id`` and ``legal_force``
            are read.

    Returns:
        The tool.

    Raises:
        ValueError: If an entry's ``legal_force`` is not a ``LegalForce`` value.
    """
    forces = {str(entry["id"]): LegalForce(str(entry["legal_force"])) for entry in documents}

    def list_documents() -> str:
        """List the documents of the corpus.

        One line per document: `<doc id> | <kind> | <title> | <pages> pages | legal force:
        <force>`, followed by `| image only` when no page has a text layer (read it with
        view_image). The doc id is the `doc` argument of every other tool and of citations. The
        legal force says how strictly a project must follow the document; it is explained
        below the list.
        """
        index = corpus.index()
        lines = ["Documents of the corpus:"]
        lines += [_document_line(document, index, forces) for document in index.documents()]
        used = [force for force in LegalForce if force in forces.values()]
        lines += ["", "Legal force:", *(f"- {force}: {_FORCE[force]}" for force in used)]
        return "\n".join(lines)

    return as_tool(list_documents)


def _document_line(document: Document, index: CorpusIndex, forces: Mapping[str, LegalForce]) -> str:
    """Describe one document on one line."""
    force = forces.get(document.id)
    line = (
        f"- {document.id} | {document.kind} | {document.title} | {document.page_count} pages | "
        f"legal force: {force or 'not stated'}"
    )
    pages = index.pages(document.id, 1, document.page_count)
    return line if any(page.text.strip() for page in pages) else f"{line} | image only"


def list_sections_tool(*, corpus: CorpusSource) -> BaseTool:
    """Build the ``list_sections`` tool, the table of contents of a document.

    Args:
        corpus: The corpus to read.

    Returns:
        The tool.
    """

    def list_sections(doc: str, parent: str | None = None) -> str:
        """Browse the table of contents of a document, one level at a time.

        Without `parent`, gives the document (id, kind, title, page count) and its top-level
        sections, one per line: `- <section id> | <title> | <pages>`, followed by
        `| <n> sub-sections` when it has some. Pass a section id as `parent` to list its
        sub-sections, or read it with read_section.

        Args:
            doc: Document id, as listed by list_documents, e.g. `plu_reglement`.
            parent: A section id of that document: list its direct sub-sections instead.
        """
        index = corpus.index()
        with lookup_errors():
            document = index.document(doc)
            if parent is None:
                return document_outline(document, index)
            section = index.section(parent)
            if section.doc != doc:
                msg = f"Section {parent!r} belongs to document {section.doc!r}, not {doc!r}."
                raise ToolException(msg)
            return sub_sections(section, index)

    return as_tool(list_sections)


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
