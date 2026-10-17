import pytest

from agent.contracts.envelope import (
    BuildingLimits,
    Distance,
    EnvelopeRules,
    EnvelopeStudy,
    Layout,
    SetbackRule,
)
from agent.contracts.evidence import Citation, ImageRegion, Limit, Rule, SourceKind
from agent.contracts.findings.site import Edge, EdgeSide, Parcel, ParcelChoice, Site
from agent.contracts.findings.zone import LegendItem, ZoneFindings
from agent.contracts.geometry import BoundaryKind, BuildingMassing, Level, Polygon, Scenario
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


def _limit(value: float | None, citation: Citation) -> Limit:
    return Limit(value=value, rule="see article", citations=() if value is None else (citation,))


@pytest.fixture
def rules(citation: Citation) -> EnvelopeRules:
    def distance(min_m: float) -> Distance:
        return Distance(min_m=min_m, rule="see article", citations=(citation,))

    return EnvelopeRules(
        setbacks=(
            SetbackRule(kind=BoundaryKind.ROAD, on_limit_allowed=True, without_windows=distance(1)),
            SetbackRule(kind=BoundaryKind.SIDE, on_limit_allowed=False, with_windows=distance(6)),
            SetbackRule(kind=BoundaryKind.REAR, on_limit_allowed=False, with_windows=distance(6)),
        ),
        buildings=(
            BuildingLimits(
                building="A",
                max_height_m=_limit(20, citation),
                max_storeys=_limit(6, citation),
            ),
            BuildingLimits(
                building="B",
                max_height_m=_limit(18, citation),
                max_storeys=_limit(None, citation),
            ),
        ),
        spacing_with_windows=distance(10),
        spacing_without_windows=distance(6),
        max_footprint_ratio=_limit(None, citation),
        min_green_ratio=_limit(0.2, citation),
    )


@pytest.fixture
def layout() -> Layout:
    return Layout(
        cut="across_long_axis",
        first_share=0.5,
        order=("A", "B"),
        facing_windows=True,
        heights_m=(15, 18),
        reasons="Halves.",
    )


@pytest.fixture
def envelope(rules: EnvelopeRules, layout: Layout, polygon: Polygon) -> EnvelopeStudy:
    massing = BuildingMassing(
        building="A",
        footprint=polygon,
        footprint_area_m2=1200,
        max_height_m=20,
        levels=(Level(from_m=0, to_m=20, area_m2=1200),),
        volume_m3=24000,
    )
    bound = Scenario(
        name="windows",
        footprint=polygon,
        footprint_area_m2=1200,
        buildings=(massing,),
        fits=True,
        total_volume_m3=24000,
    )
    return EnvelopeStudy(
        rules=rules,
        layout=layout,
        site_area_m2=1200,
        min_green_area_m2=240,
        bounds=(bound,),
        proposal=bound.model_copy(update={"name": "proposal"}),
    )


@pytest.fixture
def study(citation: Citation) -> Study:
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
