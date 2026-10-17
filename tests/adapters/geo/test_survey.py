import pytest

from agent.adapters.geo.records import SiteError
from agent.adapters.http import ServiceError
from agent.contracts.evidence import SourceKind
from agent.contracts.findings.site import EdgeSide, ParcelChoice, PublicParcel
from agent.contracts.geometry import BoundaryKind
from agent.runtime.geometry.edges import label_edges

LON, LAT = 2.165254, 48.709836
LABEL = "4 Rue Joliot-curie 91190 Gif-sur-Yvette"
PLOT, STRIP = "91272000CR0247", "91272000CR0249"
WEST, EAST, FAR = "91272000CR0227", "91272000CR0256", "91272000CR0215"


def choice(*ids: str, address: str = LABEL) -> ParcelChoice:
    return ParcelChoice(address=address, parcel_ids=ids, rationale="test")


def lengths(edges) -> dict[EdgeSide, float]:
    totals = dict.fromkeys(EdgeSide, 0.0)
    for edge in edges:
        totals[edge.other_side] += edge.length_m
    return totals


def test_candidates_put_the_strip_first(surveyor):
    candidates = surveyor.candidates(LON, LAT, 50)
    distances = [c.distance_m for c in candidates]
    assert distances == sorted(distances)
    assert [c.id for c in candidates[:2]] == [STRIP, PLOT]
    by_id = {c.id: c for c in candidates}
    assert by_id[STRIP].mean_width_m < 1
    assert by_id[STRIP].distance_m == pytest.approx(1.8, abs=0.1)
    assert by_id[PLOT].mean_width_m > 10
    assert by_id[PLOT].contenance_m2 == 5960
    assert by_id[PLOT].distance_m == pytest.approx(2.5, abs=0.1)
    assert by_id[PLOT].touches == (WEST, STRIP)
    assert not any(c.contains_point for c in candidates)


def test_describe_plot_alone_is_enclosed_by_the_strip(surveyor):
    description = surveyor.describe(LON, LAT, [PLOT])
    assert description.one_piece
    assert description.area_m2 == pytest.approx(5952, abs=2)
    assert description.distance_m == pytest.approx(2.5, abs=0.1)
    edges = {total.other_side: total for total in description.edges}
    assert edges[EdgeSide.PUBLIC_LAND].count == 0
    assert edges[EdgeSide.PARCEL].length_m == pytest.approx(308, abs=2)
    neighbours = [n.id for n in description.neighbours]
    assert neighbours == [STRIP, EAST, WEST]
    assert description.neighbours[0].mean_width_m < 1


def test_describe_plot_with_strip_faces_the_street(surveyor):
    description = surveyor.describe(LON, LAT, [PLOT, STRIP])
    assert description.one_piece
    assert description.area_m2 == pytest.approx(6071, abs=2)
    assert [p.touches for p in description.parcels] == [(STRIP,), (PLOT,)]
    edges = {total.other_side: total for total in description.edges}
    assert edges[EdgeSide.PUBLIC_LAND].length_m == pytest.approx(91, abs=2)
    assert {n.id for n in description.neighbours} == {EAST, WEST}


def test_describe_disjoint_parcels(surveyor):
    description = surveyor.describe(LON, LAT, [PLOT, FAR])
    assert not description.one_piece
    assert len(description.part_areas_m2) == 2
    assert description.area_m2 is None
    assert description.edges == ()
    assert description.neighbours == ()


def test_site_from_the_plot(surveyor):
    site = surveyor.site(choice(PLOT))
    assert site.address == LABEL
    assert (site.longitude, site.latitude) == (LON, LAT)
    assert site.choice == choice(PLOT)
    assert [(p.id, p.area_m2) for p in site.parcels] == [(PLOT, 5960)]
    assert site.polygon.crs == "EPSG:2154"
    assert site.area_m2 == pytest.approx(5952, abs=2)
    assert {edge.other_side for edge in site.edges} == {EdgeSide.PARCEL}
    across = {pid for edge in site.edges for pid in edge.neighbours}
    assert across == {STRIP, EAST, WEST}
    assert len(site.edges) == len(site.polygon.exterior) - 1


