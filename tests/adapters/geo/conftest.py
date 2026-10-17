"""Offline replay of the geocoder, cadastre and WMS services from recorded responses.

Routing of ``replay_transport`` (``route``):

- ``q`` param: ``geocode_reference.json``.
- ``numero`` param: ``cadastre_<section><numero>.json``, else the matching feature of
  ``cadastre_around_reference.json``, else an empty FeatureCollection.
- ``geom`` param: ``cadastre_neighbours_CR0247.json`` when the query geometry's centroid lies
  inside parcel CR0247 (a buffered parcel outline), else ``cadastre_around_reference.json``
  (a box around the geocoded address).
- ``REQUEST=GetMap``: ``wms_<LAYERS>.png``, a 64 x 64 image recorded around CR0247.

Any other request fails the test.
"""

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from pydantic import JsonValue, TypeAdapter
from shapely.geometry import shape

from agent.adapters.geo.cadastre import CadastreClient
from agent.adapters.geo.geocoder import AddressGeocoder
from agent.adapters.geo.records import SurveySettings
from agent.adapters.geo.survey import SiteSurveyor
from agent.adapters.http import CachedHttp

FIXTURES = Path(__file__).parent / "fixtures"
_JSON: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
EMPTY_COLLECTION: JsonValue = {
    "type": "FeatureCollection",
    "features": [],
    "totalFeatures": 0,
    "numberMatched": 0,
    "numberReturned": 0,
}
SETTINGS = SurveySettings(
    crs="EPSG:2154",
    geographic_crs="EPSG:4326",
    decimals=2,
    grid_size_m=0.05,
    max_sliver_area_m2=1.0,
    neighbour_buffer_m=2.0,
    snap_tolerance_m=0.5,
    min_shared_ratio=0.5,
    geocoder_source="geocoder",
    cadastre_source="cadastre",
)


def load_fixture(name: str) -> JsonValue:
    return _JSON.validate_json((FIXTURES / name).read_bytes())


def _parcel_shape(name: str):
    collection = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return shape(collection["features"][0]["geometry"])


def _by_id(params: httpx.QueryParams) -> JsonValue:
    name = f"cadastre_{params['section']}{params['numero']}.json"
    if (FIXTURES / name).is_file():
        return load_fixture(name)
    idu = "".join(params[key] for key in ("code_insee", "com_abs", "section", "numero"))
    around = json.loads((FIXTURES / "cadastre_around_reference.json").read_text(encoding="utf-8"))
    features = [f for f in around["features"] if f["properties"]["idu"] == idu]
    if not features:
        return EMPTY_COLLECTION
    return {"type": "FeatureCollection", "features": features, "numberMatched": len(features)}


def route(request: httpx.Request) -> httpx.Response:
    params = request.url.params
    if params.get("REQUEST") == "GetMap":
        image = (FIXTURES / f"wms_{params['LAYERS']}.png").read_bytes()
        return httpx.Response(200, content=image, headers={"content-type": "image/png"})
    if "q" in params:
        return httpx.Response(200, json=load_fixture("geocode_reference.json"))
    if "numero" in params:
        return httpx.Response(200, json=_by_id(params))
    if "geom" in params:
        centroid = shape(json.loads(params["geom"])).centroid
        inside = _parcel_shape("cadastre_CR0247.json").contains(centroid)
        name = "cadastre_neighbours_CR0247.json" if inside else "cadastre_around_reference.json"
        return httpx.Response(200, json=load_fixture(name))
    pytest.fail(f"unexpected request {request.url}")


class RecordingTransport(httpx.MockTransport):
    def __init__(self, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        self.requests: list[httpx.Request] = []

        def record(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return handler(request)

        super().__init__(record)


def make_surveyor(http: CachedHttp) -> SiteSurveyor:
    return SiteSurveyor(
        geocoder=AddressGeocoder("https://data.geopf.fr/geocodage/search", http),
        cadastre=CadastreClient("https://apicarto.ign.fr/api/cadastre/parcelle", http, 500),
        settings=SETTINGS,
    )


@pytest.fixture
def replay_transport() -> RecordingTransport:
    return RecordingTransport(route)


@pytest.fixture
def guard_transport() -> RecordingTransport:
    def refuse(request: httpx.Request) -> httpx.Response:
        pytest.fail(f"unexpected network request {request.url}")

    return RecordingTransport(refuse)


@pytest.fixture
def surveyor(tmp_path, replay_transport) -> SiteSurveyor:
    return make_surveyor(CachedHttp(tmp_path, 5, replay_transport))


@pytest.fixture
def broken_surveyor(tmp_path) -> SiteSurveyor:
    def unavailable(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="maintenance")

    return make_surveyor(CachedHttp(tmp_path / "broken", 5, httpx.MockTransport(unavailable)))
