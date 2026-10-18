import numpy as np
import pymupdf
from pydantic import Field
from shapely.geometry import MultiPolygon, Polygon

from agent.adapters.georef.raster import outlined_png
from agent.contracts.base import Contract
from agent.contracts.inputs.georeference import AffineMatrix
from agent.runtime.georef.affine import Points, apply
from agent.runtime.images.boxes import PixelBox, fit_size

_RED = (1.0, 0.0, 0.0)


class OverlaySettings(Contract):
    """Diagnostic images drawn over the plan."""

    max_px: int = Field(ge=1)
    """Long edge of the whole-plan overview."""
    line_px: float = Field(gt=0)


def _rings(geometry: Polygon | MultiPolygon, matrix: AffineMatrix) -> list[Points]:
    """Exterior rings of a (multi)polygon, mapped to pixels."""
    parts = geometry.geoms if isinstance(geometry, MultiPolygon) else (geometry,)
    return [apply(matrix, np.asarray(part.exterior.coords)[:, :2]) for part in parts]


def boundary_overview(
    image: pymupdf.Pixmap,
    outline: Polygon | MultiPolygon,
    matrix: AffineMatrix,
    settings: OverlaySettings,
) -> bytes:
    """The whole plan, downscaled, with a ground outline drawn in red.

    Args:
        image: Full-resolution plan page.
        outline: Ground geometry to draw (e.g. the commune boundary).
        matrix: Ground to full-resolution pixel transform.
        settings: Drawing settings.

    Returns:
        PNG bytes.
    """
    box = PixelBox(x0=0, y0=0, x1=image.width, y1=image.height)
    size = fit_size((image.width, image.height), settings.max_px)
    return outlined_png(
        image,
        box,
        size,
        _rings(outline, matrix),
        colour=_RED,
        line_px=settings.line_px,
    )
