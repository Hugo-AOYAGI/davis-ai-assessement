import numpy as np
import pytest
from shapely.geometry import MultiPolygon, Polygon, box

from agent.runtime.georef.crop import OffPlanError, crop_region, site_rings
from agent.runtime.images.boxes import OverviewScale, PixelBox

MATRIX = (2.0, 0.0, -1000.0, 0.0, -2.0, 3000.0)
SCALE = OverviewScale(full=(2000, 2000), overview=(1000, 1000))


def test_site_rings_project_to_pixels():
    (ring,) = site_rings(box(600, 1000, 620, 1020), MATRIX)
    assert ring.min(axis=0) == pytest.approx([200, 960])
    assert ring.max(axis=0) == pytest.approx([240, 1000])


def test_site_rings_keep_holes_and_parts():
    holed = Polygon(box(0, 0, 10, 10).exterior, [box(4, 4, 6, 6).exterior.coords])
    rings = site_rings(MultiPolygon([holed, box(20, 0, 30, 10)]), MATRIX)
    assert len(rings) == 3


def test_known_polygon_maps_to_its_crop_box():
    rings = site_rings(box(600, 1000, 620, 1020), MATRIX)
    region = crop_region(rings, margin_px=20, scale=SCALE)
    assert region == PixelBox(x0=90, y0=470, x1=130, y1=510)


def test_crop_is_clipped_to_the_page():
    rings = [np.array([[10.0, 10.0], [30.0, 10.0], [30.0, 30.0], [10.0, 10.0]])]
    region = crop_region(rings, margin_px=100, scale=SCALE)
    assert (region.x0, region.y0) == (0, 0)
    assert region.x1 == 65


def test_site_off_the_page_is_rejected():
    rings = [np.array([[3000.0, 10.0], [3010.0, 10.0], [3010.0, 20.0], [3000.0, 10.0]])]
    with pytest.raises(OffPlanError, match="outside the plan page"):
        crop_region(rings, margin_px=10, scale=SCALE)
