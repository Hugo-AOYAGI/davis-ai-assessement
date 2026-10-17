import threading
from collections.abc import Mapping, Sequence
from pathlib import Path

from agent.adapters.images.pages import PageImages

_SHARED: dict[tuple[object, ...], PageImages] = {}
_SHARED_LOCK = threading.Lock()


def page_images(  # noqa: PLR0913 - one argument per config knob
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
) -> PageImages:
    """Return the one ``PageImages`` for these settings, building it on first request.

    Config builds a new object at each interpolation of the images node; going through this
    factory lets every tool and gate share one cache of decoded pages. Arguments as for
    ``PageImages``.
    """
    paths = tuple((str(document["id"]), str(document["path"])) for document in documents)
    knobs = (render_dpi, max_image_px, max_upscale, ruler_step_px, crop_max_px, cache_size)
    key = (paths, str(root), *knobs, scan_min_coverage)
    with _SHARED_LOCK:
        if key not in _SHARED:
            _SHARED[key] = PageImages(
                documents=documents,
                root=root,
                render_dpi=render_dpi,
                max_image_px=max_image_px,
                max_upscale=max_upscale,
                ruler_step_px=ruler_step_px,
                crop_max_px=crop_max_px,
                cache_size=cache_size,
                scan_min_coverage=scan_min_coverage,
            )
        return _SHARED[key]
