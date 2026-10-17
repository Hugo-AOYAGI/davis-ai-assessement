"""Phoenix experiments use the same evaluation task and scoring as offline passes."""

import hashlib
import json
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from phoenix.client import Client
from phoenix.client.resources.datasets import Dataset
from phoenix.client.resources.experiments.types import ExperimentEvaluation
from pydantic import JsonValue, TypeAdapter

from agent.observability.logs import get_logger
from evals.harness.items import Item, Level
from evals.harness.passes.driver import BudgetReachedError
from evals.harness.passes.scoring import ItemMetrics, ItemResult

logger = get_logger(__name__)

HASH_CHARS = 12
"""Hex digits of the content hash kept in a dataset name."""

type Example = Mapping[str, JsonValue]
_JSON: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
type Evaluator = Callable[[JsonValue], ExperimentEvaluation]


@dataclass(frozen=True)
class ExperimentSettings:
    """How an experiment is named and run."""

    name: str
    """Experiment name; ``run_levels`` prefixes it with the level."""
    metadata: Mapping[str, JsonValue]
    timeout_s: int
    """Per-item task timeout (``eval.phoenix.timeout_s``)."""
    retries: int
    """Relaunches of a failed task (``eval.phoenix.retries``)."""


class DatasetsApi(Protocol):
    """The part of ``phoenix.client`` datasets used here."""

    def get_dataset(self, *, dataset: str) -> Dataset:
        """Fetch a dataset by name; raise ``ValueError`` when there is none."""
        ...

    def create_dataset(
        self,
        *,
        name: str,
        inputs: Iterable[Example],
        outputs: Iterable[Example],
        metadata: Iterable[Example],
        dataset_description: str | None,
    ) -> Dataset:
        """Upload a dataset."""
        ...


class ExperimentsApi(Protocol):
    """The part of ``phoenix.client`` experiments used here."""

    def run_experiment(  # noqa: PLR0913 - mirrors phoenix.client
        self,
        *,
        dataset: Dataset,
        task: Callable[[Example], JsonValue],
        evaluators: Mapping[str, Evaluator],
        experiment_name: str,
        experiment_metadata: Mapping[str, JsonValue],
        timeout: int,
        retries: int,
    ) -> object:
        """Run a task on every example and evaluate its outputs."""
        ...


class PhoenixApi(Protocol):
    """A Phoenix client: ``phoenix.client.Client`` or a test double."""

    @property
    def datasets(self) -> DatasetsApi:
        """Datasets endpoints."""
        ...

    @property
    def experiments(self) -> ExperimentsApi:
        """Experiments endpoints."""
        ...


def connect(base_url: str) -> PhoenixApi:
    """Open a client on the Phoenix server at ``eval.phoenix.base_url``."""
    return Client(base_url=base_url)


def dataset_name(level: str, items: Sequence[Item]) -> str:
    """Name a dataset by its level and a hash of its items' content.

    Editing ground truth changes the hash, so it creates a new dataset rather than silently
    reusing results scored against the old answers.

    Args:
        level: The items' level.
        items: The items of the dataset.

    Returns:
        ``<level>-<hash>``.
    """
    content = [item.model_dump(mode="json") for item in sorted(items, key=lambda i: i.id)]
    digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode("utf-8")).hexdigest()
    return f"{level}-{digest[:HASH_CHARS]}"


def ensure_dataset(client: PhoenixApi, level: str, items: Sequence[Item]) -> Dataset:
    """Return the dataset of these items, uploading it when Phoenix does not have it yet.

    Args:
        client: The Phoenix client.
        level: The items' level.
        items: The items, all of ``level``.

    Returns:
        The Phoenix dataset; one example per item, its id in the metadata.
    """
    name = dataset_name(level, items)
    try:
        return client.datasets.get_dataset(dataset=name)
    except ValueError:
        logger.info("uploading dataset %s (%d items)", name, len(items))
    return client.datasets.create_dataset(
        name=name,
        inputs=[item.input.model_dump(mode="json") for item in items],
        outputs=[_expected(item) for item in items],
        metadata=[
            {"item_id": item.id, "level": str(item.level), "tests": item.tests} for item in items
        ],
        dataset_description=f"{level} eval items",
    )


def run_experiment(
    client: PhoenixApi,
    items: Sequence[Item],
    evaluate: Callable[[Item], ItemResult],
    settings: ExperimentSettings,
) -> None:
    """Run one level's items as a Phoenix experiment, the scores exposed as evaluators.

    Args:
        client: The Phoenix client.
        items: Items of one level.
        evaluate: Runs and scores one item; it raises to refuse an item (budget reached).
        settings: Experiment name, metadata, timeout and retries.
    """
    level = str(items[0].level)
    by_id = {item.id: item for item in items}

    def task(metadata: Example) -> JsonValue:
        """Run and score the example's item; return its headline metrics."""
        result = evaluate(by_id[str(metadata["item_id"])])
        return _JSON.validate_python(result.metrics().model_dump(mode="json"))

    client.experiments.run_experiment(
        dataset=ensure_dataset(client, level, items),
        task=task,
        evaluators=evaluators(),
        experiment_name=settings.name,
        experiment_metadata=settings.metadata,
        timeout=settings.timeout_s,
        retries=settings.retries,
    )


def run_levels(
    client: PhoenixApi,
    items: Sequence[Item],
    evaluate: Callable[[Item], ItemResult],
    settings: ExperimentSettings,
) -> list[ItemResult]:
    """Run each level and return results in item order, excluding budget refusals.

    Raises:
        RuntimeError: If Phoenix omits an item for any reason other than the budget.
    """
    results: dict[str, ItemResult] = {}
    budget_skips: set[str] = set()
    lock = threading.Lock()

    def collect(item: Item) -> ItemResult:
        """Evaluate an item and keep its result."""
        try:
            result = evaluate(item)
        except BudgetReachedError:
            with lock:
                budget_skips.add(item.id)
            raise
        with lock:
            results[item.id] = result
        return result

    for level in Level:
        selected = [item for item in items if item.level is level]
        if selected:
            named = replace(settings, name=f"{level} {settings.name}")
            run_experiment(client, selected, collect, named)
    failed = sorted({item.id for item in items} - results.keys() - budget_skips)
    if failed:
        msg = f"Phoenix evaluations failed without results: {', '.join(failed)}"
        raise RuntimeError(msg)
    return [results[item.id] for item in items if item.id in results]


def evaluators() -> dict[str, Evaluator]:
    """One Phoenix evaluator per headline metric of an item.

    Returns:
        Evaluators by name; each reads the task's output (an ``ItemMetrics`` as JSON).
    """
    return {name: _evaluator(name) for name in ItemMetrics.model_fields if name != "item_id"}


def _evaluator(field: str) -> Evaluator:
    """Build the evaluator exposing one ``ItemMetrics`` field."""

    def evaluate(output: JsonValue) -> ExperimentEvaluation:
        """Expose the field as a score; ``n/a`` when the item has no such value."""
        value = output.get(field) if isinstance(output, dict) else None
        if isinstance(value, bool):
            return {"score": float(value), "label": "pass" if value else "fail"}
        if isinstance(value, int | float):
            return {"score": float(value)}
        return {"label": "n/a"}

    return evaluate


def _expected(item: Item) -> dict[str, JsonValue]:
    """The expected answers of an item, shown as the example's reference output."""
    data = item.model_dump(mode="json", include={"facts", "must_flag", "must_not"})
    return {key: data[key] for key in ("facts", "must_flag", "must_not")}
