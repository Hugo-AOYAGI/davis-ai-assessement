import math

import pytest
from pydantic import ValidationError

from agent.runtime.georef.affine import AffineTransform, ControlPoint, Georeference

SCALE = 1 / 1.2
ANGLE = math.radians(3)
TRUE = (
    (SCALE * math.cos(ANGLE), SCALE * math.sin(ANGLE), -530000.0),
    (SCALE * math.sin(ANGLE), -SCALE * math.cos(ANGLE), 5705000.0),
)
WORLD = [
    (633000.0, 6842000.0),
    (639000.0, 6842500.0),
    (636000.0, 6847000.0),
    (634500.0, 6845000.0),
    (638000.0, 6846000.0),
]


def true_pixel(x: float, y: float) -> tuple[float, float]:
    (a, b, c), (d, e, f) = TRUE
    return a * x + b * y + c, d * x + e * y + f


def points(world=WORLD) -> list[ControlPoint]:
    return [ControlPoint(pixel=true_pixel(x, y), world=(x, y)) for x, y in world]


def test_fit_recovers_exact_affine():
    transform = AffineTransform.fit(points())
    for fitted, expected in zip(transform.coefficients, TRUE, strict=True):
        assert fitted == pytest.approx(expected, rel=1e-9, abs=1e-6)
    assert max(transform.residuals_m(points())) < 1e-6


def test_metres_per_pixel():
    assert AffineTransform.fit(points()).metres_per_pixel == pytest.approx(1.2)


def test_round_trip():
    transform = AffineTransform.fit(points())
    world = [(635123.4, 6843210.9), (637000.0, 6846000.0)]
    pixels = transform.to_pixel(world)
    assert pixels[0] == pytest.approx(true_pixel(*world[0]))
    for back, original in zip(transform.to_world(pixels), world, strict=True):
        assert back == pytest.approx(original, abs=1e-6)


def test_residuals_measure_noise_in_metres():
    noisy = points()
    noisy[0] = ControlPoint(pixel=noisy[0].pixel, world=(WORLD[0][0] + 12.0, WORLD[0][1]))
    assert max(AffineTransform.fit(noisy).residuals_m(noisy)) > 1


def test_too_few_points():
    with pytest.raises(ValueError, match="at least 3"):
        AffineTransform.fit(points()[:2])


def test_collinear_points():
    line = [(633000.0 + 100 * i, 6842000.0 + 50 * i) for i in range(4)]
    with pytest.raises(ValueError, match="collinear"):
        AffineTransform.fit(points(line))


def test_degenerate_pixels():
    flat = [ControlPoint(pixel=(float(i), 0.0), world=world) for i, world in enumerate(WORLD)]
    with pytest.raises(ValueError, match="degenerate"):
        AffineTransform.fit(flat)


def test_georeference_needs_three_points():
    with pytest.raises(ValidationError):
        Georeference(crs="EPSG:2154", control_points=tuple(points()[:2]))
