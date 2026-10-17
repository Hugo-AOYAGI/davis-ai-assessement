from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from agent.contracts.base import Contract
from agent.contracts.evidence import CitationCheck
from agent.contracts.findings.regulation import Verdict
from agent.contracts.study import VerifiedStudy
from agent.llm.usage import ModelUsage


class RunMetrics(Contract):
    """What one CLI run consumed, whatever its outcome."""

    address: str
    overrides: tuple[str, ...]
    """Hydra overrides of the run, as given on the command line."""
    wall_time_s: float
    usage: dict[str, ModelUsage]
    """Tokens and cost per model id."""
    total_tokens: int
    cost_usd: float
    rejected_submissions: int
    """``submit_study`` calls refused by the gate."""


class BuildingVerdict(Contract):
    """Admissibility verdict of one building of the program."""

    building: str
    verdict: Verdict


class EnvelopeNumbers(Contract):
    """Key envelope figures; ``None`` where the documents set no limit."""

    site_area_m2: float
    max_height_m: float | None
    max_storeys: float | None
    max_footprint_ratio: float | None
    min_green_ratio: float | None
    footprint_area_m2: float
    max_footprint_area_m2: float
    max_volume_m3: float | None


class CitationStats(Contract):
    """Outcome of the gate's citation checks."""

    checks: int
    text_verifiable: int
    verified: int
    pass_rate: float | None
    """``verified / text_verifiable``; ``None`` when no citation could be checked."""


class StudyDigest(Contract):
    """Headline results of an accepted study."""

    zone: str
    admissibility: tuple[BuildingVerdict, ...]
    envelope: EnvelopeNumbers
    ambiguities: int
    citations: CitationStats


class RunSummary(Contract):
    """``run_summary.json``: one run's cost and headline results."""

    run: RunMetrics
    accepted: bool
    """Whether ``submit_study`` accepted a study."""
    study: StudyDigest | None


def citation_stats(checks: Sequence[CitationCheck]) -> CitationStats:
    """Count the citation checks and their pass rate over the text-verifiable ones.

    Args:
        checks: The gate's citation checks.

    Returns:
        The counts.
    """
    checkable = [check for check in checks if check.text_verifiable]
    verified = sum(check.verified for check in checkable)
    return CitationStats(
        checks=len(checks),
        text_verifiable=len(checkable),
        verified=verified,
        pass_rate=verified / len(checkable) if checkable else None,
    )


def study_digest(verified: VerifiedStudy) -> StudyDigest:
    """Extract the headline results of a verified study.

    Args:
        verified: Study accepted by the gate.

    Returns:
        The digest.
    """
    study, envelope = verified.study, verified.envelope
    return StudyDigest(
        zone=study.regime.zone,
        admissibility=tuple(
            BuildingVerdict(building=entry.building, verdict=entry.verdict)
            for entry in study.admissibility
        ),
        envelope=EnvelopeNumbers(
            site_area_m2=envelope.site_area_m2,
            max_height_m=envelope.max_height_m,
            max_storeys=study.envelope.max_storeys.value,
            max_footprint_ratio=study.envelope.max_footprint_ratio.value,
            min_green_ratio=study.envelope.min_green_ratio.value,
            footprint_area_m2=envelope.footprint_area_m2,
            max_footprint_area_m2=envelope.max_footprint_area_m2,
            max_volume_m3=envelope.max_volume_m3,
        ),
        ambiguities=len(study.ambiguities),
        citations=citation_stats(verified.citation_checks),
    )


def run_summary(metrics: RunMetrics, verified: VerifiedStudy | None) -> RunSummary:
    """Assemble the run summary.

    Args:
        metrics: What the run consumed.
        verified: The accepted study, ``None`` when none was accepted.

    Returns:
        The summary.
    """
    return RunSummary(
        run=metrics,
        accepted=verified is not None,
        study=study_digest(verified) if verified is not None else None,
    )


def rejected_submissions(messages: Sequence[BaseMessage], tool: str) -> int:
    """Count the calls of one tool answered with an error, e.g. rejected ``submit_study`` calls.

    Args:
        messages: The orchestrator's messages.
        tool: Tool name.

    Returns:
        The number of rejected submissions.
    """
    names = {
        call["id"]: call["name"]
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    }
    return sum(
        isinstance(message, ToolMessage)
        and message.status == "error"
        and names.get(message.tool_call_id) == tool
        for message in messages
    )


def final_text(messages: Sequence[BaseMessage]) -> str:
    """Return the text of the last AI message.

    Args:
        messages: The orchestrator's messages.

    Returns:
        The text, empty when the run produced no AI message.
    """
    replies = [message for message in messages if isinstance(message, AIMessage)]
    return replies[-1].text if replies else ""
