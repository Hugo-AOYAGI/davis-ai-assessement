"""The envelope scored twice (``docs/EVALS.md`` §4), against the expected values and recomputed.

The recomputation uses the agent's own site and parameters, which tells a wrong rule from a wrong
calculation.
"""

from collections.abc import Sequence
from enum import StrEnum

from agent.contracts.base import Contract
from agent.contracts.geometry import Envelope
from agent.contracts.study import VerifiedStudy
from agent.runtime.geometry.envelope import compute_envelope
from evals.harness.items import Fact, KeyFact, Value
from evals.harness.matching.values import normalise, same

ENVELOPE_PREFIX = "envelope."
"""Key prefix of the envelope figures in a ``VerifiedStudy``."""

FIGURES = (
    "site_area_m2",
    "footprint_area_m2",
    "max_footprint_area_m2",
    "min_green_area_m2",
    "max_height_m",
    "max_volume_m3",
)
"""The numeric fields of ``Envelope`` that are compared."""


class Diagnosis(StrEnum):
    """Where an envelope goes wrong, if it does."""

    CORRECT = "correct"
    """Matches the expected figures, and its own recomputation."""
    WRONG_RULE = "wrong_rule"
    """Correctly computed from parameters (or a site) that differ from the expected ones."""
    WRONG_CALCULATION = "wrong_calculation"
    """Differs from the envelope its own parameters give."""
    UNCHECKED = "unchecked"
    """Consistent with its parameters; the item expects no envelope figure."""


class FigureCheck(Contract):
    """One envelope figure compared with a reference."""

    figure: str
    expected: float | None
    actual: float | None
    ok: bool


class EnvelopeScore(Contract):
    """The envelope compared with the item and with its own recomputation."""

    against_expected: tuple[FigureCheck, ...]
    """One check per ``envelope.<figure>`` fact of the item with an ``expect``."""
    against_recomputed: tuple[FigureCheck, ...]
    """Every figure of ``FIGURES``, reported vs recomputed."""
    recomputed: Envelope
    diagnosis: Diagnosis


def expected_figures(facts: Sequence[Fact]) -> tuple[KeyFact, ...]:
    """Select the facts that expect an envelope figure.

    Args:
        facts: An end-to-end item's facts.

    Returns:
        The ``envelope.<figure>`` key facts with an ``expect``, ``<figure>`` in ``FIGURES``.
    """
    return tuple(
        fact
        for fact in facts
        if isinstance(fact, KeyFact)
        and "expect" in fact.model_fields_set
        and fact.key.removeprefix(ENVELOPE_PREFIX) in FIGURES
        and fact.key.startswith(ENVELOPE_PREFIX)
    )


def score_envelope(
    output: VerifiedStudy,
    expected: Sequence[KeyFact],
    *,
    tolerance: float,
    quad_segs: int,
    min_area_m2: float,
) -> EnvelopeScore:
    """Score the envelope of an accepted study.

    Args:
        output: The accepted study.
        expected: Facts expecting envelope figures, from ``expected_figures``; each is
            compared with its own ``tolerance`` (exact when unset).
        tolerance: Relative tolerance between the reported and the recomputed figures.
        quad_segs: ``policies.envelope.quad_segs``, as used by the gate.
        min_area_m2: ``policies.envelope.min_area_m2``, as used by the gate.

    Returns:
        Both comparisons, the recomputed envelope and the diagnosis.
    """
    reported = output.envelope
    recomputed = compute_envelope(
        output.site.polygon,
        output.boundaries,
        output.study.envelope,
        quad_segs=quad_segs,
        min_area_m2=min_area_m2,
    )
    against_expected = tuple(
        _compare(fact.key.removeprefix(ENVELOPE_PREFIX), reported, fact.expect, fact.tolerance)
        for fact in expected
    )
    against_recomputed = tuple(
        _compare(figure, reported, getattr(recomputed, figure), tolerance) for figure in FIGURES
    )
    return EnvelopeScore(
        against_expected=against_expected,
        against_recomputed=against_recomputed,
        recomputed=recomputed,
        diagnosis=_diagnose(against_expected, against_recomputed),
    )


def _compare(
    figure: str, reported: Envelope, expected: Value, tolerance: float | None
) -> FigureCheck:
    """Compare one reported figure with a reference value; ``None`` only matches ``None``."""
    actual = getattr(reported, figure)
    reference = normalise(expected)
    ok = same(normalise(actual), reference, tolerance)
    number = reference if isinstance(reference, float) else None
    return FigureCheck(figure=figure, expected=number, actual=actual, ok=ok)


def _diagnose(
    against_expected: Sequence[FigureCheck], against_recomputed: Sequence[FigureCheck]
) -> Diagnosis:
    """Tell a wrong calculation (inconsistent with its parameters) from a wrong rule."""
    if not all(check.ok for check in against_recomputed):
        return Diagnosis.WRONG_CALCULATION
    if not against_expected:
        return Diagnosis.UNCHECKED
    if all(check.ok for check in against_expected):
        return Diagnosis.CORRECT
    return Diagnosis.WRONG_RULE
