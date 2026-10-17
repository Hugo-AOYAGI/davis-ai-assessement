from enum import StrEnum

from pydantic import Field

from agent.contracts.base import Contract
from agent.contracts.evidence import Ambiguity, Citation, Rule
from agent.contracts.geometry import EnvelopeParameters


class Verdict(StrEnum):
    """Whether a use is allowed in the zone."""

    PERMITTED = "permitted"
    CONDITIONAL = "conditional"
    """Allowed subject to conditions set by the regulation."""
    RESTRICTED = "restricted"
    """Allowed only within limits (area, share of the program, location)."""
    PROHIBITED = "prohibited"


class Admissibility(Contract):
    """Whether one building's use is allowed in the zone."""

    building: str = Field(min_length=1)
    """Building label as given in the program."""
    stated_use: str = Field(min_length=1)
    """Use as the program states it, e.g. ``Résidence Jeunes Actifs``."""
    destination: str = Field(min_length=1)
    """Destination and sub-destination under the PLU it is classified into."""
    verdict: Verdict
    conditions: tuple[str, ...] = ()
    """Conditions or limits attached to the verdict."""
    citations: tuple[Citation, ...] = Field(min_length=1)


class ParkingBasis(StrEnum):
    """What a parking ratio is counted against."""

    FLOOR_AREA_M2 = "floor_area_m2"
    UNIT = "unit"
    """Dwelling or accommodation unit."""
    OTHER = "other"


class ParkingRule(Contract):
    """Car parking requirement for one use: ``spaces`` per ``per`` of ``basis``."""

    use: str = Field(min_length=1)
    """Use or destination the ratio applies to."""
    spaces: float = Field(ge=0)
    per: float = Field(gt=0)
    basis: ParkingBasis
    rule: str = Field(min_length=1)
    """The rule restated, with caps, exemptions and conditions."""
    citations: tuple[Citation, ...] = Field(min_length=1)


class RegulationFindings(Contract):
    """What the regulatory text says about the program on the site."""

    zone: str = Field(min_length=1)
    """Zone whose chapter was read."""
    admissibility: tuple[Admissibility, ...] = Field(min_length=1)
    """One entry per building of the program."""
    envelope: EnvelopeParameters
    parking: tuple[ParkingRule, ...]
    rules: tuple[Rule, ...]
    """Other applicable rules (access, networks, appearance...) in free text."""
    ambiguities: tuple[Ambiguity, ...] = ()
