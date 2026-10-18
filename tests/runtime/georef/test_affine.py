import numpy as np
import pytest

from agent.runtime.georef.affine import apply, invert, linear_scale, scaled

MATRIX = (0.8, 0.01, -500.0, -0.02, -0.79, 5000.0)


def test_apply_maps_points():
    points = np.array([[0.0, 0.0], [10.0, 20.0]])

    result = apply(MATRIX, points)

    assert result[0] == pytest.approx([-500.0, 5000.0])
    assert result[1] == pytest.approx([-500.0 + 8.0 + 0.2, 5000.0 - 0.2 - 15.8])


def test_invert_round_trips():
    points = np.array([[633000.0, 6842000.0], [639000.0, 6846000.0]])

    back = apply(invert(MATRIX), apply(MATRIX, points))

    assert back == pytest.approx(points)


def test_invert_rejects_singular_matrix():
    with pytest.raises(ValueError, match="singular"):
        invert((1.0, 2.0, 0.0, 2.0, 4.0, 0.0))


def test_scaled_multiplies_outputs():
    points = np.array([[3.0, 4.0]])

    assert apply(scaled(MATRIX, 4), points) == pytest.approx(4 * apply(MATRIX, points))
    assert linear_scale(scaled(MATRIX, 4)) == pytest.approx(4 * linear_scale(MATRIX))
