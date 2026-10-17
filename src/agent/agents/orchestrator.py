import threading
from enum import StrEnum

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from deepagents._models import get_model_identifier, get_model_provider
from hydra.utils import instantiate
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from omegaconf import DictConfig

from agent.agents.config import read_prompt
from agent.agents.subagents import AgentGraph, build_tools, subagent_specs
from agent.llm.costs import CostLedger
from agent.llm.factory import build_model
from agent.llm.truncation import OutputCapMiddleware
from agent.observability.logs import get_logger
from agent.tools.images.inline import InlineImagesMiddleware
from agent.tools.interaction.ask import ask_user_tool
from agent.tools.interaction.playbook import Playbook, load_playbook_tool
from agent.tools.submit.artifacts import ArtifactsMiddleware

logger = get_logger(__name__)

# deepagents reads the harness profile from a process-wide registry when the agent is created.
_PROFILE_LOCK = threading.Lock()


class AskUserMode(StrEnum):
    """Whether the orchestrator may put questions to the user (``policies.ask_user.mode``)."""

    INTERACTIVE = "interactive"
    """``ask_user`` is offered; it pauses the run on a LangGraph interrupt."""
    DISABLED = "disabled"
    """``ask_user`` is not offered; the program facts come with the request."""


def parse_ask_user_mode(mode: str) -> AskUserMode:
    """Validate the ``policies.ask_user.mode`` value.

    Args:
        mode: The configured mode.

    Returns:
        The mode.

    Raises:
        ValueError: If ``mode`` is not an ``AskUserMode`` value.
    """
    try:
        return AskUserMode(mode)
    except ValueError as error:
        allowed = ", ".join(item.value for item in AskUserMode)
        msg = f"unknown policies.ask_user.mode {mode!r}; expected one of: {allowed}"
        raise ValueError(msg) from error


def read_playbooks(nodes: DictConfig) -> dict[str, Playbook]:
    """Read the playbook files declared in ``agent.playbooks``.

    Args:
        nodes: Mapping of playbook name to ``{description, path}``.

    Returns:
        The playbooks by name, with their text.
    """
    return {
        str(name): Playbook(description=node.description, text=read_prompt(node.path))
        for name, node in nodes.items()
    }


def orchestrator_tools(cfg: DictConfig) -> list[BaseTool]:
    """Build the orchestrator's own tools (``task`` is added by deepagents).

    Args:
        cfg: The full composed config.

    Returns:
        The ``agent.tools`` of the config, then ``load_playbook`` when playbooks are configured,
        then ``ask_user`` in ``interactive`` mode.
    """
    tools = build_tools(cfg.agent.tools)
    playbooks = read_playbooks(cfg.agent.playbooks)
    if playbooks:
        tools.append(load_playbook_tool(playbooks, cfg.agent.language))
    if parse_ask_user_mode(cfg.policies.ask_user.mode) is AskUserMode.INTERACTIVE:
        tools.append(ask_user_tool())
    return tools


def profile_key(model: BaseChatModel) -> str:
    """Narrowest key under which deepagents looks up the harness profile of a model instance.

    That is the exact ``provider:model`` key deepagents tries first, so a profile registered
    under it applies to this model only. A model that reports no identifier is looked up by
    its provider alone.

    Args:
        model: The orchestrator's chat model.

    Returns:
        The key, e.g. ``anthropic:claude-sonnet-5-5``.

    Raises:
        ValueError: If deepagents cannot tell the model's provider.
    """
    provider, identifier = get_model_provider(model), get_model_identifier(model)
    if provider is None:
        msg = f"cannot key a harness profile for {type(model).__name__}: no provider"
        raise ValueError(msg)
    return provider if identifier is None else f"{provider}:{identifier}"


def build(cfg: DictConfig, ledger: CostLedger | None = None) -> AgentGraph:
    """Assemble the deepagents orchestrator entirely from config.

    Model from ``models.nodes[agent.model]``, system prompt from ``agent.prompt``, tools from
    ``orchestrator_tools`` and one ``task``-delegable sub-agent per entry of ``subagents``.
    deepagents' built-in ``general-purpose`` sub-agent is offered only if
    ``agent.general_purpose_subagent``: deepagents takes that switch from the harness profile of
    the model, so it is registered on the model's exact ``provider:model`` key (merged into any
    existing profile) with the explicit value of every build.

    Args:
        cfg: The full composed config (see ``agent.agents.config.load_config``).
        ledger: Keeps the cost logger of every model node built, to read a run's usage per
            node.

    Returns:
        The compiled orchestrator graph, whose state carries the ``artifacts`` mapping.
    """
    model = build_model(cfg.models, cfg.agent.model, ledger)
    tools = orchestrator_tools(cfg)
    subagents = subagent_specs(cfg, ledger)
    general_purpose = bool(cfg.agent.general_purpose_subagent)
    logger.info(
        "orchestrator: model %s, tools %s, sub-agents %s, general-purpose %s",
        cfg.models.nodes[cfg.agent.model].model,
        [tool.name for tool in tools],
        [spec["name"] for spec in subagents],
        general_purpose,
    )
    profile = HarnessProfile(
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=general_purpose)
    )
    with _PROFILE_LOCK:
        register_harness_profile(profile_key(model), profile)
        return create_deep_agent(
            model=model,
            tools=tools,
            system_prompt=read_prompt(cfg.agent.prompt),
            middleware=[
                InlineImagesMiddleware(instantiate(cfg.images.store)),
                ArtifactsMiddleware(),
                OutputCapMiddleware(),
            ],
            subagents=subagents,
            name="orchestrator",
        )