def test_site_with_the_strip_has_street_edges(surveyor):
    site = surveyor.site(choice(PLOT, STRIP, PLOT))
    assert [p.id for p in site.parcels] == [PLOT, STRIP]
    totals = lengths(site.edges)
    assert totals[EdgeSide.PUBLIC_LAND] == pytest.approx(91, abs=2)
    assert totals[EdgeSide.PARCEL] == pytest.approx(219, abs=2)
    public = [edge for edge in site.edges if edge.other_side is EdgeSide.PUBLIC_LAND]
    assert all(edge.neighbours == () for edge in public)


def with_public_strip() -> ParcelChoice:
    return choice(PLOT).model_copy(
        update={"public_parcels": (PublicParcel(id=STRIP, reason="pavement"),)}
    )


def kinds(edges) -> list[BoundaryKind]:
    labelled = label_edges(edges, snap_tolerance_m=0.5, collinear_angle_deg=20)
    return [boundary.kind for boundary in labelled]


def test_strip_declared_public_turns_the_street_edges_to_public_land(surveyor):
    site = surveyor.site(with_public_strip())
    assert site.choice == with_public_strip()
    assert [p.id for p in site.parcels] == [PLOT]
    assert lengths(site.edges)[EdgeSide.PUBLIC_LAND] == pytest.approx(91, abs=2)
    public = [edge for edge in site.edges if edge.other_side is EdgeSide.PUBLIC_LAND]
    assert all(edge.neighbours == (STRIP,) for edge in public)
    mixed = [edge for edge in site.edges if len(edge.neighbours) > 1]
    assert mixed
    assert all(edge.other_side is EdgeSide.PARCEL for edge in mixed)


def test_gate_labels_the_declared_strip_road_and_the_limits_meeting_it_side(surveyor):
    road, side, rear = BoundaryKind.ROAD, BoundaryKind.SIDE, BoundaryKind.REAR
    assert set(kinds(surveyor.site(choice(PLOT)).edges)) == {rear}
    edges = surveyor.site(with_public_strip()).edges
    assert kinds(edges) == [side, *[road] * 8, side, *[rear] * 6]
    assert edges[0].neighbours == (WEST, STRIP)
    assert edges[9].neighbours == (EAST,)


def test_site_citations(surveyor):
    site = surveyor.site(choice(PLOT, STRIP))
    assert [(c.doc, c.quote) for c in site.citations] == [
        ("geocoder", f"label={LABEL}; id=91272_1599_00004; lon={LON}; lat={LAT}"),
        ("cadastre", f"idu={PLOT}; contenance=5960"),
        ("cadastre", f"idu={STRIP}; contenance=116"),
    ]
    assert all(c.source_kind is SourceKind.GEOMETRIC and c.page is None for c in site.citations)


def test_label_is_case_and_space_insensitive(surveyor):
    site = surveyor.site(choice(PLOT, address="  4 rue joliot-curie   91190 GIF-SUR-YVETTE"))
    assert site.address == LABEL


def test_parcels_in_metric_crs(surveyor):
    (plot,) = surveyor.parcels([PLOT, PLOT])
    assert plot.id == PLOT
    assert plot.polygon.crs == "EPSG:2154"
    assert plot.polygon.exterior[0][0] > 100_000


@pytest.mark.parametrize(
    ("address", "parcels", "message"),
    [
        ("4 rue Joliot Curie, Gif", [PLOT], "exactly as geocode returned it"),
        (LABEL, ["91272000CR9999"], "91272000CR9999 is not in the cadastre"),
        (LABEL, ["CR0247"], "14 characters"),
        (LABEL, [PLOT, FAR], "2 separate parts"),
    ],
)
def test_site_errors(surveyor, address, parcels, message):
    with pytest.raises(SiteError, match=message):
        surveyor.site(choice(*parcels, address=address))


def test_empty_selection_is_a_site_error(surveyor):
    with pytest.raises(SiteError, match="no parcel id given"):
        surveyor.describe(LON, LAT, [])
    with pytest.raises(SiteError, match="no parcel id given"):
        surveyor.parcels([])


def test_service_errors_propagate(broken_surveyor):
    with pytest.raises(ServiceError, match="503"):
        broken_surveyor.candidates(LON, LAT, 50)
