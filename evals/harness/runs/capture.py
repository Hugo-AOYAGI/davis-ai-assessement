"""Capture the messages of every sub-agent run of an end-to-end study.

The orchestrator's state holds only its own messages: what a sub-agent read lives in the
sub-agent's state, discarded once it replies, and the trajectory scorer needs it.

A callback handler is used rather than ``graph.stream(..., subgraphs=True)``:

- ``run_study`` keeps its single ``invoke``, so the eval runs exactly the CLI's code path; it
  only gains a ``callbacks`` argument;
- the parent's callbacks reach every sub-agent run (deepagents' ``task`` tool relies on
  langgraph's ``ensure_config`` to pass them on), including the two parallel ``doc_analyst``
  runs;
- deepagents names each sub-agent's runnable after the sub-agent (``run_name``), so the root
  chain run of a delegation is recognised by its name, and its ``on_chain_end`` output is the
  sub-agent's final state, every message included.

Streaming would need ``run_study`` rewritten as a stream loop, and its subgraph namespaces
(``tools:<task id>``) do not name the sub-agent.
"""

import threading
from collections.abc import Iterable
from typing import NamedTuple, override
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage

_NAME = "name"
"""Keyword LangChain passes the run name under to ``on_chain_start``."""
_MESSAGES = "messages"


class SubagentRun(NamedTuple):
    """The messages of one finished sub-agent run."""

    name: str
    messages: tuple[BaseMessage, ...]


class SubagentCapture(BaseCallbackHandler):
    """Keeps the final messages of every run of the named sub-agents, in completion order.

    Thread-safe: parallel delegations finish on different threads. A run that fails is not kept.
    """

    def __init__(self, names: Iterable[str]) -> None:
        """Watch the runs of these sub-agents.

        Args:
            names: Sub-agent names (keys of ``cfg.subagents``), as their runs are named.
        """
        super().__init__()
        self._names = frozenset(names)
        self._lock = threading.Lock()
        self._open: dict[UUID, str] = {}
        self._runs: list[SubagentRun] = []

    @property
    def runs(self) -> tuple[SubagentRun, ...]:
        """The finished sub-agent runs so far, in completion order."""
        with self._lock:
            return tuple(self._runs)

    @override
    def on_chain_start(
        self, serialized: object, inputs: object, *, run_id: UUID, **kwargs: object
    ) -> None:
        """Remember a starting run when it is the root run of a watched sub-agent.

        Args:
            serialized: Serialised runnable, unused.
            inputs: Run inputs, unused.
            run_id: Id of the run.
            **kwargs: Run details; ``name`` is the run name.
        """
        name = kwargs.get(_NAME)
        if isinstance(name, str) and name in self._names:
            with self._lock:
                self._open[run_id] = name

    @override
    def on_chain_end(self, outputs: object, *, run_id: UUID, **kwargs: object) -> None:
        """Keep the messages of a finished sub-agent run.

        Args:
            outputs: The run's output: a sub-agent's final state.
            run_id: Id of the run.
            **kwargs: Run details, unused.
        """
        with self._lock:
            name = self._open.pop(run_id, None)
        if name is None or not isinstance(outputs, dict):
            return
        found = outputs.get(_MESSAGES)
        listed = found if isinstance(found, list) else []
        messages = tuple(item for item in listed if isinstance(item, BaseMessage))
        with self._lock:
            self._runs.append(SubagentRun(name, messages))

    @override
    def on_chain_error(self, error: BaseException, *, run_id: UUID, **kwargs: object) -> None:
        """Forget a sub-agent run that failed.

        Args:
            error: The error, unused.
            run_id: Id of the run.
            **kwargs: Run details, unused.
        """
        with self._lock:
            self._open.pop(run_id, None)
