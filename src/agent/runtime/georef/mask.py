import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

type Mask = NDArray[np.bool_]
"""Boolean image, ``True`` inside the area of interest; indexed ``[row, column]``."""


def downscale(rgb: NDArray[np.uint8], factor: int) -> NDArray[np.float64]:
    """Average ``factor`` x ``factor`` blocks of an RGB image, dropping incomplete edge blocks.

    Pixel ``(i, j)`` of the result covers full-resolution pixels ``[i*factor, (i+1)*factor)``,
    so continuous pixel coordinates scale by exactly ``factor``.

    Args:
        rgb: Image of shape ``(height, width, 3)``.
        factor: Block side, at least 1.

    Returns:
        Image of shape ``(height // factor, width // factor, 3)``.
    """
    height, width = rgb.shape[0] // factor * factor, rgb.shape[1] // factor * factor
    blocks = rgb[:height, :width].reshape(height // factor, factor, width // factor, factor, 3)
    return blocks.mean(axis=(1, 3))


def largest_component(mask: Mask) -> Mask:
    """Keep the largest 8-connected region of a mask (empty mask unchanged)."""
    labels, count = ndimage.label(mask, structure=np.ones((3, 3)))
    if count == 0:
        return mask
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    return labels == int(np.argmax(sizes))


def colour_region(  # noqa: PLR0913 - one argument per knob
    rgb: NDArray[np.float64],
    *,
    min_saturation: float,
    close_px: int,
    close_iterations: int,
    open_px: int,
    open_iterations: int,
) -> Mask:
    """Mask of the largest coloured area of a map: zone fills against a white or grey sheet.

    Coloured pixels (channel spread above ``min_saturation``) are closed to bridge the black
    lines and labels drawn over the fills; the largest region is kept and its holes filled;
    an opening then cuts thin spurs (roads or leader lines drawn past the boundary).

    Args:
        rgb: Image of shape ``(height, width, 3)``, values 0-255.
        min_saturation: Smallest ``max(R, G, B) - min(R, G, B)`` of a fill pixel.
        close_px: Side of the square closing element.
        close_iterations: Closing repetitions.
        open_px: Side of the square opening element.
        open_iterations: Opening repetitions; zero skips opening.

    Returns:
        The region mask, same height and width as ``rgb``.
    """
    saturation = rgb.max(axis=2) - rgb.min(axis=2)
    mask = saturation > min_saturation
    mask = ndimage.binary_closing(
        mask, structure=np.ones((close_px, close_px)), iterations=close_iterations
    )
    mask = ndimage.binary_fill_holes(largest_component(mask))
    if open_iterations > 0:
        mask = ndimage.binary_opening(
            mask, structure=np.ones((open_px, open_px)), iterations=open_iterations
        )
    return largest_component(mask)


def outline(mask: Mask) -> Mask:
    """Pixels of a mask that touch its outside (4-connectivity)."""
    return mask & ~ndimage.binary_erosion(mask)
