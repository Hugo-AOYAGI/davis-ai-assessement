from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import Field, JsonValue

from agent.adapters.raster.render import Channel, Outline, render_crop
from agent.contracts.base import Contract
from agent.contracts.findings.site import SiteContext
from agent.runtime.georef.crop import PixelBox, crop_box, output_size
from agent.runtime.georef.project import centroid, pixel_rings, to_crs
from agent.tools.map.blocks import ContentBlock, image_block, text_block
from agent.tools.map.plan import ZoningPlan, open_plan
from agent.tools.submit.artifacts import ArtifactsState, read_artifact


class _ViewSettings(Contract):
    """The ``view_map`` knobs from config."""

    site_artifact: str
    default_half_width_m: float = Field(gt=0)
    min_half_width_m: float = Field(gt=0)
    max_half_width_m: float = Field(gt=0)
    max_output_px: int = Field(gt=0)
    max_upscale: float = Field(gt=0)
    outline_rgb: tuple[Channel, Channel, Channel]
    outline_width_px: float = Field(gt=0)


def view_map_tool(  # noqa: PLR0913 - one argument per config knob
    *,
    plan: dict[str, JsonValue],
    site_artifact: str,
    default_half_width_m: float,
    min_half_width_m: float,
    max_half_width_m: float,
    max_output_px: int,
    max_upscale: float,
    outline_rgb: list[int],
    outline_width_px: float,
) -> BaseTool:
    """Build the ``view_map`` tool, showing the zoning plan around the site.

    Args:
        plan: The ``corpus.zoning_map`` config block.
        site_artifact: State artifact holding the ``SiteContext``.
        default_half_width_m: Crop half-width when the model gives none.
        min_half_width_m: Smallest half-width allowed.
        max_half_width_m: Largest half-width allowed.
        max_output_px: Long edge of the returned image.
        max_upscale: Cap on the enlargement over the plan's native resolution.
        outline_rgb: Site outline colour, 0-255 per channel.
        outline_width_px: Site outline width in output pixels.

    Returns:
        The tool.
    """
    zoning = open_plan(plan)
    settings = _ViewSettings.model_validate(
        {
            "site_artifact": site_artifact,
            "default_half_width_m": default_half_width_m,
            "min_half_width_m": min_half_width_m,
            "max_half_width_m": max_half_width_m,
            "max_output_px": max_output_px,
            "max_upscale": max_upscale,
            "outline_rgb": outline_rgb,
            "outline_width_px": outline_width_px,
        }
    )

    def view_map(
        runtime: ToolRuntime[None, ArtifactsState],
        half_width_m: float | None = None,
        east_m: float = 0,
        north_m: float = 0,
    ) -> list[ContentBlock]:
        """Look at the zoning plan around the site.

        Returns a square crop of the scanned zoning plan, north up, with the site outline drawn
        on it, and a caption giving the plan document and page, the crop position, its scale
        and the parcels outlined. The site must have been located first.

        Start with the default view and read the zone code printed on or near the site. If no
        label is visible, zoom out with a larger half_width_m to find zone labels and perimeters;
        pan with east_m / north_m to follow a boundary or reach a label outside the crop; zoom in
        with a smaller half_width_m to check whether a zone boundary, a perimeter or a symbol
        crosses or touches the site outline. Compare colours, hatching and symbols with
        view_legend.

        To cite what you read, use the document id and page given in the caption, quote the
        label exactly as printed on the plan, and keep the caption's crop reference so the
        reading can be checked.

        Args:
            runtime: Injected by the agent: the graph state holding the site.
            half_width_m: Half the side of the square crop, in metres on the ground. Omit it for
                the default view; values outside the allowed range are clamped.
            east_m: Shift of the crop centre east of the site centroid, in metres (negative
                values go west).
            north_m: Shift of the crop centre north of the site centroid, in metres (negative
                values go south).
        """
        site = read_artifact(runtime.state.get("artifacts"), settings.site_artifact, SiteContext)
        if site is None:
            return [text_block(_NO_SITE.format(artifact=settings.site_artifact))]
        return _view(zoning, settings, site, half_width_m, (east_m, north_m))

    return StructuredTool.from_function(view_map, name="view_map", parse_docstring=True)


