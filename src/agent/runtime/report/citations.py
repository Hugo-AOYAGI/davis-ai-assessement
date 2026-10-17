from collections.abc import Iterable, Sequence

from agent.contracts.evidence import Citation, CitationCheck
from agent.runtime.report.markdown import NONE, one_line, table

ELLIPSIS = "…"
RASTER = "not text-verifiable (raster)"


class CitationIndex:
    """Numbers the checked citations and renders references to them from any claim."""

    def __init__(self, checks: Sequence[CitationCheck]) -> None:
        """Number the checks from 1, in order; a repeated citation keeps its first number.

        Args:
            checks: Citation checks of the verified study.
        """
        self._numbers: dict[Citation, int] = {}
        for position, check in enumerate(checks, start=1):
            self._numbers.setdefault(check.citation, position)

    def refs(self, citations: Iterable[Citation]) -> str:
        """Render references to citations.

        Args:
            citations: Citations backing one claim.

        Returns:
            Checked citations as ``[1, 3]``, then unchecked ones inline as ``(doc, p.X)`` or
            ``(doc)``; empty when there is no citation.
        """
        cited = tuple(citations)
        numbers = sorted({self._numbers[c] for c in cited if c in self._numbers})
        parts = [f"[{', '.join(str(n) for n in numbers)}]"] if numbers else []
        parts.extend(dict.fromkeys(_inline(c) for c in cited if c not in self._numbers))
        return " ".join(parts)


def _inline(citation: Citation) -> str:
    """Render an unchecked citation as ``(doc, p.X)`` or ``(doc)``."""
    if citation.page is None:
        return f"({citation.doc})"
    return f"({citation.doc}, p.{citation.page})"


def truncate(text: str, max_chars: int) -> str:
    """Put a quote on one line and cut it to ``max_chars`` characters, ellipsis included.

    Args:
        text: Quote to shorten.
        max_chars: Maximum length of the result.

    Returns:
        The quote, unchanged apart from whitespace when it already fits.
    """
    flat = one_line(text)
    if len(flat) <= max_chars:
        return flat
    return flat[: max_chars - len(ELLIPSIS)].rstrip() + ELLIPSIS


def _status(check: CitationCheck) -> str:
    """Render whether a check passed, and where the quote was found when on another page."""
    if not check.text_verifiable:
        return RASTER
    status = "verified" if check.verified else "NOT VERIFIED"
    if check.matched_page is not None:
        return f"{status} (found on p.{check.matched_page})"
    return status


def citations_section(checks: Sequence[CitationCheck], max_quote_chars: int) -> str:
    """Render the numbered table of every citation check.

    Args:
        checks: Citation checks, numbered from 1 in this order.
        max_quote_chars: Length beyond which quotes are truncated.

    Returns:
        The ``Citations`` section.
    """
    if not checks:
        return "## Citations\n\nNo regulatory citation was checked."
    rows = (
        (
            str(position),
            check.citation.doc,
            NONE if check.citation.page is None else str(check.citation.page),
            check.citation.article or NONE,
            truncate(check.citation.quote, max_quote_chars),
            _status(check),
            f"{check.score:.2f}" if check.text_verifiable else NONE,
        )
        for position, check in enumerate(checks, start=1)
    )
    headers = ("#", "Document", "Page", "Article", "Quote", "Status", "Score")
    return f"## Citations\n\n{table(headers, rows)}"
