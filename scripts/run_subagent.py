"""Run one sub-agent standalone on a task; report its artifact, citation pass rate and cost.

Usage: ``uv run python scripts/run_subagent.py <name> "<task text>" [--override key=value ...]
[--artifacts path.json]``. ``--override`` is a repeatable Hydra override; ``--artifacts`` is a
JSON object of initial artifacts (e.g. ``{"site": ...}`` from a ``surveyor`` run, for
``zoning_analyst``; ``site`` and the ``notes.*`` artifacts for ``architect``). Calls the real
model. A JSON report is written to ``outputs/runs/<name>-<timestamp>.json``. Example:
``... run_subagent.py surveyor "<address>"``.
"""

import argparse
import json
from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.messages.ai import UsageMetadata
from omegaconf import DictConfig
from pydantic import BaseModel, JsonValue, TypeAdapter

from agent.adapters.corpus.store import load_corpus
from agent.agents.config import PROJECT_ROOT, load_config, project_path
from agent.agents.subagents import build_subagent
from agent.contracts.evidence import Citation, CitationCheck, SourceKind
from agent.llm.factory import load_pricing
from agent.llm.pricing import TokenCounts, find_price
from agent.observability.logs import get_logger, setup_logging
from agent.tools.study.checks import check_regulatory, corpus_facts
from agent.tools.study.messages import Verification

logger = get_logger("agent.scripts.run_subagent")

_ARTIFACTS = TypeAdapter(dict[str, JsonValue])


class Options(BaseModel):
    """Command-line options."""

    name: str
    task: str
    override: list[str]
    artifacts: Path | None
    recursion_limit: int
    output_dir: Path
    max_chars: int
    log_level: str


class LocatedCheck(CitationCheck):
    """A citation check with the dotted path of the citation in the artifacts."""

    path: str


class ModelUsage(TokenCounts):
    """Tokens of one model over the run, with their cost."""

    cost_usd: float


class Report(BaseModel):
    """The JSON report of one run."""

    subagent: str
    task: str
    overrides: list[str]
    artifacts: dict[str, JsonValue]
    citation_checks: list[LocatedCheck]
    rejections: list[str]
    tool_calls: list[dict[str, str]]
    usage: dict[str, ModelUsage]
    total_tokens: int
    cost_usd: float


