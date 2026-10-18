"""Capture graph messages for scoring, including runs that end in an exception.

Each delegation owns its descendant callbacks. Node outputs update that run's message
history; a successful root output replaces it with the authoritative final state.
"""

import threading
from collections.abc import Iterable
from typing import NamedTuple, override
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.messages.utils import MessageLikeRepresentation
from langchain_core.outputs import ChatGeneration, LLMResult
from langgraph.graph.message import add_messages


class SubagentRun(NamedTuple):
    """Messages of one completed or failed delegated run."""

    name: str
    messages: tuple[BaseMessage, ...]


class RunCapture(BaseCallbackHandler):
    """Keep the root graph and delegated histories, isolated across parallel branches."""

    def __init__(self, names: Iterable[str]) -> None:
        """Watch delegated graphs named in ``names`` and the outermost graph."""
        super().__init__()
        self._names = frozenset(names)
        self._lock = threading.RLock()
        self._owners: dict[UUID, UUID] = {}
        self._histories: dict[UUID, list[BaseMessage]] = {}
        self._delegated: dict[UUID, str] = {}
        self._root: UUID | None = None
        self._runs: list[SubagentRun] = []

    @property
    def messages(self) -> tuple[BaseMessage, ...]:
        """The outer graph's latest messages, even when it failed."""
        with self._lock:
            return tuple(self._histories.get(self._root, ())) if self._root else ()

    @property
    def runs(self) -> tuple[SubagentRun, ...]:
        """Finished delegated runs in completion order, including failed runs."""
        with self._lock:
            return tuple(self._runs)

    def _update(self, owner: UUID, value: object, *, replace: bool = False) -> None:
        """Merge a state update without duplicating messages with the same LangGraph id."""
        found = value.get("messages") if isinstance(value, dict) else value
        listed = found if isinstance(found, (list, tuple)) else [found]
        messages = [item for item in listed if isinstance(item, BaseMessage)]
        if messages or (replace and isinstance(found, (list, tuple))):
            left: list[MessageLikeRepresentation] = list(self._histories.get(owner, []))
            right: list[MessageLikeRepresentation] = list(messages)
            merged = messages if replace else add_messages(left, right)
            self._histories[owner] = [item for item in merged if isinstance(item, BaseMessage)]

    @override
    def on_chain_start(
        self,
        serialized: object,
        inputs: object,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: object,
    ) -> None:
        """Associate each chain with its graph, starting a separate history per delegation."""
        with self._lock:
            parent = self._owners.get(parent_run_id) if parent_run_id else None
            name = kwargs.get("name")
            if parent is None:
                self._root = run_id
                owner = run_id
            elif isinstance(name, str) and name in self._names:
                owner = run_id
                self._delegated[run_id] = name
            else:
                owner = parent
            self._owners[run_id] = owner
            if isinstance(inputs, dict):
                self._update(owner, inputs)

    @override
    def on_chain_end(self, outputs: object, *, run_id: UUID, **kwargs: object) -> None:
        """Store node updates and a completed graph's authoritative final history."""
        with self._lock:
            owner = self._owners.pop(run_id, None)
            if owner is None:
                return
            if isinstance(outputs, dict):
                self._update(owner, outputs, replace=owner == run_id)
            self._finish(run_id)

    @override
    def on_chain_error(self, error: BaseException, *, run_id: UUID, **kwargs: object) -> None:
        """Retain all updates observed before a graph failed."""
        with self._lock:
            self._owners.pop(run_id, None)
            self._finish(run_id)

    @override
    def on_tool_start(
        self,
        serialized: object,
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: object,
    ) -> None:
        """Propagate ownership through tools that invoke delegated graphs."""
        with self._lock:
            owner = self._owners.get(parent_run_id) if parent_run_id else None
            if owner is not None:
                self._owners[run_id] = owner

    @override
    def on_tool_end(self, output: object, *, run_id: UUID, **kwargs: object) -> None:
        """Keep a tool reply even if the following graph node fails."""
        with self._lock:
            owner = self._owners.pop(run_id, None)
            if owner is not None:
                self._update(owner, output)

    @override
    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: object) -> None:
        """Release the ownership entry of a failed tool."""
        with self._lock:
            self._owners.pop(run_id, None)

    @override
    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: object,
    ) -> None:
        """Keep model replies before their surrounding node finishes."""
        with self._lock:
            owner = self._owners.get(parent_run_id) if parent_run_id else None
            if owner is not None:
                self._update(
                    owner,
                    [
                        generation.message
                        for batch in response.generations
                        for generation in batch
                        if isinstance(generation, ChatGeneration)
                    ],
                )

    def _finish(self, run_id: UUID) -> None:
        """Publish a delegated history exactly once."""
        name = self._delegated.pop(run_id, None)
        if name is not None:
            self._runs.append(SubagentRun(name, tuple(self._histories.pop(run_id, ()))))
