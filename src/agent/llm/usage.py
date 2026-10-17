from collections.abc import Mapping

from langchain_core.messages.ai import UsageMetadata
from omegaconf import DictConfig

from agent.llm.factory import load_pricing
from agent.llm.pricing import TokenCounts, find_price
from agent.observability.logs import get_logger

logger = get_logger(__name__)


class ModelUsage(TokenCounts):
    """Tokens of one model id over a run, with their cost."""

    cost_usd: float


def price_usage(
    models_cfg: DictConfig, usage: Mapping[str, UsageMetadata]
) -> dict[str, ModelUsage]:
    """Price a run's usage summed per model id, e.g. from ``UsageMetadataCallbackHandler``.

    Unpriced models cost zero, with a warning.

    Args:
        models_cfg: The ``models`` config group (its ``pricing`` map is used).
        usage: Usage metadata keyed by model id.

    Returns:
        Token counts and cost per model id.
    """
    pricing = load_pricing(models_cfg)
    priced: dict[str, ModelUsage] = {}
    for model, metadata in usage.items():
        counts = TokenCounts.from_usage(metadata)
        model_price = find_price(pricing, model)
        if model_price is None:
            logger.warning("no price for model %s; cost counted as 0", model)
        cost = counts.cost(model_price) if model_price is not None else 0.0
        priced[model] = ModelUsage(**counts.model_dump(), cost_usd=cost)
    return priced
