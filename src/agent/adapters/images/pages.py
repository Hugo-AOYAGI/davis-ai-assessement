import threading
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from pathlib import Path

import pymupdf
from pydantic import Field, PositiveFloat, PositiveInt

from agent.adapters.images.load import page_count, page_image
from agent.adapters.images.render import RULER_BAND_PX, crop_png, render_view
from agent.contracts.base import Contract
from agent.contracts.evidence import ImageRegion, StoredCrop
from agent.runtime.images.boxes import OverviewScale, PixelBox, Size, fit_size, output_size


class RegionError(ValueError):
    """A page or region that does not exist; the message tells the model why."""


class RenderedImage(Contract):
    """A page view with rulers labelled in overview coordinates."""

    png: bytes
    image_size: Size
    """``(width, height)`` of the PNG, ruler bands included."""
    overview_size: Size
    """``(width, height)`` of the page overview, the coordinate system of the rulers."""
    full_size: Size
    """``(width, height)`` of the full-resolution page image."""


class _Settings(Contract):
    """Validated knobs of ``PageImages``."""

    render_dpi: PositiveInt
    max_image_px: int = Field(gt=RULER_BAND_PX)
    max_upscale: PositiveFloat
    ruler_step_px: PositiveInt
    crop_max_px: PositiveInt
    cache_size: PositiveInt
    scan_min_coverage: float = Field(gt=0, le=1)


