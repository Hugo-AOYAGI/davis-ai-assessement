import pytest

from agent.contracts.envelope import (
    BuildingLimits,
    Distance,
    EnvelopeRules,
    Layout,
    SetbackRule,
)
from agent.contracts.evidence import (
    Ambiguity,
    Citation,
    CitationCheck,
    ImageRegion,
    Limit,
    Resolution,
    SourceKind,
    StoredCrop,
)
from agent.contracts.findings.site import Edge, EdgeSide, Parcel, ParcelChoice, Site
from agent.contracts.findings.zone import LegendItem, ZoneFindings
from agent.contracts.geometry import Boundary, BoundaryKind, Polygon
from agent.contracts.study import Admissibility, Regime, Study, Verdict, VerifiedStudy
from agent.runtime.geometry.envelope.study import EnvelopeSettings, compute_envelope_study

SQUARE = ((0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0), (0.0, 0.0))
USES = Citation(
    doc="plu_reglement", page=321, quote="Sont autorisées", source_kind=SourceKind.REGULATORY
)
HEIGHT = Citation(
    doc="plu_reglement", page=327, quote="20 mètres", source_kind=SourceKind.REGULATORY
)
PLAN = Citation(doc="plu_graphique", page=1, quote="UMG", source_kind=SourceKind.REGULATORY)
CADASTRE = Citation(doc="cadastre", quote="91272000AB0123", source_kind=SourceKind.GEOMETRIC)
PLAN_REGION = ImageRegion(doc="plu_graphique", page=1, region=(10, 20, 110, 90))
CROP = StoredCrop(
    region=PLAN_REGION, pixels=(35, 70, 386, 316), path="data/crops/plu_graphique_p1.png"
)


def limit(value):
    return Limit(value=value, rule="see article", citations=() if value is None else (USES,))


def distance(min_m):
    return Distance(min_m=min_m, rule="see article", citations=(USES,))


@pytest.fixture
def verified():
    polygon = Polygon(crs="EPSG:2154", exterior=SQUARE)
    kinds = (BoundaryKind.ROAD, BoundaryKind.SIDE, BoundaryKind.REAR, BoundaryKind.SIDE)
    sides = (EdgeSide.PUBLIC_LAND, EdgeSide.PARCEL, EdgeSide.PARCEL, EdgeSide.PARCEL)
    site = Site(
        address="4 Rue Joliot Curie 91190 Gif-sur-Yvette",
        longitude=2.16,
        latitude=48.71,
        choice=ParcelChoice(
            address="4 Rue Joliot Curie 91190 Gif-sur-Yvette",
            parcel_ids=("91272000AB0123",),
            rationale="Only parcel at the address.",
        ),
        parcels=(Parcel(id="91272000AB0123", area_m2=1200, polygon=polygon),),
        polygon=polygon,
        area_m2=1200,
        edges=tuple(
            Edge(start=start, end=end, length_m=1, other_side=side)
            for side, start, end in zip(sides, SQUARE[:-1], SQUARE[1:], strict=True)
        ),
        citations=(CADASTRE,),
    )
    boundaries = tuple(
        Boundary(kind=kind, start=start, end=end)
        for kind, start, end in zip(kinds, SQUARE[:-1], SQUARE[1:], strict=True)
    )
    zone = ZoneFindings(
        zone="UMG",
        overlays=(LegendItem(item="Périmètre d'OAP", applies=True, note="site inside"),),
        rationale="Found by the road layout.",
        region=PLAN_REGION,
    )
    study = Study(
        address="4 rue Joliot Curie, 91190 Gif-sur-Yvette",
        program="RSE + RJA",
        regime=Regime(
            zone="UMG",
            overlays=(LegendItem(item="Périmètre d'OAP", applies=True, note="site inside"),),
            oap_applicable=True,
            citations=(USES,),
        ),
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
    rules = EnvelopeRules(
        setbacks=tuple(
            SetbackRule(kind=kind, on_limit_allowed=False, with_windows=distance(4))
            for kind in BoundaryKind
        ),
        buildings=tuple(
            BuildingLimits(building=label, max_height_m=limit(20), max_storeys=limit(6))
            for label in ("RSE", "RJA")
        ),
        spacing_with_windows=distance(10),
        spacing_without_windows=distance(6),
        max_footprint_ratio=limit(None),
        min_green_ratio=limit(0.2),
    )
    layout = Layout(
        cut="along_long_axis",
        first_share=0.5,
        order=("RSE", "RJA"),
        facing_windows=False,
        reasons="Halves.",
    )
    settings = EnvelopeSettings(level_step_m=1, quad_segs=8, min_area_m2=1, cut_tolerance_m=0.01)
    envelope = compute_envelope_study(polygon, boundaries, rules, layout, settings=settings)
    checks = (
        CitationCheck(citation=USES, verified=True, score=1.0),
        CitationCheck(citation=HEIGHT, verified=False, score=0.4),
        CitationCheck(citation=PLAN, verified=False, score=0.0, text_verifiable=False),
    )
    return VerifiedStudy(
        study=study,
        site=site,
        boundaries=boundaries,
        zone=zone,
        envelope=envelope,
        citation_checks=checks,
        evidence=(CROP,),
    )
