"""Hydra CLI: run the orchestrator on the configured case and write its outputs.

Usage: ``uv run python -m agent.entrypoints.run [hydra overrides...]``, e.g.
``case=reference models.nodes.orchestrator.max_tokens=8000``. Outputs land in the Hydra run dir
(``outputs/<date>/<time>``): ``verified_study.json``, ``report.md``, ``run_summary.json`` and
``final_message.md``, the evidence crops linked by the report in ``evidence/``, plus the agent's
log lines in ``agent.log``.
"""

import shutil
import time
from collections.abc import Sequence
from pathlib import Path

import hydra
from dotenv import load_dotenv
from hydra.core.hydra_config import HydraConfig
from langchain_core.callbacks import BaseCallbackHandler, UsageMetadataCallbackHandler
from langchain_core.messages import BaseMessage, HumanMessage
from omegaconf import DictConfig, OmegaConf, open_dict

from agent.agents.config import PROJECT_ROOT, read_prompt
from agent.agents.orchestrator import build
from agent.agents.request import case_request
from agent.contracts.inputs.case import Case
from agent.contracts.study import VerifiedStudy
from agent.entrypoints.summary import (
    RunMetrics,
    RunSummary,
    final_text,
    rejected_submissions,
    run_summary,
)
from agent.llm.costs import CostLedger
from agent.llm.factory import load_pricing
from agent.llm.usage import price_usage
from agent.observability.logs import get_logger, log_to_file, setup_logging
from agent.observability.tracing import setup_tracing
from agent.runtime.report.render import render_report
from agent.tools.submit.artifacts import read_artifact

# Run as ``python -m``, ``__name__`` is ``__main__``, outside the ``agent`` hierarchy.
logger = get_logger("agent.entrypoints.run")

_CONFIG_DIR = str(PROJECT_ROOT / "conf")
_CONFIG_NAME = "config"
_HYDRA_VERSION_BASE = "1.3"
_STUDY_ARTIFACT = "study"
_EVIDENCE_DIR = "evidence"
_UNATTENDED_ASK_USER = "disabled"


def make_unattended(cfg: DictConfig) -> None:
    """Disable ``ask_user``: nobody answers during a CLI run, facts come with the request.

    Args:
        cfg: The composed config, modified in place.
    """
    previous = cfg.policies.ask_user.mode
    if previous == _UNATTENDED_ASK_USER:
        return
    with open_dict(cfg):
        cfg.policies.ask_user.mode = _UNATTENDED_ASK_USER
    logger.info("ask_user mode %r -> %r for an unattended run", previous, _UNATTENDED_ASK_USER)


def run_study(
    cfg: DictConfig,
    case: Case,
    overrides: list[str],
    callbacks: Sequence[BaseCallbackHandler] = (),
) -> tuple[RunMetrics, list[BaseMessage], VerifiedStudy | None]:
    """Run the orchestrator on one case.

    Args:
        cfg: The composed config.
        case: What to study.
        overrides: Hydra overrides of the run, recorded as trace metadata.
        callbacks: Extra callback handlers of the run; they also reach every sub-agent run
            (evals capture the sub-agents' messages this way).

    Returns:
        The run's metrics, the orchestrator's messages and the accepted study, if any.
    """
    ledger = CostLedger(load_pricing(cfg.models))
    graph = build(cfg, ledger)
    message = case_request(case, read_prompt(cfg.agent.request), no_facts=cfg.agent.no_facts)
    usage_handler = UsageMetadataCallbackHandler()
    start = time.perf_counter()
    state = graph.invoke(
        {"messages": [HumanMessage(message)]},
        config={
            "recursion_limit": cfg.agent.recursion_limit,
            "callbacks": [usage_handler, *callbacks],
            "run_name": "study",
            "metadata": {
                "address": case.address,
                "corpus_id": case.corpus_id,
                "overrides": overrides,
            },
        },
    )
    wall_time_s = time.perf_counter() - start
    messages: list[BaseMessage] = [
        item for item in state["messages"] if isinstance(item, BaseMessage)
    ]
    usage = price_usage(cfg.models, usage_handler.usage_metadata)
    metrics = RunMetrics(
        address=case.address,
        overrides=tuple(overrides),
        wall_time_s=wall_time_s,
        usage=usage,
        usage_by_node=ledger.usage(),
        total_tokens=sum(meta["total_tokens"] for meta in usage_handler.usage_metadata.values()),
        cost_usd=sum(entry.cost_usd for entry in usage.values()),
        rejected_submissions=rejected_submissions(messages, f"submit_{_STUDY_ARTIFACT}"),
    )
    verified = read_artifact(state.get("artifacts"), _STUDY_ARTIFACT, VerifiedStudy)
    return metrics, messages, verified


