import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from agent.agents.config import load_config
from agent.llm.factory import load_pricing
from evals.harness import judge as judge_module
from evals.harness.judge import ANTI_PATTERNS, Judge, JudgeAnswer, JudgePrompts, Question
from evals.harness.judging.cache import AnswerCache
from evals.harness.judging.views import ViewSettings

VIEWS = ViewSettings(max_quote_chars=100, crops_link_base="evidence")
PROMPTS = JudgePrompts(
    system="be strict",
    questions={question: f"{question.value}: $subject // $output" for question in Question},
)


class FakeStructured:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def invoke(self, messages, /):
        self.calls.append(messages)
        return self.replies.pop(0)


def make(model, cache=None):
    return Judge(model, model_id="m", prompts=PROMPTS, views=VIEWS, cache=cache)


def test_asks_one_question_with_system_and_filled_template():
    model = FakeStructured({"verdict": "yes", "reason": "it says 7 m"})
    answer = make(model).ask(Question.MUST_NOT, "the output", "states 7 m")
    assert answer == JudgeAnswer(verdict="yes", reason="it says 7 m")
    assert answer.yes
    ((system, human),) = model.calls
    assert isinstance(system, SystemMessage)
    assert system.content == "be strict"
    assert isinstance(human, HumanMessage)
    assert human.content == "must_not: states 7 m // the output"


def test_accepts_a_parsed_answer_with_note_numbers():
    reply = JudgeAnswer(verdict="yes", reason="notes 2 and 3", notes=(2, 3))
    answer = make(FakeStructured(reply)).ask(Question.COVERS, "[1] a", "fact")
    assert answer.notes == (2, 3)


def test_rejects_an_answer_outside_yes_no():
    with pytest.raises(ValidationError):
        make(FakeStructured({"verdict": "maybe", "reason": "r"})).ask(Question.HEDGING, "o")


def test_cache_answers_the_same_question_without_calling_the_model(tmp_path):
    model = FakeStructured(
        {"verdict": "no", "reason": "first"}, {"verdict": "yes", "reason": "second"}
    )
    judge = make(model, AnswerCache(tmp_path))
    first = judge.ask(Question.DEFERRAL, "study")
    assert judge.ask(Question.DEFERRAL, "study") == first
    assert len(model.calls) == 1
    other = judge.ask(Question.DEFERRAL, "another study")
    assert other.reason == "second"
    fresh = make(FakeStructured(), AnswerCache(tmp_path))
    assert fresh.ask(Question.DEFERRAL, "study") == first
    other_model = Judge(
        FakeStructured({"verdict": "yes", "reason": "new model"}),
        model_id="m2",
        prompts=PROMPTS,
        views=VIEWS,
        cache=AnswerCache(tmp_path),
    )
    assert other_model.ask(Question.DEFERRAL, "study").reason == "new model"


def test_every_question_needs_a_template():
    prompts = PROMPTS._replace(questions={Question.MUST_NOT: "$output"})
    with pytest.raises(ValueError, match="must_flag"):
        Judge(FakeStructured(), model_id="m", prompts=prompts, views=VIEWS)


def test_anti_patterns_are_the_six_of_the_spec():
    assert [q.value for q in ANTI_PATTERNS] == [
        "hedging",
        "deferral",
        "invented_rule",
        "restating",
        "inconsistency",
        "unflagged_gap",
    ]


def test_from_config_builds_the_judge_node(monkeypatch, tmp_path):
    cfg = load_config(["+eval=harness", f"eval.judge.cache_dir={tmp_path.as_posix()}"])
    structured = FakeStructured({"verdict": "no", "reason": "none"})

    class FakeModel:
        schema = None
        method = None

        def with_structured_output(self, schema, method):
            FakeModel.schema = schema
            FakeModel.method = method
            return structured

    nodes = []

    def build(models, node, ledger):
        nodes.append(node)
        return FakeModel()

    monkeypatch.setattr(judge_module, "build_model", build)
    judge = Judge.from_config(cfg)
    assert nodes == ["judge"]
    assert FakeModel.schema is JudgeAnswer
    assert FakeModel.method == "json_schema"
    assert judge.views.max_quote_chars == cfg.eval.judge.views.max_quote_chars
    answer = judge.ask(Question.MUST_FLAG, "OUTPUT TEXT", "EXPECTED POINT")
    assert answer.verdict == "no"
    prompt = structured.calls[0][1].content
    assert "EXPECTED POINT" in prompt
    assert "OUTPUT TEXT" in prompt
    assert "$" not in prompt
    assert any(tmp_path.rglob("*.json"))


def test_judge_model_is_priced():
    cfg = load_config()
    assert cfg.models.nodes.judge.model == "claude-opus-5-5"
    price = load_pricing(cfg.models)["claude-opus-5-5"]
    assert (price.input, price.output) == (5.0, 25.0)


@pytest.mark.parametrize("setting", ["max_tokens", "structured_output"])
def test_configured_judge_cache_changes_with_generation_settings(monkeypatch, tmp_path, setting):
    cfg = load_config(["+eval=harness", f"eval.judge.cache_dir={tmp_path.as_posix()}"])
    structured = FakeStructured(
        {"verdict": "no", "reason": "original"},
        {"verdict": "yes", "reason": "changed settings"},
    )

    class FakeModel:
        def with_structured_output(self, schema, method):
            return structured

    monkeypatch.setattr(judge_module, "build_model", lambda *_: FakeModel())
    first = Judge.from_config(cfg).ask(Question.HEDGING, "study")
    assert Judge.from_config(cfg).ask(Question.HEDGING, "study") == first
    assert len(structured.calls) == 1
    if setting == "max_tokens":
        cfg.models.nodes.judge.max_tokens += 1
    else:
        cfg.eval.judge.structured_output = "function_calling"
    assert Judge.from_config(cfg).ask(Question.HEDGING, "study").reason == "changed settings"
    assert len(structured.calls) == 2
