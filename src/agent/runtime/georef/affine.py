from typing import cast

import numpy as np
from numpy.typing import NDArray

from agent.contracts.inputs.georeference import AffineMatrix

type Points = NDArray[np.float64]
"""Array of shape ``(n, 2)``: one ``(x, y)`` or ``(u, v)`` pair per row."""


def apply(matrix: AffineMatrix, points: Points) -> Points:
    """Map points through an affine transform.

    Args:
        matrix: ``(a, b, c, d, e, f)``, ``u = a*x + b*y + c`` and ``v = d*x + e*y + f``.
        points: Input coordinates, shape ``(n, 2)``.

    Returns:
        Output coordinates, shape ``(n, 2)``.
    """
    a, b, c, d, e, f = matrix
    x, y = points[:, 0], points[:, 1]
    return np.column_stack((a * x + b * y + c, d * x + e * y + f))


def invert(matrix: AffineMatrix) -> AffineMatrix:
    """Inverse transform.

    Raises:
        ValueError: If the matrix is singular.
    """
    a, b, c, d, e, f = matrix
    det = a * e - b * d
    if det == 0:
        msg = "singular affine matrix"
        raise ValueError(msg)
    ia, ib, id_, ie = e / det, -b / det, -d / det, a / det
    return (ia, ib, -(ia * c + ib * f), id_, ie, -(id_ * c + ie * f))


def scaled(matrix: AffineMatrix, factor: float) -> AffineMatrix:
    """Same transform with its output coordinates multiplied by ``factor``.

    Turns a matrix fitted on an image downscaled ``factor`` times into one for the full image.
    """
    return cast("AffineMatrix", tuple(value * factor for value in matrix))


def from_linear(linear: NDArray[np.float64], offset: Points) -> AffineMatrix:
    """Build a matrix from its 2x2 linear part and its translation ``(c, f)``."""
    return (
        float(linear[0, 0]),
        float(linear[0, 1]),
        float(offset[0]),
        float(linear[1, 0]),
        float(linear[1, 1]),
        float(offset[1]),
    )


def linear_scale(matrix: AffineMatrix) -> float:
    """Mean linear scale factor: square root of the absolute determinant."""
    a, b, _, d, e, _ = matrix
    return float(np.sqrt(abs(a * e - b * d)))
