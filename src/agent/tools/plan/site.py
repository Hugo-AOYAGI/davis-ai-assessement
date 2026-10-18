from pathlib import Path

import shapely
from langchain_core.tools import BaseTool, StructuredTool, ToolException
from pydantic import Field
from shapely.geometry import MultiPolygon, Polygon

from agent.adapters.geo.records import SiteError
from agent.adapters.geo.survey import SiteSurveyor
from agent.adapters.georef.store import load_georeference
from agent.adapters.http import ServiceError
from agent.adapters.images.pages import PageImages, RegionError, RenderedImage
from agent.adapters.images.render import RULER_BAND_PX, LineStyle, Overlay
from agent.adapters.images.store import ImageStore
from agent.contracts.base import Contract
from agent.contracts.evidence import ImageRegion
from agent.contracts.inputs.georeference import PlanGeoreference
from agent.runtime.geometry.parcels import to_shape
from agent.runtime.georef.affine import Points
from agent.runtime.georef.crop import OffPlanError, crop_region, site_rings
from agent.runtime.images.boxes import OverviewScale
from agent.tools.images.blocks import ContentBlock, image_block, text_block


class _PlanSiteSettings(Contract):
    """The ``plan_site`` knobs from config."""

    close_margin_m: float = Field(gt=0)
    context_margin_m: float = Field(gt=0)
    context_max_px: int = Field(gt=RULER_BAND_PX)
    max_upscale: float = Field(gt=0)
    uncertainty_factor: float = Field(gt=0)
    style: LineStyle


def plan_site_tool(  # noqa: PLR0913 - one argument per config knob
    *,
    surveyor: SiteSurveyor,
    pages: PageImages,
    store: ImageStore,
    georeference: Path,
    close_margin_m: float,
    context_margin_m: float,
    context_max_px: int,
    max_upscale: float,
    uncertainty_factor: float,
    style: LineStyle,
) -> BaseTool:
    """Build the ``plan_site`` tool: the site outlined on the georeferenced zoning plan.

    Args:
        surveyor: Site surveyor, which fetches the parcels (shared HTTP cache).
        pages: The corpus page images.
        store: Where the returned images are stored.
        georeference: JSON file of the plan georeference (``ingest georef`` output), read at
            each call so that the tool builds without it.
        close_margin_m: Ground margin around the site in the close-up crop, in metres.
        context_margin_m: Ground margin around the site in the context crop, in metres.
        context_max_px: Long edge of the context image, rulers included (the close-up uses
            the page images' ``max_image_px``).
        max_upscale: Upper bound of the enlargement of the plan's full-resolution pixels.
        uncertainty_factor: Stated outline uncertainty, as a multiple of the georeference's
            mean error.
        style: How the site outline is drawn.

    Returns:
        The tool.
    """
    settings = _PlanSiteSettings(
        close_margin_m=close_margin_m,
        context_margin_m=context_margin_m,
        context_max_px=context_max_px,
        max_upscale=max_upscale,
        uncertainty_factor=uncertainty_factor,
        style=style,
    )

    def plan_site(ids: list[str]) -> list[ContentBlock]:
        """Show the site on the zoning plan: its outline drawn in red, so you need not find it.

        Returns two crops of the plan with the outline of the parcels (merged) drawn as a thin
        red line: a close-up to read the zone code and the legend items on or near the site,
        and a wider context crop to follow district-wide perimeters around it. Both carry
        rulers in overview coordinates, like zoom: the reply gives each crop's region, usable
        as-is in zoom or as submit_zone's region. Zoom shows the plan without the outline. The
        outline is placed by georeferencing, with the stated uncertainty in metres.

        Args:
            ids: Cadastral ids of the site's parcels, e.g. ["91272000CR0247"].
        """
        georef = _georeference(georeference)
        site = _site(surveyor, ids)
        rings = site_rings(site, georef.matrix)
        overlay = Overlay(
            rings=tuple(tuple((float(u), float(v)) for u, v in ring) for ring in rings),
            style=settings.style,
        )
        views = (
            (settings.close_margin_m, None),
            (settings.context_margin_m, settings.context_max_px),
        )
        try:
            scale = pages.scale(georef.document, georef.page)
            _check_size(georef, scale)
            crops = [
                _crop(pages, georef, rings, scale, overlay=overlay, view=view, settings=settings)
                for view in views
            ]
        except (RegionError, OffPlanError) as error:
            raise ToolException(str(error)) from error
        caption = _caption(ids, georef, crops, settings)
        return [text_block(caption), *(image_block(store, view.png) for _, view in crops)]

    return StructuredTool.from_function(plan_site, parse_docstring=True, handle_tool_error=True)


