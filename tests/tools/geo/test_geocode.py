import json

import httpx

from agent.adapters.geo.geocoder import AddressGeocoder
from agent.adapters.http import CachedHttp
from agent.tools.geo.geocode import geocode_tool

URL = "https://data.geopf.fr/geocodage/search"
LON, LAT = 2.165254, 48.709836


def test_geocode_schema_and_description(http):
    tool = geocode_tool(AddressGeocoder(URL, http), max_results=5)
    assert tool.name == "geocode"
    assert set(tool.args) == {"query"}
    assert "pass it unchanged as `address` to submit_parcel" in tool.description


def test_geocode_returns_candidates(http):
    tool = geocode_tool(AddressGeocoder(URL, http), max_results=3)
    rows = json.loads(tool.invoke({"query": "4 rue Joliot Curie, 91190 Gif-sur-Yvette"}))
    assert rows == [
        {
            "label": "4 Rue Joliot-curie 91190 Gif-sur-Yvette",
            "score": 0.96,
            "kind": "housenumber",
            "longitude": LON,
            "latitude": LAT,
            "city": "Gif-sur-Yvette",
            "postcode": "91190",
            "citycode": "91272",
        }
    ]


def test_geocode_no_match(tmp_path):
    def empty(request: httpx.Request) -> httpx.Response:
        assert request.url.params["limit"] == "5"
        return httpx.Response(200, json={"type": "FeatureCollection", "features": []})

    http = CachedHttp(tmp_path, 5, httpx.MockTransport(empty))
    reply = geocode_tool(AddressGeocoder(URL, http), max_results=5).invoke({"query": "nowhere"})
    assert reply.startswith("No address matches 'nowhere'")


def test_geocode_service_error_is_a_message(broken_http):
    reply = geocode_tool(AddressGeocoder(URL, broken_http), max_results=5).invoke({"query": "x"})
    assert reply.startswith("geocode failed:")
    assert "503" in reply
