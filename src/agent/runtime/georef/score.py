import numpy as np
import shapely
from numpy.typing import NDArray
from shapely.geometry import Polygon

from agent.contracts.inputs.georeference import AffineMatrix
from agent.runtime.georef.affine import apply, invert, linear_scale
from agent.runtime.georef.fit import edge_distance, outline_samples, sample
from agent.runtime.georef.mask import Mask, outline


def rasterize(boundary: Polygon, matrix: AffineMatrix, shape: tuple[int, int]) -> Mask:
    """Mask of the pixels whose centre falls inside a ground polygon once projected.

    Args:
        boundary: Polygon in ground coordinates.
        matrix: Ground to pixel transform.
        shape: ``(height, width)`` of the mask.

    Returns:
        The mask.
    """
    height, width = shape
    rows, columns = np.mgrid[0:height, 0:width]
    pixels = np.column_stack((columns.ravel() + 0.5, rows.ravel() + 0.5)).astype(np.float64)
    ground = apply(invert(matrix), pixels)
    return shapely.contains_xy(boundary, ground[:, 0], ground[:, 1]).reshape(shape)


def iou(first: Mask, second: Mask) -> float:
    """Intersection over union of two masks of the same shape (0 when both are empty)."""
    union = int((first | second).sum())
    return int((first & second).sum()) / union if union else 0.0


def outline_errors(
    mask: Mask, boundary: Polygon, matrix: AffineMatrix, *, sample_step_m: float
) -> NDArray[np.float64]:
    """Distances in metres between the mask outline and the projected boundary, both ways.

    Boundary samples are measured to the mask edge; each mask outline pixel is measured on the
    ground from the boundary ring to the pixel's outer side, half a pixel beyond its centre.

    Args:
        mask: The region on the image.
        boundary: The region on the ground.
        matrix: Ground to mask-pixel transform.
        sample_step_m: Spacing of the boundary samples, in metres.

    Returns:
        All distances, boundary samples first.
    """
    metres_per_pixel = 1.0 / linear_scale(matrix)
    projected = apply(matrix, outline_samples(boundary, sample_step_m))
    to_mask = np.abs(sample(edge_distance(mask), projected)) * metres_per_pixel
    rows, columns = np.nonzero(outline(mask))
    pixels = np.column_stack((columns + 0.5, rows + 0.5)).astype(np.float64)
    ground = apply(invert(matrix), pixels)
    depth = np.asarray(shapely.distance(shapely.points(ground), boundary.exterior))
    inside = shapely.contains_xy(boundary, ground[:, 0], ground[:, 1])
    to_boundary = np.abs(np.where(inside, depth, -depth) - 0.5 * metres_per_pixel)
    return np.concatenate((to_mask, to_boundary.astype(np.float64)))
