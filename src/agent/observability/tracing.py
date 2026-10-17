import re
from collections.abc import Callable, Sequence
from typing import override

from openinference.instrumentation import TraceConfig
from openinference.instrumentation.langchain import LangChainInstrumentor
from phoenix.otel import register

from agent.observability.logs import get_logger

logger = get_logger(__name__)

type SpanValue = (
    str | bool | int | float | Sequence[str] | Sequence[bool] | Sequence[int] | Sequence[float]
)
"""An OpenTelemetry span attribute value, as OpenInference types it."""


def strip_base64(text: str, max_chars: int) -> str:
    """Replace every run of base64 characters longer than ``max_chars`` by a short placeholder.

    Text has spaces and punctuation; a long unbroken base64 run is encoded binary data (a page
    image, a map).

    Args:
        text: An attribute value.
        max_chars: Longest base64 run kept as is.

    Returns:
        The text with each longer run replaced by ``<base64, N chars>``.
    """
    pattern = rf"[A-Za-z0-9+/]{{{max_chars + 1},}}={{0,2}}"
    return re.sub(pattern, lambda match: f"<base64, {len(match[0])} chars>", text)


class ImageFreeTraceConfig(TraceConfig):
    """OpenInference trace settings that also strip base64 data from every string attribute.

    OpenInference redacts only the images it recognises in ``llm.input_messages``; the LangChain
    instrumentor serialises whole inputs and outputs into ``input.value`` and ``output.value``,
    so the images returned by tools (and every state that carries them) would be exported in
    full. Runs longer than ``base64_image_max_length`` are replaced.
    """

    @override
    def mask(
        self,
        key: str,
        value: SpanValue | Callable[[], SpanValue],
        *,
        externalize: bool = True,
    ) -> SpanValue | None:
        """Apply the OpenInference masking, then strip base64 runs from a string result.

        Args:
            key: Span attribute name.
            value: Attribute value, or a callable producing it.
            externalize: Passed to the OpenInference masking.

        Returns:
            The value to record, or ``None`` to drop the attribute.
        """
        masked = super().mask(key, value, externalize=externalize)
        if isinstance(masked, str):
            return strip_base64(masked, self.base64_image_max_length or 0)
        return masked


def trace_config(*, hide_images: bool, base64_max_chars: int) -> TraceConfig:
    """Build the OpenInference trace settings.

    Args:
        hide_images: Whether to keep base64 image data out of span attributes.
        base64_max_chars: Longest base64 run kept in an attribute when images are hidden.

    Returns:
        The image-free settings, or the OpenInference defaults.
    """
    if not hide_images:
        return TraceConfig()
    return ImageFreeTraceConfig(hide_input_images=True, base64_image_max_length=base64_max_chars)


def setup_tracing(
    *, enabled: bool, project: str, endpoint: str, hide_images: bool, base64_max_chars: int
) -> None:
    """Send LangChain and LangGraph spans to a Phoenix collector.

    Registers a Phoenix tracer provider (batch export) as the global OpenTelemetry provider and
    instruments LangChain only. Safe to call several times: the LangChain instrumentor is a
    singleton that records whether it is active, so later calls change nothing.

    Args:
        enabled: Whether to trace at all; ``False`` makes this a no-op.
        project: Phoenix project the spans are filed under.
        endpoint: Collector URL, e.g. ``http://localhost:6006/v1/traces``.
        hide_images: Whether to keep base64 image data out of span attributes; page images make
            span batches larger than the collector accepts.
        base64_max_chars: Longest base64 run kept in an attribute when images are hidden.
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
    instrumentor.instrument(
        tracer_provider=provider,
        config=trace_config(hide_images=hide_images, base64_max_chars=base64_max_chars),
    )
    logger.info("tracing to Phoenix project %r at %s", project, endpoint)
