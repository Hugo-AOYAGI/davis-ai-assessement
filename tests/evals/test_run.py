import json
import shutil

import pytest
from phoenix.client.__generated__ import v1
from phoenix.client.resources.datasets import Dataset

from agent.agents.config import load_config
from evals.harness.items import Item, Level
from evals.harness.judge import Judge, JudgeAnswer, JudgePrompts, Question
from evals.harness.judging.views import ViewSettings
from evals.harness.passes.driver import Budget, Harness
from evals.harness.passes.outputs import RECORDS_DIR, SCORES_FILE, SUMMARY_FILE, PassScores
from evals.harness.passes.scoring import EnvelopeSettings, Scoring
from evals.harness.passes.setup import select_items
from evals.harness.runs.record import RunRecord
from evals.harness.scorers.trajectory import RunCost
from evals.run import main, rescore_pass, run_pass
from tests.evals.conftest import ITEMS

IDS = ["s01_joliot_curie", "z01_zone_boundary", "e01_reference"]
CLAIM_MADE = "Uses parcel CR0249 as the site"


class FakeModel:
    """Answers yes only to the questions about the given subjects."""

    def __init__(self, yes_for=()):
        self.yes_for = yes_for
        self.calls = 0

    def invoke(self, messages, /):
        self.calls += 1
        prompt = str(messages[-1].content)
        verdict = "yes" if any(subject in prompt for subject in self.yes_for) else "no"
        return JudgeAnswer(verdict=verdict, reason="fake")


def fake_judge(*yes_for):
    prompts = JudgePrompts(system="s", questions={q: f"{q.value}: $subject" for q in Question})
    views = ViewSettings(max_quote_chars=100, crops_link_base="evidence")
    return Judge(FakeModel(yes_for), model_id="fake", prompts=prompts, views=views)


@pytest.fixture
def datasets(tmp_path, items):
    root = tmp_path / "datasets"
    for item_id in IDS:
        level_dir = root / items[item_id].level
        level_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(next(ITEMS.glob(f"{item_id}.yaml")), level_dir)
    return root


def eval_config(datasets, *overrides):
    return load_config(
        [
            f"eval.datasets_dir='{datasets.as_posix()}'",
            "eval.statuses=[verified,draft]",
            "eval.phoenix.enabled=false",
            *overrides,
        ],
        config_name="eval",
    )


@pytest.fixture
def scoring(matcher):
    return Scoring(
        matcher=matcher,
        judge=fake_judge(),
        sections=(),
        mode="full_sections",
        envelope=EnvelopeSettings(
            tolerance=0.02, quad_segs=8, min_area_m2=1.0, level_step_m=1, cut_tolerance_m=0.01
        ),
    )


class FakeRunner:
    def __init__(self, study_json, cost=0.5):
        self.outputs = {
            Level.SURVEYOR: study_json["site"],
            Level.ZONING: study_json["zone"],
            Level.E2E: study_json,
        }
        self.cost = cost
        self.ran: list[str] = []

    def __call__(self, item: Item) -> RunRecord:
        self.ran.append(item.id)
        return RunRecord(
            item_id=item.id,
            level=item.level,
            output=self.outputs[item.level],
            cost=RunCost(cost_usd=self.cost, wall_time_s=2.0),
        )


def read_scores(run_dir) -> PassScores:
    return PassScores.model_validate_json((run_dir / SCORES_FILE).read_text(encoding="utf-8"))


def test_eval_config_composes_the_agent_config_and_the_eval_group():
    cfg = load_config(
        ["eval.dataset=surveyor", "models.nodes.orchestrator.max_tokens=8000"], config_name="eval"
    )
    assert cfg.eval.dataset == "surveyor"
    assert cfg.models.nodes.orchestrator.max_tokens == 8000
    assert cfg.eval.tolerances.quad_segs == cfg.policies.envelope.settings.quad_segs
    assert cfg.eval.tolerances.min_area_m2 == cfg.policies.envelope.settings.min_area_m2
    assert cfg.eval.judge.model in cfg.models.nodes
    assert set(cfg.eval.eval_tasks.artifacts) == {"surveyor", "zoning", "doc"}
    assert cfg.policies.ask_user.mode == "disabled"
    assert set(load_config()) | {"eval"} == set(cfg)


