from enum import StrEnum

from pydantic import Field

from agent.contracts.base import Contract
from agent.contracts.envelope import EnvelopeStudy
from agent.contracts.evidence import Ambiguity, Citation, CitationCheck, Rule, StoredCrop
from agent.contracts.findings.site import Site
from agent.contracts.findings.zone import LegendItem, ZoneFindings
from agent.contracts.geometry import Boundary


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


class Regime(Contract):
    """The regulatory regime applying to the site."""

    zone: str = Field(min_length=1)
    overlays: tuple[LegendItem, ...]
    """The zoning plan legend items that apply to the site."""
    oap_applicable: bool
    oap_prescriptions: tuple[Rule, ...] = ()
    citations: tuple[Citation, ...] = Field(min_length=1)


class Study(Contract):
    """The buildability study.

    The site and the envelope are not part of it: the gate reads the `site` artifact built from
    the surveyor's choice and labels its edges, reads the architect's `envelope` artifact and
    recomputes it, and returns both once the study is accepted.
    """

    address: str = Field(min_length=1)
    program: str = Field(min_length=1)
    regime: Regime
    admissibility: tuple[Admissibility, ...] = Field(min_length=1)
    """One entry per building of the program."""
    parking: tuple[ParkingRule, ...]
    conditions: tuple[Rule, ...]
    """Other feasibility conditions: access, networks, appearance..."""
    ambiguities: tuple[Ambiguity, ...]
    summary: str = Field(min_length=1)
    """Markdown narrative for a human reader: reasoning, conclusions, caveats."""


class VerifiedStudy(Contract):
    """A study accepted by the ``submit_study`` gate, with what the gate computed."""

    study: Study
    site: Site
    boundaries: tuple[Boundary, ...]
    """The site's edges labelled road / side / rear by the gate."""
    zone: ZoneFindings
    envelope: EnvelopeStudy
    """The architect's envelope, recomputed by the gate from its rules and layout."""
    citation_checks: tuple[CitationCheck, ...]
    """One check per distinct regulatory citation of ``study``, then of ``envelope``.

    Geometric citations are not checked against the corpus and have no entry. Citations of a
    raster document (no text layer) have an entry with ``text_verifiable`` False unless the
    configuration asks for them to be text-checked.
    """
    evidence: tuple[StoredCrop, ...]
    """Image regions saved as evidence: the zoning plan region and every note view."""
