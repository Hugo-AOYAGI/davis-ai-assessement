import math

from pydantic import Field

from agent.contracts.base import Contract

_NICE_MANTISSAS = (1, 2, 5)


def nice_step(target: float) -> int:
    """Round a tick spacing to the closest value of the form 1, 2 or 5 times a power of ten.

    Args:
        target: Wanted spacing, in the units the ticks are labelled with.

    Returns:
        The nice spacing, at least 1.
    """
    if target <= 1:
        return 1
    exponent = math.floor(math.log10(target))
    candidates = [
        mantissa * 10**power for power in (exponent, exponent + 1) for mantissa in _NICE_MANTISSAS
    ]
    return min(candidates, key=lambda candidate: abs(candidate - target))


class Ruler(Contract):
    """One axis of an image, labelled in overview pixel coordinates."""

    start: float = Field(ge=0)
    """Overview coordinate at the first output pixel of the axis."""
    scale: float = Field(gt=0)
    """Output pixels per overview pixel."""
    length: int = Field(gt=0)
    """Number of output pixels along the axis."""

    def ticks(self, step_px: int) -> tuple[tuple[float, int], ...]:
        """Place labelled ticks roughly ``step_px`` output pixels apart.

        Args:
            step_px: Wanted spacing between ticks, in output pixels.

        Returns:
            ``(position, value)`` pairs: the output pixel offset along the axis and the overview
            coordinate found there, a multiple of a nice step.
        """
        step = nice_step(step_px / self.scale)
        end = self.start + self.length / self.scale
        first = math.ceil(self.start / step) * step
        return tuple(
            ((value - self.start) * self.scale, value)
            for value in range(first, math.ceil(end), step)
        )