def _georeference(path: Path) -> PlanGeoreference:
    """Load the plan georeference, telling the model how to build it when missing."""
    try:
        return load_georeference(path)
    except FileNotFoundError as error:
        raise ToolException(str(error)) from error


def _site(surveyor: SiteSurveyor, ids: list[str]) -> Polygon | MultiPolygon:
    """Fetch the parcels and merge them into the site's ground shape."""
    try:
        parcels = surveyor.parcels(ids)
    except (SiteError, ServiceError) as error:
        raise ToolException(str(error)) from error
    merged = shapely.union_all([to_shape(parcel.polygon) for parcel in parcels])
    if not isinstance(merged, Polygon | MultiPolygon) or merged.is_empty:
        msg = f"parcels {ids} have no area to outline"
        raise ToolException(msg)
    return merged


def _check_size(georef: PlanGeoreference, scale: OverviewScale) -> None:
    """Refuse a georeference fitted on a page image of another size."""
    expected = (georef.image_width, georef.image_height)
    if scale.full != expected:
        msg = (
            f"the plan georeference was fitted on a {expected[0]}x{expected[1]} page image but "
            f"the page renders at {scale.full[0]}x{scale.full[1]}; rebuild it with "
            "`uv run python -m agent.entrypoints.ingest georef`"
        )
        raise ToolException(msg)


def _crop(  # noqa: PLR0913 - one crop of the plan
    pages: PageImages,
    georef: PlanGeoreference,
    rings: list[Points],
    scale: OverviewScale,
    *,
    overlay: Overlay,
    view: tuple[float, int | None],
    settings: _PlanSiteSettings,
) -> tuple[ImageRegion, RenderedImage]:
    """Render the site outlined, with ``view`` = (ground margin, long edge or None) around it."""
    margin_m, max_px = view
    box = crop_region(rings, margin_m * georef.pixels_per_metre, scale)
    region = ImageRegion(
        doc=georef.document, page=georef.page, region=(box.x0, box.y0, box.x1, box.y1)
    )
    rendered = pages.outlined(region, overlay, max_upscale=settings.max_upscale, max_px=max_px)
    return region, rendered


def _caption(
    ids: list[str],
    georef: PlanGeoreference,
    crops: list[tuple[ImageRegion, RenderedImage]],
    settings: _PlanSiteSettings,
) -> str:
    """Say what the crops show, their regions and how far the outline may be off."""
    red, green, blue = settings.style.rgb
    uncertainty = settings.uncertainty_factor * georef.mean_error_m
    lines = [
        f"Site {', '.join(ids)} on {georef.document} p.{georef.page}, outlined in RGB ({red}, "
        f"{green}, {blue}). Outline position ±{uncertainty:.0f} m (plan georeferencing mean "
        f"error {georef.mean_error_m:.1f} m): a line within that distance of the outline may "
        "lie on either side of it."
    ]
    names = ("Image 1, close-up", "Image 2, context")
    margins = (settings.close_margin_m, settings.context_margin_m)
    for name, margin, (region, view) in zip(names, margins, crops, strict=True):
        x0, _, x1, _ = region.region
        enlargement = (view.image_size[0] - RULER_BAND_PX) / (x1 - x0)
        lines.append(
            f"{name} (site + {margin:.0f} m): region {list(region.region)}, enlarged "
            f"{enlargement:.1f}x over the overview."
        )
    lines.append(
        "Rulers give overview coordinates: pass a region to zoom (plan without the outline) or "
        "as submit_zone's region."
    )
    return "\n".join(lines)
