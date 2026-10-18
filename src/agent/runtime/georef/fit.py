import numpy as np
import shapely
from numpy.typing import NDArray
from scipy import ndimage, optimize
from shapely.geometry import Polygon

from agent.contracts.inputs.georeference import AffineMatrix
from agent.runtime.georef.affine import Points, from_linear
from agent.runtime.georef.mask import Mask

_MOMENT_SAMPLES = 200
"""Grid steps across the boundary's extent when sampling its area for second moments."""


def outline_samples(boundary: Polygon, step_m: float) -> Points:
    """Points along the exterior ring of a polygon, at most ``step_m`` apart."""
    ring = shapely.segmentize(boundary.exterior, step_m)
    return np.asarray(ring.coords, dtype=np.float64)[:, :2]


def edge_distance(mask: Mask) -> NDArray[np.float64]:
    """Signed distance in pixels from each pixel centre to the edge of ``mask``.

    The edge runs between inside and outside pixels, half a pixel from each centre; distances
    are negative inside, so bilinear samples cross zero exactly on the edge.
    """
    inside = ndimage.distance_transform_edt(mask)
    outside = ndimage.distance_transform_edt(~mask)
    return np.asarray(np.where(mask, 0.5 - inside, outside - 0.5), dtype=np.float64)


def sample(image: NDArray[np.float64], pixels: Points) -> NDArray[np.float64]:
    """Bilinear samples of an image at continuous pixel coordinates ``(u, v)``."""
    rows, columns = pixels[:, 1] - 0.5, pixels[:, 0] - 0.5
    return ndimage.map_coordinates(image, [rows, columns], order=1, mode="nearest")


def fit_affine(
    mask: Mask, boundary: Polygon, *, sample_step_m: float, robust_scale_px: float
) -> AffineMatrix:
    """Fit the affine transform that lays a ground polygon on the matching region of an image.

    Starting points come from moments: centroids for the translation, the area ratio for the
    scale and the principal axes for the rotation, tried with and without a mirror (image rows
    grow downwards) and with both axis orientations. Each is refined by robust least squares on
    the distance from the projected outline samples to the mask outline; the lowest cost wins.

    Args:
        mask: The region on the image (e.g. the commune drawn on a plan).
        boundary: The same region on the ground, in a metric CRS.
        sample_step_m: Spacing of the outline samples, in metres.
        robust_scale_px: Residual in pixels beyond which a sample's weight decreases
            (``soft_l1`` loss), so local mismatches do not drag the fit.

    Returns:
        Matrix from ground coordinates to the mask's continuous pixel coordinates.

    Raises:
        ValueError: If the mask is empty.
    """
    if not mask.any():
        msg = "cannot fit an affine transform on an empty mask"
        raise ValueError(msg)
    centre = np.array([boundary.centroid.x, boundary.centroid.y])
    points = outline_samples(boundary, sample_step_m) - centre
    distance = edge_distance(mask)

    def residuals(params: NDArray[np.float64]) -> NDArray[np.float64]:
        """Signed edge distances of the projected outline samples, in pixels."""
        pixels = points @ params[:4].reshape(2, 2).T + params[4:]
        return sample(distance, pixels)

    fits = []
    for start in initial_guesses(mask, boundary):
        result = optimize.least_squares(residuals, start, loss="soft_l1", f_scale=robust_scale_px)
        fits.append((float(result.cost), np.asarray(result.x, dtype=np.float64)))
    _, params = min(fits, key=lambda fit: fit[0])
    linear = params[:4].reshape(2, 2)
    return from_linear(linear, params[4:] - linear @ centre)


def initial_guesses(mask: Mask, boundary: Polygon) -> list[NDArray[np.float64]]:
    """Starting parameters ``(A11, A12, A21, A22, u0, v0)`` for :func:`fit_affine`.

    ``A`` maps ground offsets from the boundary centroid to pixel offsets; ``(u0, v0)`` is the
    mask centroid. Four candidates: two mirror states times two principal-axis orientations.
    """
    rows, columns = np.nonzero(mask)
    pixels = np.column_stack((columns + 0.5, rows + 0.5)).astype(np.float64)
    ground = _area_samples(boundary)
    scale = float(np.sqrt(mask.sum() / boundary.area))
    image_angle = _principal_angle(pixels)
    guesses = []
    for mirror in (1.0, -1.0):
        flip = np.diag([1.0, mirror])
        ground_angle = _principal_angle(ground @ flip.T)
        for turn in (0.0, np.pi):
            linear = scale * _rotation(image_angle - ground_angle + turn) @ flip
            guesses.append(np.concatenate((linear.ravel(), pixels.mean(axis=0))))
    return guesses


def _area_samples(boundary: Polygon) -> Points:
    """Grid points inside a polygon, about ``_MOMENT_SAMPLES`` per side of its extent."""
    min_x, min_y, max_x, max_y = boundary.bounds
    step = max(max_x - min_x, max_y - min_y) / _MOMENT_SAMPLES
    xs, ys = np.meshgrid(np.arange(min_x, max_x, step), np.arange(min_y, max_y, step))
    inside = shapely.contains_xy(boundary, xs.ravel(), ys.ravel())
    return np.column_stack((xs.ravel()[inside], ys.ravel()[inside]))


def _principal_angle(points: Points) -> float:
    """Angle of the major principal axis of a point cloud, in radians."""
    covariance = np.cov(points.T)
    values, vectors = np.linalg.eigh(covariance)
    major = vectors[:, int(np.argmax(values))]
    return float(np.arctan2(major[1], major[0]))


def _rotation(angle: float) -> NDArray[np.float64]:
    """2x2 rotation matrix."""
    cos, sin = np.cos(angle), np.sin(angle)
    return np.array([[cos, -sin], [sin, cos]])
