import pytest
from langchain_core.messages.ai import UsageMetadata

from agent.llm.pricing import ModelPrice, TokenCounts, cost_usd, find_price

SONNET = ModelPrice(input=2.0, output=10.0, cache_read=0.2, cache_write=2.5)


def usage(input_tokens: int, output_tokens: int, **details: int) -> UsageMetadata:
    return UsageMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_token_details=details,  # ty: ignore[invalid-argument-type]
    )


def test_cost_without_cache():
    assert cost_usd(usage(1_000_000, 100_000), SONNET) == pytest.approx(2.0 + 1.0)


def test_cached_tokens_are_priced_at_cache_rates():
    call = usage(1_000_000, 0, cache_read=600_000, cache_creation=300_000)
    counts = TokenCounts.from_usage(call)
    assert counts == TokenCounts(input=100_000, output=0, cache_read=600_000, cache_write=300_000)
    assert cost_usd(call, SONNET) == pytest.approx(0.2 + 0.12 + 0.75)


def test_ttl_split_cache_writes_are_summed():
    call = usage(
        1_000,
        0,
        cache_creation=0,
        ephemeral_5m_input_tokens=400,
        ephemeral_1h_input_tokens=100,
    )
    assert TokenCounts.from_usage(call).cache_write == 500
    assert TokenCounts.from_usage(call).input == 500


def test_missing_details_mean_no_cache():
    call = UsageMetadata(input_tokens=10, output_tokens=5, total_tokens=15)
    assert TokenCounts.from_usage(call) == TokenCounts(input=10, output=5)


def test_counts_add():
    total = TokenCounts(input=1, output=2) + TokenCounts(cache_read=3, cache_write=4)
    assert total == TokenCounts(input=1, output=2, cache_read=3, cache_write=4)


def test_find_price_exact_prefix_and_unknown():
    pricing = {"claude-sonnet-5-5": SONNET}
    assert find_price(pricing, "claude-sonnet-5-5") is SONNET
    assert find_price(pricing, "claude-sonnet-5-5-20260928") is SONNET
    assert find_price(pricing, "claude-sonnet-5") is None
    assert find_price(pricing, "gpt-x") is None
