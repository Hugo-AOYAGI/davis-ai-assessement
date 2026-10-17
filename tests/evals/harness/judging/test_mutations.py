import pytest

from agent.agents.config import load_config
from evals.harness.judge import Judge, JudgeAnswer, JudgePrompts, Question
from evals.harness.judging.mutations import BreakKind, BreakSettings, breaks
from evals.harness.judging.validation import break_settings, flags_defect, validate_judge
from evals.harness.judging.views import ViewSettings, study_view

VIEWS = ViewSettings(max_quote_chars=400, crops_link_base="evidence")


@pytest.fixture(scope="module")
def settings() -> BreakSettings:
    return break_settings(load_config(["+eval=harness"]))


@pytest.fixture
def made(study, settings):
    return {item.kind: item for item in breaks(study, settings)}


def test_every_kind_of_break_is_made(made):
    assert set(made) == set(BreakKind)
    assert made[BreakKind.DROPPED_AMBIGUITY].question is Question.MUST_FLAG
    assert made[BreakKind.HEDGE].question is Question.HEDGING
    assert made[BreakKind.CONTRADICTION].question is Question.INCONSISTENCY
    assert made[BreakKind.CHANGED_LIMIT].question is Question.INVENTED_RULE
    assert made[BreakKind.INVENTED_CONDITION].question is Question.INVENTED_RULE


def test_changed_limit_keeps_rule_and_citations(study, made, settings):
    good = study.study.envelope.max_height_m
    bad = made[BreakKind.CHANGED_LIMIT].study.study.envelope.max_height_m
    assert bad.value == good.value + settings.shift
    assert (bad.rule, bad.citations) == (good.rule, good.citations)
    assert made[BreakKind.CHANGED_LIMIT].study.envelope == study.envelope


def test_invented_condition_cites_a_quote_without_it(study, made, settings):
    conditions = made[BreakKind.INVENTED_CONDITION].study.study.conditions
    assert conditions[:-1] == study.study.conditions
    added = conditions[-1]
    assert added.text == settings.invented_rule
    assert added.citations == study.study.regime.citations[:1]
    assert "tuiles" not in added.citations[0].quote
    assert settings.invented_rule not in added.citations[0].quote


def test_hedge_gives_two_values_for_one_limit(study, made):
    good = study.study.envelope.max_height_m
    bad = made[BreakKind.HEDGE].study.study.envelope.max_height_m
    assert bad.value == good.value
    assert bad.rule.startswith(good.rule)
    assert "between 17 and 20 m" in bad.rule


def test_contradiction_only_changes_the_summary(study, made):
    broken = made[BreakKind.CONTRADICTION].study
    assert broken.study.summary.startswith(study.study.summary)
    assert broken.study.summary.endswith("buildings may rise to 23 m.")
    assert broken.study.envelope == study.study.envelope
    assert broken.study.model_copy(update={"summary": study.study.summary}) == study.study


def test_dropped_ambiguity_is_the_subject(study, made):
    dropped = made[BreakKind.DROPPED_AMBIGUITY]
    assert dropped.subject == study.study.ambiguities[0].question
    assert dropped.study.study.ambiguities == study.study.ambiguities[1:]
    assert dropped.subject not in study_view(dropped.study, VIEWS)
    assert dropped.subject in study_view(study, VIEWS)


def test_breaks_render_differently(study, made):
    good = study_view(study, VIEWS)
    views = {kind: study_view(item.study, VIEWS) for kind, item in made.items()}
    assert all(view != good for view in views.values())
    assert len(set(views.values())) == len(views)


def test_limit_without_value_and_no_ambiguity(study, settings):
    envelope = study.study.envelope
    unset = envelope.max_height_m.model_copy(update={"value": None, "citations": ()})
    bare = study.model_copy(
        update={
            "study": study.study.model_copy(
                update={
                    "envelope": envelope.model_copy(update={"max_height_m": unset}),
                    "ambiguities": (),
                }
            )
        }
    )
    assert [item.kind for item in breaks(bare, settings)] == [BreakKind.INVENTED_CONDITION]
    with pytest.raises(ValueError, match="not a limit"):
        breaks(study, settings.model_copy(update={"limit": "summary"}))


class KnowingModel:
    """Answers from the text: flags hedges, contradictions and dropped ambiguities only."""

    def __init__(self, ambiguity, settings):
        self.ambiguity = ambiguity
        self.settings = settings

    def invoke(self, messages, /):
        question, prompt = messages[1].content.split("|", 1)
        flags = {
            "must_flag": self.ambiguity in prompt.split("@@", 1)[1],
            "hedging": "between 17 and 20 m" in prompt,
            "inconsistency": "rise to 23 m" in prompt,
        }
        return {"verdict": "yes" if flags.get(question, False) else "no", "reason": "r"}


def test_validation_reports_catch_and_false_alarm_rates(study, settings):
    ambiguity = study.study.ambiguities[0].question
    prompts = JudgePrompts(
        system="s", questions={q: f"{q.value}|$subject@@$output" for q in Question}
    )
    judge = Judge(KnowingModel(ambiguity, settings), model_id="m", prompts=prompts, views=VIEWS)
    result = validate_judge(judge, [study], settings)
    rates = {rate.kind: rate for rate in result.kinds}
    assert set(rates) == set(BreakKind)
    for kind in (BreakKind.HEDGE, BreakKind.CONTRADICTION, BreakKind.DROPPED_AMBIGUITY):
        assert (rates[kind].caught, rates[kind].catch_rate, rates[kind].false_alarms) == (1, 1, 0)
    assert rates[BreakKind.INVENTED_CONDITION].caught == 0
    assert rates[BreakKind.CHANGED_LIMIT].catch_rate == 0
    assert result.good_answers == len(BreakKind)
    assert result.good_yes == 1
    assert result.yes_rate_good == pytest.approx(1 / len(BreakKind))


def test_flags_defect():
    yes = {"verdict": "yes", "reason": "r"}
    no = {"verdict": "no", "reason": "r"}
    assert flags_defect(Question.HEDGING, JudgeAnswer.model_validate(yes))
    assert not flags_defect(Question.HEDGING, JudgeAnswer.model_validate(no))
    assert flags_defect(Question.MUST_FLAG, JudgeAnswer.model_validate(no))
