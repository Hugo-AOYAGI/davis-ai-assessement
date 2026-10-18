import httpx
import pytest

from agent.adapters.georef.boundary import CommuneBoundaryClient
from agent.adapters.http import CachedHttp, ServiceError

URL = "https://apicarto.example/api/cadastre/commune"
SQUARE = [[2.16, 48.70], [2.17, 48.70], [2.17, 48.71], [2.16, 48.71], [2.16, 48.70]]
SPECK = [[2.20, 48.70], [2.2001, 48.70], [2.2001, 48.7001], [2.20, 48.70]]


def _client(tmp_path, body):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=body)

    http = CachedHttp(tmp_path, 5, httpx.MockTransport(handler))
    client = CommuneBoundaryClient(
        URL, http, crs="EPSG:2154", geographic_crs="EPSG:4326", source="test"
    )
    return client, requests


def test_outline_returns_the_largest_part_in_lambert93(tmp_path):
    geometry = {"type": "MultiPolygon", "coordinates": [[SPECK], [SQUARE]]}
    body = {"type": "FeatureCollection", "features": [{"geometry": geometry}]}
    client, requests = _client(tmp_path, body)

    outline = client.outline("91272")

    assert requests[0].url.params["code_insee"] == "91272"
    assert 630000 < outline.centroid.x < 640000
    assert 6840000 < outline.centroid.y < 6850000
    assert outline.area == pytest.approx(735 * 1112, rel=0.02)


def test_outline_without_polygon_is_a_service_error(tmp_path):
    client, _ = _client(tmp_path, {"type": "FeatureCollection", "features": []})

    with pytest.raises(ServiceError, match="no polygon"):
        client.outline("91272")
