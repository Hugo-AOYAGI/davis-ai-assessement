from collections.abc import Mapping
from functools import cache

from agent.adapters.images.pages import PageImages, RegionError
from agent.contracts.findings.notes import DocNotes
from agent.tools.documents.source import CorpusSource
from agent.tools.study.checks import (
    CitationRules,
    CorpusFacts,
    check_submission,
    corpus_facts,
    parse_policy,
)
from agent.tools.study.messages import Verification
from agent.tools.submit.artifacts import ArtifactData
from agent.tools.submit.factory import Finalizer, SubmissionRejected


def notes_finalizer(  # noqa: PLR0913 - one argument per config knob
    *,
    corpus: CorpusSource,
    images: PageImages,
    policy: str,
    min_score: float,
    neighbour_pages: int,
    max_quote_chars: int,
    check_raster: bool,
) -> Finalizer[DocNotes, DocNotes]:
    """Build the ``submit_notes`` finalizer: every quote verified, every view on its page.

    Each distinct regulatory citation is checked once against the corpus page it cites, as
    ``submit_study`` does: under the ``reject`` policy an unverified citation refuses the
    submission, under ``flag`` it is logged; a citation of a raster document is only recorded
    unless ``check_raster``; a corpus document cited as geometric is always refused. Every view
    region must lie on an existing page overview. All errors come back in one rejection, so the
    model fixes everything at once. The submission is stored unchanged.

    Args:
        corpus: The corpus the quotes are checked against; its pages are indexed on first use.
        images: The page images the view regions are checked against.
        policy: ``reject`` or ``flag``, see ``CitationPolicy``.
        min_score: Similarity in [0, 1] from which a quote counts as found on its page.
        neighbour_pages: How many pages around the cited one are also searched.
        max_quote_chars: Quotes longer than this are truncated in error messages.
        check_raster: Whether citations of raster documents are text-checked, and then fail.

    Returns:
        The finalizer, for ``submit_tool(..., finalize=...)``.

    Raises:
        ValueError: If ``policy`` is not a ``CitationPolicy`` value.
    """
    rules = CitationRules(
        parse_policy(policy),
        Verification(min_score, neighbour_pages, max_quote_chars),
        check_raster,
    )

    @cache
    def facts() -> CorpusFacts:
        """Index the corpus, once."""
        return corpus_facts(corpus.index().corpus)

    def finalize(submission: DocNotes, _artifacts: Mapping[str, ArtifactData]) -> DocNotes:
        """Check the citations and the views, and refuse with every error found."""
        errors = _view_errors(submission, images)
        try:
            check_submission(type(submission).__name__, submission, facts(), rules)
        except SubmissionRejected as rejection:
            errors = [*rejection.errors, *errors]
        if errors:
            raise SubmissionRejected(errors)
        return submission

    return finalize


def _view_errors(submission: DocNotes, images: PageImages) -> list[str]:
    """Return one ``notes.<i>.views.<j>: message`` error per view off its page."""
    errors: list[str] = []
    for i, note in enumerate(submission.notes):
        for j, view in enumerate(note.views):
            try:
                images.check(view)
            except RegionError as error:
                errors.append(f"notes.{i}.views.{j}: {error}")
    return errors
