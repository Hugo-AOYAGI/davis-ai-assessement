from typing import ClassVar

import pytest

from agent.observability import tracing


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
    tracing.setup_tracing(enabled=False, project="p", endpoint="http://collector/v1/traces")
    assert registered == []
    assert FakeInstrumentor.instances == []


def test_enabled_registers_and_instruments(fakes):
    registered, provider = fakes
    tracing.setup_tracing(enabled=True, project="p", endpoint="http://collector/v1/traces")
    assert registered == [
        {
            "endpoint": "http://collector/v1/traces",
            "project_name": "p",
            "batch": True,
            "verbose": False,
            "auto_instrument": False,
        }
    ]
    calls = [call for instance in FakeInstrumentor.instances for call in instance.calls]
    assert calls == [{"tracer_provider": provider}]


def test_second_call_does_not_reinstrument(fakes):
    registered, _ = fakes
    tracing.setup_tracing(enabled=True, project="p", endpoint="http://collector/v1/traces")
    tracing.setup_tracing(enabled=True, project="p", endpoint="http://collector/v1/traces")
    assert len(registered) == 1
    calls = [call for instance in FakeInstrumentor.instances for call in instance.calls]
    assert len(calls) == 1
