from pydantic import Field

from agent.contracts.base import Contract


class Case(Contract):
    """One run's input: what to study, and against which corpus."""

    address: str = Field(min_length=1)
    program: str = Field(min_length=1)
    """Program as free text, read directly by the agent."""
    corpus_id: str = Field(min_length=1)
    """Ingested corpus, e.g. ``gif-sur-yvette@2021-07-06``."""
    facts: tuple[str, ...] = ()
    """Program facts supplied up front, standing in for ``ask_user`` answers in evals."""
