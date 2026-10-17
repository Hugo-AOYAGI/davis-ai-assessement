from collections import defaultdict
from collections.abc import Sequence
from difflib import get_close_matches
from functools import cache
from pathlib import Path
from typing import NamedTuple

from agent.adapters.corpus.search import Bm25
from agent.adapters.corpus.store import load_corpus
from agent.contracts.inputs.corpus import Corpus, Document, Page, Section


class Hit(NamedTuple):
    """A search result."""

    section: Section
    score: float


class CorpusIndex:
    """Read-only navigation over an ingested corpus: documents, pages, sections, search.

    Section ids are hierarchical (``{parent_id}/{key}``); a section's parent is its id minus the
    last ``/`` component when that id is a section. Lookup errors are ``LookupError`` with a
    message listing the valid options, meant to be relayed to the model.
    """

    def __init__(self, corpus: Corpus, stopwords: Sequence[str] = ()) -> None:
        """Build the lookup tables and the search index.

        Args:
            corpus: The ingested corpus.
            stopwords: Words ignored by keyword search.
        """
        self._corpus = corpus
        self._documents = {document.id: document for document in corpus.documents}
        self._pages = {(page.doc, page.number): page for page in corpus.pages}
        self._sections = {section.id: section for section in corpus.sections}
        self._children: defaultdict[str, list[Section]] = defaultdict(list)
        for section in corpus.sections:
            parent = self.parent(section.id)
            if parent is not None:
                self._children[parent.id].append(section)
        self._bm25 = Bm25(
            ["\n".join((*section.heading_path, section.text)) for section in corpus.sections],
            stopwords,
        )

    @property
    def corpus(self) -> Corpus:
        """The indexed corpus."""
        return self._corpus

    def documents(self) -> list[Document]:
        """Return the documents of the corpus."""
        return list(self._corpus.documents)

    def document(self, doc: str) -> Document:
        """Return a document by id, or raise ``LookupError`` listing the known ids."""
        if doc not in self._documents:
            msg = f"Unknown document {doc!r}. Known documents: {', '.join(self._documents)}."
            raise LookupError(msg)
        return self._documents[doc]

    def page(self, doc: str, number: int) -> Page:
        """Return one page (1-based), or raise ``LookupError`` naming the valid range."""
        return self.pages(doc, number, number)[0]

    def pages(self, doc: str, start: int, end: int) -> list[Page]:
        """Return pages ``start`` to ``end`` inclusive (1-based).

        Raises:
            LookupError: Unknown document, or a range outside the document's pages.
        """
        count = self.document(doc).page_count
        if not 1 <= start <= end <= count:
            msg = f"Invalid page range {start}-{end} for {doc!r}: valid pages are 1-{count}."
            raise LookupError(msg)
        return [self._pages[doc, number] for number in range(start, end + 1)]

    def sections(self, doc: str | None = None) -> list[Section]:
        """Return all sections, or those of one document, in document order."""
        if doc is None:
            return list(self._corpus.sections)
        self.document(doc)
        return [section for section in self._corpus.sections if section.doc == doc]

    def section(self, section_id: str) -> Section:
        """Return a section by id, or raise ``LookupError`` suggesting close ids."""
        if section_id not in self._sections:
            close = get_close_matches(section_id, self._sections, n=5)
            hint = f" Did you mean: {', '.join(close)}?" if close else ""
            raise LookupError(f"Unknown section {section_id!r}.{hint}")
        return self._sections[section_id]

    def parent(self, section_id: str) -> Section | None:
        """Return the parent section, or ``None`` for a top-level section."""
        return self._sections.get(section_id.rpartition("/")[0])

    def children(self, section_id: str) -> list[Section]:
        """Return the direct sub-sections, in document order."""
        self.section(section_id)
        return list(self._children[section_id])

    def subtree(self, section_id: str) -> list[Section]:
        """Return the section followed by all its descendants, in document order."""
        prefix = self.section(section_id).id + "/"
        return [
            section
            for section in self._corpus.sections
            if section.id == section_id or section.id.startswith(prefix)
        ]

    def search(self, query: str, k: int, doc: str | None = None) -> list[Hit]:
        """Return up to ``k`` sections ranked by BM25 over heading path and text, best first.

        Only positive scores are kept; ``doc`` restricts to one document before taking ``k``.
        """
        if doc is not None:
            self.document(doc)
        sections = self._corpus.sections
        ranked = self._bm25.search(query, len(sections))
        hits = [Hit(sections[i], score) for i, score in ranked if doc in (None, sections[i].doc)]
        return hits[:k]


@cache
def load_index(directory: Path, stopwords: tuple[str, ...]) -> CorpusIndex:
    """Load a corpus directory into a shared, cached index.

    Args:
        directory: Corpus directory written by ``ingest``.
        stopwords: Words ignored by keyword search.

    Returns:
        The same index for the same arguments (clear with ``load_index.cache_clear()``).
    """
    return CorpusIndex(load_corpus(directory), stopwords)
