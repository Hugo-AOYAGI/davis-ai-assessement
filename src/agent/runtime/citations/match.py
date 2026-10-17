import re
from collections import Counter
from collections.abc import Mapping

from rapidfuzz import fuzz

from agent.contracts.evidence import Citation, CitationCheck, SourceKind
from agent.contracts.inputs.corpus import Corpus
from agent.runtime.citations.normalise import normalise

type PageIndex = Mapping[tuple[str, int], str]
"""Normalised page text keyed by ``(doc id, 1-based page)``."""

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def index_pages(corpus: Corpus) -> dict[tuple[str, int], str]:
    """Normalise every page of a corpus once, for repeated citation checks.

    Args:
        corpus: The ingested corpus.

    Returns:
        Normalised page text keyed by ``(doc id, 1-based page)``.
    """
    return {(page.doc, page.number): normalise(page.text) for page in corpus.pages}


def check_citation(
    citation: Citation, pages: PageIndex, *, min_score: float, neighbour_pages: int
) -> CitationCheck:
    """Verify that a regulatory citation's quote appears on its cited page.

    The quote is searched on the cited page and on up to ``neighbour_pages`` pages before and
    after it, since a passage often runs over a page break or the page is off by one. Fuzzy
    matching tolerates extraction noise but not a changed figure: every number of the quote must
    also appear in the matched passage, otherwise the citation is not verified on that page.
    A page that verifies the quote is preferred, then the higher score, then the nearest page, so
    an unverified check still reports how close the best match came.

    Args:
        citation: A regulatory citation.
        pages: Normalised page text, as built by ``index_pages``.
        min_score: Similarity in [0, 1] from which the quote counts as found.
        neighbour_pages: How many pages around the cited one are also searched.

    Returns:
        The best similarity found, whether some page reaches ``min_score`` with matching
        numbers, and the page holding the best match when it is not the cited one.

    Raises:
        ValueError: If the citation is geometric; those are not checked against the corpus.
    """
    if citation.source_kind is not SourceKind.REGULATORY or citation.page is None:
        msg = "only regulatory citations with a page can be checked against the corpus"
        raise ValueError(msg)
    cited = citation.page
    quote = normalise(citation.quote)
    nearest_first = sorted(
        range(cited - neighbour_pages, cited + neighbour_pages + 1),
        key=lambda number: abs(number - cited),
    )
    best_page, best = cited, (False, 0.0)
    for number in nearest_first:
        text = pages.get((citation.doc, number))
        if text is None:
            continue
        numbers_match, score = _match(quote, text)
        candidate = (numbers_match and score >= min_score, score)
        if candidate > best:
            best_page, best = number, candidate
    verified, score = best
    return CitationCheck(
        citation=citation,
        verified=verified,
        score=score,
        matched_page=None if best_page == cited else best_page,
    )


def _match(quote: str, text: str) -> tuple[bool, float]:
    """Score in [0, 1] how well ``quote`` occurs within ``text``, and check its numbers.

    ``partial_ratio`` aligns the shorter string inside the longer one, so a quote longer than the
    page would score a short page as fully matched. In that case the whole strings are compared.

    Returns:
        Whether the quote's numbers all appear in the matched passage, and the similarity.
    """
    if not quote or not text:
        return False, 0.0
    if len(quote) > len(text):
        return _numbers_within(quote, text, 0, len(text)), fuzz.ratio(quote, text) / 100
    alignment = fuzz.partial_ratio_alignment(quote, text)
    if alignment is None:
        return False, 0.0
    start, end = alignment.dest_start, alignment.dest_end
    return _numbers_within(quote, text, start, end), alignment.score / 100


def _numbers_within(quote: str, text: str, start: int, end: int) -> bool:
    """Tell whether every number of ``quote`` appears in ``text[start:end]``, with multiplicity.

    A number of ``text`` counts when it overlaps the window, so that a figure cut by the edge of
    the fuzzy alignment is still seen whole. Decimal commas are already points after
    normalisation.
    """
    window = Counter(
        found.group()
        for found in _NUMBER.finditer(text)
        if found.end() > start and found.start() < end
    )
    return Counter(_NUMBER.findall(quote)) <= window
