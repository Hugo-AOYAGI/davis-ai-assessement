import numpy as np
import pytest
from shapely.geometry import Polygon

from agent.contracts.inputs.georeference import AffineMatrix
from agent.runtime.georef.affine import apply, linear_scale
from agent.runtime.georef.fit import edge_distance, fit_affine, sample
from agent.runtime.georef.score import iou, outline_errors, rasterize

GROUND = Polygon(
    [
        (633000, 6842000),
        (636000, 6842300),
        (638500, 6844000),
        (637800, 6846500),
        (635200, 6845200),
        (634000, 6846000),
        (632800, 6844200),
    ]
)
SHAPE = (360, 420)


def _centred(linear: tuple[float, float, float, float]) -> AffineMatrix:
    """Matrix with this linear part that puts the ground centroid at the image centre."""
    a, b, d, e = linear
    cx, cy = float(GROUND.centroid.x), float(GROUND.centroid.y)
    u0, v0 = SHAPE[1] / 2, SHAPE[0] / 2
    return (a, b, u0 - a * cx - b * cy, d, e, v0 - d * cx - e * cy)


KNOWN = _centred((0.0601, 0.0012, -0.0009, -0.0598))


def test_fit_recovers_a_known_transform_from_a_synthetic_mask():
    mask = rasterize(GROUND, KNOWN, SHAPE)

    fitted = fit_affine(mask, GROUND, sample_step_m=20, robust_scale_px=3)

    corners = np.asarray(GROUND.exterior.coords)
    error_px = np.linalg.norm(apply(fitted, corners) - apply(KNOWN, corners), axis=1)
    assert error_px.max() < 0.5
    assert iou(mask, rasterize(GROUND, fitted, SHAPE)) > 0.99
    errors = outline_errors(mask, GROUND, fitted, sample_step_m=20)
    assert errors.mean() < 0.3 / linear_scale(fitted)


def test_fit_finds_a_quarter_turn_without_mirror():
    turned = _centred((0.0009, 0.0598, 0.0601, 0.0012))
    mask = rasterize(GROUND, turned, SHAPE)

    fitted = fit_affine(mask, GROUND, sample_step_m=20, robust_scale_px=3)

    assert iou(mask, rasterize(GROUND, fitted, SHAPE)) > 0.99


def test_fit_rejects_an_empty_mask():
    with pytest.raises(ValueError, match="empty mask"):
        fit_affine(np.zeros((10, 10), dtype=bool), GROUND, sample_step_m=20, robust_scale_px=3)


def test_edge_distance_is_zero_between_inside_and_outside_pixels():
    mask = np.zeros((9, 9), dtype=bool)
    mask[:, :4] = True
    distance = edge_distance(mask)

    on_edge = sample(distance, np.array([[4.0, 4.5]]))
    inside = sample(distance, np.array([[1.5, 4.5]]))

    assert on_edge == pytest.approx([0.0])
    assert inside == pytest.approx([-2.5])


def test_rasterize_covers_the_projected_area():
    mask = rasterize(GROUND, KNOWN, SHAPE)

    assert mask.sum() == pytest.approx(GROUND.area * linear_scale(KNOWN) ** 2, rel=0.02)
    assert mask[SHAPE[0] // 2, SHAPE[1] // 2]
