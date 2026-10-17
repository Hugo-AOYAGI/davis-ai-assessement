import pytest

from agent.contracts.evidence import Citation, Limit, Rule, SourceKind
from agent.contracts.findings.map import Overlay
from agent.contracts.findings.regulation import (
    Admissibility,
    ParkingBasis,
    ParkingRule,
    Verdict,
)
from agent.contracts.findings.site import Parcel, SiteContext
from agent.contracts.geometry import Boundary, BoundaryKind, EnvelopeParameters, Polygon
from agent.contracts.study import Regime, Study

SQUARE = ((0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0), (0.0, 0.0))


@pytest.fixture
def citation() -> Citation:
    return Citation(
        doc="plu_reglement",
        page=327,
        article="UMG 10",
        quote="20 mètres",
        source_kind=SourceKind.REGULATORY,
    )


@pytest.fixture
def polygon() -> Polygon:
    return Polygon(crs="EPSG:2154", exterior=SQUARE)


@pytest.fixture
def site(polygon: Polygon) -> SiteContext:
    cadastre = Citation(doc="cadastre", quote="91272000AB0123", source_kind=SourceKind.GEOMETRIC)
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
        citations=(cadastre,),
    )


@pytest.fixture
def parameters(citation: Citation) -> EnvelopeParameters:
    def limit(value: float | None) -> Limit:
        return Limit(
            value=value, rule="see article", citations=() if value is None else (citation,)
        )

    return EnvelopeParameters(
        setback_road_m=limit(5),
        setback_side_m=limit(4),
        setback_rear_m=limit(4),
        max_height_m=limit(20),
        max_storeys=limit(6),
        max_footprint_ratio=limit(None),
        min_green_ratio=limit(0.2),
    )


@pytest.fixture
def study(citation: Citation, parameters: EnvelopeParameters) -> Study:
    return Study(
        address="4 rue Joliot Curie, 91190 Gif-sur-Yvette",
        program="RSE + RJA, two buildings",
        regime=Regime(
            zone="UMG",
            overlays=(Overlay(name="Espace boisé classé", applies=False, rationale="none drawn"),),
            oap_applicable=True,
            citations=(citation,),
        ),
        admissibility=(
            Admissibility(
                building="A",
                stated_use="Résidence sociale étudiante",
                destination="Habitation / Hébergement",
                verdict=Verdict.PERMITTED,
                citations=(citation,),
            ),
        ),
        envelope=parameters,
        parking=(
            ParkingRule(
                use="résidence étudiante",
                spaces=1,
                per=150,
                basis=ParkingBasis.FLOOR_AREA_M2,
                rule="1 place / 150 m² SDP",
                citations=(citation,),
            ),
        ),
        conditions=(
            Rule(topic="access", text="Access from a public road.", citations=(citation,)),
        ),
        ambiguities=(),
        summary="# Study",
    )
