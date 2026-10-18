from datetime import date

import pytest

from agent.adapters.georef.store import load_georeference, save_georeference
from agent.contracts.inputs.georeference import PlanGeoreference


def test_save_and_load_round_trip(tmp_path):
    georeference = PlanGeoreference(
        document="plan",
        page=1,
        image_width=7021,
        image_height=4966,
        crs="EPSG:2154",
        matrix=(0.84, 0.0, -534000.0, 0.0, -0.84, 5784000.0),
        pixels_per_metre=0.84,
        iou=0.99,
        mean_error_m=2.9,
        max_error_m=39.0,
        boundary_source="test",
        created=date(2026, 10, 18),
    )
    path = tmp_path / "georef" / "plan.json"

    save_georeference(georeference, path)

    assert load_georeference(path) == georeference


def test_load_missing_file_explains_how_to_build_it(tmp_path):
    with pytest.raises(FileNotFoundError, match="ingest georef"):
        load_georeference(tmp_path / "missing.json")
