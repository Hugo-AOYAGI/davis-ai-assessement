"""Hydra entrypoint of the eval harness (``evals/README.md``§7).

Usage: ``uv run python -m evals.run [overrides...]``, e.g. ``eval.dataset=surveyor``,
``eval.items=[s01_joliot_curie]``, ``eval.phoenix.enabled=false``, or any agent knob such as
``models.nodes.orchestrator.max_tokens=8000``. ``eval.rescore=<run dir>`` scores the saved
records of that pass again without running any agent. Each pass writes ``records/<item_id>.json``,
``scores.json`` and ``summary.md`` to its Hydra run dir, ``outputs/evals/<date>/<time>/``.
"""

from collections.abc import Sequence
from functools import partial
from pathlib import Path

import hydra
from dotenv import load_dotenv
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig

from agent.agents.config import PROJECT_ROOT, project_path
from agent.llm.costs import CostLedger
from agent.llm.factory import load_pricing
from agent.observability.logs import get_logger, log_to_file, setup_logging
from agent.observability.tracing import setup_tracing
from evals.harness.judge import Judge
from evals.harness.passes import phoenix
from evals.harness.passes.driver import Budget, Harness, evaluate, rescore, run_offline
from evals.harness.passes.outputs import RECORDS_DIR, PassInfo, PassScores, write_pass
from evals.harness.passes.scoring import Scoring
from evals.harness.passes.setup import build_scoring, ledger_total, select_items, statistics
from evals.harness.report.aggregate import Spending
from evals.harness.tasks import run_item

logger = get_logger("evals.run")

_CONFIG_DIR = str(PROJECT_ROOT / "conf")
_CONFIG_NAME = "eval"
_HYDRA_VERSION_BASE = "1.3"


def run_pass(
    cfg: DictConfig,
    harness: Harness,
    *,
    overrides: Sequence[str],
    client: phoenix.PhoenixApi | None = None,
) -> PassScores:
    """Run and score the selected items, then write the pass's files.

    Args:
        cfg: The composed eval config.
        harness: Runner, scoring, budget (``eval.max_cost_usd``) and run directory.
        overrides: Hydra overrides of the pass, recorded in ``scores.json``.
        client: A Phoenix client to run each level as an experiment; ``None`` runs offline.

    Returns:
        What was written to ``scores.json``.
    """
    items = select_items(cfg)
    evaluate_item = partial(evaluate, harness)
    run_dir = harness.run_dir
    if client is None:
        results = run_offline(items, evaluate_item, concurrency=cfg.eval.concurrency)
    else:
        settings = phoenix.ExperimentSettings(
            name=f"{run_dir.parent.name} {run_dir.name}",
            metadata={"overrides": list(overrides), "run_dir": run_dir.as_posix()},
            timeout_s=cfg.eval.phoenix.timeout_s,
            retries=cfg.eval.phoenix.retries,
        )
        results = phoenix.run_levels(client, items, evaluate_item, settings)
    done = {result.item_id for result in results}
    budget = harness.budget
    info = PassInfo(
        overrides=tuple(overrides),
        spending=Spending(runs_usd=budget.runs_usd, judging_usd=budget.judging_usd),
        skipped=tuple(item.id for item in items if item.id not in done),
    )
    return write_pass(run_dir, results, statistics(cfg), info)


def rescore_pass(
    cfg: DictConfig, run_dir: Path, *, scoring: Scoring, budget: Budget, overrides: Sequence[str]
) -> PassScores:
    """Score the records of ``eval.rescore`` against the current items and scorers.

    Args:
        cfg: The composed eval config.
        run_dir: Directory of this re-scoring pass.
        scoring: Scoring dependencies.
        budget: Reads the judge's spending; no agent runs.
        overrides: Hydra overrides, recorded in ``scores.json``.

    Returns:
        What was written to ``scores.json``.
    """
    source = project_path(cfg.eval.rescore)
    results = rescore(select_items(cfg), source / RECORDS_DIR, scoring)
    info = PassInfo(
        overrides=tuple(overrides),
        spending=Spending(
            runs_usd=sum(result.run.cost_usd or 0.0 for result in results),
            judging_usd=budget.judging_usd,
        ),
        rescored_from=source.as_posix(),
    )
    return write_pass(run_dir, results, statistics(cfg), info)


def main(cfg: DictConfig) -> None:
    """Run or re-score an eval pass and write its files to the Hydra run dir.

    Args:
        cfg: The config composed by Hydra from ``conf/eval.yaml``.
    """
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    select_items(cfg)
    setup_logging(cfg.policies.logging.level)
    tracing = cfg.policies.tracing
    setup_tracing(
        enabled=tracing.enabled,
        project=tracing.project,
        endpoint=tracing.endpoint,
        hide_images=tracing.hide_images,
        base64_max_chars=tracing.base64_max_chars,
    )
    hydra_cfg = HydraConfig.get()
    run_dir = Path(hydra_cfg.runtime.output_dir)
    log_to_file(run_dir / "eval.log")
    overrides = list(hydra_cfg.overrides.task)
    ledger = CostLedger(load_pricing(cfg.models))
    scoring = build_scoring(cfg, Judge.from_config(cfg, ledger))
    budget = Budget(cfg.eval.max_cost_usd, judging=partial(ledger_total, ledger))
    if cfg.eval.rescore:
        scores = rescore_pass(cfg, run_dir, scoring=scoring, budget=budget, overrides=overrides)
    else:
        client = phoenix.connect(cfg.eval.phoenix.base_url) if cfg.eval.phoenix.enabled else None
        harness = Harness(partial(run_item, cfg), scoring, budget, run_dir)
        scores = run_pass(cfg, harness, overrides=overrides, client=client)
    for level in scores.levels:
        logger.info("%s: %d/%d items passed", level.level, level.passed, level.items)
    logger.info("pass done: $%.4f spent, files in %s", budget.spent_usd, run_dir)


if __name__ == "__main__":
    cli = hydra.main(
        version_base=_HYDRA_VERSION_BASE, config_path=_CONFIG_DIR, config_name=_CONFIG_NAME
    )
    cli(main)()
