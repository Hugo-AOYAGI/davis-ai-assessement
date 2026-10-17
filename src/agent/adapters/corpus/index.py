from collections import defaultdict
from collections.abc import Sequence
from difflib import get_close_matches
from functools import cache
from pathlib import Path
from typing import NamedTuple

from agent.adapters.corpus.search import Bm25
from agent.adapters.corpus.store import load_corpus
from agent.adapters.corpus.text import fold
from agent.contracts.inputs.corpus import Corpus, Document, Page, Section

_NO_MATCH = 3


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

    def __init__(
        self, corpus: Corpus, lexicon: Sequence[str] = (), stopwords: Sequence[str] = ()
    ) -> None:
        """Build the lookup tables and the search index.

        Args:
            corpus: The ingested corpus.
            lexicon: Ids of glossary sections whose children are term definitions.
            stopwords: Words ignored by keyword search.

        Raises:
            ValueError: When a lexicon id is not a section of the corpus.
        """
        self._corpus = corpus
        self._documents = {document.id: document for document in corpus.documents}
        self._pages = {(page.doc, page.number): page for page in corpus.pages}
        self._sections = {section.id: section for section in corpus.sections}
        self._children: defaultdict[str, list[Section]] = defaultdict(list)
        self._zones: defaultdict[str, list[Section]] = defaultdict(list)
        for section in corpus.sections:
            parent = self.parent(section.id)
            if parent is not None:
                self._children[parent.id].append(section)
            zone = fold(section.zone or "")
            if zone and (parent is None or fold(parent.zone or "") != zone):
                self._zones[zone].append(section)
        missing = [key for key in lexicon if key not in self._sections]
        if missing:
            msg = f"Lexicon sections not found in corpus {corpus.id!r}: {', '.join(missing)}"
            raise ValueError(msg)
        self._terms = [
            (_term_key(t.heading_path[-1]), t) for key in lexicon for t in self._children[key]
        ]
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

    def zone(self, zone: str, sector: str | None = None) -> Section:
        """Return the chapter section of a zone (its intro; articles are its children).

        Args:
            zone: Zone code, case-insensitive, e.g. ``UMG``.
            sector: Sector name, needed when the zone code exists in several sectors.

        Raises:
            LookupError: Unknown zone, no match in the sector, or ambiguous without a sector.
        """
        candidates = self._zones.get(fold(zone.strip()), [])
        if not candidates:
            known = sorted({s.zone or "" for found in self._zones.values() for s in found})
            raise LookupError(f"Unknown zone {zone!r}. Known zones: {', '.join(known)}.")
        sectors = [self._sector(section) for section in candidates]
        matches = candidates if sector is None else self._in_sector(candidates, sector)
        if len(matches) == 1:
            return matches[0]
        problem = f"is not in sector {sector!r}" if not matches else "exists in several sectors"
        msg = f"Zone {zone!r} {problem}. Its sectors: {', '.join(sectors)}; pass one as `sector`."
        raise LookupError(msg)

    def article(self, zone: str, article: str | int, sector: str | None = None) -> Section:
        """Return an article of a zone chapter.

        Args:
            zone: Zone code, case-insensitive, e.g. ``UMG``.
            article: Article number, e.g. ``10``.
            sector: Sector name, needed when the zone code exists in several sectors.

        Raises:
            LookupError: Unknown or ambiguous zone (see :meth:`zone`), or unknown article.
        """
        head = self.zone(zone, sector)
        articles = [section for section in self.subtree(head.id) if section.article is not None]
        key = fold(str(article).strip())
        for section in articles:
            if fold(section.article or "") == key:
                return section
        available = ", ".join(dict.fromkeys(section.article or "" for section in articles))
        msg = (
            f"Article {article!r} not found in zone {head.zone} ({self._sector(head)}). "
            f"Available articles: {available or 'none'}."
        )
        raise LookupError(msg)

    def definition(self, term: str) -> list[Section]:
        """Return the glossary entries matching a term (e.g. ``hauteur``), best first.

        Titles are compared after folding accents and case, collapsing spaces and dropping a
        trailing colon. Order: exact title, titles starting with the term, then titles containing
        the term or contained in it. Empty when nothing matches.
        """
        query = _term_key(term)
        if not query:
            return []
        ranked = [(_match_rank(title, query), term) for title, term in self._terms]
        return [term for rank, term in sorted(ranked, key=lambda pair: pair[0]) if rank < _NO_MATCH]

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

    def _sector(self, section: Section) -> str:
        """Return the heading of the nearest ancestor outside any zone (the sector)."""
        node = self.parent(section.id)
        while node is not None and node.zone is not None:
            node = self.parent(node.id)
        return node.heading_path[-1] if node is not None else section.doc

    def _in_sector(self, candidates: list[Section], sector: str) -> list[Section]:
        """Keep the candidates with a heading path component containing the sector name."""
        key = _term_key(sector)
        return [
            section
            for section in candidates
            if any(key in _term_key(heading) for heading in section.heading_path)
        ]


@cache
def load_index(
    directory: Path, lexicon: tuple[str, ...], stopwords: tuple[str, ...]
) -> CorpusIndex:
    """Load a corpus directory into a shared, cached index.

    Args:
        directory: Corpus directory written by ``ingest``.
        lexicon: Ids of glossary sections whose children are term definitions.
        stopwords: Words ignored by keyword search.

    Returns:
        The same index for the same arguments (clear with ``load_index.cache_clear()``).
    """
    return CorpusIndex(load_corpus(directory), lexicon, stopwords)


def _match_rank(title: str, query: str) -> int:
    """Rank a normalized title against a normalized query: 0 exact, 1 prefix, 2 partial."""
    if title == query:
        return 0
    if title.startswith(query):
        return 1
    return 2 if query in title or title in query else _NO_MATCH


def _term_key(text: str) -> str:
    """Normalize a heading or term for comparison: folded, single-spaced, no trailing colon."""
    return " ".join(fold(text).split()).rstrip(":").strip()