def parse_options(argv: Sequence[str] | None = None) -> Options:
    """Parse the command line.

    Args:
        argv: Arguments, ``sys.argv[1:]`` when ``None``.

    Returns:
        The options.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="sub-agent name, a file of conf/subagents/")
    parser.add_argument("task", help="task text sent as the human message")
    parser.add_argument("--override", action="append", default=[], help="Hydra override")
    parser.add_argument("--artifacts", type=Path, help="JSON file of initial artifacts")
    parser.add_argument("--recursion-limit", type=int, default=100)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "outputs" / "runs")
    parser.add_argument("--max-chars", type=int, default=300, help="truncation of logged text")
    parser.add_argument("--log-level", default="INFO")
    return Options.model_validate(vars(parser.parse_args(argv)))


def find_citations(value: JsonValue, path: str) -> Iterator[tuple[str, Citation]]:
    """Yield ``(dotted path, citation)`` for every dict with ``quote`` and ``source_kind``."""
    if isinstance(value, dict):
        if "quote" in value and "source_kind" in value:
            yield path, Citation.model_validate(value)
            return
        items = list(value.items())
    elif isinstance(value, list):
        items = [(str(index), item) for index, item in enumerate(value)]
    else:
        return
    for key, item in items:
        yield from find_citations(item, f"{path}.{key}")


def check_citations(cfg: DictConfig, artifacts: Mapping[str, JsonValue]) -> list[LocatedCheck]:
    """Check every regulatory citation of the artifacts against the ingested corpus.

    Args:
        cfg: The composed config (``corpus.dir``, ``policies.citations`` with ``check_raster``).
        artifacts: Artifacts stored by the run, by name.

    Returns:
        One check per regulatory citation, in artifact order.
    """
    cited = [
        (path, citation)
        for name, data in artifacts.items()
        for path, citation in find_citations(data, name)
        if citation.source_kind is SourceKind.REGULATORY
    ]
    if not cited:
        return []
    corpus = corpus_facts(load_corpus(project_path(cfg.corpus.dir)))
    policy = cfg.policies.citations
    verification = Verification(policy.min_score, policy.neighbour_pages, policy.max_quote_chars)
    return [
        LocatedCheck(
            path=path,
            **check_regulatory(
                citation, corpus, verification, check_raster=policy.check_raster
            ).model_dump(),
        )
        for path, citation in cited
    ]


def tool_calls(messages: Sequence[BaseMessage], max_chars: int) -> list[dict[str, str]]:
    """List the tool calls of the run in order (name and truncated JSON arguments)."""
    return [
        {"name": call["name"], "args": json.dumps(call["args"], ensure_ascii=False)[:max_chars]}
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    ]


def rejections(messages: Sequence[BaseMessage], max_chars: int) -> list[str]:
    """List the error replies of ``submit_*`` tools (rejected submissions), truncated."""
    names = {
        call["id"]: call["name"]
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    }
    return [
        f"{names[message.tool_call_id]}: {message.text[:max_chars]}"
        for message in messages
        if isinstance(message, ToolMessage)
        and message.status == "error"
        and names.get(message.tool_call_id, "").startswith("submit_")
    ]


def price(cfg: DictConfig, usage: Mapping[str, UsageMetadata]) -> dict[str, ModelUsage]:
    """Price the usage summed per model id; unpriced models cost zero, with a warning."""
    pricing = load_pricing(cfg.models)
    priced: dict[str, ModelUsage] = {}
    for model, metadata in usage.items():
        counts = TokenCounts.from_usage(metadata)
        model_price = find_price(pricing, model)
        if model_price is None:
            logger.warning("no price for model %s", model)
        cost = counts.cost(model_price) if model_price else 0.0
        priced[model] = ModelUsage(**counts.model_dump(), cost_usd=cost)
    return priced


def log_report(report: Report) -> None:
    """Log the stored artifacts, citation pass rate, failing citations, rejections and cost."""
    logger.info("artifacts stored: %s", sorted(report.artifacts) or "none")
    checks = [check for check in report.citation_checks if check.text_verifiable]
    failing = [check for check in checks if not check.verified]
    raster = len(report.citation_checks) - len(checks)
    logger.info("citations verified: %d/%d", len(checks) - len(failing), len(checks))
    logger.info("citations not text-verifiable (raster): %d", raster)
    for check in failing:
        cited = check.citation
        where = f"{cited.doc} p.{cited.page}"
        logger.info("FAIL %s %s score=%.2f quote=%r", check.path, where, check.score, cited.quote)
    logger.info("rejected submissions: %d", len(report.rejections))
    for rejection in report.rejections:
        logger.info("REJECTED %s", rejection)
    logger.info("tokens: %d, cost: $%.4f", report.total_tokens, report.cost_usd)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the sub-agent and write the report.

    Args:
        argv: Arguments, ``sys.argv[1:]`` when ``None``.

    Returns:
        0 when the sub-agent stored an artifact, 1 otherwise.
    """
    options = parse_options(argv)
    setup_logging(options.log_level)
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    cfg = load_config([f"subagents=[{options.name}]", *options.override])
    initial = _ARTIFACTS.validate_json(options.artifacts.read_bytes()) if options.artifacts else {}
    graph = build_subagent(cfg, options.name)
    usage_handler = UsageMetadataCallbackHandler()
    state = graph.invoke(
        {"messages": [HumanMessage(options.task)], "artifacts": initial},
        config={"recursion_limit": options.recursion_limit, "callbacks": [usage_handler]},
    )
    messages = [message for message in state["messages"] if isinstance(message, BaseMessage)]
    final = _ARTIFACTS.validate_python(state.get("artifacts", {}))
    stored = {key: value for key, value in final.items() if initial.get(key) != value}
    usage = price(cfg, usage_handler.usage_metadata)
    report = Report(
        subagent=options.name,
        task=options.task,
        overrides=options.override,
        artifacts=stored,
        citation_checks=check_citations(cfg, stored),
        rejections=rejections(messages, options.max_chars),
        tool_calls=tool_calls(messages, options.max_chars),
        usage=usage,
        total_tokens=sum(meta["total_tokens"] for meta in usage_handler.usage_metadata.values()),
        cost_usd=sum(entry.cost_usd for entry in usage.values()),
    )
    log_report(report)
    options.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    path = options.output_dir / f"{options.name}-{stamp}.json"
    path.write_text(report.model_dump_json(indent=1), encoding="utf-8")
    logger.info("report: %s", path)
    return 0 if stored else 1


if __name__ == "__main__":
    raise SystemExit(main())
