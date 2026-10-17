from hydra.utils import instantiate
from langchain_core.language_models import BaseChatModel
from omegaconf import DictConfig, OmegaConf

from agent.llm.costs import CostLedger, CostLogger
from agent.llm.pricing import ModelPrice


def load_pricing(models_cfg: DictConfig) -> dict[str, ModelPrice]:
    """Read the ``pricing`` map of the ``models`` config group.

    Args:
        models_cfg: The ``models`` config group.

    Returns:
        Prices keyed by model id.
    """
    raw = OmegaConf.to_container(models_cfg.pricing, resolve=True)
    if not isinstance(raw, dict):
        msg = "models.pricing must be a mapping of model id to prices"
        raise TypeError(msg)
    return {str(model): ModelPrice.model_validate(price) for model, price in raw.items()}


def build_model(
    models_cfg: DictConfig, node: str, ledger: CostLedger | None = None
) -> BaseChatModel:
    """Build the chat model of one node, with per-call token and cost logging attached.

    This is the only place chat models are instantiated.

    Args:
        models_cfg: The ``models`` config group (``pricing`` and ``nodes``).
        node: Key in ``models.nodes``, e.g. ``orchestrator`` or ``surveyor``.
        ledger: Where the node's cost logger is kept, to read the node's totals later; the
            model gets its own logger when ``None``.

    Returns:
        The configured chat model.

    Raises:
        KeyError: If ``node`` is not configured.
        TypeError: If the node's ``_target_`` does not build a chat model.
    """
    nodes = models_cfg.nodes
    if node not in nodes:
        msg = f"unknown model node {node!r}; configured nodes: {sorted(nodes.keys())}"
        raise KeyError(msg)
    max_tokens = nodes[node].get("max_tokens")
    cost_logger = (
        CostLogger(node, load_pricing(models_cfg), max_tokens)
        if ledger is None
        else ledger.logger(node, max_tokens)
    )
    model = instantiate(nodes[node], _convert_="all", callbacks=[cost_logger])
    if not isinstance(model, BaseChatModel):
        msg = f"models.nodes.{node} built {type(model).__name__}, expected a BaseChatModel"
        raise TypeError(msg)
    return model