def copy_evidence(verified: VerifiedStudy, root: Path, target: Path) -> None:
    """Copy the study's evidence crops next to the report, keeping their file names.

    A crop file that no longer exists is skipped with a warning; its link stays in the report.

    Args:
        verified: The accepted study.
        root: Directory the crop paths are relative to (the project root).
        target: Directory the crops are copied into.
    """
    for crop in verified.evidence:
        source = root / crop.path
        if not source.is_file():
            logger.warning("evidence crop %s is missing, not copied", source)
            continue
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target / source.name)


def write_outputs(
    run_dir: Path,
    summary: RunSummary,
    verified: VerifiedStudy | None,
    *,
    max_quote_chars: int,
    root: Path,
) -> None:
    """Write the summary and, when a study was accepted, the study, its report and its crops.

    Args:
        run_dir: Hydra run directory.
        summary: The run summary.
        verified: The accepted study, if any.
        max_quote_chars: Quote truncation length in the report's citations table.
        root: Directory the crop paths are relative to (the project root).
    """
    (run_dir / "run_summary.json").write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    if verified is None:
        return
    (run_dir / "verified_study.json").write_text(
        verified.model_dump_json(indent=2), encoding="utf-8"
    )
    copy_evidence(verified, root, run_dir / _EVIDENCE_DIR)
    report = render_report(verified, max_quote_chars=max_quote_chars, crops_link_base=_EVIDENCE_DIR)
    (run_dir / "report.md").write_text(report, encoding="utf-8")


def main(cfg: DictConfig) -> None:
    """Run the study for the configured case and write its outputs to the Hydra run dir.

    Args:
        cfg: The config composed by Hydra.

    Raises:
        SystemExit: With code 1 when no study was accepted (outputs are still written).
    """
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    setup_logging(cfg.policies.logging.level)
    tracing = cfg.policies.tracing
    setup_tracing(
        enabled=tracing.enabled,
        project=tracing.project,
        endpoint=tracing.endpoint,
        hide_images=tracing.hide_images,
        base64_max_chars=tracing.base64_max_chars,
    )
    make_unattended(cfg)
    hydra_cfg = HydraConfig.get()
    run_dir = Path(hydra_cfg.runtime.output_dir)
    log_to_file(run_dir / "agent.log")
    overrides = list(hydra_cfg.overrides.task)
    case = Case.model_validate(OmegaConf.to_container(cfg.case, resolve=True))
    metrics, messages, verified = run_study(cfg, case, overrides)
    summary = run_summary(metrics, verified)
    (run_dir / "final_message.md").write_text(final_text(messages), encoding="utf-8")
    write_outputs(
        run_dir,
        summary,
        verified,
        max_quote_chars=cfg.policies.report.max_quote_chars,
        root=PROJECT_ROOT,
    )
    logger.info(
        "run done: accepted=%s cost=$%.4f wall=%.0fs rejected=%d dir=%s",
        summary.accepted,
        metrics.cost_usd,
        metrics.wall_time_s,
        metrics.rejected_submissions,
        run_dir,
    )
    if not summary.accepted:
        raise SystemExit(1)


if __name__ == "__main__":
    cli = hydra.main(
        version_base=_HYDRA_VERSION_BASE, config_path=_CONFIG_DIR, config_name=_CONFIG_NAME
    )
    cli(main)()
