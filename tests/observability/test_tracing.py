import json
from typing import ClassVar

import pytest
from openinference.instrumentation import TraceConfig

from agent.observability import tracing


def setup(*, enabled: bool) -> None:
    tracing.setup_tracing(
        enabled=enabled,
        project="p",
        endpoint="http://collector/v1/traces",
        hide_images=True,
        base64_max_chars=100,
    )


IMAGE = "iVBORw0KGgo" + "A" * 5000 + "=="


class FakeInstrumentor:
    instances: ClassVar[list["FakeInstrumentor"]] = []

    def __init__(self):
        self.calls = []
        FakeInstrumentor.instances.append(self)

    @property
    def is_instrumented_by_opentelemetry(self):
        return any(instance.calls for instance in FakeInstrumentor.instances)

    def instrument(self, **kwargs):
        self.calls.append(kwargs)


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch):
    registered = []
    FakeInstrumentor.instances = []
    provider = object()

    def fake_register(**kwargs):
        registered.append(kwargs)
        return provider

    monkeypatch.setattr(tracing, "register", fake_register)
    monkeypatch.setattr(tracing, "LangChainInstrumentor", FakeInstrumentor)
    return registered, provider


def test_disabled_is_noop(fakes):
    registered, _ = fakes
    setup(enabled=False)
    assert registered == []
    assert FakeInstrumentor.instances == []


def test_enabled_registers_and_instruments(fakes):
    registered, provider = fakes
    setup(enabled=True)
    assert registered == [
        {
            "endpoint": "http://collector/v1/traces",
            "project_name": "p",
            "batch": True,
            "verbose": False,
            "auto_instrument": False,
        }
    ]
    [call] = [call for instance in FakeInstrumentor.instances for call in instance.calls]
    assert call["tracer_provider"] is provider
    assert isinstance(call["config"], tracing.ImageFreeTraceConfig)
    assert call["config"].hide_input_images


def test_second_call_does_not_reinstrument(fakes):
    registered, _ = fakes
    setup(enabled=True)
    setup(enabled=True)
    assert len(registered) == 1
    calls = [call for instance in FakeInstrumentor.instances for call in instance.calls]
    assert len(calls) == 1


def test_strip_base64_keeps_text_and_short_runs():
    text = f"page 3 id=abc123 {IMAGE} end"
    assert tracing.strip_base64(text, 100) == f"page 3 id=abc123 <base64, {len(IMAGE)} chars> end"
    assert tracing.strip_base64("short QUJD== run", 100) == "short QUJD== run"


def test_tool_output_images_are_stripped_from_span_values():
    config = tracing.trace_config(hide_images=True, base64_max_chars=100)
    block = {"type": "image", "base64": IMAGE, "mime_type": "image/png"}
    value = json.dumps({"messages": [{"type": "tool", "content": [block]}]})
    masked = config.mask("output.value", value)
    assert isinstance(masked, str)
    assert IMAGE not in masked
    assert '"mime_type": "image/png"' in masked
    assert config.mask("input.value", lambda: IMAGE) == f"<base64, {len(IMAGE)} chars>"
    assert config.mask("llm.token_count.total", 12) == 12


def test_images_kept_when_not_hidden():
    config = tracing.trace_config(hide_images=False, base64_max_chars=100)
    assert type(config) is TraceConfig
    assert config.mask("output.value", IMAGE) == IMAGE
