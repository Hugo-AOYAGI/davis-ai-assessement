import pytest

from agent.contracts.evidence import (
    Ambiguity,
    Citation,
    CitationCheck,
    Limit,
    Resolution,
    Rule,
    SourceKind,
)
from agent.contracts.findings.map import Overlay
from agent.contracts.findings.regulation import (
    Admissibility,
    ParkingBasis,
    ParkingRule,
    Verdict,
)
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


@pytest.fixture
def site():
    polygon = Polygon(crs="EPSG:2154", exterior=SQUARE)
    kinds = (BoundaryKind.ROAD, BoundaryKind.SIDE, BoundaryKind.REAR, BoundaryKind.SIDE)
    return SiteContext(
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
        method="geocoded, single parcel",
        assumptions=("Road limit is the southern edge.",),
        citations=(CADASTRE, GEOCODER),
    )


@pytest.fixture
def study():
    return Study(
        address="4 rue Joliot Curie, 91190 Gif-sur-Yvette",
        program="RSE + RJA, two buildings",
        regime=Regime(
            zone="UMG",
            overlays=(
                Overlay(name="Espace boisé classé", applies=False, rationale="none drawn"),
                Overlay(
                    name="Linéaire commercial",
                    applies=True,
                    rationale="along the street",
                    citations=(USES,),
                ),
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
        envelope=EnvelopeParameters(
            setback_road_m=limit(5, SETBACK),
            setback_side_m=limit(4),
            setback_rear_m=limit(4),
            max_height_m=limit(20),
            max_storeys=limit(6),
            max_footprint_ratio=limit(None),
            min_green_ratio=limit(0.2),
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


@pytest.fixture
def envelope():
    return Envelope(
        site_area_m2=1200,
        footprint=Polygon(crs="EPSG:2154", exterior=INNER),
        footprint_area_m2=651,
        max_footprint_area_m2=651,
        min_green_area_m2=240,
        max_height_m=20,
        max_volume_m3=13020,
        assumptions=("Setbacks applied as straight offsets.",),
    )


@pytest.fixture
def verified(study, site, envelope):
    return VerifiedStudy(study=study, site=site, envelope=envelope, citation_checks=CHECKS)