def _view(
    zoning: ZoningPlan,
    settings: _ViewSettings,
    site: SiteContext,
    half_width_m: float | None,
    offset_m: tuple[float, float],
) -> list[ContentBlock]:
    """Crop the plan around the site centroid shifted by ``offset_m`` and caption it."""
    requested = settings.default_half_width_m if half_width_m is None else half_width_m
    half = min(max(requested, settings.min_half_width_m), settings.max_half_width_m)
    crs = zoning.settings.georeference.crs
    x, y = centroid(to_crs(site.polygon, crs))
    (centre,) = zoning.transform.to_pixel([(x + offset_m[0], y + offset_m[1])])
    box = crop_box(centre, half, zoning.transform.metres_per_pixel, zoning.settings.size_px)
    if box is None:
        return [text_block(_OFF_PLAN.format(east=offset_m[0], north=offset_m[1]))]
    outline = Outline(
        rings=pixel_rings(site.polygon, zoning.transform, crs),
        rgb=settings.outline_rgb,
        width_px=settings.outline_width_px,
    )
    png = render_crop(
        zoning.image,
        box,
        max_output_px=settings.max_output_px,
        max_upscale=settings.max_upscale,
        outline=outline,
    )
    lines = [
        _plan_line(zoning),
        _crop_line(settings, offset_m, requested, half),
        _scale_line(zoning, settings, box),
        _site_line(settings, site),
        _georef_line(zoning),
    ]
    return [text_block("\n".join(lines)), image_block(png)]


def _plan_line(zoning: ZoningPlan) -> str:
    """Name the document, page and plan size."""
    width, height = zoning.settings.size_px
    return (
        f"Zoning plan `{zoning.settings.doc}`, page {zoning.settings.page} "
        f"(plan image {width}x{height} px)."
    )


def _crop_line(
    settings: _ViewSettings, offset_m: tuple[float, float], requested: float, half: float
) -> str:
    """Describe where the crop is and its half-width."""
    clamped = "" if half == requested else f", clamped from the requested {requested:g} m"
    return (
        f"Crop centred {offset_m[0]:g} m east and {offset_m[1]:g} m north of the site centroid; "
        f"half-width {half:g} m{clamped} (allowed {settings.min_half_width_m:g}-"
        f"{settings.max_half_width_m:g} m)."
    )


def _scale_line(zoning: ZoningPlan, settings: _ViewSettings, box: PixelBox) -> str:
    """Give the crop reference, output size and scale."""
    width, height = output_size(box, settings.max_output_px, settings.max_upscale)
    metres = box.width * zoning.transform.metres_per_pixel / width
    plan_width, plan_height = zoning.settings.size_px
    at_edge = box.x0 == 0 or box.y0 == 0 or box.x1 == plan_width or box.y1 == plan_height
    edge = " The crop is cut by the plan edge, so it is off-centre." if at_edge else ""
    return (
        f"Crop reference: plan px {box.as_list()} ([x0, y0, x1, y1]); image {width}x{height} px, "
        f"{metres:.2f} m per image pixel, north up.{edge}"
    )


def _site_line(settings: _ViewSettings, site: SiteContext) -> str:
    """Say how the site is drawn and which parcels it covers."""
    red, green, blue = settings.outline_rgb
    parcels = ", ".join(parcel.id for parcel in site.parcels)
    return f"Site outlined in RGB ({red}, {green}, {blue}); parcels {parcels}."


def _georef_line(zoning: ZoningPlan) -> str:
    """State the georeference quality."""
    count = len(zoning.settings.georeference.control_points)
    return (
        f"Georeference: {count} control points, max residual {zoning.max_residual_m:.1f} m; "
        "the outline may be off by about that much."
    )


_NO_SITE = (
    "The site is not known yet: the `{artifact}` artifact (submitted by site_locator) is "
    "missing, so there is nothing to centre the plan on. Stop and report that the site must be "
    "located first; do not guess a location."
)
_OFF_PLAN = (
    "A crop centred {east:g} m east and {north:g} m north of the site lies entirely outside the "
    "plan image. Reduce east_m / north_m."
)
