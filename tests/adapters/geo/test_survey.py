import math

import httpx
import pytest

from agent.adapters.geo.cadastre import CadastreClient
from agent.adapters.geo.geocoder import AddressGeocoder
from agent.adapters.geo.http import CachedHttp, GeoServiceError
from agent.adapters.geo.records import SiteDraft, SiteError
from agent.adapters.geo.survey import SiteSurveyor
from agent.contracts.evidence import SourceKind
from agent.contracts.geometry import BoundaryKind

LON, LAT = 2.165254, 48.709836
LABEL = "4 Rue Joliot-curie 91190 Gif-sur-Yvette"
PLOT, STRIP = "91272000CR0247", "91272000CR0249"


def make_surveyor(http: CachedHttp) -> SiteSurveyor:
    return SiteSurveyor(
        geocoder=AddressGeocoder("https://data.geopf.fr/geocodage/search", http),
        cadastre=CadastreClient("https://apicarto.ign.fr/api/cadastre/parcelle", http, 500),
        crs="EPSG:2154",
        geographic_crs="EPSG:4326",
        decimals=2,
        grid_size_m=0.05,
        max_sliver_area_m2=1.0,
        neighbour_buffer_m=2.0,
        snap_tolerance_m=0.5,
        min_shared_ratio=0.5,
        collinear_angle_deg=20,
        geocoder_source="geocoder",
        cadastre_source="cadastre",
    )


@pytest.fixture
def surveyor(tmp_path, replay_transport) -> SiteSurveyor:
    return make_surveyor(CachedHttp(tmp_path, 5, replay_transport))


def lengths(draft: SiteDraft) -> dict[BoundaryKind, float]:
    totals = dict.fromkeys(BoundaryKind, 0.0)
    for boundary in draft.boundaries:
        totals[boundary.kind] += math.dist(boundary.start, boundary.end)
    return totals


def test_candidates_sorted_with_clues(surveyor):
    candidates = surveyor.candidates(LON, LAT, 50)
    distances = [c.distance_m for c in candidates]
    assert distances == sorted(distances)
    assert [c.id for c in candidates[:2]] == [STRIP, PLOT]
    by_id = {c.id: c for c in candidates}
    assert by_id[STRIP].mean_width_m < 1
    assert by_id[PLOT].mean_width_m > 10
    assert by_id[PLOT].contenance_m2 == 5960
    assert not any(c.contains_point for c in candidates)
    assert by_id[PLOT].distance_m == pytest.approx(2.5, abs=0.1)
    assert by_id[PLOT].touches == ("91272000CR0227", STRIP)


def test_draft_with_public_strip(surveyor):
    draft = surveyor.draft(LABEL, [PLOT], [STRIP])
    assert draft.area_m2 == pytest.approx(5952, abs=2)
    totals = lengths(draft)
    assert totals[BoundaryKind.ROAD] == pytest.approx(91, abs=2)
    assert totals[BoundaryKind.SIDE] == pytest.approx(90, abs=2)
    assert totals[BoundaryKind.REAR] == pytest.approx(127, abs=2)
    assert draft.nearest_boundary.kind is BoundaryKind.ROAD
    assert draft.nearest_distance_m == pytest.approx(2.5, abs=0.1)
    assert draft.polygon.crs == "EPSG:2154"
    assert [(p.id, p.area_m2) for p in draft.parcels] == [(PLOT, 5960)]
    neighbours = {n.id: n for n in draft.neighbours}
    assert set(neighbours) == {STRIP, "91272000CR0227", "91272000CR0256"}
    assert neighbours[STRIP].public
    assert neighbours[STRIP].mean_width_m < 1
    assert not neighbours["91272000CR0256"].public
    assert draft.address.label == LABEL


def test_draft_citations(surveyor):
    draft = surveyor.draft(LABEL, [PLOT], [STRIP])
    assert [(c.doc, c.quote) for c in draft.citations] == [
        ("geocoder", f"label={LABEL}; id=91272_1599_00004; lon={LON}; lat={LAT}"),
        ("cadastre", f"idu={PLOT}; contenance=5960"),
        ("cadastre", f"idu={STRIP}; contenance=116"),
    ]
    assert all(c.source_kind is SourceKind.GEOMETRIC and c.page is None for c in draft.citations)


def test_draft_strip_as_neighbour_is_all_rear(surveyor):
    draft = surveyor.draft(LABEL, [PLOT], [])
    assert {b.kind for b in draft.boundaries} == {BoundaryKind.REAR}
    assert draft.nearest_boundary.kind is BoundaryKind.REAR


def test_draft_merged_strip(surveyor):
    draft = surveyor.draft(LABEL, [PLOT, STRIP, PLOT], [])
    assert draft.area_m2 == pytest.approx(6071, abs=2)
    assert [p.id for p in draft.parcels] == [PLOT, STRIP]
    totals = lengths(draft)
    assert totals[BoundaryKind.ROAD] == pytest.approx(91, abs=2)
    assert totals[BoundaryKind.REAR] == pytest.approx(127, abs=2)
    assert draft.nearest_boundary.kind is BoundaryKind.ROAD
    assert STRIP not in {n.id for n in draft.neighbours}


def test_label_is_case_and_space_insensitive(surveyor):
    draft = surveyor.draft("  4 rue joliot-curie   91190 GIF-SUR-YVETTE", [PLOT], [STRIP])
    assert draft.address.label == LABEL


@pytest.mark.parametrize(
    ("address", "parcels", "public", "message"),
    [
        ("4 rue Joliot Curie, Gif", [PLOT], [], "exactly as geocode_address returned it"),
        (LABEL, ["91272000CR9999"], [], "91272000CR9999 is not in the cadastre"),
        (LABEL, ["CR0247"], [], "14 characters"),
        (LABEL, [], [], "parcel_ids is empty"),
        (LABEL, [PLOT], ["91272000CR0215"], r"\['91272000CR0215'\] are not neighbours"),
        (LABEL, [PLOT, STRIP], [STRIP], "both in parcel_ids and public_parcel_ids"),
        (LABEL, [PLOT, "91272000CR0215"], [], "2 separate parts"),
    ],
)
def test_draft_errors(surveyor, address, parcels, public, message):
    with pytest.raises(SiteError, match=message):
        surveyor.draft(address, parcels, public)


def test_service_errors_propagate(tmp_path):
    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="maintenance")

    surveyor = make_surveyor(CachedHttp(tmp_path, 5, httpx.MockTransport(broken)))
    with pytest.raises(GeoServiceError, match="503"):
        surveyor.candidates(LON, LAT, 50)
