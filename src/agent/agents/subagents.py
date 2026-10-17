from collections.abc import Iterable

from deepagents import CompiledSubAgent
from hydra.utils import instantiate
from langchain.agents import create_agent
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from omegaconf import DictConfig

from agent.agents.config import read_prompt
from agent.llm.costs import CostLedger
from agent.llm.factory import build_model
from agent.observability.logs import get_logger
from agent.tools.submit.artifacts import ArtifactsMiddleware, ArtifactsState

logger = get_logger(__name__)

# ty cannot check a TypedDict state against langgraph's StateLike bound.
type AgentGraph = CompiledStateGraph[ArtifactsState]  # ty: ignore[invalid-type-arguments]
"""A compiled agent graph (orchestrator or sub-agent) whose state carries ``artifacts``."""


def build_tools(nodes: Iterable[DictConfig]) -> list[BaseTool]:
    """Instantiate tool factories declared in config as ``_target_`` nodes.

    Each node calls a factory returning a LangChain tool, e.g.
    ``{_target_: agent.tools.submit.factory.submit_tool, artifact: site, contract: ...}``.
    Nested ``_target_`` nodes (such as ``hydra.utils.get_class`` for a contract) are
    instantiated first.

    Args:
        nodes: The ``tools`` list of an agent or sub-agent config.

    Returns:
        The tools, in config order.

    Raises:
        TypeError: If a node does not build a ``BaseTool``.
    """
    tools: list[BaseTool] = []
    for node in nodes:
        tool = instantiate(node, _convert_="all")
        if not isinstance(tool, BaseTool):
            msg = f"tool node {node.get('_target_')!r} built {type(tool).__name__}, not a BaseTool"
            raise TypeError(msg)
        tools.append(tool)
    return tools


def build_subagent(cfg: DictConfig, name: str, ledger: CostLedger | None = None) -> AgentGraph:
    """Build one sub-agent as a standalone graph, from ``conf/subagents/<name>.yaml``.

    The same graph is delegated to by the orchestrator's ``task`` tool and invoked directly by
    per-sub-agent evals with ``{"messages": [HumanMessage(task)]}``. It declares the
    ``artifacts`` state key, so what its ``submit_<artifact>`` tool stores flows back to the
    parent. Prompt caching is added here because deepagents only adds it to the sub-agents it
    compiles itself; it is a no-op for non-Anthropic models.

    Args:
        cfg: The full composed config.
        name: Sub-agent name, a key of ``cfg.subagents``.
        ledger: Keeps the cost logger of the sub-agent's model node, if given.

    Returns:
        The compiled sub-agent graph.

    Raises:
        KeyError: If the sub-agent is not enabled in ``cfg.subagents``.
    """
    if name not in cfg.subagents:
        msg = f"unknown sub-agent {name!r}; enabled sub-agents: {sorted(cfg.subagents.keys())}"
        raise KeyError(msg)
    spec = cfg.subagents[name]
    tools = build_tools(spec.tools)
    logger.info(
        "sub-agent %s: model node %s, tools %s", name, spec.model, [tool.name for tool in tools]
    )
    return create_agent(
        model=build_model(cfg.models, spec.model, ledger),
        tools=tools,
        system_prompt=read_prompt(spec.prompt),
        middleware=[
            ArtifactsMiddleware(),
            AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
        ],
        name=name,
    )


def subagent_specs(cfg: DictConfig, ledger: CostLedger | None = None) -> list[CompiledSubAgent]:
    """Build every sub-agent enabled in ``cfg.subagents``, ready for ``create_deep_agent``.

    Args:
        cfg: The full composed config.
        ledger: Keeps the cost loggers of the sub-agents' model nodes, if given.

    Returns:
        One spec per sub-agent; its ``description`` is what the orchestrator reads to decide
        when to delegate.
    """
    return [
        CompiledSubAgent(
            name=str(name),
            description=spec.description,
            runnable=build_subagent(cfg, str(name), ledger),
        )
        for name, spec in cfg.subagents.items()
    ]
