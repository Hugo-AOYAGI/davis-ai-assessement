import pytest

from agent.contracts.evidence import (
    Ambiguity,
    Citation,
    CitationCheck,
    Limit,
    Resolution,
    SourceKind,
)
from agent.contracts.findings.regulation import Admissibility, Verdict
from agent.contracts.findings.site import Parcel, SiteContext
from agent.contracts.geometry import (
    Boundary,
    BoundaryKind,
    Envelope,
    EnvelopeParameters,
    Polygon,
)
from agent.contracts.study import Regime, Study, VerifiedStudy

SQUARE = ((0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0), (0.0, 0.0))
USES = Citation(
    doc="plu_reglement", page=321, quote="Sont autorisées", source_kind=SourceKind.REGULATORY
)
HEIGHT = Citation(
    doc="plu_reglement", page=327, quote="20 mètres", source_kind=SourceKind.REGULATORY
)
PLAN = Citation(doc="plu_graphique", page=1, quote="UMG", source_kind=SourceKind.REGULATORY)
CADASTRE = Citation(doc="cadastre", quote="91272000AB0123", source_kind=SourceKind.GEOMETRIC)


def limit(value):
    return Limit(value=value, rule="see article", citations=() if value is None else (USES,))


@pytest.fixture
def verified():
    polygon = Polygon(crs="EPSG:2154", exterior=SQUARE)
    kinds = (BoundaryKind.ROAD, BoundaryKind.SIDE, BoundaryKind.REAR, BoundaryKind.SIDE)
    site = SiteContext(
        address="4 Rue Joliot Curie 91190 Gif-sur-Yvette",
        longitude=2.16,
        latitude=48.71,
        parcels=(Parcel(id="91272000AB0123", area_m2=1200, polygon=polygon),),
        polygon=polygon,
        area_m2=1200,
        boundaries=tuple(
            Boundary(kind=kind, start=start, end=end)
            for kind, start, end in zip(kinds, SQUARE[:-1], SQUARE[1:], strict=True)
        ),
        method="geocoded",
        citations=(CADASTRE,),
    )
    study = Study(
        address="4 rue Joliot Curie, 91190 Gif-sur-Yvette",
        program="RSE + RJA",
        regime=Regime(zone="UMG", overlays=(), oap_applicable=False, citations=(USES,)),
        admissibility=(
            Admissibility(
                building="RSE",
                stated_use="Résidence sociale étudiante",
                destination="Habitation / Hébergement",
                verdict=Verdict.PERMITTED,
                citations=(USES,),
            ),
            Admissibility(
                building="RJA",
                stated_use="Résidence Jeunes Actifs",
                destination="Habitation / Hébergement",
                verdict=Verdict.CONDITIONAL,
                citations=(USES,),
            ),
        ),
        envelope=EnvelopeParameters(
            setback_road_m=limit(5),
            setback_side_m=limit(4),
            setback_rear_m=limit(4),
            max_height_m=limit(20),
            max_storeys=limit(6),
            max_footprint_ratio=limit(None),
            min_green_ratio=limit(0.2),
        ),
        parking=(),
        conditions=(),
        ambiguities=(
            Ambiguity(
                question="Is the RJA a hébergement?",
                chosen="hébergement",
                rationale="Managed residence.",
                resolved_by=Resolution.AGENT,
            ),
        ),
        summary="Buildable.",
    )
    envelope = Envelope(
        site_area_m2=1200,
        footprint=None,
        footprint_area_m2=651,
        max_footprint_area_m2=651,
        min_green_area_m2=240,
        max_height_m=20,
        max_volume_m3=13020,
    )
    checks = (
        CitationCheck(citation=USES, verified=True, score=1.0),
        CitationCheck(citation=HEIGHT, verified=False, score=0.4),
        CitationCheck(citation=PLAN, verified=False, score=0.0, text_verifiable=False),
    )
    return VerifiedStudy(study=study, site=site, envelope=envelope, citation_checks=checks)
