import httpx
import pytest

from agent.adapters.geo.geocoder import AddressGeocoder
from agent.adapters.geo.http import CachedHttp, GeoServiceError

URL = "https://data.geopf.fr/geocodage/search"


def test_search_parses_reference_fixture(tmp_path, replay_transport):
    geocoder = AddressGeocoder(URL, CachedHttp(tmp_path, timeout_s=5, transport=replay_transport))
    candidates = geocoder.search("4 rue Joliot Curie, 91190 Gif-sur-Yvette", limit=5)
    assert len(candidates) == 1
    top = candidates[0]
    assert top.label == "4 Rue Joliot-curie 91190 Gif-sur-Yvette"
    assert top.score == pytest.approx(0.9635, abs=1e-4)
    assert top.kind == "housenumber"
    assert (top.longitude, top.latitude) == (2.165254, 48.709836)
    assert (top.city, top.postcode, top.citycode) == ("Gif-sur-Yvette", "91190", "91272")
    assert top.ban_id == "91272_1599_00004"
    params = replay_transport.requests[0].url.params
    assert params["limit"] == "5"
    assert params["q"] == "4 rue Joliot Curie, 91190 Gif-sur-Yvette"


@pytest.mark.parametrize(
    "body",
    [
        {"features": [{"geometry": {"type": "Point"}, "properties": {}}]},
        {"features": "nope"},
        [1, 2],
    ],
    ids=["incomplete-feature", "bad-features", "not-an-object"],
)
def test_unexpected_payload_raises(tmp_path, body):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    geocoder = AddressGeocoder(URL, CachedHttp(tmp_path, timeout_s=5, transport=transport))
    with pytest.raises(GeoServiceError, match="unexpected geocoding payload"):
        geocoder.search("anything", limit=1)


def test_no_match_is_empty(tmp_path):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"features": []}))
    geocoder = AddressGeocoder(URL, CachedHttp(tmp_path, timeout_s=5, transport=transport))
    assert geocoder.search("nowhere", limit=1) == ()
