from collections.abc import Mapping, Sequence
from typing import Literal, TypeAliasType, get_args

import shapely
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import Field

from agent.adapters.geo.imagery import ImageryClient, Outline, OutlineStyle, draw_outlines
from agent.adapters.geo.records import SiteError
from agent.adapters.geo.survey import SiteSurveyor
from agent.adapters.http import ServiceError
from agent.adapters.images.store import ImageStore
from agent.contracts.base import Contract
from agent.contracts.findings.site import Parcel
from agent.runtime.geometry.parcels import to_shape
from agent.runtime.geometry.projection import Bounds, fit_half_width, square_around, to_pixels
from agent.tools.images.blocks import ContentBlock, image_block, text_block

type Kind = Literal["map", "aerial"]
type Scale = Literal["town", "neighbourhood", "parcel"]

_FITTED: Scale = "parcel"
_KIND_NAMES: dict[str, str] = {
    "map": "IGN map (streets and their names, buildings, places)",
    "aerial": "Aerial photo (orthophoto)",
}
_MAX_IMAGE_PX = 2000


class _ViewSettings(Contract):
    """The ``site_view`` knobs from config."""

    half_widths_m: dict[str, float]
    parcel_margin_ratio: float = Field(ge=0)
    min_half_width_m: float = Field(gt=0)
    image_px: int = Field(gt=0, le=_MAX_IMAGE_PX)
    style: OutlineStyle


def site_view_tool(  # noqa: PLR0913 - one argument per config knob
    *,
    surveyor: SiteSurveyor,
    imagery: ImageryClient,
    store: ImageStore,
    half_widths_m: Mapping[str, float],
    parcel_margin_ratio: float,
    min_half_width_m: float,
    image_px: int,
    style: OutlineStyle,
) -> BaseTool:
    """Build the ``site_view`` tool: a map or aerial photo with parcel outlines drawn on it.

    Args:
        surveyor: Site surveyor, which fetches the parcels.
        imagery: WMS client; its layers must cover every image kind.
        store: Where the returned images are stored.
        half_widths_m: Half the side of the square view per fixed scale (``town``,
            ``neighbourhood``), in metres.
        parcel_margin_ratio: Margin around the parcels at the ``parcel`` scale, as a share of
            their extent.
        min_half_width_m: Smallest half-side of a ``parcel`` view.
        image_px: Side of the square image, in pixels (at most 2000).
        style: How the outlines and ids are drawn.

    Returns:
        The tool.

    Raises:
        ValueError: If a scale or an image kind has no setting.
    """
    settings = _ViewSettings(
        half_widths_m=dict(half_widths_m),
        parcel_margin_ratio=parcel_margin_ratio,
        min_half_width_m=min_half_width_m,
        image_px=image_px,
        style=style,
    )
    unset_scales = _names(Scale) - {_FITTED} - set(settings.half_widths_m)
    if missing := sorted(unset_scales | (_names(Kind) - set(imagery.layers))):
        msg = f"site_view has no setting for {missing}"
        raise ValueError(msg)

    def site_view(ids: list[str], kind: Kind, scale: Scale = "parcel") -> list[ContentBlock]:
        """Look at parcels on the ground: an IGN map or aerial photo with their outlines drawn.

        The image is north up; each parcel's outline and id are drawn on it. Use `aerial` to see
        what is on the parcels (buildings, gardens, trees, a strip along the street) and `map`
        for street names and the surroundings. The `town` scale shows the
        parcels within the town, `neighbourhood` the surrounding blocks, `parcel` fits the
        parcels with a margin. The caption gives the scale in metres per pixel. The image is a
        geometric source: it shows the ground, not what planning rules allow.

        Args:
            ids: Cadastral ids of the parcels to outline, e.g. ["91272000CR0247"].
            kind: `map` or `aerial`.
            scale: `town`, `neighbourhood` or `parcel`.
        """
        try:
            parcels = surveyor.parcels(ids)
        except (SiteError, ServiceError) as error:
            return [text_block(f"site_view failed: {error}")]
        bounds = _view_bounds(parcels, scale, settings)
        size = (settings.image_px, settings.image_px)
        try:
            image = imagery.get_map(kind, bounds, size)
        except ServiceError as error:
            return [text_block(f"site_view failed: {error}")]
        png = draw_outlines(image, _outlines(parcels, bounds, size), settings.style)
        caption = _caption(parcels, kind, scale, bounds, settings=settings, imagery=imagery)
        return [text_block(caption), image_block(store, png)]

    return StructuredTool.from_function(site_view, name="site_view", parse_docstring=True)


def _names(alias: TypeAliasType) -> set[str]:
    """Return the values of a ``Literal`` type alias."""
    return {str(value) for value in get_args(alias.__value__)}


def _view_bounds(parcels: Sequence[Parcel], scale: str, settings: _ViewSettings) -> Bounds:
    """Return the square ground box shown at a scale, centred on the parcels."""
    min_x, min_y, max_x, max_y = shapely.union_all([to_shape(p.polygon) for p in parcels]).bounds
    extent = (min_x, min_y, max_x, max_y)
    if scale == _FITTED:
        half = fit_half_width(extent, settings.parcel_margin_ratio, settings.min_half_width_m)
    else:
        half = settings.half_widths_m[scale]
    return square_around(((min_x + max_x) / 2, (min_y + max_y) / 2), half)


def _outlines(parcels: Sequence[Parcel], bounds: Bounds, size: tuple[int, int]) -> list[Outline]:
    """Convert the parcels' rings and label points to image pixels."""
    outlines = []
    for parcel in parcels:
        rings = (parcel.polygon.exterior, *parcel.polygon.holes)
        point = to_shape(parcel.polygon).representative_point()
        outlines.append(
            Outline(
                label=parcel.id,
                rings=tuple(tuple(to_pixels(ring, bounds, size)) for ring in rings),
                anchor=to_pixels([(point.x, point.y)], bounds, size)[0],
            )
        )
    return outlines


def _caption(  # noqa: PLR0913 - everything the caption states
    parcels: Sequence[Parcel],
    kind: str,
    scale: str,
    bounds: Bounds,
    *,
    settings: _ViewSettings,
    imagery: ImageryClient,
) -> str:
    """Describe the view: kind, scale, ground size, resolution, outlines and source."""
    side = bounds[2] - bounds[0]
    red, green, blue = settings.style.rgb
    ids = ", ".join(parcel.id for parcel in parcels)
    return (
        f"{_KIND_NAMES[kind]}, scale `{scale}`: {side:.0f} m x {side:.0f} m, "
        f"{side / settings.image_px:.2f} m per pixel, north up.\n"
        f"Outlined in RGB ({red}, {green}, {blue}) with their ids, from the cadastre: {ids}.\n"
        f"Source: {imagery.source}, layer {imagery.layers[kind]}. Geometric source, not "
        "regulatory: it shows the ground, not what the planning rules allow."
    )
