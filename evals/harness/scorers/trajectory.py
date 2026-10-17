"""Trajectory of a run (``docs/EVALS.md`` §4): tool calls, gate rejections, evidence read."""

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import NamedTuple

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.messages.tool import ToolCall

from agent.contracts.base import Contract
from agent.contracts.inputs.corpus import Section
from agent.entrypoints.summary import rejected_submissions
from agent.tools.documents.source import RetrievalMode
from agent.tools.submit.replies import revise_name
from evals.harness.items import Fact, KeyFact

type PageRef = tuple[str, int]
"""``(doc id, 1-based page)``."""

SUBMIT_PREFIX = "submit_"
"""Name prefix of the tools that deliver an artifact."""
DELIVERING = (SUBMIT_PREFIX, revise_name(SUBMIT_PREFIX))
"""Name prefixes of the calls that deliver an artifact: ``submit_*`` and their ``revise_*``."""


class FactRead(Contract):
    """Whether the pages an expected fact lives on were read before the final submission."""

    fact: str
    """The fact's key or statement."""
    pages: tuple[PageRef, ...]
    """Its evidence pages."""
    read: bool
    """Some evidence page was read by a tool call before the last ``submit_*`` call."""


class RunCost(Contract):
    """What a run consumed, measured by the runner."""

    cost_usd: float | None = None
    wall_time_s: float | None = None


class TrajectoryScore(Contract):
    """What a run did on its way to the output."""

    tool_calls: dict[str, int]
    """Calls per tool name."""
    rejections: dict[str, int]
    """Calls answered with an error, per ``submit_*`` tool."""
    reads: tuple[FactRead, ...]
    """One entry per fact with evidence."""
    read_share: float | None
    """Share of the facts with evidence whose pages were read; ``None`` without such facts."""
    cost: RunCost


class _Call(NamedTuple):
    """A tool call and whether its reply was an error."""

    call: ToolCall
    failed: bool


def score_trajectory(
    messages: Sequence[BaseMessage],
    facts: Sequence[Fact],
    *,
    sections: Sequence[Section],
    mode: str,
    cost: RunCost | None = None,
) -> TrajectoryScore:
    """Score the trajectory of one run.

    Args:
        messages: The run's messages; for a sub-agent, its own. Reads done by sub-agents only
            show in their own messages.
        facts: The item's facts; those with evidence are checked for reads.
        sections: The corpus sections, to map ``read_section`` ids to pages.
        mode: ``retrieval.mode`` of the run: in ``full_sections`` a section read covers its
            sub-sections, in ``navigation`` only its own text.
        cost: The run's cost and wall time, measured by the runner.

    Returns:
        The trajectory score.
    """
    calls = _calls(messages)
    read = pages_read(messages, sections=sections, mode=mode)
    reads = tuple(
        FactRead(fact=_label(fact), pages=pages, read=any(page in read for page in pages))
        for fact in facts
        if (pages := tuple(dict.fromkeys((item.doc, item.page) for item in fact.evidence)))
    )
    submit_tools = sorted(
        {c.call["name"] for c in calls if c.call["name"].startswith(SUBMIT_PREFIX)}
    )
    return TrajectoryScore(
        tool_calls=dict(Counter(c.call["name"] for c in calls)),
        rejections={tool: rejected_submissions(messages, tool) for tool in submit_tools},
        reads=reads,
        read_share=sum(entry.read for entry in reads) / len(reads) if reads else None,
        cost=cost or RunCost(),
    )


def pages_read(
    messages: Sequence[BaseMessage], *, sections: Sequence[Section], mode: str
) -> frozenset[PageRef]:
    """Collect the corpus pages read by successful calls made before the last delivery.

    A delivery is a ``submit_*`` call or a ``revise_*`` call correcting a rejected one.

    ``read_pages`` reads its page range, ``read_section`` its section's pages (and its
    sub-sections' in ``full_sections`` mode), ``view_image`` and ``zoom`` their page. Search
    snippets are not reads: the model is told to read the section before citing it.

    Args:
        messages: The run's messages.
        sections: The corpus sections.
        mode: ``retrieval.mode`` of the run (``full_sections`` or ``navigation``).

    Returns:
        The pages read.

    Raises:
        ValueError: If ``mode`` is not a ``RetrievalMode`` value.
    """
    retrieval = RetrievalMode(mode)
    calls = _calls(messages)
    submits = [i for i, c in enumerate(calls) if c.call["name"].startswith(DELIVERING)]
    before = calls[: submits[-1]] if submits else calls
    by_id = {section.id: section for section in sections}
    readers: Mapping[str, Callable[[Mapping[str, object]], set[PageRef]]] = {
        "read_pages": _page_range,
        "read_section": lambda args: _section_pages(args, by_id, retrieval),
        "view_image": _one_page,
        "zoom": _one_page,
    }
    found: set[PageRef] = set()
    for call, failed in before:
        reader = readers.get(call["name"])
        if reader is not None and not failed:
            found |= reader(call["args"])
    return frozenset(found)


def _calls(messages: Sequence[BaseMessage]) -> list[_Call]:
    """List the tool calls in order, with whether their reply was an error."""
    failed = {
        message.tool_call_id
        for message in messages
        if isinstance(message, ToolMessage) and message.status == "error"
    }
    return [
        _Call(call, call["id"] in failed)
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    ]


def _page_range(args: Mapping[str, object]) -> set[PageRef]:
    """Pages of a ``read_pages(doc, start, end)`` call."""
    doc, start, end = args.get("doc"), args.get("start"), args.get("end")
    if not (isinstance(doc, str) and isinstance(start, int) and isinstance(end, int)):
        return set()
    return {(doc, page) for page in range(start, end + 1)}


def _one_page(args: Mapping[str, object]) -> set[PageRef]:
    """Page of a ``view_image(doc, page)`` or ``zoom(doc, page, region)`` call."""
    doc, page = args.get("doc"), args.get("page")
    return {(doc, page)} if isinstance(doc, str) and isinstance(page, int) else set()


def _section_pages(
    args: Mapping[str, object], sections: Mapping[str, Section], mode: RetrievalMode
) -> set[PageRef]:
    """Pages of a ``read_section(section_id)`` call; nothing for an unknown id."""
    section_id = args.get("section_id")
    if not isinstance(section_id, str) or section_id not in sections:
        return set()
    read = [sections[section_id]]
    if mode is RetrievalMode.FULL_SECTIONS:
        prefix = f"{section_id}/"
        read += [section for key, section in sections.items() if key.startswith(prefix)]
    return {
        (section.doc, page)
        for section in read
        for page in range(section.page_start, section.page_end + 1)
    }


def _label(fact: Fact) -> str:
    """The key or statement naming a fact."""
    return fact.key if isinstance(fact, KeyFact) else fact.statement
