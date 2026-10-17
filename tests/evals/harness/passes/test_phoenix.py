from typing import cast

import pytest
from phoenix.client.__generated__ import v1
from phoenix.client.resources.datasets import Dataset
from pydantic import JsonValue, TypeAdapter

from evals.harness.items import Item, Level
from evals.harness.passes import phoenix
from evals.harness.passes.scoring import ItemMetrics, ItemResult, RunInfo
from evals.harness.scorers.facts import FactScore

JSON: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


def make_dataset(name, inputs, outputs, metadata):
    examples = [
        {"id": f"ex{i}", "input": x, "output": y, "metadata": m, "updated_at": ""}
        for i, (x, y, m) in enumerate(zip(inputs, outputs, metadata, strict=True))
    ]
    info = {"id": name, "name": name, "description": None, "metadata": {}}
    return Dataset(
        cast("v1.Dataset", info),
        cast(
            "v1.ListDatasetExamplesData",
            {"dataset_id": name, "version_id": "v1", "examples": examples},
        ),
    )


class FakeDatasets:
    def __init__(self):
        self.stored: dict[str, Dataset] = {}
        self.created: list[str] = []

    def get_dataset(self, *, dataset):
        if dataset not in self.stored:
            raise ValueError(f"Dataset not found: {dataset}")
        return self.stored[dataset]

    def create_dataset(self, *, name, inputs, outputs, metadata, dataset_description):
        self.created.append(name)
        self.stored[name] = make_dataset(name, list(inputs), list(outputs), list(metadata))
        return self.stored[name]


class FakeExperiments:
    def __init__(self):
        self.calls: list[dict[str, object]] = []
        self.evaluations: dict[str, dict[str, object]] = {}

    def run_experiment(self, *, dataset, task, evaluators, **options):
        self.calls.append(options)
        for example in dataset.examples:
            output = task(example["metadata"])
            self.evaluations[example["metadata"]["item_id"]] = {
                name: evaluator(output) for name, evaluator in evaluators.items()
            }


class FakeClient:
    def __init__(self):
        self.datasets = FakeDatasets()
        self.experiments = FakeExperiments()


@pytest.fixture
def surveyor_items(items) -> list[Item]:
    return [item for item in items.values() if item.level is Level.SURVEYOR]


def test_dataset_name_is_a_content_hash(items):
    item = items["s01_joliot_curie"]
    name = phoenix.dataset_name("surveyor", [item])
    assert name.startswith("surveyor-")
    assert len(name.removeprefix("surveyor-")) == phoenix.HASH_CHARS
    assert phoenix.dataset_name("surveyor", [item]) == name
    edited = item.model_copy(update={"must_not": ("Uses parcel CR0249",)})
    assert phoenix.dataset_name("surveyor", [edited]) != name


def test_dataset_name_ignores_item_order(items):
    two = [items["s01_joliot_curie"], items["z01_zone_boundary"]]
    assert phoenix.dataset_name("x", two) == phoenix.dataset_name("x", two[::-1])


def test_dataset_is_uploaded_once(surveyor_items):
    client = FakeClient()
    first = phoenix.ensure_dataset(client, "surveyor", surveyor_items)
    again = phoenix.ensure_dataset(client, "surveyor", surveyor_items)
    assert first is again
    assert client.datasets.created == [phoenix.dataset_name("surveyor", surveyor_items)]
    example = first.examples[0]
    assert example["metadata"]["item_id"] == surveyor_items[0].id
    assert example["input"]["address"] == surveyor_items[0].input.model_dump()["address"]
    assert {"facts", "must_flag", "must_not"} == set(example["output"])


def metrics(**changes) -> JsonValue:
    base = ItemMetrics(
        item_id="s01",
        item_pass=True,
        grounded_accuracy=0.75,
        answer_accuracy=1.0,
        citation_validity=None,
        must_flag_rate=0.5,
        must_not_hits=0,
        anti_patterns=2,
        cost_usd=0.03,
    )
    return JSON.validate_python(base.model_copy(update=changes).model_dump(mode="json"))


def test_evaluators_expose_every_metric():
    evaluators = phoenix.evaluators()
    assert set(evaluators) == set(ItemMetrics.model_fields) - {"item_id"}
    output = metrics()
    assert evaluators["item_pass"](output) == {"score": 1.0, "label": "pass"}
    assert evaluators["grounded_accuracy"](output) == {"score": 0.75}
    assert evaluators["answer_accuracy"](output) == {"score": 1.0}
    assert evaluators["citation_validity"](output) == {"label": "n/a"}
    assert evaluators["must_flag_rate"](output) == {"score": 0.5}
    assert evaluators["must_not_hits"](output) == {"score": 0.0}
    assert evaluators["anti_patterns"](output) == {"score": 2.0}
    assert evaluators["cost_usd"](output) == {"score": 0.03}
    assert evaluators["item_pass"](metrics(item_pass=False)) == {"score": 0.0, "label": "fail"}


def test_evaluators_on_a_failed_task():
    assert phoenix.evaluators()["item_pass"](None) == {"label": "n/a"}


def test_experiment_runs_the_harness_task(surveyor_items):
    client = FakeClient()
    seen: list[str] = []

    def evaluate(item: Item) -> ItemResult:
        seen.append(item.id)
        fact = FactScore(
            key_or_statement="k",
            correct=True,
            grounded=False,
            critical=True,
            cited=False,
            detail="",
        )
        return ItemResult(
            item_id=item.id,
            level=item.level,
            passed=False,
            run=RunInfo(cost_usd=0.02),
            facts=(fact,),
        )

    settings = phoenix.ExperimentSettings(name="x", metadata={"k": 1}, timeout_s=9, retries=0)
    results = phoenix.run_levels(client, surveyor_items, evaluate, settings)
    assert seen == [item.id for item in surveyor_items]
    assert [result.item_id for result in results] == seen
    assert client.experiments.calls == [
        {
            "experiment_name": "surveyor x",
            "experiment_metadata": {"k": 1},
            "timeout": 9,
            "retries": 0,
        }
    ]
    scores = client.experiments.evaluations[surveyor_items[0].id]
    assert scores["item_pass"] == {"score": 0.0, "label": "fail"}
    assert scores["answer_accuracy"] == {"score": 1.0}
    assert scores["grounded_accuracy"] == {"score": 0.0}
    assert scores["cost_usd"] == {"score": 0.02}
