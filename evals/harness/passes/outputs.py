"""The files of a pass: ``records/<item_id>.json``, ``scores.json`` and ``summary.md``."""

from collections.abc import Sequence
from pathlib import Path

from agent.contracts.base import Contract
from evals.harness.passes.scoring import ItemResult
from evals.harness.report.aggregate import LevelReport, Spending, Statistics, report_levels
from evals.harness.report.summary import render_summary
from evals.harness.runs.record import RunRecord

RECORDS_DIR = "records"
SCORES_FILE = "scores.json"
SUMMARY_FILE = "summary.md"


class PassInfo(Contract):
    """How a pass was run."""

    overrides: tuple[str, ...]
    """Hydra overrides of the pass."""
    spending: Spending
    skipped: tuple[str, ...] = ()
    """Items not launched because the budget was reached."""
    rescored_from: str | None = None
    """Run directory whose records were scored again, for a re-scoring pass."""


class PassScores(Contract):
    """Content of ``scores.json``: the level figures and every item's scores."""

    run_dir: str
    info: PassInfo
    levels: tuple[LevelReport, ...]
    items: tuple[ItemResult, ...]


def write_record(records_dir: Path, record: RunRecord) -> Path:
    """Save one run record.

    Args:
        records_dir: ``<run dir>/records``.
        record: The run.

    Returns:
        The file written.
    """
    records_dir.mkdir(parents=True, exist_ok=True)
    path = records_dir / f"{record.item_id}.json"
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return path


def read_records(records_dir: Path) -> list[RunRecord]:
    """Read the run records of a pass.

    Args:
        records_dir: ``<run dir>/records``.

    Returns:
        The records, sorted by file name.

    Raises:
        FileNotFoundError: When the directory does not exist.
    """
    if not records_dir.is_dir():
        msg = f"no run records in {records_dir}"
        raise FileNotFoundError(msg)
    return [
        RunRecord.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(records_dir.glob("*.json"))
    ]


def write_pass(
    run_dir: Path, results: Sequence[ItemResult], stats: Statistics, info: PassInfo
) -> PassScores:
    """Aggregate a pass and write ``scores.json`` and ``summary.md``.

    Args:
        run_dir: The pass's directory.
        results: The item results.
        stats: Interval settings.
        info: How the pass was run.

    Returns:
        What was written to ``scores.json``.
    """
    levels = report_levels(results, stats)
    scores = PassScores(run_dir=run_dir.as_posix(), info=info, levels=levels, items=tuple(results))
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / SCORES_FILE).write_text(scores.model_dump_json(indent=2), encoding="utf-8")
    summary = render_summary(
        levels, title=run_dir.name, spending=info.spending, skipped=info.skipped
    )
    (run_dir / SUMMARY_FILE).write_text(summary, encoding="utf-8")
    return scores
