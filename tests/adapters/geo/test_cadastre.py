import json
from collections.abc import Mapping

import httpx
import pytest
from pydantic import JsonValue
from shapely.geometry import Polygon, box

from agent.adapters.geo.cadastre import CadastreClient
from agent.adapters.geo.http import CachedHttp, GeoServiceError

URL = "https://apicarto.ign.fr/api/cadastre/parcelle"
LON, LAT = 2.165254, 48.709836
AROUND = box(LON - 0.0006, LAT - 0.0004, LON + 0.0006, LAT + 0.0004)
AROUND_IDS = {
    f"91272000CR{numero}"
    for numero in ("0215", "0227", "0239", "0240", "0247", "0249", "0251", "0258", "0259")
}


@pytest.fixture
def client(tmp_path, replay_transport) -> CadastreClient:
    return CadastreClient(URL, CachedHttp(tmp_path, 5, replay_transport), page_size=1000)


def test_intersecting_parses_reference_box(client, replay_transport):
    parcels = client.intersecting(AROUND)
    assert {parcel.id for parcel in parcels} == AROUND_IDS
    by_id = {parcel.id: parcel for parcel in parcels}
    assert by_id["91272000CR0247"].contenance_m2 == 5960
    for parcel in parcels:
        assert parcel.polygons
        for rings in parcel.polygons:
            for ring in rings:
                assert len(ring) >= 4
                assert ring[0] == ring[-1]
    params = replay_transport.requests[0].url.params
    assert params["_limit"] == "1000"
    assert params["_start"] == "0"
    assert json.loads(params["geom"])["type"] == "Polygon"
    assert len(replay_transport.requests) == 1


def test_intersecting_buffered_parcel_returns_neighbours(client):
    parcel = client.by_id("91272000CR0247")
    assert parcel is not None
    outline = Polygon(parcel.polygons[0][0]).buffer(0.00003)
    ids = {neighbour.id for neighbour in client.intersecting(outline)}
    assert ids == {f"91272000CR{n}" for n in ("0227", "0247", "0249", "0256")}


def test_by_id_found(client, replay_transport):
    parcel = client.by_id("91272000CR0247")
    assert parcel is not None
    assert parcel.id == "91272000CR0247"
    assert parcel.contenance_m2 == 5960
    assert dict(replay_transport.requests[0].url.params) == {
        "code_insee": "91272",
        "com_abs": "000",
        "section": "CR",
        "numero": "0247",
    }


def test_by_id_not_found(client):
    assert client.by_id("91272000CR9999") is None


@pytest.mark.parametrize("parcel_id", ["CR0247", "91272000CR02470", ""])
def test_by_id_rejects_malformed_ids(tmp_path, guard_transport, parcel_id):
    client = CadastreClient(URL, CachedHttp(tmp_path, 5, guard_transport), page_size=10)
    with pytest.raises(ValueError, match="14 characters"):
        client.by_id(parcel_id)


def page(features: list[JsonValue], matched: int | None) -> dict[str, JsonValue]:
    body: dict[str, JsonValue] = {"type": "FeatureCollection", "features": features}
    if matched is not None:
        body["numberMatched"] = matched
    return body


def square(idu: str) -> JsonValue:
    ring: list[JsonValue] = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {"idu": idu, "contenance": None},
    }


def paged_client(tmp_path, pages: Mapping[str, JsonValue], page_size: int):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        start = request.url.params["_start"]
        seen.append(start)
        return httpx.Response(200, json=pages[start])

    transport = httpx.MockTransport(handler)
    return CadastreClient(URL, CachedHttp(tmp_path, 5, transport), page_size), seen


def test_intersecting_follows_pagination(tmp_path):
    pages = {
        "0": page([square("A"), square("B")], matched=3),
        "2": page([square("C")], matched=3),
    }
    client, seen = paged_client(tmp_path, pages, page_size=2)
    parcels = client.intersecting(AROUND)
    assert [parcel.id for parcel in parcels] == ["A", "B", "C"]
    assert seen == ["0", "2"]
    assert parcels[0].polygons == ((((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)),),)
    assert parcels[0].contenance_m2 is None


def test_intersecting_warns_when_count_is_missing(tmp_path, caplog):
    client, seen = paged_client(tmp_path, {"0": page([square("A")], matched=None)}, 1)
    caplog.set_level("WARNING", logger="agent")
    assert [parcel.id for parcel in client.intersecting(AROUND)] == ["A"]
    assert seen == ["0"]
    assert "truncated" in caplog.text


def test_unexpected_payload_raises(tmp_path):
    bad: dict[str, JsonValue] = {
        "0": {"features": [{"geometry": {"type": "Point", "coordinates": [0, 0]}}]}
    }
    client, _ = paged_client(tmp_path, bad, 10)
    with pytest.raises(GeoServiceError, match="unexpected cadastre payload"):
        client.intersecting(AROUND)
