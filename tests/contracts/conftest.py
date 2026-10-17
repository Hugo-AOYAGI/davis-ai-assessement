import pytest

from agent.contracts.evidence import Citation, ImageRegion, Limit, Rule, SourceKind
from agent.contracts.findings.site import Edge, EdgeSide, Parcel, ParcelChoice, Site
from agent.contracts.findings.zone import LegendItem, ZoneFindings
from agent.contracts.geometry import EnvelopeParameters, Polygon
from agent.contracts.study import (
    Admissibility,
    ParkingBasis,
    ParkingRule,
    Regime,
    Study,
    Verdict,
)

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
def site(polygon: Polygon) -> Site:
    cadastre = Citation(doc="cadastre", quote="91272000AB0123", source_kind=SourceKind.GEOMETRIC)
    sides = (EdgeSide.PUBLIC_LAND, EdgeSide.PARCEL, EdgeSide.PARCEL, EdgeSide.PARCEL)
    return Site(
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
        citations=(cadastre,),
    )


@pytest.fixture
def zone() -> ZoneFindings:
    return ZoneFindings(
        zone="UMG",
        overlays=(LegendItem(item="Espace boisé classé", applies=False, note="none drawn"),),
        rationale="Site found by the road layout.",
        region=ImageRegion(doc="plu_reglement_graphique", page=1, region=(10, 20, 110, 90)),
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
            overlays=(LegendItem(item="Périmètre d'OAP", applies=True, note="site inside"),),
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
