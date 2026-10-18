from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from evals.gt import cases, check
from evals.gt.geography import source
from evals.gt.geography.records import ParcelCollection
from evals.gt.settings import ROOT


def test_source_features_validate_cadastral_identity_and_coordinates():
    fixture = ROOT / "tests/adapters/geo/fixtures/cadastre_CR0247.json"
    collection = ParcelCollection.model_validate_json(fixture.read_bytes())
    feature = collection.features[0]
    assert feature.properties.idu == "91272000CR0247"
    assert source.metric(feature).area == pytest.approx(5951.492549, abs=0.001)
    data = collection.model_dump(mode="json")
    data["features"][0]["properties"].pop("idu")
    with pytest.raises(ValidationError):
        ParcelCollection.model_validate(data)


def test_failed_ban_download_is_not_cached(tmp_path, monkeypatch):
    cache = tmp_path / "addresses.csv.gz"
    monkeypatch.setattr(source, "CACHE", cache)
    response = httpx.Response(503, request=httpx.Request("GET", "https://example.test"))
    monkeypatch.setattr(source.httpx, "get", lambda *args, **kwargs: response)
    with pytest.raises(httpx.HTTPStatusError):
        source.load_ban()
    assert not cache.exists()


def test_malformed_authoring_commands_return_usage():
    assert cases.main(["show", "surveyor"]) == 2
    assert cases.main(["list", "unknown"]) == 1
    assert check.main([]) == 2


def test_all_case_indexes_load():
    for path in sorted((ROOT / "evals/cases").glob("*.yaml")):
        assert cases.load_cases(path.stem), Path(path).name
