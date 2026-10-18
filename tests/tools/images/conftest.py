import numpy as np
import pymupdf
import pytest
from langchain_core.messages import ToolMessage

from agent.adapters.images.pages import PageImages
from agent.adapters.images.store import ImageStore


def quadrants(width, height):
    array = np.full((height, width, 3), 255, dtype=np.uint8)
    array[: height // 2, : width // 2] = (255, 0, 0)
    return pymupdf.Pixmap(pymupdf.csRGB, width, height, array.tobytes(), 0)


@pytest.fixture(scope="session")
def images(tmp_path_factory):
    root = tmp_path_factory.mktemp("pdfs")
    with pymupdf.open() as document:
        scan = document.new_page(width=300, height=150)
        scan.insert_image(scan.rect, pixmap=quadrants(1200, 600))
        document.save(root / "plan.pdf")
    return PageImages(
        documents=[{"id": "plan", "path": "plan.pdf"}],
        root=root,
        render_dpi=72,
        max_image_px=440,
        max_upscale=2.0,
        ruler_step_px=100,
        crop_max_px=500,
        cache_size=2,
        scan_min_coverage=0.8,
        max_image_bytes=4_000_000,
    )


@pytest.fixture
def store(tmp_path):
    return ImageStore(directory=tmp_path / "images", url_prefix="/images")


@pytest.fixture
def invoke():
    def call(tool, **args):
        message = tool.invoke({"type": "tool_call", "id": "1", "name": tool.name, "args": args})
        assert isinstance(message, ToolMessage)
        return message

    return call
