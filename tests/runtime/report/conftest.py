import pytest

from agent.contracts.envelope import (
    BuildingLimits,
    Distance,
    EnvelopeRules,
    Layout,
    OapChoice,
    SetbackRule,
)
from agent.contracts.evidence import (
    Ambiguity,
    Citation,
    CitationCheck,
    ImageRegion,
    Limit,
    Resolution,
    Rule,
    SourceKind,
    StoredCrop,
)
from agent.contracts.findings.site import Edge, EdgeSide, Parcel, ParcelChoice, Site
from agent.contracts.findings.zone import LegendItem, ZoneFindings
from agent.contracts.geometry import Boundary, BoundaryKind, Polygon
from agent.contracts.study import (
    Admissibility,
    ParkingBasis,
    ParkingRule,
    Regime,
    Study,
    Verdict,
    VerifiedStudy,
)
from agent.runtime.geometry.envelope.study import EnvelopeSettings, compute_envelope_study

SQUARE = ((0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0), (0.0, 0.0))
INNER = ((5.0, 4.0), (36.0, 4.0), (36.0, 25.0), (5.0, 25.0), (5.0, 4.0))


def regulatory(page, article, quote):
    return Citation(
        doc="plu_reglement",
        page=page,
        article=article,
        quote=quote,
        source_kind=SourceKind.REGULATORY,
    )


HEIGHT = regulatory(327, "UMG 10", "La hauteur maximale est fixée à 20 mètres")
SETBACK = regulatory(325, "UMG 6", "Recul minimal de 5 mètres | par rapport à l'alignement")
USES = regulatory(321, "UMG 1", "Sont autorisées les constructions à destination d'habitation")
PARKING = regulatory(329, "UMG 12", "1 place pour 150 m² de surface de plancher")
OAP = Citation(
    doc="oap",
    page=34,
    article="Joliot Curie",
    quote="Préserver une frange paysagère " + "le long de la rue " * 20,
    source_kind=SourceKind.REGULATORY,
)
CADASTRE = Citation(doc="cadastre", quote="91272000AB0123", source_kind=SourceKind.GEOMETRIC)
GEOCODER = Citation(doc="ban", quote="4 Rue Joliot Curie", source_kind=SourceKind.GEOMETRIC)

CHECKS = (
    CitationCheck(citation=HEIGHT, verified=True, score=0.987),
    CitationCheck(citation=SETBACK, verified=True, score=0.91, matched_page=326),
    CitationCheck(citation=USES, verified=True, score=1.0),
    CitationCheck(citation=PARKING, verified=False, score=0.4321),
    CitationCheck(citation=OAP, verified=True, score=0.95),
)


def limit(value, citation=HEIGHT):
    return Limit(value=value, rule="see article", citations=() if value is None else (citation,))


KINDS = (BoundaryKind.ROAD, BoundaryKind.SIDE, BoundaryKind.REAR, BoundaryKind.SIDE)
PLAN = ImageRegion(doc="plu_reglement_graphique", page=1, region=(10, 20, 110, 90))
DIAGRAM = ImageRegion(doc="oap", page=34, region=(120, 400, 900, 1100))


@pytest.fixture
def site():
    polygon = Polygon(crs="EPSG:2154", exterior=SQUARE)
    sides = (EdgeSide.PUBLIC_LAND, EdgeSide.PARCEL, EdgeSide.PARCEL, EdgeSide.PARCEL)
    return Site(
        address="4 Rue Joliot Curie 91190 Gif-sur-Yvette",
        longitude=2.16,
        latitude=48.71,
        choice=ParcelChoice(
            address="4 Rue Joliot Curie 91190 Gif-sur-Yvette",
            parcel_ids=("91272000AB0123",),
            rationale="Address point 2.5 m from AB0123; AB0124 rejected: 116 m² strip.",
            assumptions=("Cadastre is current.",),
        ),
        parcels=(Parcel(id="91272000AB0123", area_m2=1200, polygon=polygon),),
        polygon=polygon,
        area_m2=1200,
        edges=tuple(
            Edge(start=start, end=end, length_m=1, other_side=side)
            for side, start, end in zip(sides, SQUARE[:-1], SQUARE[1:], strict=True)
        ),
        citations=(CADASTRE, GEOCODER),
    )


@pytest.fixture
def boundaries():
    return tuple(
        Boundary(kind=kind, start=start, end=end)
        for kind, start, end in zip(KINDS, SQUARE[:-1], SQUARE[1:], strict=True)
    )


