from deepagents import create_deep_agent
from omegaconf import DictConfig

from agent.agents.config import read_prompt
from agent.agents.subagents import AgentGraph, build_tools, subagent_specs
from agent.llm.factory import build_model
from agent.observability.logs import get_logger
from agent.tools.submit.artifacts import ArtifactsMiddleware

logger = get_logger(__name__)


def system_prompt(agent_cfg: DictConfig) -> str:
    """Assemble the orchestrator's system prompt: the base prompt, then the playbook if set.

    Args:
        agent_cfg: The ``agent`` config group.

    Returns:
        The prompt text.
    """
    parts = [read_prompt(agent_cfg.prompt)]
    if agent_cfg.playbook:
        parts.append(read_prompt(agent_cfg.playbook))
    return "\n\n".join(parts)


def build(cfg: DictConfig) -> AgentGraph:
    """Assemble the deepagents orchestrator entirely from config.

    Model from ``models.nodes[agent.model]``, prompt (and playbook) files from ``agent``, tools
    from ``agent.tools`` and one ``task``-delegable sub-agent per entry of ``subagents``.

    Args:
        cfg: The full composed config (see ``agent.agents.config.load_config``).

    Returns:
        The compiled orchestrator graph, whose state carries the ``artifacts`` mapping.
    """
    model = build_model(cfg.models, cfg.agent.model)
    tools = build_tools(cfg.agent.tools)
    subagents = subagent_specs(cfg)
    logger.info(
        "orchestrator: model %s, tools %s, sub-agents %s",
        cfg.models.nodes[cfg.agent.model].model,
        [tool.name for tool in tools],
        [spec["name"] for spec in subagents],
    )
    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt(cfg.agent),
        middleware=[ArtifactsMiddleware()],
        subagents=subagents,
        name="orchestrator",
    )
