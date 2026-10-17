import pytest
from langchain_core.messages.ai import UsageMetadata
from omegaconf import OmegaConf

from agent.llm.usage import ModelUsage, price_usage

MODELS = OmegaConf.create(
    {"pricing": {"sonnet": {"input": 2.0, "output": 10.0, "cache_read": 0.2, "cache_write": 2.5}}}
)


def usage(input_tokens: int, output_tokens: int, **details: int) -> UsageMetadata:
    return UsageMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_token_details=details,  # ty: ignore[invalid-argument-type]
    )


def test_prices_dated_snapshot_with_cache_rates():
    priced = price_usage(MODELS, {"sonnet-20261001": usage(1_000_000, 100_000, cache_read=600_000)})
    entry = priced["sonnet-20261001"]
    assert isinstance(entry, ModelUsage)
    assert (entry.input, entry.output, entry.cache_read) == (400_000, 100_000, 600_000)
    assert entry.cost_usd == pytest.approx(0.8 + 1.0 + 0.12)


def test_unpriced_model_costs_zero():
    priced = price_usage(MODELS, {"other": usage(1_000, 1_000)})
    assert priced["other"].cost_usd == 0.0
    assert priced["other"].input == 1_000


def test_empty_usage():
    assert price_usage(MODELS, {}) == {}
