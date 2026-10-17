"""Citation validity and evidence pages: what makes a correct answer grounded-correct."""

from collections.abc import Iterable, Sequence

from agent.contracts.evidence import Citation, CitationCheck, SourceKind
from agent.tools.study.checks import CorpusFacts, check_regulatory
from agent.tools.study.messages import Verification
from evals.harness.items import Evidence
from evals.harness.matching.values import label


class CitationMatcher:
    """Checks regulatory citations against the corpus, as the ``submit_*`` gates do.

    Each distinct citation is checked once and the result kept.
    """

    def __init__(
        self, corpus: CorpusFacts, verification: Verification, *, check_raster: bool
    ) -> None:
        """Keep the corpus and the ``policies.citations`` settings.

        Args:
            corpus: The corpus facts, from ``agent.tools.study.checks.corpus_facts``.
            verification: Match settings (``min_score``, ``neighbour_pages``).
            check_raster: Whether citations of raster documents are text-checked.
        """
        self._corpus = corpus
        self._verification = verification
        self._check_raster = check_raster
        self._checks: dict[Citation, CitationCheck] = {}

    @property
    def neighbour_pages(self) -> int:
        """Pages around a cited page that also count as that page."""
        return self._verification.neighbour_pages

    def check(self, citation: Citation) -> CitationCheck:
        """Check one regulatory citation.

        Args:
            citation: A regulatory citation.

        Returns:
            Its check; not text-verifiable for a raster document unless ``check_raster``.
        """
        if citation not in self._checks:
            self._checks[citation] = check_regulatory(
                citation, self._corpus, self._verification, check_raster=self._check_raster
            )
        return self._checks[citation]

    def valid_on(self, citation: Citation, evidence: Sequence[Evidence]) -> bool:
        """Tell whether a citation is valid and sits on one of the evidence pages.

        A text citation is valid when the matcher finds its quote on its page; the page it is
        placed on is the one where the quote was found. A raster citation (zoning plan) is
        valid when it names the legend item quoted by the evidence on its page, or when that
        evidence has no quote. Pages within ``neighbour_pages`` of an evidence page count.

        Args:
            citation: Any citation backing the answer.
            evidence: The fact's evidence.

        Returns:
            Whether it grounds the answer. Geometric citations never do.
        """
        if citation.source_kind is not SourceKind.REGULATORY or citation.page is None:
            return False
        check = self.check(citation)
        page = check.matched_page or citation.page
        nearby = [
            item
            for item in evidence
            if item.doc == citation.doc and abs(item.page - page) <= self.neighbour_pages
        ]
        if check.text_verifiable:
            return check.verified and bool(nearby)
        return any(_names(citation.quote, item.quote) for item in nearby)

    def cited(self, citations: Iterable[Citation], evidence: Sequence[Evidence]) -> bool | None:
        """Tell whether one of the citations grounds an answer with this evidence.

        Args:
            citations: The citations backing the answer.
            evidence: The fact's evidence.

        Returns:
            ``None`` when the fact has no evidence, otherwise whether a citation is valid on an
            evidence page.
        """
        if not evidence:
            return None
        return any(self.valid_on(citation, evidence) for citation in citations)


def _names(quote: str, expected: str | None) -> bool:
    """Tell whether a raster citation's quote names the expected legend item."""
    return expected is None or label(expected) in label(quote)
