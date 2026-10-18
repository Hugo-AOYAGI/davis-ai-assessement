import math
from collections.abc import Sequence
from typing import Self

from pydantic import model_validator

from agent.contracts.base import Contract
from agent.runtime.images.rulers import Ruler

_BOX_LENGTH = 4

type Size = tuple[int, int]
"""``(width, height)`` in pixels."""


class PixelBox(Contract):
    """A rectangle of raster pixels, ``x`` for columns and ``y`` for rows, end-exclusive."""

    x0: int
    y0: int
    x1: int
    y1: int

    @model_validator(mode="before")
    @classmethod
    def _from_sequence(cls, data: object) -> object:
        """Accept ``[x0, y0, x1, y1]``."""
        if isinstance(data, Sequence) and not isinstance(data, str):
            if len(data) != _BOX_LENGTH:
                msg = f"a pixel box is [x0, y0, x1, y1], got {len(data)} values"
                raise ValueError(msg)
            return dict(zip(("x0", "y0", "x1", "y1"), data, strict=True))
        return data

    @model_validator(mode="after")
    def _non_empty(self) -> Self:
        """Reject boxes with no area or starting at a negative coordinate."""
        if self.x0 < 0 or self.y0 < 0:
            msg = "a pixel box needs x0 >= 0 and y0 >= 0"
            raise ValueError(msg)
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


def output_size(box: PixelBox, max_output_px: int, max_upscale: float) -> Size:
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


def fit_size(size: Size, max_long_edge: int) -> Size:
    """Shrink a size so that its long edge fits, never enlarging it.

    Args:
        size: ``(width, height)`` to fit.
        max_long_edge: Upper bound of the long edge.

    Returns:
        The fitted ``(width, height)``, each at least one pixel.
    """
    width, height = size
    long_edge = max(width, height)
    if long_edge <= max_long_edge:
        return size
    scale = max_long_edge / long_edge
    return max(1, round(width * scale)), max(1, round(height * scale))


def scaled_size(size: Size, factor: float) -> Size:
    """Multiply a size by ``factor``, each side at least one pixel and never above ``size``.

    Args:
        size: ``(width, height)`` to scale.
        factor: Scale factor, below 1 to shrink.

    Returns:
        The scaled ``(width, height)``.
    """
    width, height = size
    return (
        min(width, max(1, math.floor(width * factor))),
        min(height, max(1, math.floor(height * factor))),
    )


def _to_full_axis(lo: int, hi: int, full: int, overview: int) -> tuple[int, int]:
    """Map an overview interval to the full-resolution pixels covering it, never empty."""
    start = min(lo * full // overview, full - 1)
    end = max(min(-(-hi * full // overview), full), start + 1)
    return start, end


class OverviewScale(Contract):
    """Correspondence between a page's full-resolution image and its downscaled overview."""

    full: Size
    """Full-resolution ``(width, height)``."""
    overview: Size
    """Overview ``(width, height)``."""

    @model_validator(mode="after")
    def _positive(self) -> Self:
        """Reject empty images."""
        if min(*self.full, *self.overview) < 1:
            msg = "image sizes need positive widths and heights"
            raise ValueError(msg)
        return self

    def contains(self, box: PixelBox) -> bool:
        """Whether an overview box lies within the overview."""
        return box.x1 <= self.overview[0] and box.y1 <= self.overview[1]

    def to_full(self, box: PixelBox) -> PixelBox:
        """Map an overview box to the full-resolution pixels covering it.

        Starts are floored and ends ceiled, then clamped to the full image; the result always
        holds at least one pixel.
        """
        x0, x1 = _to_full_axis(box.x0, box.x1, self.full[0], self.overview[0])
        y0, y1 = _to_full_axis(box.y0, box.y1, self.full[1], self.overview[1])
        return PixelBox(x0=x0, y0=y0, x1=x1, y1=y1)

    def rulers(self, box: PixelBox, size: Size) -> tuple[Ruler, Ruler]:
        """Rulers of a full-resolution box drawn at ``size``, labelled in overview coordinates.

        Args:
            box: Full-resolution pixels shown.
            size: Output ``(width, height)`` they are drawn at.

        Returns:
            The horizontal and vertical rulers.
        """
        return (
            Ruler(
                start=box.x0 * self.overview[0] / self.full[0],
                scale=size[0] / box.width * self.full[0] / self.overview[0],
                length=size[0],
            ),
            Ruler(
                start=box.y0 * self.overview[1] / self.full[1],
                scale=size[1] / box.height * self.full[1] / self.overview[1],
                length=size[1],
            ),
        )
