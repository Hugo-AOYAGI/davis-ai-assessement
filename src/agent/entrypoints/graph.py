import asyncio
from functools import lru_cache

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig

from agent.agents.config import PROJECT_ROOT, load_config
from agent.agents.orchestrator import build
from agent.agents.subagents import AgentGraph
from agent.observability.logs import get_logger, setup_logging

load_dotenv(PROJECT_ROOT / ".env", override=False)
_DEFAULTS = load_config()
setup_logging(_DEFAULTS.policies.logging.level)
# The server loads this file by path, so ``__name__`` is not under the ``agent`` hierarchy.
logger = get_logger("agent.entrypoints.graph")


def _build_uncached(overrides: tuple[str, ...]) -> AgentGraph:
    """Compose the config with ``overrides`` and assemble the orchestrator.

    Args:
        overrides: Hydra override strings.

    Returns:
        The compiled orchestrator graph.
    """
    logger.info("building graph with overrides %s", list(overrides))
    return build(load_config(overrides))


_build = lru_cache(maxsize=_DEFAULTS.policies.server.graph_cache_size)(_build_uncached)
_build(())  # import runs off the event loop: the first run then hits the cache


def run_overrides(config: RunnableConfig) -> tuple[str, ...]:
    """Read the Hydra overrides of a run from ``configurable.overrides``.

    Args:
        config: The run config passed by the Agent Server.

    Returns:
        The override strings, in order (empty when none are given).

    Raises:
        TypeError: If ``overrides`` is not a list of strings.
    """
    raw: object = config.get("configurable", {}).get("overrides", [])
    overrides = (
        tuple(item for item in raw if isinstance(item, str)) if isinstance(raw, list) else ()
    )
    if not isinstance(raw, list) or len(overrides) != len(raw):
        msg = f"configurable.overrides must be a list of Hydra override strings, got {raw!r}"
        raise TypeError(msg)
    return overrides


async def graph(config: RunnableConfig) -> AgentGraph:
    """Agent Server graph factory (``langgraph.json`` → ``graph``).

    The server calls it for every run, and for schema and state endpoints, with the assistant
    config merged with the thread and request ``configurable``. Hydra overrides can therefore
    be set per assistant or per run, e.g.
    ``{"configurable": {"overrides": ["models.nodes.orchestrator.effort=low"]}}``.
    One compiled graph is cached per distinct override list (the server attaches its own
    checkpointer and store to a copy), so repeated calls are cheap. The build runs in a worker
    thread because Hydra's compose does blocking file-system calls.

    Args:
        config: The run config passed by the Agent Server.

    Returns:
        The compiled orchestrator graph for these overrides.
    """
    return await asyncio.to_thread(_build, run_overrides(config))
