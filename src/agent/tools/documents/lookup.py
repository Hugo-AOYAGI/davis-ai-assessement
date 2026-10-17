import re
from collections.abc import Sequence

from langchain_core.tools import BaseTool

from agent.adapters.corpus.index import CorpusIndex, Hit
from agent.adapters.corpus.text import fold, tokens
from agent.contracts.inputs.corpus import Section
from agent.tools.documents.render import page_range, paginate
from agent.tools.documents.source import CorpusSource, as_tool, lookup_errors, require_positive


def search_tool(*, corpus: CorpusSource, k: int, snippet_chars: int) -> BaseTool:
    """Build the ``search`` tool, a keyword search over every section of the corpus.

    Args:
        corpus: The corpus to read.
        k: Most hits per reply.
        snippet_chars: Length of the text shown around each hit.

    Returns:
        The tool.
    """
    require_positive(k=k, snippet_chars=snippet_chars)

    def search(query: str, doc: str | None = None) -> str:
        """Find the sections of the documents about some words (BM25 keyword search).

        Use it to find where a topic, a use or a defined term appears, including outside the
        sections you are reading (general provisions, glossary, another chapter). Each hit gives
        `<section id> | <heading path> | <pages>` and a passage where the words occur, prefixed
        with its page `(p.<n>)`. A snippet is not enough to cite: read the section with
        read_section (or the page with read_pages) and quote from the full text. Accents and
        case do not matter.

        Args:
            query: A few key words, e.g. `stationnement résidence étudiante`.
            doc: A document id, to search only that document.
        """
        index = corpus.index()
        with lookup_errors():
            hits = index.search(query, k, doc)
        if not hits:
            return (
                f"No section matches {query!r}. Try other words: synonyms, the documents' own "
                "terms (destination, emprise, gabarit...), or a single key word."
            )
        terms = list(dict.fromkeys(tokens(query, corpus.stopwords)))
        lines = [f"Sections matching {query!r}, best first:"]
        lines += [_hit(hit, index, terms, snippet_chars) for hit in hits]
        return "\n".join(lines)

    return as_tool(search)


def _hit(hit: Hit, index: CorpusIndex, terms: Sequence[str], width: int) -> str:
    """Render one hit: its id, heading path and pages, then a snippet with its page."""
    section = hit.section
    head = (
        f"- {section.id} | {' > '.join(section.heading_path)} | "
        f"{page_range(section.page_start, section.page_end)}"
    )
    page, snippet = _snippet(section, index, terms, width)
    return f"{head}\n  (p.{page}) {snippet}" if snippet else head


def _snippet(
    section: Section, index: CorpusIndex, terms: Sequence[str], width: int
) -> tuple[int, str]:
    """Pick the passage of ``width`` characters holding the most distinct query terms.

    Passages never cross a page break, so the page given is the one the passage is on. Without
    any term in the text, the passage is the start of the section.

    Returns:
        The page and the passage on one line, with ``…`` where it was cut.
    """
    chunks = paginate(section, index)
    if not chunks:
        return section.page_start, ""
    best = (0, chunks[0][0], chunks[0][1], 0)
    for page, text in chunks:
        folded = fold(text)
        found = [
            (match.start(), term)
            for term in terms
            for match in re.finditer(rf"\b{re.escape(term)}", folded)
        ]
        for centre, _ in found:
            count = len({term for at, term in found if abs(at - centre) <= width // 2})
            if count > best[0]:
                best = (count, page, text, centre)
    _, page, text, centre = best
    start = max(0, min(centre - width // 2, len(text) - width))
    end = min(len(text), start + width)
    passage = " ".join(text[start:end].split())
    return page, f"{'…' if start else ''}{passage}{'…' if end < len(text) else ''}"
