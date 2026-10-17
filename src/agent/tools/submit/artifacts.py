from collections.abc import Mapping
from typing import Annotated, NotRequired

from langchain.agents.middleware import AgentMiddleware, AgentState
from pydantic import JsonValue

from agent.contracts.base import Contract

type ArtifactData = dict[str, JsonValue]
"""A contract dumped with ``model_dump(mode="json")``, so checkpointers can serialise it."""

type Artifacts = dict[str, ArtifactData]
"""Artifacts by name (``site``, ``map_findings``, ``study``...)."""


def merge_artifacts(left: Artifacts | None, right: Artifacts | None) -> Artifacts:
    """Merge two artifact mappings, the right one winning per key.

    Idempotent, which matters because a deepagents sub-agent returns its whole ``artifacts``
    mapping (the parent's snapshot plus its own writes) rather than a delta.

    Args:
        left: Current artifacts in the graph state.
        right: Update written by a node or tool.

    Returns:
        A new mapping holding the keys of both.
    """
    return {**(left or {}), **(right or {})}


class ArtifactsState(AgentState):
    """Agent state extended with the artifacts delivered through ``submit_<artifact>`` tools."""

    artifacts: NotRequired[Annotated[Artifacts, merge_artifacts]]


class ArtifactsMiddleware(AgentMiddleware):
    """Declares the ``artifacts`` state key.

    Add it to the orchestrator and to every sub-agent: a key a graph does not declare is dropped
    from its state, so a sub-agent's artifacts would not reach the parent.
    """

    state_schema = ArtifactsState


def read_artifact[C: Contract](
    artifacts: Mapping[str, ArtifactData] | None, key: str, contract: type[C]
) -> C | None:
    """Read a stored artifact back as its contract.

    Args:
        artifacts: The ``artifacts`` value of the graph state (absent before the first submit).
        key: Artifact name, e.g. ``site``.
        contract: Contract the artifact was stored from.

    Returns:
        The revalidated contract, or ``None`` when the artifact has not been submitted.
    """
    data = (artifacts or {}).get(key)
    return None if data is None else contract.model_validate(data)
