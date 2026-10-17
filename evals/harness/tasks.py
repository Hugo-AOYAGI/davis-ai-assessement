"""Run the unit under test on one eval item (``docs/EVALS.md`` §1, §7).

Component items run one sub-agent standalone (``build_subagent``) on the task text the
orchestrator would write; end-to-end items run ``run_study``, as the CLI does, unattended.
"""

import copy
import time
from collections.abc import Callable, Mapping, Sequence
from typing import NamedTuple

from langchain_core.callbacks import BaseCallbackHandler, UsageMetadataCallbackHandler
from langchain_core.messages import BaseMessage, HumanMessage
from omegaconf import DictConfig, OmegaConf
from pydantic import JsonValue, TypeAdapter

from agent.agents.config import read_prompt
from agent.agents.subagents import build_subagent
from agent.contracts.inputs.case import Case
from agent.entrypoints.run import make_unattended, run_study
from agent.llm.usage import price_usage
from agent.observability.logs import get_logger
from evals.harness.items import DocInput, E2EInput, Item, Level
from evals.harness.runs.capture import SubagentCapture
from evals.harness.runs.record import RunRecord, rejections
from evals.harness.runs.texts import TaskWords, task_text
from evals.harness.scorers.trajectory import RunCost

__all__ = ["RunRecord", "run_item"]

logger = get_logger("evals.harness.tasks")

_ARTIFACT: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])


class _Outcome(NamedTuple):
    """What a runner returns: the delivered artifact as JSON, and the unit's own messages."""

    output: dict[str, JsonValue] | None
    messages: list[BaseMessage]


type _Runner = Callable[[DictConfig, Item, Sequence[BaseCallbackHandler]], _Outcome]


def run_item(cfg: DictConfig, item: Item) -> RunRecord:
    """Run the unit under test of an item's level on its input.

    An exception does not escape: it is logged and the record carries it in ``error``, with
    the cost and the sub-agent messages captured until then, so one failing item never stops
    a pass.

    Args:
        cfg: The composed config, with the ``eval`` group (``eval.eval_tasks``).
        item: The item to run.

    Returns:
        The run record.
    """
    usage = UsageMetadataCallbackHandler()
    capture = SubagentCapture(cfg.subagents.keys())
    callbacks: list[BaseCallbackHandler] = [usage]
    if item.level is Level.E2E:
        callbacks.append(capture)
    start = time.perf_counter()
    outcome, error = _Outcome(None, []), None
    try:
        outcome = _RUNNERS[item.level](cfg, item, callbacks)
    # One failing item (API error, recursion limit, bad output) must not stop the pass: the
    # failure is logged with its traceback and kept in the record.
    except Exception as failure:
        logger.exception("eval item %s failed", item.id)
        error = f"{type(failure).__name__}: {failure}"
    wall_time_s = time.perf_counter() - start
    priced = price_usage(cfg.models, usage.usage_metadata)
    cost_usd = sum(entry.cost_usd for entry in priced.values())
    runs = capture.runs
    messages = [message for run in runs for message in run.messages] + outcome.messages
    return RunRecord.model_validate(
        {
            "item_id": item.id,
            "level": item.level,
            "output": outcome.output,
            "messages": messages,
            "subagent_runs": [run.name for run in runs],
            "cost": RunCost(cost_usd=cost_usd, wall_time_s=wall_time_s),
            "wall_time_s": wall_time_s,
            "rejections": rejections(messages, cfg.eval.eval_tasks.max_rejection_chars),
            "error": error,
        }
    )


def _run_component(
    cfg: DictConfig, item: Item, callbacks: Sequence[BaseCallbackHandler]
) -> _Outcome:
    """Run the level's sub-agent standalone on the item's task text."""
    settings = cfg.eval.eval_tasks
    task = item.input
    if isinstance(task, E2EInput):
        msg = f"item {item.id}: an e2e input is not a component task"
        raise TypeError(msg)
    level = item.level.value
    words = TaskWords.model_validate(OmegaConf.to_container(settings.texts, resolve=True))
    text = task_text(
        task, read_prompt(settings.templates[level]), words=words, language=cfg.agent.language
    )
    graph = build_subagent(cfg, settings.subagents[level])
    state = graph.invoke(
        {"messages": [HumanMessage(text)]},
        config={
            "recursion_limit": settings.recursion_limit,
            "callbacks": list(callbacks),
            "metadata": {"eval_item": item.id},
        },
    )
    label = task.label if isinstance(task, DocInput) else ""
    key = str(settings.artifacts[level]).format(label=label)
    return _Outcome(_artifact(state.get("artifacts"), key), _messages(state))


def _run_e2e(cfg: DictConfig, item: Item, callbacks: Sequence[BaseCallbackHandler]) -> _Outcome:
    """Run the whole study unattended, as the CLI does, on the item's address and program."""
    task = item.input
    if not isinstance(task, E2EInput):
        msg = f"item {item.id}: an e2e item needs an e2e input"
        raise TypeError(msg)
    study_cfg = copy.deepcopy(cfg)
    make_unattended(study_cfg)
    case = Case(
        address=task.address, program=task.program, corpus_id=cfg.corpus.id, facts=task.facts
    )
    _, messages, verified = run_study(study_cfg, case, [], callbacks)
    output = None if verified is None else verified.model_dump(mode="json")
    return _Outcome(output, messages)


def _artifact(artifacts: Mapping[str, JsonValue] | None, key: str) -> dict[str, JsonValue] | None:
    """Read one stored artifact as JSON, ``None`` when it was not delivered."""
    data = (artifacts or {}).get(key)
    return None if data is None else _ARTIFACT.validate_python(data)


def _messages(state: Mapping[str, object]) -> list[BaseMessage]:
    """The messages of a final graph state."""
    found = state.get("messages")
    return (
        [item for item in found if isinstance(item, BaseMessage)] if isinstance(found, list) else []
    )


_RUNNERS: dict[Level, _Runner] = {
    Level.SURVEYOR: _run_component,
    Level.ZONING: _run_component,
    Level.DOC: _run_component,
    Level.E2E: _run_e2e,
}
