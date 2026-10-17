from collections.abc import Sequence
from dataclasses import dataclass

from agent.contracts.evidence import Citation, CitationCheck

ADVICE = (
    "Read the page with the regulation tools and copy the exact text, or fix the page number; "
    "drop the claim if no page supports it."
)


@dataclass(frozen=True)
class Verification:
    """Settings of the citation check, which its error messages also quote."""

    min_score: float
    neighbour_pages: int
    max_quote_chars: int


def describe_unverified(
    paths: Sequence[str],
    check: CitationCheck,
    documents: Sequence[str],
    verification: Verification,
) -> str:
    """Write the error the model reads for one unverified regulatory citation.

    Args:
        paths: Every study field path the citation appears at.
        check: The failed check.
        documents: Ids of the corpus documents.
        verification: Settings the check ran with.

    Returns:
        One line naming the paths and the source, the reason and what to do.
    """
    citation = check.citation
    where = f"{', '.join(paths)} ({source(citation)})"
    if citation.doc not in documents:
        return (
            f"{where}: unknown document {citation.doc!r}; the corpus documents are "
            f"{', '.join(documents)}. Set doc to the id of the document the quote comes from."
        )
    quote = shorten(citation.quote, verification.max_quote_chars)
    return f'{where}: {shortfall(check, verification)}: "{quote}". {ADVICE}'


def describe_mislabelled(paths: Sequence[str], doc: str) -> str:
    """Write the error for a corpus document cited as a geometric source.

    Args:
        paths: Every study field path the citation appears at.
        doc: The corpus document id.

    Returns:
        One line naming the paths and asking for a regulatory citation with a page.
    """
    return (
        f"{', '.join(paths)} ({doc}): cites corpus document {doc!r} as geometric; corpus "
        "documents are regulatory sources: set source_kind to regulatory and give the page the "
        "quote is on."
    )


def source(citation: Citation) -> str:
    """Render ``doc p.N, article`` for an error message.

    Args:
        citation: A regulatory citation.

    Returns:
        The document, page and article, when there is one.
    """
    article = f", {citation.article}" if citation.article is not None else ""
    return f"{citation.doc} p.{citation.page}{article}"


def shortfall(check: CitationCheck, verification: Verification) -> str:
    """Explain how far the best match came from verifying the quote.

    Args:
        check: The failed check.
        verification: Settings the check ran with.

    Returns:
        The pages searched, the best score against the threshold and where it was found.
    """
    searched = f"p.{check.citation.page}"
    if verification.neighbour_pages:
        searched += " or its neighbours"
    if check.score >= verification.min_score:
        best = f"best score {check.score:.2f}, but its numbers differ from the page text"
    else:
        best = f"best score {check.score:.2f} < {verification.min_score:.2f}"
    if check.matched_page is not None:
        best += f", best on p.{check.matched_page}"
    return f"quote not found verbatim on {searched} ({best})"


def shorten(quote: str, max_chars: int) -> str:
    """Collapse whitespace and truncate a quote.

    Args:
        quote: The quote as cited.
        max_chars: Length above which it is truncated, ellipsis included.

    Returns:
        The quote on one line, at most ``max_chars`` characters long.
    """
    flat = " ".join(quote.split())
    return flat if len(flat) <= max_chars else f"{flat[: max_chars - 3].rstrip()}..."
