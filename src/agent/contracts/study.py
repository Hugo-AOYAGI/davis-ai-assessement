from pydantic import Field

from agent.contracts.base import Contract
from agent.contracts.evidence import Ambiguity, Citation, CitationCheck, Rule
from agent.contracts.findings.map import Overlay
from agent.contracts.findings.regulation import Admissibility, ParkingRule
from agent.contracts.findings.site import SiteContext
from agent.contracts.geometry import Envelope, EnvelopeParameters


class Regime(Contract):
    """The regulatory regime applying to the site."""

    zone: str = Field(min_length=1)
    overlays: tuple[Overlay, ...]
    """Every plan feature checked, including those that do not apply."""
    oap_applicable: bool
    oap_prescriptions: tuple[Rule, ...] = ()
    citations: tuple[Citation, ...] = Field(min_length=1)


class Study(Contract):
    """The buildability study, submitted through ``submit_study``.

    The site is not part of it: the gate takes the ``SiteContext`` submitted by ``site_locator``.
    """

    address: str = Field(min_length=1)
    program: str = Field(min_length=1)
    regime: Regime
    admissibility: tuple[Admissibility, ...] = Field(min_length=1)
    """One entry per building of the program."""
    envelope: EnvelopeParameters
    parking: tuple[ParkingRule, ...]
    conditions: tuple[Rule, ...]
    """Other feasibility conditions: access, networks, appearance..."""
    ambiguities: tuple[Ambiguity, ...]
    summary: str = Field(min_length=1)
    """Markdown narrative for a human reader: reasoning, conclusions, caveats."""


class VerifiedStudy(Contract):
    """A study accepted by the ``submit_study`` gate, with what the gate computed."""

    study: Study
    site: SiteContext
    envelope: Envelope
    citation_checks: tuple[CitationCheck, ...]
    """One check per distinct regulatory citation found anywhere in ``study``.

    Geometric citations are not checked against the corpus and have no entry.
    """
