from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from agent.contracts.evidence import Citation, CitationCheck, ImageRegion
from agent.contracts.geometry import BoundaryKind
from agent.contracts.study import VerifiedStudy
from agent.runtime.geometry.envelope.summary import describe_envelope

ADVICE = (
    "Re-read the page and copy the exact text (in a study, take the citation as it is in the "
    "notes), or fix the page number; drop the claim if no page supports it."
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


def describe_missing_artifact(artifact: str, producer: str) -> str:
    """Write the error for a sub-agent artifact the study needs but the state lacks.

    Args:
        artifact: The missing artifact key, e.g. ``site``.
        producer: The sub-agent delivering it.

    Returns:
        One line saying whom to delegate to.
    """
    return (
        f"(whole study): no `{artifact}` artifact in state. Delegate to {producer} so that it "
        f"delivers `{artifact}`, then submit the study again."
    )


def describe_missing_notes(artifact: str, label: str, producer: str) -> str:
    """Write the error for required document notes the state lacks.

    Args:
        artifact: The missing artifact key, e.g. ``notes.rules``.
        label: The notes label, e.g. ``rules``.
        producer: The sub-agent delivering notes.

    Returns:
        One line saying whom to delegate to, with which label.
    """
    return (
        f"(whole study): no `{artifact}` artifact in state. Delegate to {producer} with the "
        f"`{label}` task of the playbook (label `{label}`), read `{artifact}` with "
        "read_artifact, then submit the study again."
    )


def describe_open_point(artifact: str, question: str) -> str:
    """Write the error for an open point of the notes that no ambiguity answers.

    Args:
        artifact: The notes artifact holding the open point, e.g. ``notes.rules``.
        question: The open point's question.

    Returns:
        One line quoting the question and asking for an ambiguity copying it.
    """
    return (
        f'ambiguities: the open point "{" ".join(question.split())}" of `{artifact}` has no '
        "ambiguity. Add an ambiguity whose question copies this text exactly, with the "
        "options, your choice and its rationale."
    )


def describe_unsaved_crop(region: ImageRegion, artifact: str, producer: str, error: str) -> str:
    """Write the error for an evidence region that cannot be saved.

    Args:
        region: The region, as delivered.
        artifact: The artifact it comes from.
        producer: The sub-agent that delivered it.
        error: Why it cannot be saved.

    Returns:
        One line saying whom to delegate to so that the region is corrected.
    """
    box = ", ".join(str(value) for value in region.region)
    return (
        f"(evidence) {region.doc} p.{region.page} [{box}] from `{artifact}`: {error}. Delegate "
        f"to {producer} again so that it delivers a valid region, then submit the study again."
    )


def describe_accepted(verified: VerifiedStudy) -> str:
    """Write the figures the gate computed, for the orchestrator's reply to the user.

    Args:
        verified: The accepted study.

    Returns:
        The site limits by kind, the number of evidence crops saved, then the envelope recomputed
        from the architect's rules and layout: each bound and the proposal.
    """
    if verified.envelope is None:
        return (
            "All proposed uses are prohibited. No building envelope was computed. "
            f"Evidence crops saved: {len(verified.evidence)}."
        )
    kinds = Counter(boundary.kind for boundary in verified.boundaries)
    limits = ", ".join(f"{kinds[kind]} {kind.value}" for kind in BoundaryKind if kinds[kind])
    return (
        "Envelope recomputed by the gate; report these figures, do not recompute them:\n"
        f"- Site limits (edges by kind): {limits}\n"
        f"- Evidence crops saved: {len(verified.evidence)}\n\n"
        f"{describe_envelope(verified.envelope)}"
    )
