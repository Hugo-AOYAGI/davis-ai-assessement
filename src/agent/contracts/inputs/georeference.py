from datetime import date

from pydantic import Field

from agent.contracts.base import Contract

type AffineMatrix = tuple[float, float, float, float, float, float]
"""Affine ``(a, b, c, d, e, f)``: ``u = a*x + b*y + c`` and ``v = d*x + e*y + f``.

``(x, y)`` are metric CRS coordinates; ``(u, v)`` are continuous image pixel coordinates, pixel
``(i, j)`` covering ``[i, i + 1) x [j, j + 1)`` with ``v`` growing downwards.
"""


class PlanGeoreference(Contract):
    """Affine transform from ground coordinates to the pixels of a raster plan page."""

    document: str = Field(min_length=1)
    """Corpus document id of the plan."""
    page: int = Field(ge=1)
    """1-based page of the plan in its PDF."""
    image_width: int = Field(ge=1)
    """Width in pixels of the full-resolution page image the matrix refers to."""
    image_height: int = Field(ge=1)
    """Height in pixels of that image."""
    crs: str
    """Metric CRS of the ground coordinates, e.g. ``EPSG:2154``."""
    matrix: AffineMatrix
    """Ground metres to full-resolution pixels (see ``AffineMatrix``)."""
    pixels_per_metre: float = Field(gt=0)
    """Mean linear scale of the matrix (square root of its determinant)."""
    iou: float = Field(ge=0, le=1)
    """Intersection over union of the plan's commune mask and the projected boundary."""
    mean_error_m: float = Field(ge=0)
    """Mean distance between the plan outline and the projected boundary, both ways."""
    max_error_m: float = Field(ge=0)
    """Largest such distance."""
    boundary_source: str
    """Where the ground boundary came from (service and commune code)."""
    created: date
    """Day the transform was fitted."""
