"""Build what a pass needs from the composed config: its items, scoring and statistics."""

from omegaconf import DictConfig

from agent.adapters.corpus.store import load_corpus
from agent.agents.config import project_path
from agent.llm.costs import CostLedger
from agent.tools.study.checks import corpus_facts
from agent.tools.study.messages import Verification
from evals.harness.items import Item, Level, Status, load_items
from evals.harness.judge import Judge
from evals.harness.matching.grounding import CitationMatcher
from evals.harness.passes.scoring import EnvelopeSettings, Scoring
from evals.harness.report.aggregate import Statistics

ALL_LEVELS = "all"
"""``eval.dataset`` value selecting every level."""


def select_items(cfg: DictConfig) -> list[Item]:
    """Load the items of ``eval.dataset``, filtered by ``eval.statuses`` and ``eval.items``.

    Args:
        cfg: The composed eval config.

    Returns:
        The items, level by level, each level sorted by file name.

    Raises:
        ValueError: When the selected dataset is missing or empty, or ``eval.items`` names
            an item that is not in the selection.
    """
    dataset = cfg.eval.dataset
    levels = list(Level) if dataset == ALL_LEVELS else [Level(dataset)]
    root = project_path(cfg.eval.datasets_dir)
    if dataset != ALL_LEVELS and not (root / levels[0]).is_dir():
        msg = f"eval dataset does not exist: {root / levels[0]}"
        raise ValueError(msg)
    statuses = [Status(status) for status in cfg.eval.statuses]
    items = [
        item
        for level in levels
        if (root / level).is_dir()
        for item in load_items(root / level, statuses=statuses)
    ]
    if not items:
        msg = f"no eval items match dataset={dataset!r} and statuses={list(cfg.eval.statuses)!r}"
        raise ValueError(msg)
    wanted = list(cfg.eval["items"] or [])  # `cfg.eval.items` is the DictConfig method
    if not wanted:
        return items
    unknown = sorted(set(wanted) - {item.id for item in items})
    if unknown:
        msg = f"eval.items not in the selection: {', '.join(unknown)}"
        raise ValueError(msg)
    return [item for item in items if item.id in wanted]


def build_scoring(cfg: DictConfig, judge: Judge) -> Scoring:
    """Build the citation matcher on the ingested corpus and gather the scoring settings.

    Args:
        cfg: The composed eval config.
        judge: The yes/no judge.

    Returns:
        The scoring dependencies.
    """
    corpus = load_corpus(project_path(cfg.corpus.dir))
    policy = cfg.policies.citations
    verification = Verification(policy.min_score, policy.neighbour_pages, policy.max_quote_chars)
    tolerances = cfg.eval.tolerances
    return Scoring(
        matcher=CitationMatcher(
            corpus_facts(corpus), verification, check_raster=policy.check_raster
        ),
        judge=judge,
        sections=tuple(corpus.sections),
        mode=cfg.retrieval.mode,
        envelope=EnvelopeSettings(
            tolerance=tolerances.envelope,
            quad_segs=tolerances.quad_segs,
            min_area_m2=tolerances.min_area_m2,
        ),
    )


def statistics(cfg: DictConfig) -> Statistics:
    """Read the interval settings.

    Args:
        cfg: The composed eval config.

    Returns:
        ``eval.confidence`` and ``eval.bootstrap``.
    """
    return Statistics(
        confidence=cfg.eval.confidence,
        resamples=cfg.eval.bootstrap.resamples,
        seed=cfg.eval.bootstrap.seed,
    )


def ledger_total(ledger: CostLedger) -> float:
    """Total cost recorded by a ledger, e.g. the judge's.

    Args:
        ledger: A cost ledger.

    Returns:
        The sum over its model nodes, in USD.
    """
    return sum(usage.cost_usd for usage in ledger.usage().values())
