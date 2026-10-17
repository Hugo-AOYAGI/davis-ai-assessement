from collections.abc import Sequence
from typing import Self

import numpy as np
from numpy.typing import NDArray
from pydantic import Field

from agent.contracts.base import Contract
from agent.contracts.geometry import Point

_MIN_POINTS = 3
_FULL_RANK = 2


class ControlPoint(Contract):
    """A point whose position is known both on a raster and in the world."""

    pixel: tuple[float, float]
    """``(column, row)`` on the raster at its native size, origin top-left."""
    world: tuple[float, float]
    """``(x, y)`` in the georeference CRS (easting, northing in metres)."""


class Georeference(Contract):
    """Control points tying a raster to a projected CRS."""

    crs: str = Field(min_length=1)
    """CRS of the ``world`` coordinates, e.g. ``EPSG:2154``."""
    control_points: tuple[ControlPoint, ...] = Field(min_length=_MIN_POINTS)


type Row = tuple[float, float, float]


class AffineTransform(Contract):
    """World to pixel affine map: ``[col, row] = coefficients @ [x, y, 1]``."""

    coefficients: tuple[Row, Row]
    """Two rows of three coefficients, giving the column then the row of a world point."""

    @classmethod
    def fit(cls, points: Sequence[ControlPoint]) -> Self:
        """Fit the transform on control points by least squares.

        Args:
            points: At least three control points, not all on one line.

        Returns:
            The fitted transform.

        Raises:
            ValueError: If there are fewer than three points or they are collinear.
        """
        if len(points) < _MIN_POINTS:
            msg = f"an affine fit needs at least {_MIN_POINTS} control points, got {len(points)}"
            raise ValueError(msg)
        world = np.array([point.world for point in points], dtype=float)
        pixel = np.array([point.pixel for point in points], dtype=float)
        origin = world.mean(axis=0)
        centred = world - origin
        if np.linalg.matrix_rank(centred) < _FULL_RANK:
            msg = "control points are collinear: their world positions span no area"
            raise ValueError(msg)
        design = np.column_stack([centred, np.ones(len(points))])
        solution, *_ = np.linalg.lstsq(design, pixel, rcond=None)
        linear = solution[:2].T
        offset = solution[2] - linear @ origin
        if np.linalg.matrix_rank(linear) < _FULL_RANK:
            msg = "control points are degenerate: their pixel positions span no area"
            raise ValueError(msg)
        rows = np.column_stack([linear, offset])
        return cls(coefficients=(_row(rows[0]), _row(rows[1])))

    @property
    def metres_per_pixel(self) -> float:
        """Ground distance covered by one raster pixel (geometric mean of both axes)."""
        return float(1 / np.sqrt(abs(np.linalg.det(self._linear))))

    def to_pixel(self, points: Sequence[Point]) -> tuple[Point, ...]:
        """Map world points to raster pixels.

        Args:
            points: ``(x, y)`` in the georeference CRS.

        Returns:
            ``(column, row)`` at the raster's native size.
        """
        world = np.asarray(points, dtype=float).reshape(-1, 2)
        return _points(world @ self._linear.T + self._offset)

    def to_world(self, points: Sequence[Point]) -> tuple[Point, ...]:
        """Map raster pixels back to world points.

        Args:
            points: ``(column, row)`` at the raster's native size.

        Returns:
            ``(x, y)`` in the georeference CRS.
        """
        pixel = np.asarray(points, dtype=float).reshape(-1, 2)
        return _points((pixel - self._offset) @ np.linalg.inv(self._linear).T)

    def residuals_m(self, points: Sequence[ControlPoint]) -> tuple[float, ...]:
        """Measure how far each control point's pixel lands from its world position.

        Args:
            points: Control points, usually those the transform was fitted on.

        Returns:
            Distance in metres between each point's world position and its pixel mapped back.
        """
        mapped = np.asarray(self.to_world([point.pixel for point in points]))
        world = np.array([point.world for point in points], dtype=float)
        return tuple(float(distance) for distance in np.hypot(*(mapped - world).T))

    @property
    def _linear(self) -> NDArray[np.float64]:
        """The 2x2 linear part."""
        return np.array(self.coefficients, dtype=float)[:, :2]

    @property
    def _offset(self) -> NDArray[np.float64]:
        """The translation part."""
        return np.array(self.coefficients, dtype=float)[:, 2]


def _row(values: NDArray[np.float64]) -> Row:
    """Turn three numbers into a coefficient row."""
    return (float(values[0]), float(values[1]), float(values[2]))


def _points(array: NDArray[np.float64]) -> tuple[Point, ...]:
    """Turn an ``(n, 2)`` array into a tuple of points."""
    return tuple((float(x), float(y)) for x, y in array)
