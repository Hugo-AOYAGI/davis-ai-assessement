from pathlib import Path

from agent.adapters.images.pages import PageImages
from agent.adapters.images.shared import page_images

DOCUMENTS = [{"id": "plan", "path": "plan.pdf", "legal_force": "conformity"}]


def shared(root: Path, documents=DOCUMENTS, render_dpi: int = 144) -> PageImages:
    return page_images(
        documents=documents,
        root=root,
        render_dpi=render_dpi,
        max_image_px=440,
        max_upscale=4.0,
        ruler_step_px=100,
        crop_max_px=500,
        cache_size=2,
        scan_min_coverage=0.8,
    )


def test_same_settings_share_one_instance(tmp_path):
    first = shared(tmp_path)
    assert shared(tmp_path, documents=[{"id": "plan", "path": "plan.pdf"}]) is first
    assert shared(tmp_path, render_dpi=72) is not first
    assert shared(tmp_path / "x") is not first
