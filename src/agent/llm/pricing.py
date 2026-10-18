from collections.abc import Mapping
from typing import Self

from langchain_core.messages.ai import UsageMetadata
from pydantic import Field

from agent.contracts.base import Contract

_TOKENS_PER_UNIT = 1_000_000
_CACHE_WRITE_KEYS = ("cache_creation", "ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens")


def _count(details: Mapping[str, object], key: str) -> int:
    """Read one token count from usage details, absent or null counting as zero.

    Args:
        details: ``input_token_details`` of a call.
        key: Detail key.

    Returns:
        The count.
    """
    value = details.get(key)
    return value if isinstance(value, int) else 0


class ModelPrice(Contract):
    """Prices of one model, in USD per million tokens."""

    input: float = Field(ge=0)
    output: float = Field(ge=0)
    cache_read: float = Field(ge=0)
    cache_write: float = Field(ge=0)


class TokenCounts(Contract):
    """Tokens of one or more calls, split by billing rate."""

    input: int = Field(default=0, ge=0)
    """Uncached input tokens."""
    output: int = Field(default=0, ge=0)
    cache_read: int = Field(default=0, ge=0)
    cache_write: int = Field(default=0, ge=0)

    @classmethod
    def from_usage(cls, usage: UsageMetadata) -> Self:
        """Split LangChain usage metadata by billing rate.

        LangChain's ``input_tokens`` includes cached tokens, so cache reads and writes are
        subtracted from it to be priced at their own rates. Cache writes may be reported as a
        single ``cache_creation`` count or split by TTL; all are summed (and priced at the
        5-minute write rate).

        Args:
            usage: ``AIMessage.usage_metadata`` of one call.

        Returns:
            The call's token counts.
        """
        details: Mapping[str, object] = dict(usage.get("input_token_details") or {})
        cache_read = _count(details, "cache_read")
        cache_write = sum(_count(details, key) for key in _CACHE_WRITE_KEYS)
        uncached = max(usage["input_tokens"] - cache_read - cache_write, 0)
        return cls(
            input=uncached,
            output=usage["output_tokens"],
            cache_read=cache_read,
            cache_write=cache_write,
        )

    def __add__(self, other: Self) -> Self:
        """Sum two token counts field by field.

        Args:
            other: Counts to add.

        Returns:
            The summed counts.
        """
        return type(self)(
            input=self.input + other.input,
            output=self.output + other.output,
            cache_read=self.cache_read + other.cache_read,
            cache_write=self.cache_write + other.cache_write,
        )

    def cost(self, price: ModelPrice) -> float:
        """Price these tokens.

        Args:
            price: The model's prices.

        Returns:
            Cost in USD.
        """
        total = (
            self.input * price.input
            + self.output * price.output
            + self.cache_read * price.cache_read
            + self.cache_write * price.cache_write
        )
        return total / _TOKENS_PER_UNIT


def find_price(pricing: Mapping[str, ModelPrice], model: str) -> ModelPrice | None:
    """Look up a model's price, accepting dated snapshot ids of a priced model.

    Args:
        pricing: Prices keyed by model id.
        model: Model id reported by the API, e.g. ``claude-sonnet-5-5`` or a dated variant.

    Returns:
        The price of the exact id, else of the longest priced id prefixing it, else ``None``.
    """
    if model in pricing:
        return pricing[model]
    prefixes = [key for key in pricing if model.startswith(f"{key}-")]
    return pricing[max(prefixes, key=len)] if prefixes else None
