from collections.abc import Mapping, Sequence

import pymupdf
from pydantic import Field

from agent.adapters.http import CachedHttp
from agent.contracts.base import Contract
from agent.runtime.geometry.projection import Bounds

type Pixel = tuple[float, float]
type Rgb = tuple[int, int, int]

_CHANNEL_MAX = 255


class Outline(Contract):
    """A labelled shape to draw on an image, in pixel coordinates."""

    label: str
    """Text written at ``anchor``; empty for none."""
    rings: tuple[tuple[Pixel, ...], ...]
    """Rings, ``(column, row)`` pixels from the top-left corner."""
    anchor: Pixel
    """Where the label is written."""
    rgb: Rgb | None = None
    """Line and label colour; the style's when null."""
    fill_rgb: Rgb | None = None
    """Fill colour (even-odd, so inner rings are holes); no fill when null."""
    fill_opacity: float = Field(default=1.0, ge=0, le=1)
    closed: bool = True
    """Whether each ring is closed; an open ring is a polyline, e.g. a dimension line."""


class OutlineStyle(Contract):
    """How outlines and their labels are drawn."""

    rgb: Rgb
    """Line and text colour, 0-255 per channel."""
    width_px: float
    font_px: float
    label_background_rgb: Rgb
    """Colour of the box behind each label, for legibility on photos."""


class ImageryClient:
    """Client of a WMS ``GetMap`` endpoint (IGN Géoplateforme): one layer per image kind."""

    def __init__(  # noqa: PLR0913 - one argument per config knob
        self,
        *,
        url: str,
        http: CachedHttp,
        version: str,
        crs: str,
        media_type: str,
        layers: Mapping[str, str],
        source: str,
    ) -> None:
        """Create the client.

        Args:
            url: WMS endpoint, e.g. ``https://data.geopf.fr/wms-r/wms``.
            http: Cached HTTP client.
            version: WMS version, e.g. ``1.3.0``.
            crs: CRS of the requested boxes, e.g. ``EPSG:2154`` (x east, y north).
            media_type: Image format requested and expected, e.g. ``image/png``.
            layers: WMS layer name per image kind, e.g. ``{"aerial": "ORTHOIMAGERY.ORTHOPHOTOS"}``.
            source: Name of the service, for captions.
        """
        self._url = url
        self._http = http
        self._version = version
        self._crs = crs
        self._media_type = media_type
        self.layers = dict(layers)
        self.source = source

    def get_map(self, kind: str, bounds: Bounds, size_px: tuple[int, int]) -> bytes:
        """Return the image of a ground box, north up.

        Args:
            kind: Image kind, a key of ``layers``.
            bounds: Ground box in the client's CRS.
            size_px: Image ``(width, height)`` in pixels.

        Returns:
            The image bytes.

        Raises:
            KeyError: If ``kind`` has no layer.
            ServiceError: If the service fails or answers something else than an image.
        """
        width, height = size_px
        params = {
            "SERVICE": "WMS",
            "VERSION": self._version,
            "REQUEST": "GetMap",
            "LAYERS": self.layers[kind],
            "STYLES": "",
            "CRS": self._crs,
            "BBOX": ",".join(str(value) for value in bounds),
            "WIDTH": str(width),
            "HEIGHT": str(height),
            "FORMAT": self._media_type,
        }
        return self._http.get_bytes(self._url, params, self._media_type)


def blank_image(size_px: tuple[int, int]) -> bytes:
    """Return a white PNG, the canvas used when no map can be fetched.

    Args:
        size_px: Image ``(width, height)`` in pixels.

    Returns:
        PNG bytes.
    """
    width, height = size_px
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height), False)
    pixmap.clear_with(_CHANNEL_MAX)
    return bytes(pixmap.tobytes("png"))


def draw_outlines(image: bytes, outlines: Sequence[Outline], style: OutlineStyle) -> bytes:
    """Draw labelled outlines over an image, in order, then every label on top.

    The image is placed on a temporary PDF page whose size in points equals its size in pixels,
    so MuPDF does the drawing and the PNG encoding; no imaging library is needed.

    Args:
        image: Image bytes (PNG or JPEG).
        outlines: Shapes to draw, in the image's pixel coordinates; later ones on top.
        style: Line width, font, label background, and the colour of outlines that set none.

    Returns:
        PNG bytes of the same size as ``image``.
    """
    pixmap = pymupdf.Pixmap(image)
    background = _unit(style.label_background_rgb)
    with pymupdf.open() as document:
        page = document.new_page(width=pixmap.width, height=pixmap.height)
        page.insert_image(page.rect, pixmap=pixmap)
        shape = page.new_shape()
        for outline in outlines:
            for ring in outline.rings:
                shape.draw_polyline(ring)
            shape.finish(
                color=_unit(outline.rgb or style.rgb),
                fill=None if outline.fill_rgb is None else _unit(outline.fill_rgb),
                fill_opacity=outline.fill_opacity,
                width=style.width_px,
                closePath=outline.closed,
                even_odd=True,
            )
        for outline in (outline for outline in outlines if outline.label):
            x, y = outline.anchor
            length = pymupdf.get_text_length(outline.label, fontsize=style.font_px)
            shape.draw_rect(pymupdf.Rect(x, y - style.font_px, x + length, y + style.font_px / 4))
            shape.finish(color=None, fill=background)
            colour = _unit(outline.rgb or style.rgb)
            shape.insert_text((x, y), outline.label, fontsize=style.font_px, color=colour)
        shape.commit()
        return bytes(page.get_pixmap(alpha=False).tobytes("png"))


def _unit(rgb: Rgb) -> tuple[float, float, float]:
    """Convert a 0-255 colour to MuPDF's 0-1 channels."""
    red, green, blue = rgb
    return (red / _CHANNEL_MAX, green / _CHANNEL_MAX, blue / _CHANNEL_MAX)
