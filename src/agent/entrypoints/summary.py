from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from agent.contracts.base import Contract
from agent.contracts.evidence import CitationCheck
from agent.contracts.geometry import Scenario
from agent.contracts.study import Verdict, VerifiedStudy
from agent.llm.costs import NodeUsage
from agent.llm.usage import ModelUsage
from agent.tools.submit.replies import revise_name


class RunMetrics(Contract):
    """What one CLI run consumed, whatever its outcome."""

    address: str
    overrides: tuple[str, ...]
    """Hydra overrides of the run, as given on the command line."""
    wall_time_s: float
    usage: dict[str, ModelUsage]
    """Tokens and cost per model id."""
    usage_by_node: dict[str, NodeUsage]
    """Calls, tokens and cost per model node (orchestrator, each sub-agent)."""
    total_tokens: int
    cost_usd: float
    rejected_submissions: int
    """``submit_study`` and ``revise_study`` calls refused by the gate."""


class BuildingVerdict(Contract):
    """Admissibility verdict of one building of the program."""

    building: str
    verdict: Verdict


class MassingNumbers(Contract):
    """Key figures of one building of a scenario."""

    building: str
    footprint_area_m2: float
    max_height_m: float
    volume_m3: float


class ScenarioNumbers(Contract):
    """Key figures of one envelope scenario (a bound or the proposal)."""

    name: str
    footprint_area_m2: float
    """Ground footprint after setbacks, before any cap."""
    fits: bool
    total_volume_m3: float
    buildings: tuple[MassingNumbers, ...]


class EnvelopeNumbers(Contract):
    """Key envelope figures; ``None`` where the documents set no limit."""

    site_area_m2: float
    max_footprint_ratio: float | None
    min_green_ratio: float | None
    min_green_area_m2: float | None
    bounds: tuple[ScenarioNumbers, ...]
    proposal: ScenarioNumbers


class CitationStats(Contract):
    """Outcome of the gate's citation checks."""

    checks: int
    text_verifiable: int
    verified: int
    pass_rate: float | None
    """``verified / text_verifiable``; ``None`` when no citation could be checked."""


class StudyDigest(Contract):
    """Headline results of an accepted study."""

    parcel_ids: tuple[str, ...]
    """Parcels the surveyor chose as the site."""
    zone: str
    overlays: tuple[str, ...]
    """Legend items applying to the site."""
    oap_applicable: bool
    admissibility: tuple[BuildingVerdict, ...]
    envelope: EnvelopeNumbers | None
    ambiguities: int
    evidence_crops: int
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


def _scenario_numbers(scenario: Scenario) -> ScenarioNumbers:
    """Extract the key figures of one envelope scenario."""
    return ScenarioNumbers(
        name=scenario.name,
        footprint_area_m2=scenario.footprint_area_m2,
        fits=scenario.fits,
        total_volume_m3=scenario.total_volume_m3,
        buildings=tuple(
            MassingNumbers(
                building=massing.building,
                footprint_area_m2=massing.footprint_area_m2,
                max_height_m=massing.max_height_m,
                volume_m3=massing.volume_m3,
            )
            for massing in scenario.buildings
        ),
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
        parcel_ids=verified.site.choice.parcel_ids,
        zone=study.regime.zone,
        overlays=tuple(item.item for item in study.regime.overlays),
        oap_applicable=study.regime.oap_applicable,
        admissibility=tuple(
            BuildingVerdict(building=entry.building, verdict=entry.verdict)
            for entry in study.admissibility
        ),
        envelope=None
        if envelope is None
        else EnvelopeNumbers(
            site_area_m2=envelope.site_area_m2,
            max_footprint_ratio=envelope.rules.max_footprint_ratio.value,
            min_green_ratio=envelope.rules.min_green_ratio.value,
            min_green_area_m2=envelope.min_green_area_m2,
            bounds=tuple(_scenario_numbers(bound) for bound in envelope.bounds),
            proposal=_scenario_numbers(envelope.proposal),
        ),
        ambiguities=len(study.ambiguities),
        evidence_crops=len(verified.evidence),
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
    """Count the calls of a submit tool, or of its revise tool, answered with an error.

    A rejected revision (e.g. ``revise_study``) is a rejected submission of the same result, so
    ``rejected_submissions(messages, "submit_study")`` counts both tools' refusals.

    Args:
        messages: The orchestrator's messages.
        tool: Submit tool name.

    Returns:
        The number of rejected submissions.
    """
    tools = {tool, revise_name(tool)}
    names = {
        call["id"]: call["name"]
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    }
    return sum(
        isinstance(message, ToolMessage)
        and message.status == "error"
        and names.get(message.tool_call_id) in tools
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
