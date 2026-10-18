from datetime import date
from pathlib import Path

import numpy as np
from omegaconf import DictConfig, OmegaConf
from pydantic import ConfigDict, Field

from agent.adapters.files import publish
from agent.adapters.georef.boundary import CommuneBoundaryClient
from agent.adapters.georef.raster import mask_png, pixmap_array
from agent.adapters.georef.store import save_georeference
from agent.adapters.images.load import page_image
from agent.contracts.base import Contract
from agent.contracts.inputs.georeference import PlanGeoreference
from agent.ingest.georef.overlay import OverlaySettings, boundary_overview
from agent.observability.logs import get_logger
from agent.runtime.georef.affine import linear_scale, scaled
from agent.runtime.georef.fit import fit_affine
from agent.runtime.georef.mask import colour_region, downscale
from agent.runtime.georef.score import iou, outline_errors, rasterize

logger = get_logger(__name__)


class MaskSettings(Contract):
    """How the commune interior is found on the plan (see ``runtime.georef.mask``)."""

    downscale: int = Field(ge=1)
    """Block side used to shrink the page before masking and fitting."""
    min_saturation: float = Field(ge=0)
    close_px: int = Field(ge=1)
    close_iterations: int = Field(ge=1)
    open_px: int = Field(ge=1)
    open_iterations: int = Field(ge=0)


class FitSettings(Contract):
    """Affine fit settings (see ``runtime.georef.fit.fit_affine``)."""

    sample_step_m: float = Field(gt=0)
    robust_scale_px: float = Field(gt=0)


class GeorefSettings(Contract):
    """The ``corpus.georef`` config node, without the boundary client built from it."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    document: str = Field(min_length=1)
    """Corpus document id of the raster plan (its PDF is looked up in ``corpus.documents``)."""
    page: int = Field(ge=1)
    insee: str = Field(min_length=5, max_length=5)
    """Commune whose outline is matched."""
    crs: str
    output: str
    """Georeference JSON, relative to the project root."""
    debug_dir: str
    """Directory of the mask and overlay PNGs, relative to the project root."""
    render_dpi: int = Field(ge=1)
    scan_min_coverage: float = Field(gt=0, le=1)
    mask: MaskSettings
    fit: FitSettings
    overlay: OverlaySettings


def load_georef_settings(georef_cfg: DictConfig) -> GeorefSettings:
    """Validate the ``corpus.georef`` config node."""
    return GeorefSettings.model_validate(OmegaConf.to_container(georef_cfg, resolve=True))


def georeference_plan(
    settings: GeorefSettings,
    root: Path,
    plan: Path,
    boundary: CommuneBoundaryClient,
    today: date,
) -> PlanGeoreference:
    """Fit ground metres to plan pixels by matching the commune outline, and save it.

    The commune interior is masked on the plan from its zone fills, the official outline is
    fetched, and an affine transform is fitted between them at reduced resolution then scaled
    to the full-resolution page image. A mask PNG and an overview with the projected outline
    are written to ``settings.debug_dir``.

    Args:
        settings: Georeferencing settings.
        root: Project root, against which config paths are resolved.
        plan: The plan's PDF.
        boundary: Client of the commune outline service.
        today: Date recorded with the result.

    Returns:
        The saved georeference.
    """
    image = page_image(
        plan,
        settings.page,
        render_dpi=settings.render_dpi,
        scan_min_coverage=settings.scan_min_coverage,
    )
    knobs = settings.mask
    mask = colour_region(
        downscale(pixmap_array(image), knobs.downscale),
        min_saturation=knobs.min_saturation,
        close_px=knobs.close_px,
        close_iterations=knobs.close_iterations,
        open_px=knobs.open_px,
        open_iterations=knobs.open_iterations,
    )
    outline = boundary.outline(settings.insee)
    fit = settings.fit
    reduced = fit_affine(
        mask, outline, sample_step_m=fit.sample_step_m, robust_scale_px=fit.robust_scale_px
    )
    errors = outline_errors(mask, outline, reduced, sample_step_m=fit.sample_step_m)
    matrix = scaled(reduced, knobs.downscale)
    result = PlanGeoreference(
        document=settings.document,
        page=settings.page,
        image_width=image.width,
        image_height=image.height,
        crs=settings.crs,
        matrix=matrix,
        pixels_per_metre=linear_scale(matrix),
        iou=iou(mask, rasterize(outline, reduced, mask.shape)),
        mean_error_m=float(np.mean(errors)),
        max_error_m=float(np.max(errors)),
        boundary_source=f"{boundary.source} code_insee={settings.insee}",
        created=today,
    )
    save_georeference(result, root / settings.output)
    debug = root / settings.debug_dir
    publish(debug / "mask.png", mask_png(mask))
    publish(debug / "boundary.png", boundary_overview(image, outline, matrix, settings.overlay))
    logger.info(
        "%s p%d georeferenced: IoU %.3f, outline error mean %.1f m max %.1f m, written to %s",
        settings.document,
        settings.page,
        result.iou,
        result.mean_error_m,
        result.max_error_m,
        settings.output,
    )
    return result
