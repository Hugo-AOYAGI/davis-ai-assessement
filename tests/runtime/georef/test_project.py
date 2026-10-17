import pytest
from pyproj import Transformer

from agent.contracts.geometry import Polygon
from agent.runtime.georef.affine import AffineTransform, ControlPoint
from agent.runtime.georef.project import centroid, pixel_rings, to_crs

L93 = "EPSG:2154"
EXTERIOR = (
    (638560.0, 6845870.0),
    (638620.0, 6845870.0),
    (638620.0, 6845910.0),
    (638560.0, 6845910.0),
    (638560.0, 6845870.0),
)
HOLE = (
    (638580.0, 6845880.0),
    (638590.0, 6845880.0),
    (638590.0, 6845890.0),
    (638580.0, 6845880.0),
)
TRANSFORM = AffineTransform.fit(
    [
        ControlPoint(pixel=(0.0, 0.0), world=(638000.0, 6846500.0)),
        ControlPoint(pixel=(1000.0, 0.0), world=(639200.0, 6846500.0)),
        ControlPoint(pixel=(0.0, 1000.0), world=(638000.0, 6845300.0)),
    ]
)


def in_wgs84(ring):
    transformer = Transformer.from_crs(L93, "EPSG:4326", always_xy=True)
    points = tuple(transformer.transform(x, y) for x, y in ring[:-1])
    return (*points, points[0])


def test_same_crs_is_unchanged():
    polygon = Polygon(crs=L93, exterior=EXTERIOR)
    assert to_crs(polygon, L93) is polygon


def test_centroid():
    assert centroid(Polygon(crs=L93, exterior=EXTERIOR)) == pytest.approx((638590.0, 6845890.0))


def test_pixel_rings_in_projected_crs():
    exterior, hole = pixel_rings(Polygon(crs=L93, exterior=EXTERIOR, holes=(HOLE,)), TRANSFORM, L93)
    assert exterior[0] == pytest.approx((560 / 1.2, 630 / 1.2))
    assert len(exterior) == len(EXTERIOR)
    assert len(hole) == len(HOLE)


def test_wgs84_polygon_lands_on_same_pixels():
    projected = pixel_rings(Polygon(crs=L93, exterior=EXTERIOR, holes=(HOLE,)), TRANSFORM, L93)
    geographic = Polygon(crs="EPSG:4326", exterior=in_wgs84(EXTERIOR), holes=(in_wgs84(HOLE),))
    reprojected = pixel_rings(geographic, TRANSFORM, L93)
    for ring, expected in zip(reprojected, projected, strict=True):
        for point, target in zip(ring, expected, strict=True):
            assert point == pytest.approx(target, abs=1e-3)