def test_agent_config_is_unchanged_by_the_eval_group():
    cfg = load_config()
    assert "eval" not in cfg
    assert cfg.policies.ask_user.mode == "interactive"


def test_select_items_by_level_status_and_id(datasets):
    assert [i.id for i in select_items(eval_config(datasets))] == [
        "s01_joliot_curie",
        "z01_zone_boundary",
        "e01_reference",
    ]
    assert [i.id for i in select_items(eval_config(datasets, "eval.statuses=[verified]"))] == [
        "s01_joliot_curie"
    ]
    assert [i.id for i in select_items(eval_config(datasets, "eval.dataset=zoning"))] == [
        "z01_zone_boundary"
    ]
    only = eval_config(datasets, "eval.items=[e01_reference]")
    assert [i.id for i in select_items(only)] == ["e01_reference"]
    with pytest.raises(ValueError, match="nope"):
        select_items(eval_config(datasets, "eval.items=[nope]"))


def test_missing_explicit_dataset_is_rejected(datasets):
    with pytest.raises(ValueError, match="eval dataset does not exist"):
        select_items(eval_config(datasets, "eval.dataset=doc"))


@pytest.mark.parametrize("dataset", ["all", "surveyor"])
def test_empty_dataset_is_rejected(datasets, dataset):
    for path in datasets.rglob("*.yaml"):
        path.unlink()
    with pytest.raises(ValueError, match="no eval items match"):
        select_items(eval_config(datasets, f"eval.dataset={dataset}"))


def test_status_filter_matching_nothing_is_rejected(datasets):
    with pytest.raises(ValueError, match="no eval items match"):
        select_items(eval_config(datasets, "eval.statuses=[dropped]"))


def test_invalid_selection_fails_before_runtime_setup(datasets, monkeypatch):
    setup_calls = []
    monkeypatch.setattr("evals.run.setup_logging", lambda *_: setup_calls.append("logging"))
    with pytest.raises(ValueError, match="eval dataset does not exist"):
        main(eval_config(datasets, "eval.dataset=doc"))
    assert setup_calls == []


def test_full_pass_writes_records_scores_and_summary(tmp_path, datasets, scoring, study_json):
    runner = FakeRunner(study_json)
    run_dir = tmp_path / "run"
    harness = Harness(runner, scoring, Budget(100.0), run_dir)
    scores = run_pass(eval_config(datasets), harness, overrides=["eval.dataset=all"])
    assert runner.ran == IDS
    assert sorted(p.stem for p in (run_dir / RECORDS_DIR).glob("*.json")) == sorted(IDS)
    assert read_scores(run_dir) == scores
    assert scores.info.overrides == ("eval.dataset=all",)
    assert scores.info.spending.runs_usd == pytest.approx(1.5)
    assert scores.info.skipped == ()
    assert [level.level for level in scores.levels] == [Level.SURVEYOR, Level.ZONING, Level.E2E]
    by_id = {result.item_id: result for result in scores.items}
    survey = by_id["s01_joliot_curie"]
    assert survey.notes is not None and survey.notes.must_flag == ()
    assert survey.trajectory is not None and survey.envelope is None
    e2e = by_id["e01_reference"]
    assert e2e.envelope is not None
    assert e2e.notes is not None and len(e2e.notes.anti_patterns) == 6
    assert scores.levels[2].must_flag_coverage == 0.0
    summary = (run_dir / SUMMARY_FILE).read_text(encoding="utf-8")
    for heading in ("## surveyor (1 items)", "## zoning (1 items)", "## e2e (1 items)"):
        assert heading in summary
    for failed in (r for r in scores.items if not r.passed):
        assert f"`{failed.item_id}`" in summary