@pytest.fixture
def zone():
    return ZoneFindings(
        zone="UMG",
        overlays=(
            LegendItem(item="Espace boisé classé", applies=False, note="none drawn"),
            LegendItem(item="Linéaire commercial", applies=True, note="along the street"),
        ),
        rationale="Site found by the road layout near the Saclay limit.",
        region=PLAN,
    )


@pytest.fixture
def study():
    return Study(
        address="4 rue Joliot Curie, 91190 Gif-sur-Yvette",
        program="RSE + RJA, two buildings",
        regime=Regime(
            zone="UMG",
            overlays=(
                LegendItem(item="Linéaire commercial", applies=True, note="along the street"),
            ),
            oap_applicable=True,
            oap_prescriptions=(
                Rule(topic="landscape", text="Keep a planted strip.", citations=(OAP,)),
            ),
            citations=(USES, HEIGHT),
        ),
        admissibility=(
            Admissibility(
                building="A",
                stated_use="Résidence sociale étudiante",
                destination="Habitation / Hébergement",
                verdict=Verdict.PERMITTED,
                citations=(USES,),
            ),
            Admissibility(
                building="B",
                stated_use="Résidence Jeunes Actifs",
                destination="Habitation / Hébergement",
                verdict=Verdict.CONDITIONAL,
                conditions=("Social mix required",),
                citations=(USES,),
            ),
        ),
        parking=(
            ParkingRule(
                use="résidence étudiante",
                spaces=1,
                per=150,
                basis=ParkingBasis.FLOOR_AREA_M2,
                rule="1 place / 150 m² SDP",
                citations=(PARKING,),
            ),
        ),
        conditions=(Rule(topic="access", text="Access from a public road.", citations=(HEIGHT,)),),
        ambiguities=(
            Ambiguity(
                question="Is the RJA a hébergement?",
                options=("hébergement", "logement"),
                chosen="hébergement",
                rationale="Managed residence with shared services.",
                resolved_by=Resolution.AGENT,
                citations=(USES,),
            ),
        ),
        summary="The program is **buildable** in zone UMG.",
    )


def distance(min_m, citation=HEIGHT):
    return Distance(min_m=min_m, rule="see article", citations=(citation,))


@pytest.fixture
def rules():
    return EnvelopeRules(
        setbacks=(
            SetbackRule(
                kind=BoundaryKind.ROAD,
                on_limit_allowed=False,
                with_windows=distance(5, SETBACK),
            ),
            SetbackRule(kind=BoundaryKind.SIDE, on_limit_allowed=False, with_windows=distance(4)),
            SetbackRule(kind=BoundaryKind.REAR, on_limit_allowed=True, without_windows=distance(4)),
        ),
        buildings=(
            BuildingLimits(building="A", max_height_m=limit(20), max_storeys=limit(6)),
            BuildingLimits(building="B", max_height_m=limit(18), max_storeys=limit(None)),
        ),
        spacing_with_windows=distance(10),
        spacing_without_windows=distance(6),
        max_footprint_ratio=limit(None),
        min_green_ratio=limit(0.2),
    )


@pytest.fixture
def layout():
    return Layout(
        cut="along_long_axis",
        first_share=0.5,
        order=("A", "B"),
        facing_windows=False,
        oap=(
            OapChoice(
                prescription=Rule(
                    topic="landscape", text="Keep a planted strip.", citations=(OAP,)
                ),
                how="B set back behind the strip.",
            ),
        ),
        reasons="A on the street, B at the back.",
    )


@pytest.fixture
def envelope(rules, layout, site, boundaries):
    settings = EnvelopeSettings(level_step_m=1, quad_segs=8, min_area_m2=1, cut_tolerance_m=0.01)
    return compute_envelope_study(site.polygon, boundaries, rules, layout, settings=settings)


@pytest.fixture
def verified(study, site, boundaries, zone, envelope):
    return VerifiedStudy(
        study=study,
        site=site,
        boundaries=boundaries,
        zone=zone,
        envelope=envelope,
        citation_checks=CHECKS,
        evidence=(
            StoredCrop(
                region=PLAN,
                pixels=(35, 70, 386, 316),
                path="data/crops/plu_reglement_graphique_p1_10-20-110-90.png",
            ),
            StoredCrop(
                region=DIAGRAM,
                pixels=(240, 800, 1800, 2200),
                path="data/crops/oap_p34_120-400-900-1100.png",
            ),
        ),
    )
