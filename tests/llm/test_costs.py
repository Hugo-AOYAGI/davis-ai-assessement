import logging
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.messages.ai import UsageMetadata
from langchain_core.outputs import ChatGeneration, Generation, LLMResult

from agent.llm.costs import CostLogger
from agent.llm.pricing import ModelPrice, TokenCounts

PRICING = {"claude-sonnet-5-5": ModelPrice(input=2.0, output=10.0, cache_read=0.2, cache_write=2.5)}


def result(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0) -> LLMResult:
    message = AIMessage(
        content="ok",
        usage_metadata=UsageMetadata(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            input_token_details={"cache_read": cache_read},
        ),
        response_metadata={"model_name": model},
    )
    return LLMResult(generations=[[ChatGeneration(message=message)]])


def test_logs_and_accumulates(caplog: pytest.LogCaptureFixture):
    cost_logger = CostLogger("orchestrator", PRICING)
    with caplog.at_level(logging.INFO, logger="agent"):
        cost_logger.on_llm_end(result("claude-sonnet-5-5", 1_000_000, 0, cache_read=500_000))
        cost_logger.on_llm_end(result("claude-sonnet-5-5", 0, 100_000), run_id=uuid4())
    assert cost_logger.calls == 2
    assert cost_logger.total_usd == pytest.approx(1.0 + 0.1 + 1.0)
    assert cost_logger.tokens == TokenCounts(input=500_000, output=100_000, cache_read=500_000)
    lines = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert len(lines) == 2
    assert "node=orchestrator" in lines[1]
    assert "model=claude-sonnet-5-5" in lines[1]
    assert "total=$2.1000" in lines[1]


def test_unknown_model_warns_and_costs_nothing(caplog: pytest.LogCaptureFixture):
    cost_logger = CostLogger("site_locator", PRICING)
    with caplog.at_level(logging.INFO, logger="agent"):
        cost_logger.on_llm_end(result("mystery-model", 100, 100))
    assert cost_logger.total_usd == 0.0
    assert cost_logger.calls == 1
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_ignores_results_without_usage():
    cost_logger = CostLogger("orchestrator", PRICING)
    cost_logger.on_llm_end(LLMResult(generations=[[Generation(text="plain")]]))
    cost_logger.on_llm_end(LLMResult(generations=[]))
    cost_logger.on_llm_end(LLMResult(generations=[[ChatGeneration(message=AIMessage("x"))]]))
    assert cost_logger.calls == 0


def test_concurrent_calls_are_all_counted():
    cost_logger = CostLogger("orchestrator", PRICING)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(
            pool.map(
                lambda _: cost_logger.on_llm_end(result("claude-sonnet-5-5", 10, 1)), range(200)
            )
        )
    assert cost_logger.calls == 200
    assert cost_logger.tokens == TokenCounts(input=2_000, output=200)
