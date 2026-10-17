from pydantic import Field

from agent.contracts.base import Contract
from agent.contracts.evidence import Ambiguity, Citation, Rule


class OAPFindings(Contract):
    """Whether an OAP covers the site and what it prescribes (compatibility, not conformity)."""

    applicable: bool
    name: str | None
    """Title of the applicable OAP, ``None`` when none applies."""
    prescriptions: tuple[Rule, ...] = ()
    """Orientations relevant to the program, in free text."""
    rationale: str = Field(min_length=1)
    citations: tuple[Citation, ...] = Field(min_length=1)
    ambiguities: tuple[Ambiguity, ...] = ()