class PageImages:
    """Corpus pages as images: overviews, zooms and full-resolution crops.

    Regions are given in overview coordinates, i.e. pixels of the page image downscaled so that
    the overview plus its ruler bands fits ``max_image_px``. PyMuPDF is not thread-safe, so all
    its work and the page cache run under one lock.
    """

    def __init__(  # noqa: PLR0913 - one argument per config knob
        self,
        *,
        documents: Sequence[Mapping[str, object]],
        root: Path,
        render_dpi: int,
        max_image_px: int,
        max_upscale: float,
        ruler_step_px: int,
        crop_max_px: int,
        cache_size: int,
        scan_min_coverage: float,
    ) -> None:
        """Index the documents and validate the knobs.

        Args:
            documents: Corpus documents; only their ``id`` and ``path`` (relative to ``root``)
                are read.
            root: Project root.
            render_dpi: Resolution at which pages that are not scans are rendered.
            max_image_px: Upper bound of the long edge of every returned image.
            max_upscale: Upper bound of the enlargement of full-resolution pixels in a zoom.
            ruler_step_px: Wanted spacing between ruler ticks, in output pixels.
            crop_max_px: Upper bound of the long edge of a saved crop.
            cache_size: Number of decoded page images kept in memory.
            scan_min_coverage: Share of the page an image must cover to make the page a scan.
        """
        self._settings = _Settings(
            render_dpi=render_dpi,
            max_image_px=max_image_px,
            max_upscale=max_upscale,
            ruler_step_px=ruler_step_px,
            crop_max_px=crop_max_px,
            cache_size=cache_size,
            scan_min_coverage=scan_min_coverage,
        )
        self._root = root
        self._paths = {str(document["id"]): root / str(document["path"]) for document in documents}
        self._counts: dict[str, int] = {}
        self._images: OrderedDict[tuple[str, int], pymupdf.Pixmap] = OrderedDict()
        self._lock = threading.Lock()

    def overview(self, doc: str, page: int) -> RenderedImage:
        """The whole page, downscaled to its overview size, with rulers.

        Raises:
            RegionError: If the document or page does not exist.
        """
        with self._lock:
            self._check_page(doc, page)
            image, scale = self._load(doc, page)
            box = PixelBox(x0=0, y0=0, x1=scale.full[0], y1=scale.full[1])
            return self._render(image, box, scale, scale.overview)

    def zoom(self, region: ImageRegion) -> RenderedImage:
        """A region of a page, enlarged, with rulers still labelled in overview coordinates.

        Raises:
            RegionError: If the document, page or region does not exist.
        """
        with self._lock:
            image, scale, box = self._locate(region)
            content_px = self._settings.max_image_px - RULER_BAND_PX
            size = output_size(box, content_px, self._settings.max_upscale)
            return self._render(image, box, scale, size)

    def check(self, region: ImageRegion) -> None:
        """Make sure a region lies on an existing page's overview.

        Raises:
            RegionError: If the document, page or region does not exist.
        """
        with self._lock:
            self._locate(region)

    def save_crop(self, region: ImageRegion, directory: Path) -> StoredCrop:
        """Save a region at full resolution (capped at ``crop_max_px``) as a PNG.

        The file name derives from the region, so saving the same region twice writes the same
        file.

        Args:
            region: The region, in overview coordinates.
            directory: Where to write the PNG; created if missing.

        Returns:
            The stored crop, its path relative to the project root.

        Raises:
            RegionError: If the document, page or region does not exist.
        """
        with self._lock:
            image, _, box = self._locate(region)
            size = fit_size((box.width, box.height), self._settings.crop_max_px)
            png = crop_png(image, box, size)
        x0, y0, x1, y1 = region.region
        target = directory / f"{region.doc}_p{region.page}_{x0}-{y0}-{x1}-{y1}.png"
        directory.mkdir(parents=True, exist_ok=True)
        target.write_bytes(png)
        return StoredCrop(
            region=region,
            pixels=(box.x0, box.y0, box.x1, box.y1),
            path=target.resolve().relative_to(self._root.resolve(), walk_up=True).as_posix(),
        )

    def _check_page(self, doc: str, page: int) -> None:
        """Raise ``RegionError`` unless the document and page exist."""
        if doc not in self._paths:
            msg = f"unknown document {doc!r}; known documents: {', '.join(sorted(self._paths))}"
            raise RegionError(msg)
        if doc not in self._counts:
            self._counts[doc] = page_count(self._paths[doc])
        count = self._counts[doc]
        if not 1 <= page <= count:
            msg = f"{doc} has {count} pages (1 to {count}); page {page} does not exist"
            raise RegionError(msg)

    def _locate(self, region: ImageRegion) -> tuple[pymupdf.Pixmap, OverviewScale, PixelBox]:
        """Page image, its scale and the full-resolution box of an overview region."""
        self._check_page(region.doc, region.page)
        image, scale = self._load(region.doc, region.page)
        box = PixelBox.model_validate(region.region)
        if not scale.contains(box):
            width, height = scale.overview
            msg = (
                f"the overview of {region.doc} p.{region.page} is {width}x{height} px; "
                f"region {list(region.region)} exceeds it"
            )
            raise RegionError(msg)
        return image, scale, scale.to_full(box)

    def _load(self, doc: str, page: int) -> tuple[pymupdf.Pixmap, OverviewScale]:
        """Full-resolution page image, from the LRU cache when possible, and its scale."""
        key = (doc, page)
        image = self._images.pop(key, None)
        if image is None:
            image = page_image(
                self._paths[doc],
                page,
                render_dpi=self._settings.render_dpi,
                scan_min_coverage=self._settings.scan_min_coverage,
            )
        self._images[key] = image
        while len(self._images) > self._settings.cache_size:
            self._images.popitem(last=False)
        full = (image.width, image.height)
        overview = fit_size(full, self._settings.max_image_px - RULER_BAND_PX)
        return image, OverviewScale(full=full, overview=overview)

    def _render(
        self, image: pymupdf.Pixmap, box: PixelBox, scale: OverviewScale, size: Size
    ) -> RenderedImage:
        """Render a full-resolution box at ``size`` with rulers in overview coordinates."""
        png = render_view(image, box, scale.rulers(box, size), step_px=self._settings.ruler_step_px)
        return RenderedImage(
            png=png,
            image_size=(size[0] + RULER_BAND_PX, size[1] + RULER_BAND_PX),
            overview_size=scale.overview,
            full_size=scale.full,
        )
