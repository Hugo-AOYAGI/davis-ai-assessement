"""Deliberately broken studies, made in code from a good one, to validate the judge (EVALS §4).

Each break is paired with the question that should catch it: the judge catches it when its
answer on the broken study flags the defect.
"""

from enum import StrEnum
from typing import NamedTuple

from agent.contracts.base import Contract
from agent.contracts.envelope import EnvelopeRules
from agent.contracts.evidence import Limit, Rule
from agent.contracts.study import VerifiedStudy
from evals.harness.judge import Question


class BreakKind(StrEnum):
    """How a good study is broken."""

    CHANGED_LIMIT = "changed_limit"
    """A limit's value no longer matches its citations."""
    INVENTED_CONDITION = "invented_condition"
    """A condition none of its citations contains."""
    HEDGE = "hedge"
    """A limit's rule hedges between two values."""
    CONTRADICTION = "contradiction"
    """The summary contradicts a typed limit."""
    DROPPED_AMBIGUITY = "dropped_ambiguity"
    """A recorded ambiguity is gone."""


class BreakSettings(Contract):
    """What the breaks change (``eval.judge.validation``)."""

    limit: str
    """Numeric envelope rule changed, hedged and contradicted; it needs a value."""
    shift: float
    """Added to the limit's value (changed, contradicted) or taken off it (hedge's low end)."""
    hedge: str
    """Sentence appended to the limit's rule, formatted with ``low`` and ``high``."""
    contradiction: str
    """Text appended to the summary, formatted with ``value``."""
    invented_topic: str
    invented_rule: str
    """Text of the invented condition, cited with the regime's first citation."""


class Break(NamedTuple):
    """A broken study and the question that should catch it."""

    kind: BreakKind
    question: Question
    subject: str
    """Asked with the question: the dropped ambiguity's question; empty otherwise."""
    study: VerifiedStudy


def breaks(good: VerifiedStudy, settings: BreakSettings) -> tuple[Break, ...]:
    """Make every break that applies to a good study.

    The limit breaks need the limit to have a value; the dropped ambiguity needs one.

    Args:
        good: An accepted study believed correct.
        settings: What the breaks change.

    Returns:
        The broken studies, one per kind that applies.

    Raises:
        ValueError: If ``settings.limit`` is not a limit of ``EnvelopeRules or BuildingLimits``.
    """
    limit = _limit(good, settings.limit)
    made = [
        Break(
            BreakKind.INVENTED_CONDITION,
            Question.INVENTED_RULE,
            "",
            invented_condition(good, settings),
        )
    ]
    if limit.value is not None:
        made += [
            Break(
                BreakKind.CHANGED_LIMIT, Question.INVENTED_RULE, "", changed_limit(good, settings)
            ),
            Break(BreakKind.HEDGE, Question.HEDGING, "", hedged_limit(good, settings)),
            Break(
                BreakKind.CONTRADICTION,
                Question.INCONSISTENCY,
                "",
                contradicting_summary(good, settings),
            ),
        ]
    if good.study.ambiguities:
        dropped = good.study.ambiguities[0].question
        made.append(
            Break(BreakKind.DROPPED_AMBIGUITY, Question.MUST_FLAG, dropped, dropped_ambiguity(good))
        )
    return tuple(made)


def changed_limit(good: VerifiedStudy, settings: BreakSettings) -> VerifiedStudy:
    """Shift a limit's value, keeping its rule and citations.

    Args:
        good: The good study.
        settings: The limit and the shift.

    Returns:
        The broken study.
    """
    limit = _limit(good, settings.limit)
    return _with_limit(
        good, settings.limit, limit.model_copy(update={"value": _value(limit) + settings.shift})
    )


def hedged_limit(good: VerifiedStudy, settings: BreakSettings) -> VerifiedStudy:
    """Append a hedge between ``value - shift`` and ``value`` to a limit's rule.

    Args:
        good: The good study.
        settings: The limit, the shift and the hedge sentence.

    Returns:
        The broken study.
    """
    limit = _limit(good, settings.limit)
    high = _value(limit)
    hedge = settings.hedge.format(low=high - settings.shift, high=high)
    return _with_limit(
        good, settings.limit, limit.model_copy(update={"rule": f"{limit.rule} {hedge}"})
    )


def contradicting_summary(good: VerifiedStudy, settings: BreakSettings) -> VerifiedStudy:
    """Append to the summary a value of the limit that differs from the typed one.

    Args:
        good: The good study.
        settings: The limit, the shift and the contradicting sentence.

    Returns:
        The broken study.
    """
    value = _value(_limit(good, settings.limit)) + settings.shift
    summary = good.study.summary + settings.contradiction.format(value=value)
    return _with_study(good, summary=summary)


def invented_condition(good: VerifiedStudy, settings: BreakSettings) -> VerifiedStudy:
    """Add a condition whose citation (the regime's first) does not contain it.

    Args:
        good: The good study.
        settings: The invented condition's topic and text.

    Returns:
        The broken study.
    """
    rule = Rule(
        topic=settings.invented_topic,
        text=settings.invented_rule,
        citations=good.study.regime.citations[:1],
    )
    return _with_study(good, conditions=(*good.study.conditions, rule))


def dropped_ambiguity(good: VerifiedStudy) -> VerifiedStudy:
    """Drop the first recorded ambiguity.

    Args:
        good: The good study.

    Returns:
        The broken study.
    """
    return _with_study(good, ambiguities=good.study.ambiguities[1:])


def _limit(good: VerifiedStudy, name: str) -> Limit:
    """Read one limit of the study's envelope parameters."""
    if name in ("max_height_m", "max_storeys"):
        limit = getattr(good.envelope.rules.buildings[0], name)
    elif name in EnvelopeRules.model_fields:
        limit = getattr(good.envelope.rules, name)
    else:
        msg = f"{name!r} is not a limit of EnvelopeRules or BuildingLimits"
        raise ValueError(msg)
    if not isinstance(limit, Limit):
        msg = f"{name!r} is not a numeric limit"
        raise TypeError(msg)
    return limit


def _value(limit: Limit) -> float:
    """A limit's value; only called on limits that have one."""
    if limit.value is None:
        msg = "this break needs a limit with a value"
        raise ValueError(msg)
    return limit.value


def _with_limit(good: VerifiedStudy, name: str, limit: Limit) -> VerifiedStudy:
    """Replace one limit of the study's envelope parameters."""
    rules = good.envelope.rules
    if name in ("max_height_m", "max_storeys"):
        first, *rest = rules.buildings
        rules = rules.model_copy(
            update={"buildings": (first.model_copy(update={name: limit}), *rest)}
        )
    else:
        rules = rules.model_copy(update={name: limit})
    envelope = good.envelope.model_copy(update={"rules": rules})
    return good.model_copy(update={"envelope": envelope})


def _with_study(good: VerifiedStudy, **changes: object) -> VerifiedStudy:
    """Replace fields of the study inside a verified study."""
    return good.model_copy(update={"study": good.study.model_copy(update=changes)})
