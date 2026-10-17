"""Validate the judge on deliberately broken studies (``docs/EVALS.md`` §4).

For each good study, every break is judged twice with the question meant to catch it: on the
good study and on the broken one. A defect is flagged by ``yes`` for an anti-pattern and by
``no`` for ``must_flag`` (the dropped ambiguity is no longer raised).
"""

from collections.abc import Sequence
from typing import NamedTuple

from omegaconf import DictConfig, OmegaConf

from agent.contracts.base import Contract
from agent.contracts.study import VerifiedStudy
from evals.harness.judge import Judge, JudgeAnswer, Question
from evals.harness.judging.mutations import BreakKind, BreakSettings, breaks
from evals.harness.judging.views import study_view


class KindRate(Contract):
    """How the judge does on one kind of break."""

    kind: BreakKind
    question: Question
    broken: int
    """Broken studies judged."""
    caught: int
    """Broken studies on which the judge flagged the defect."""
    catch_rate: float
    good: int
    """Good studies judged with the same question."""
    false_alarms: int
    """Good studies on which the judge flagged the defect."""
    false_alarm_rate: float


class JudgeValidation(Contract):
    """The judge's catch rates on broken studies and its answers on good ones."""

    kinds: tuple[KindRate, ...]
    good_answers: int
    """Questions answered on good studies (one per break made)."""
    good_yes: int
    yes_rate_good: float | None
    """Share of ``yes`` among the answers on good studies."""


class _Trial(NamedTuple):
    """One break judged on its good and broken studies."""

    kind: BreakKind
    question: Question
    on_good: JudgeAnswer
    on_broken: JudgeAnswer


def break_settings(cfg: DictConfig) -> BreakSettings:
    """Read the break settings from ``eval.judge.validation``.

    Args:
        cfg: The composed config, with the ``eval`` group.

    Returns:
        The settings.
    """
    return BreakSettings.model_validate(
        OmegaConf.to_container(cfg.eval.judge.validation, resolve=True)
    )


def flags_defect(question: Question, answer: JudgeAnswer) -> bool:
    """Tell whether an answer flags a defect.

    Args:
        question: The question asked.
        answer: The judge's answer.

    Returns:
        ``no`` for ``must_flag`` (the point is not raised), ``yes`` for the other questions.
    """
    return not answer.yes if question is Question.MUST_FLAG else answer.yes


def validate_judge(
    judge: Judge, goods: Sequence[VerifiedStudy], settings: BreakSettings
) -> JudgeValidation:
    """Judge every break of every good study, and its good study, with the same question.

    Args:
        judge: The judge under validation.
        goods: Accepted studies believed correct.
        settings: What the breaks change.

    Returns:
        Catch and false-alarm rates per kind of break, and the yes-rate on good studies.
    """
    trials: list[_Trial] = []
    for good in goods:
        good_view = study_view(good, judge.views)
        for made in breaks(good, settings):
            broken_view = study_view(made.study, judge.views)
            trials.append(
                _Trial(
                    made.kind,
                    made.question,
                    judge.ask(made.question, good_view, made.subject),
                    judge.ask(made.question, broken_view, made.subject),
                )
            )
    yes = sum(trial.on_good.yes for trial in trials)
    return JudgeValidation(
        kinds=tuple(_rate(kind, trials) for kind in BreakKind if _of(kind, trials)),
        good_answers=len(trials),
        good_yes=yes,
        yes_rate_good=yes / len(trials) if trials else None,
    )


def _of(kind: BreakKind, trials: Sequence[_Trial]) -> list[_Trial]:
    """The trials of one kind of break."""
    return [trial for trial in trials if trial.kind is kind]


def _rate(kind: BreakKind, trials: Sequence[_Trial]) -> KindRate:
    """Aggregate the trials of one kind of break."""
    found = _of(kind, trials)
    question = found[0].question
    caught = sum(flags_defect(question, trial.on_broken) for trial in found)
    alarms = sum(flags_defect(question, trial.on_good) for trial in found)
    return KindRate(
        kind=kind,
        question=question,
        broken=len(found),
        caught=caught,
        catch_rate=caught / len(found),
        good=len(found),
        false_alarms=alarms,
        false_alarm_rate=alarms / len(found),
    )
