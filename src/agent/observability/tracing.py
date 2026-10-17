from openinference.instrumentation.langchain import LangChainInstrumentor
from phoenix.otel import register

from agent.observability.logs import get_logger

logger = get_logger(__name__)


def setup_tracing(*, enabled: bool, project: str, endpoint: str) -> None:
    """Send LangChain and LangGraph spans to a Phoenix collector.

    Registers a Phoenix tracer provider (batch export) as the global OpenTelemetry provider and
    instruments LangChain only. Safe to call several times: the LangChain instrumentor is a
    singleton that records whether it is active, so later calls change nothing.

    Args:
        enabled: Whether to trace at all; ``False`` makes this a no-op.
        project: Phoenix project the spans are filed under.
        endpoint: Collector URL, e.g. ``http://localhost:6006/v1/traces``.
    """
    if not enabled:
        logger.debug("tracing disabled")
        return
    instrumentor = LangChainInstrumentor()
    if instrumentor.is_instrumented_by_opentelemetry:
        logger.debug("tracing already set up")
        return
    provider = register(
        endpoint=endpoint,
        project_name=project,
        batch=True,
        verbose=False,
        auto_instrument=False,
    )
    instrumentor.instrument(tracer_provider=provider)
    logger.info("tracing to Phoenix project %r at %s", project, endpoint)
