from collections.abc import Sequence
from typing import Self

from pydantic import model_validator

from agent.contracts.base import Contract
from agent.contracts.geometry import Point

_BOX_LENGTH = 4


class PixelBox(Contract):
    """A rectangle of raster pixels, ``x`` for columns and ``y`` for rows, end-exclusive."""

    x0: int
    y0: int
    x1: int
    y1: int

    @model_validator(mode="before")
    @classmethod
    def _from_sequence(cls, data: object) -> object:
        """Accept ``[x0, y0, x1, y1]`` as written in config."""
        if isinstance(data, Sequence) and not isinstance(data, str):
            if len(data) != _BOX_LENGTH:
                msg = f"a pixel box is [x0, y0, x1, y1], got {len(data)} values"
                raise ValueError(msg)
            return dict(zip(("x0", "y0", "x1", "y1"), data, strict=True))
        return data

    @model_validator(mode="after")
    def _non_empty(self) -> Self:
        """Reject boxes with no area."""
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            msg = "a pixel box needs x1 > x0 and y1 > y0"
            raise ValueError(msg)
        return self

    @property
    def width(self) -> int:
        """Number of columns."""
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        """Number of rows."""
        return self.y1 - self.y0

    def as_list(self) -> list[int]:
        """Return ``[x0, y0, x1, y1]``."""
        return [self.x0, self.y0, self.x1, self.y1]


def crop_box(
    centre: Point, half_width_m: float, metres_per_pixel: float, size_px: tuple[int, int]
) -> PixelBox | None:
    """Square crop around a pixel, clamped to the raster.

    Near the raster edges the clamped box is smaller than requested and no longer centred on
    ``centre``.

    Args:
        centre: ``(column, row)`` of the crop centre at native size.
        half_width_m: Half the side of the square, in metres on the ground.
        metres_per_pixel: Ground distance covered by one raster pixel.
        size_px: Raster ``(width, height)``.

    Returns:
        The clamped box, or ``None`` when the requested square lies entirely outside the raster.
    """
    side = max(1, round(2 * half_width_m / metres_per_pixel))
    column, row = centre
    left, top = round(column - side / 2), round(row - side / 2)
    width, height = size_px
    x0, y0 = max(0, left), max(0, top)
    x1, y1 = min(width, left + side), min(height, top + side)
    if x1 <= x0 or y1 <= y0:
        return None
    return PixelBox(x0=x0, y0=y0, x1=x1, y1=y1)


def output_size(box: PixelBox, max_output_px: int, max_upscale: float) -> tuple[int, int]:
    """Size of a crop once scaled for display.

    The long edge becomes ``max_output_px``, unless that would enlarge the native pixels more
    than ``max_upscale`` times.

    Args:
        box: The crop at native size.
        max_output_px: Upper bound of the output's long edge.
        max_upscale: Upper bound of the enlargement factor.

    Returns:
        Output ``(width, height)``, each at least one pixel.
    """
    long_edge = max(box.width, box.height)
    scale = min(max_output_px, long_edge * max_upscale) / long_edge
    return max(1, round(box.width * scale)), max(1, round(box.height * scale))
