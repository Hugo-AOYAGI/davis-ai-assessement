from collections.abc import Mapping
from functools import cache, cached_property
from pathlib import Path

import pymupdf
from pydantic import Field, JsonValue

from agent.adapters.raster.load import load_raster
from agent.contracts.base import Contract
from agent.runtime.georef.affine import AffineTransform, Georeference
from agent.runtime.georef.crop import PixelBox

# Tools may not import agent.agents.config (layering), so the root is derived here:
# src/agent/tools/map/plan.py -> parents[4] is the repository root.
_PROJECT_ROOT = Path(__file__).resolve().parents[4]


class ZoningPlanSettings(Contract):
    """The ``corpus.zoning_map`` config block: a raster zoning plan and its georeference."""

    doc: str = Field(min_length=1)
    """Corpus document id used in citations."""
    source: str = Field(min_length=1)
    """PDF or image file, absolute or relative to the project root."""
    page: int = Field(ge=1)
    """1-based page of ``source`` holding the plan image."""
    size_px: tuple[int, int]
    """Expected native ``(width, height)``; the control points are only valid at this size."""
    georeference: Georeference
    legend: tuple[PixelBox, ...]
    """Pixel boxes of the legend panels."""


class ZoningPlan:
    """A zoning plan raster, loaded on first use, with its fitted georeference."""

    def __init__(self, settings: ZoningPlanSettings) -> None:
        """Keep the settings; nothing is loaded yet.

        Args:
            settings: The validated config block.
        """
        self.settings = settings

    @property
    def path(self) -> Path:
        """Absolute path of the source file."""
        source = Path(self.settings.source)
        return source if source.is_absolute() else _PROJECT_ROOT / source

    @cached_property
    def image(self) -> pymupdf.Pixmap:
        """The plan raster at native size.

        Raises:
            ValueError: If its size differs from ``size_px``.
        """
        image = load_raster(self.path, self.settings.page)
        if (image.width, image.height) != self.settings.size_px:
            msg = (
                f"{self.path.name} page {self.settings.page} is {image.width}x{image.height} px, "
                f"the georeference expects {self.settings.size_px[0]}x{self.settings.size_px[1]}"
            )
            raise ValueError(msg)
        return image

    @cached_property
    def transform(self) -> AffineTransform:
        """World to pixel transform fitted on the control points."""
        return AffineTransform.fit(self.settings.georeference.control_points)

    @cached_property
    def max_residual_m(self) -> float:
        """Largest control point residual of the fitted transform, in metres."""
        return max(self.transform.residuals_m(self.settings.georeference.control_points))


@cache
def _open(settings: ZoningPlanSettings) -> ZoningPlan:
    """Share one plan (and one decoded raster) between all tools using the same settings."""
    return ZoningPlan(settings)


def open_plan(plan: Mapping[str, JsonValue]) -> ZoningPlan:
    """Validate the ``zoning_map`` config block and return the shared plan for it.

    Args:
        plan: The block as a plain mapping (Hydra instantiates with ``_convert_="all"``).

    Returns:
        The plan; its raster is loaded on first access and then reused.
    """
    return _open(ZoningPlanSettings.model_validate(plan))
