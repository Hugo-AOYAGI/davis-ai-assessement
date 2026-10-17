"""Offline geo services for the tool tests, replayed from the adapter fixtures.

Same routing as ``tests/adapters/geo/conftest.py``: ``q`` -> geocoder fixture; ``numero`` ->
the parcel's fixture or its feature in the around-reference collection; ``geom`` -> neighbours
of CR0247 when the query centroid lies inside it, else the parcels around the address.
"""

import json
from pathlib import Path

import httpx
import pytest
from shapely.geometry import shape

from agent.adapters.geo.cadastre import CadastreClient
from agent.adapters.geo.geocoder import AddressGeocoder
from agent.adapters.geo.http import CachedHttp
from agent.adapters.geo.survey import SiteSurveyor

FIXTURES = Path(__file__).parents[2] / "adapters" / "geo" / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _by_id(params: httpx.QueryParams):
    name = f"cadastre_{params['section']}{params['numero']}.json"
    if (FIXTURES / name).is_file():
        return fixture(name)
    idu = "".join(params[key] for key in ("code_insee", "com_abs", "section", "numero"))
    features = fixture("cadastre_around_reference.json")["features"]
    matches = [f for f in features if f["properties"]["idu"] == idu]
    return {"type": "FeatureCollection", "features": matches, "numberMatched": len(matches)}


def route(request: httpx.Request) -> httpx.Response:
    params = request.url.params
    if "q" in params:
        return httpx.Response(200, json=fixture("geocode_reference.json"))
    if "numero" in params:
        return httpx.Response(200, json=_by_id(params))
    if "geom" in params:
        plot = shape(fixture("cadastre_CR0247.json")["features"][0]["geometry"])
        inside = plot.contains(shape(json.loads(params["geom"])).centroid)
        name = "cadastre_neighbours_CR0247.json" if inside else "cadastre_around_reference.json"
        return httpx.Response(200, json=fixture(name))
    pytest.fail(f"unexpected request {request.url}")


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
        geocoder_source="geoplateforme-geocodage",
        cadastre_source="apicarto-cadastre",
    )


@pytest.fixture
def transport() -> httpx.MockTransport:
    return httpx.MockTransport(route)


@pytest.fixture
def http(tmp_path, transport) -> CachedHttp:
    return CachedHttp(tmp_path, 5, transport)


@pytest.fixture
def surveyor(http) -> SiteSurveyor:
    return make_surveyor(http)


@pytest.fixture
def broken_http(tmp_path) -> CachedHttp:
    def unavailable(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="maintenance")

    return CachedHttp(tmp_path / "broken", 5, httpx.MockTransport(unavailable))


@pytest.fixture
def broken_surveyor(broken_http) -> SiteSurveyor:
    return make_surveyor(broken_http)