def test_a_run_without_output_fails_every_fact(tmp_path, datasets, scoring, study_json):
    runner = FakeRunner(study_json)
    runner.outputs[Level.SURVEYOR] = None
    harness = Harness(runner, scoring, Budget(100.0), tmp_path / "run")
    scores = run_pass(eval_config(datasets, "eval.dataset=surveyor"), harness, overrides=[])
    (result,) = scores.items
    assert not result.passed
    assert not any(fact.correct for fact in result.facts)
    assert result.citations is None and result.trajectory is None
    assert scores.levels[0].grounded_accuracy is not None
    assert scores.levels[0].grounded_accuracy.estimate == 0.0


def test_budget_guard_stops_launching_items(tmp_path, datasets, scoring, study_json):
    runner = FakeRunner(study_json, cost=0.5)
    harness = Harness(runner, scoring, Budget(0.6), tmp_path / "run")
    scores = run_pass(eval_config(datasets), harness, overrides=[])
    assert runner.ran == IDS[:2]
    assert scores.info.skipped == (IDS[2],)
    assert [r.item_id for r in scores.items] == IDS[:2]
    summary = (tmp_path / "run" / SUMMARY_FILE).read_text(encoding="utf-8")
    assert f"Not launched (budget reached): {IDS[2]}." in summary


def test_budget_counts_the_judge(tmp_path, datasets, scoring, study_json):
    runner = FakeRunner(study_json)
    harness = Harness(runner, scoring, Budget(1.0, judging=lambda: 1.0), tmp_path / "run")
    scores = run_pass(eval_config(datasets), harness, overrides=[])
    assert runner.ran == []
    assert scores.info.skipped == tuple(IDS)
    assert scores.info.spending.judging_usd == 1.0


def test_concurrent_pass_keeps_item_order(tmp_path, datasets, scoring, study_json):
    harness = Harness(FakeRunner(study_json), scoring, Budget(100.0), tmp_path / "run")
    cfg = eval_config(datasets, "eval.concurrency=3")
    scores = run_pass(cfg, harness, overrides=[])
    assert [r.item_id for r in scores.items] == IDS


def test_rescore_uses_saved_records_and_current_ground_truth(
    tmp_path, datasets, scoring, study_json
):
    first = tmp_path / "first"
    runner = FakeRunner(study_json)
    run_pass(eval_config(datasets), Harness(runner, scoring, Budget(100.0), first), overrides=[])
    item_file = datasets / "zoning" / "z01_zone_boundary.yaml"
    item_file.write_text(
        item_file.read_text(encoding="utf-8") + f"must_not:\n  - {CLAIM_MADE}\n",
        encoding="utf-8",
    )
    strict = Scoring(
        matcher=scoring.matcher,
        judge=fake_judge(CLAIM_MADE),
        sections=(),
        mode="full_sections",
        envelope=scoring.envelope,
    )
    cfg = eval_config(datasets, f"eval.rescore='{first.as_posix()}'")
    second = tmp_path / "second"
    scores = rescore_pass(cfg, second, scoring=strict, budget=Budget(0.0), overrides=[])
    assert len(runner.ran) == len(IDS)
    assert scores.info.rescored_from == first.as_posix()
    assert scores.info.spending.runs_usd == pytest.approx(1.5)
    before = {r.item_id: r for r in read_scores(first).items}["z01_zone_boundary"]
    rescored = {r.item_id: r for r in scores.items}["z01_zone_boundary"]
    assert before.notes is not None and not any(before.notes.must_not_hits)
    assert rescored.notes is not None and rescored.notes.must_not_hits[0]
    assert len(rescored.notes.must_not) == len(before.notes.must_not) + 1
    assert not rescored.passed
    assert (second / SCORES_FILE).is_file()
    assert not (second / RECORDS_DIR).exists()


