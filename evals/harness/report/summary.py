"""Render ``summary.md``: one table per level, then the failed items."""

from collections.abc import Sequence

from evals.harness.report.aggregate import Failure, LevelReport, Spending
from evals.harness.report.stats import Interval

MISSING = "n/a"
"""Shown for a figure that has nothing to measure."""


def render_summary(
    reports: Sequence[LevelReport], *, title: str, spending: Spending, skipped: Sequence[str]
) -> str:
    """Write the pass summary in Markdown.

    Args:
        reports: One report per level.
        title: Heading of the summary (the run directory).
        spending: What the agent runs and the judge cost.
        skipped: Items not launched because the budget was reached.

    Returns:
        The Markdown text.
    """
    lines = [
        f"# Eval pass {title}",
        "",
        f"Agent runs: ${spending.runs_usd:.2f}; judge: ${spending.judging_usd:.2f}.",
    ]
    if skipped:
        lines.append(f"Not launched (budget reached): {', '.join(skipped)}.")
    for report in reports:
        lines += ["", *_level_table(report), *_failures(report.failures)]
    return "\n".join(lines) + "\n"


def _level_table(report: LevelReport) -> list[str]:
    """The figures of one level as a two-column table."""
    rows = [
        ("Item pass", f"{report.passed}/{report.items}, {_interval(report.pass_rate)}"),
        ("Grounded accuracy", _interval(report.grounded_accuracy)),
        ("Answer accuracy", _interval(report.answer_accuracy)),
        ("Luck rate (answer - grounded)", _number(report.luck_rate)),
        ("Citation validity", _number(report.citation_validity)),
        ("Facts cited on an evidence page", _number(report.facts_cited)),
        ("`must_flag` coverage", _number(report.must_flag_coverage)),
        ("`must_not` hits", str(report.must_not_hits)),
        ("Anti-pattern hits", str(report.anti_pattern_hits)),
        ("Evidence read before submitting", _number(report.read_share)),
        ("Gate rejections", str(report.rejections)),
        ("Tool calls per item", _number(report.tool_calls, digits=1)),
        ("Cost", f"${report.cost_usd:.2f}"),
        ("Wall time per item", _seconds(report.wall_time_s)),
        ("Runs with an error", str(report.errors)),
    ]
    return [
        f"## {report.level} ({report.items} items)",
        "",
        "| Metric | Value |",
        "|---|---|",
        *(f"| {name} | {value} |" for name, value in rows),
    ]


def _failures(failures: Sequence[Failure]) -> list[str]:
    """The failed items with their failing critical facts."""
    if not failures:
        return []
    lines = ["", "Failed items:", ""]
    for failure in failures:
        reasons = [*failure.critical_facts]
        if failure.must_not:
            reasons.append(f"{failure.must_not} `must_not` claim(s) made")
        if failure.error is not None:
            reasons.append(f"run error: {failure.error}")
        lines.append(f"- `{failure.item_id}`: {'; '.join(reasons) or 'no critical fact failed'}")
    return lines


def _interval(interval: Interval | None) -> str:
    """``0.70 [0.40, 0.89]``."""
    if interval is None:
        return MISSING
    return f"{interval.estimate:.2f} [{interval.low:.2f}, {interval.high:.2f}]"


def _number(value: float | None, *, digits: int = 2) -> str:
    """A share or a mean, rounded."""
    return MISSING if value is None else f"{value:.{digits}f}"


def _seconds(value: float | None) -> str:
    """A duration in whole seconds."""
    return MISSING if value is None else f"{value:.0f} s"
