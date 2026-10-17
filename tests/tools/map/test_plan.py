import pymupdf
import pytest

from agent.contracts.geometry import Polygon
from agent.runtime.georef.project import centroid, to_crs
from agent.tools.map.plan import ZoningPlanSettings, open_plan

REFERENCE_WORLD = (638580.2, 6845846.57)
REFERENCE_PIXEL = (4676.5, 1283.7)
METRES_PER_PIXEL = 1.1855


def test_plan_is_shared_and_loads_at_configured_size(plan_block):
    plan = open_plan(plan_block)
    assert open_plan(dict(plan_block)) is plan
    assert plan.path.is_file()
    assert (plan.image.width, plan.image.height) == plan.settings.size_px


def test_georeference_quality(plan_block):
    plan = open_plan(plan_block)
    assert plan.max_residual_m < 2
    assert plan.transform.metres_per_pixel == pytest.approx(METRES_PER_PIXEL, rel=1e-3)
    (pixel,) = plan.transform.to_pixel([REFERENCE_WORLD])
    assert pixel == pytest.approx(REFERENCE_PIXEL, abs=1)


def test_site_centroid_lands_near_reference(plan_block, site):
    plan = open_plan(plan_block)
    x, y = centroid(to_crs(site.polygon, plan.settings.georeference.crs))
    (column, row) = plan.transform.to_pixel([(x, y)])[0]
    expected = (
        REFERENCE_PIXEL[0] + (x - REFERENCE_WORLD[0]) / METRES_PER_PIXEL,
        REFERENCE_PIXEL[1] - (y - REFERENCE_WORLD[1]) / METRES_PER_PIXEL,
    )
    assert abs(column - expected[0]) < 10
    assert abs(row - expected[1]) < 10
    assert 4650 < column < 4720
    assert 1210 < row < 1300


def test_site_polygon_is_in_lambert93(site):
    assert isinstance(site.polygon, Polygon)
    assert site.polygon.crs == "EPSG:2154"
    assert site.parcels[0].id == "91272000CR0247"


def test_size_mismatch_is_rejected(plan_block, tmp_path):
    path = tmp_path / "plan.png"
    pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 20), 0).save(path)
    settings = ZoningPlanSettings.model_validate({**plan_block, "source": str(path), "page": 1})
    plan = open_plan(settings.model_dump())
    with pytest.raises(ValueError, match="40x20 px"):
        _ = plan.image
