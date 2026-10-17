import threading
from collections.abc import Mapping
from typing import override

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from agent.llm.pricing import ModelPrice, TokenCounts, find_price
from agent.observability.logs import get_logger

_UNKNOWN_MODEL = "unknown"

logger = get_logger(__name__)


def _response_message(response: LLMResult) -> AIMessage | None:
    """Return the AI message of a chat model response, if any.

    Args:
        response: Result passed to ``on_llm_end``.

    Returns:
        The first generation's message, or ``None`` for empty or non-chat results.
    """
    generations = response.generations[0] if response.generations else []
    generation = generations[0] if generations else None
    if isinstance(generation, ChatGeneration) and isinstance(generation.message, AIMessage):
        return generation.message
    return None


class CostLogger(BaseCallbackHandler):
    """Logs tokens and USD cost of every call made by one model node, and keeps running totals.

    Works with streamed calls: usage is read from the final message, not from ``llm_output``.
    Accumulation is thread-safe, so one instance can serve concurrent calls.
    """

    def __init__(self, node: str, pricing: Mapping[str, ModelPrice]) -> None:
        """Create a logger for one node.

        Args:
            node: Model node name (key in ``models.nodes``), shown on every log line.
            pricing: Prices keyed by model id.
        """
        super().__init__()
        self._node = node
        self._pricing = dict(pricing)
        self._lock = threading.Lock()
        self._calls = 0
        self._tokens = TokenCounts()
        self._total_usd = 0.0

    @property
    def node(self) -> str:
        """Model node name."""
        return self._node

    @property
    def calls(self) -> int:
        """Number of calls with usage recorded so far."""
        with self._lock:
            return self._calls

    @property
    def tokens(self) -> TokenCounts:
        """Tokens of all calls so far."""
        with self._lock:
            return self._tokens

    @property
    def total_usd(self) -> float:
        """Cost of all calls so far, in USD."""
        with self._lock:
            return self._total_usd

    @override
    def on_llm_end(self, response: LLMResult, **_kwargs: object) -> None:
        """Record and log the usage of one finished call.

        Args:
            response: The call's result.
            **_kwargs: Run identifiers passed by LangChain, unused.
        """
        message = _response_message(response)
        if message is None or message.usage_metadata is None:
            return
        model = str(message.response_metadata.get("model_name") or _UNKNOWN_MODEL)
        tokens = TokenCounts.from_usage(message.usage_metadata)
        price = find_price(self._pricing, model)
        if price is None:
            logger.warning("no price for model %r (node %s); cost counted as 0", model, self._node)
        cost = tokens.cost(price) if price is not None else 0.0
        with self._lock:
            self._calls += 1
            self._tokens = self._tokens + tokens
            self._total_usd += cost
            total = self._total_usd
        logger.info(
            "llm node=%s model=%s in=%d out=%d cache_read=%d cache_write=%d cost=$%.4f total=$%.4f",
            self._node,
            model,
            tokens.input,
            tokens.output,
            tokens.cache_read,
            tokens.cache_write,
            cost,
            total,
        )