def test_rescore_skips_items_without_records(tmp_path, datasets, scoring, study_json):
    first = tmp_path / "first"
    runner = FakeRunner(study_json)
    cfg = eval_config(datasets, "eval.dataset=surveyor")
    run_pass(cfg, Harness(runner, scoring, Budget(100.0), first), overrides=[])
    cfg = eval_config(datasets, f"eval.rescore='{first.as_posix()}'")
    scores = rescore_pass(cfg, tmp_path / "again", scoring=scoring, budget=Budget(0), overrides=[])
    assert [r.item_id for r in scores.items] == ["s01_joliot_curie"]


class PhoenixDatasets:
    def __init__(self):
        self.stored: dict[str, Dataset] = {}

    def get_dataset(self, *, dataset):
        if dataset not in self.stored:
            raise ValueError(dataset)
        return self.stored[dataset]

    def create_dataset(self, *, name, inputs, outputs, metadata, dataset_description):
        examples = [
            {"id": str(i), "input": x, "output": y, "metadata": m, "updated_at": ""}
            for i, (x, y, m) in enumerate(zip(inputs, outputs, metadata, strict=True))
        ]
        info: v1.Dataset = json.loads(json.dumps({"id": name, "name": name, "metadata": {}}))
        data: v1.ListDatasetExamplesData = json.loads(
            json.dumps({"dataset_id": name, "version_id": "v", "examples": examples})
        )
        self.stored[name] = Dataset(info, data)
        return self.stored[name]


class PhoenixExperiments:
    def __init__(self):
        self.names: list[str] = []
        self.scores: dict[str, object] = {}

    def run_experiment(self, *, dataset, task, evaluators, **options):
        self.names.append(options["experiment_name"])
        for example in dataset.examples:
            try:
                output = task(example["metadata"])
            except RuntimeError:
                continue
            self.scores[example["metadata"]["item_id"]] = evaluators["item_pass"](output)


class PhoenixClient:
    def __init__(self):
        self.datasets = PhoenixDatasets()
        self.experiments = PhoenixExperiments()


def test_phoenix_pass_scores_like_the_offline_pass(tmp_path, datasets, scoring, study_json):
    cfg = eval_config(datasets)
    offline = run_pass(
        cfg, Harness(FakeRunner(study_json), scoring, Budget(100.0), tmp_path / "a"), overrides=[]
    )
    client = PhoenixClient()
    harness = Harness(FakeRunner(study_json), scoring, Budget(100.0), tmp_path / "day" / "b")
    online = run_pass(cfg, harness, overrides=[], client=client)
    assert online.items == offline.items
    assert online.levels == offline.levels
    assert client.experiments.names == ["surveyor day b", "zoning day b", "e2e day b"]
    assert len(client.datasets.stored) == 3
    for result in online.items:
        expected = {"score": float(result.passed), "label": "pass" if result.passed else "fail"}
        assert client.experiments.scores[result.item_id] == expected


def test_phoenix_pass_under_budget_skips_refused_items(tmp_path, datasets, scoring, study_json):
    runner = FakeRunner(study_json, cost=0.5)
    harness = Harness(runner, scoring, Budget(0.6), tmp_path / "run")
    scores = run_pass(eval_config(datasets), harness, overrides=[], client=PhoenixClient())
    assert runner.ran == IDS[:2]
    assert scores.info.skipped == (IDS[2],)


def test_phoenix_cannot_hide_scoring_errors(tmp_path, datasets, scoring, study_json, monkeypatch):
    def fail_scoring(*_):
        raise RuntimeError("judge unavailable")

    monkeypatch.setattr("evals.harness.passes.driver.score_record", fail_scoring)
    harness = Harness(FakeRunner(study_json), scoring, Budget(100), tmp_path / "run")
    with pytest.raises(RuntimeError, match="Phoenix evaluations failed without results") as error:
        run_pass(eval_config(datasets), harness, overrides=[], client=PhoenixClient())
    assert all(item_id in str(error.value) for item_id in IDS)
    assert not (tmp_path / "run" / SCORES_FILE).exists()
    assert len(list(harness.records_dir.glob("*.json"))) == len(IDS)
