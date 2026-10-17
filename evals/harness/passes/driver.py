"""Drive a pass: run and score each item under a budget, offline or as a Phoenix experiment."""

import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from agent.observability.logs import get_logger
from evals.harness.items import Item
from evals.harness.passes.outputs import RECORDS_DIR, read_records, write_record
from evals.harness.passes.scoring import ItemResult, Scoring, score_record
from evals.harness.runs.record import RunRecord

logger = get_logger(__name__)

type RunItem = Callable[[Item], RunRecord]
"""Runs the unit under test on one item (``evals.harness.tasks.run_item`` with its config)."""


class BudgetReachedError(RuntimeError):
    """The pass has spent its budget: the item is not launched."""


class Budget:
    """What the pass may spend, agent runs and judging together; thread-safe."""

    def __init__(self, limit_usd: float, *, judging: Callable[[], float] | None = None) -> None:
        """Start with nothing spent.

        Args:
            limit_usd: ``eval.max_cost_usd``; no item is launched once this much is spent.
            judging: Reads what the judge has cost so far; judging is free when ``None``.
        """
        self._limit = limit_usd
        self._judging = judging
        self._runs = 0.0
        self._lock = threading.Lock()

    @property
    def runs_usd(self) -> float:
        """What the agent runs have cost so far."""
        return self._runs

    @property
    def judging_usd(self) -> float:
        """What the judge has cost so far."""
        return self._judging() if self._judging is not None else 0.0

    @property
    def spent_usd(self) -> float:
        """Runs and judging."""
        return self._runs + self.judging_usd

    def check(self, item_id: str) -> None:
        """Refuse to launch an item once the budget is reached.

        Args:
            item_id: The item about to be launched.

        Raises:
            BudgetReachedError: When the spending has reached the limit.
        """
        with self._lock:
            spent = self.spent_usd
        if spent >= self._limit:
            msg = f"budget ${self._limit:.2f} reached (${spent:.2f}), {item_id} not launched"
            raise BudgetReachedError(msg)

    def spend(self, cost_usd: float | None) -> None:
        """Add the cost of a finished run.

        Args:
            cost_usd: The run's cost; unknown counts as zero.
        """
        with self._lock:
            self._runs += cost_usd or 0.0


@dataclass(frozen=True)
class Harness:
    """Everything a pass needs to evaluate an item."""

    run: RunItem
    scoring: Scoring
    budget: Budget
    run_dir: Path
    """Directory of the pass."""

    @property
    def records_dir(self) -> Path:
        """Where each run record is saved as soon as it ends, before it is scored."""
        return self.run_dir / RECORDS_DIR


def evaluate(harness: Harness, item: Item) -> ItemResult:
    """Run one item within the budget, save its record, then score it.

    Args:
        harness: Runner, scoring, budget and record directory.
        item: The item.

    Returns:
        Its scores.

    Raises:
        BudgetReachedError: When the budget is reached before the item is launched.
    """
    harness.budget.check(item.id)
    record = harness.run(item)
    harness.budget.spend(record.cost.cost_usd)
    write_record(harness.records_dir, record)
    logger.info("%s ran: cost=$%.4f error=%s", item.id, record.cost.cost_usd or 0.0, record.error)
    result = score_record(item, record, harness.scoring)
    logger.info("%s scored: passed=%s", item.id, result.passed)
    return result


def run_offline(
    items: Sequence[Item], evaluate_item: Callable[[Item], ItemResult], *, concurrency: int
) -> list[ItemResult]:
    """Evaluate items with a thread pool; those refused by the budget are left out.

    With ``concurrency`` workers, at most that many runs are in flight when the budget is
    reached, so the overshoot is bounded by their cost.

    Args:
        items: The items, in order.
        evaluate_item: ``evaluate`` bound to a harness.
        concurrency: Items run at once.

    Returns:
        The results of the items that ran, in item order.
    """
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(_or_skip, evaluate_item, item) for item in items]
        outcomes = [future.result() for future in futures]
    return [result for result in outcomes if result is not None]


def rescore(items: Sequence[Item], records_dir: Path, scoring: Scoring) -> list[ItemResult]:
    """Score saved run records again, without running any agent.

    Items are matched to records by id, so edited ground truth applies; a record without its
    item, or an item without its record, is left out with a warning.

    Args:
        items: The current items.
        records_dir: ``records/`` of a previous pass.
        scoring: Matcher, judge, sections and tolerances.

    Returns:
        The results, in item order.
    """
    records = {record.item_id: record for record in read_records(records_dir)}
    for orphan in sorted(set(records) - {item.id for item in items}):
        logger.warning("record %s has no item in the selection, not scored", orphan)
    results: list[ItemResult] = []
    for item in items:
        record = records.get(item.id)
        if record is None:
            logger.warning("item %s has no record in %s, not scored", item.id, records_dir)
            continue
        results.append(score_record(item, record, scoring))
    return results


def _or_skip(evaluate_item: Callable[[Item], ItemResult], item: Item) -> ItemResult | None:
    """Evaluate an item; ``None`` when the budget refuses it."""
    try:
        return evaluate_item(item)
    except BudgetReachedError as error:
        logger.warning("%s", error)
        return None
