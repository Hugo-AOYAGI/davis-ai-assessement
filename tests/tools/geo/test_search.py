import json

import httpx

from agent.adapters.geo.geocoder import AddressGeocoder
from agent.adapters.geo.http import CachedHttp
from agent.tools.geo.geocode import geocode_tool
from agent.tools.geo.parcels import find_parcels_tool

URL = "https://data.geopf.fr/geocodage/search"
LON, LAT = 2.165254, 48.709836


def schema_properties(tool) -> set[str]:
    return set(tool.tool_call_schema.model_json_schema()["properties"])


def test_geocode_schema_and_description(http):
    tool = geocode_tool(AddressGeocoder(URL, http), max_results=5)
    assert tool.name == "geocode_address"
    assert schema_properties(tool) == {"query"}
    assert "pass it unchanged" in tool.description


def test_geocode_returns_candidates(http, transport):
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
    assert reply.startswith("geocode_address failed:")
    assert "503" in reply


def test_find_parcels(surveyor):
    tool = find_parcels_tool(surveyor, radius_m=50)
    assert tool.name == "find_parcels"
    assert schema_properties(tool) == {"longitude", "latitude"}
    rows = json.loads(tool.invoke({"longitude": LON, "latitude": LAT}))
    assert [row["id"] for row in rows[:2]] == ["91272000CR0249", "91272000CR0247"]
    strip, plot = rows[0], rows[1]
    assert strip["mean_width_m"] <= 1
    assert plot == {
        "id": "91272000CR0247",
        "contenance_m2": 5960,
        "distance_m": 2.5,
        "contains_point": False,
        "mean_width_m": 38.7,
        "touches": ["91272000CR0227", "91272000CR0249"],
    }


def test_find_parcels_service_error_is_a_message(broken_surveyor):
    reply = find_parcels_tool(broken_surveyor, radius_m=50).invoke(
        {"longitude": LON, "latitude": LAT}
    )
    assert reply.startswith("find_parcels failed:")
